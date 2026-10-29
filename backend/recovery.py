"""Encrypted, versioned off-site backup for both Gilbertos SQLite databases.

Never restore over live databases. Client-side AES-256-GCM encrypts an archive of
SQLite online snapshots *before* uploading to a distinct S3-compatible bucket.
Decrypt and check AEAD authentication before inspecting archive contents.
"""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import struct
import sys
import tarfile
import tempfile
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"GILBERTO-BACKUP-1\n"
AAD = b"Gilberto identity and legal checkpoint backup format 1"
CHUNK = 1024 * 1024
DATABASES = ("identity.sqlite3", "sessions.sqlite3")
MANIFEST = "manifest.json"


class BackupError(RuntimeError):
    pass


def key_from_env():
    raw = os.environ.get("BACKUP_ENCRYPTION_KEY_B64", "")
    try:
        key = base64.b64decode(raw, validate=True)
    except (ValueError, base64.binascii.Error):
        raise BackupError("Backup encryption key is invalid") from None
    if len(key) != 32:
        raise BackupError("Backup encryption key must decode to 32 bytes")
    return key


def _db_paths():
    return {
        "identity.sqlite3": Path(os.environ.get("IDENTITY_DB_PATH", "data/identity.sqlite3")),
        "sessions.sqlite3": Path(os.environ.get("SESSION_DB_PATH", "data/sessions.sqlite3")),
    }


def _hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_db(path, name):
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise BackupError("Backup database integrity verification failed")
        if name == "identity.sqlite3":
            required = {"identity_users", "identity_sessions"}
            count = conn.execute("SELECT COUNT(*) FROM identity_users").fetchone()[0]
        else:
            required = {"sessions"}
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        present = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(present):
            raise BackupError("Backup contains a database with an unexpected schema")
        return count


def _snapshot(src, dest):
    if not src.is_file() or src.is_symlink():
        raise BackupError("Both persistent databases must exist as regular files")
    # sqlite3.backup includes committed WAL content; do not copy raw -wal files.
    with closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)) as source:
        with closing(sqlite3.connect(str(dest), timeout=30)) as target:
            source.backup(target, pages=128, sleep=0.2)
            target.commit()


def _validate_cross_refs(identity_db, session_db):
    with closing(sqlite3.connect(str(identity_db))) as identities:
        users = {row[0] for row in identities.execute("SELECT id FROM identity_users")}
    with closing(sqlite3.connect(str(session_db))) as checkpoints:
        for (payload,) in checkpoints.execute("SELECT payload FROM sessions"):
            try:
                data = json.loads(payload)
            except (TypeError, ValueError):
                raise BackupError("A checkpoint could not be decoded") from None
            if data.get("owner_issuer") == "urn:gilberto:local:v1":
                if data.get("owner_subject") not in users:
                    raise BackupError("Checkpoint references an absent local user")


def _write_tar(folder, manifest):
    archive = folder / "bundle.tar"
    with tarfile.open(archive, "w") as tar:
        for name in (*DATABASES, MANIFEST):
            tar.add(folder / name, arcname=name, recursive=False)
    return archive


def _encrypt_archive(archive, output, key):
    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(AAD)
    with open(archive, "rb") as source, open(output, "xb") as dest:
        dest.write(MAGIC + nonce)
        for chunk in iter(lambda: source.read(CHUNK), b""):
            dest.write(encryptor.update(chunk))
        dest.write(encryptor.finalize())
        dest.write(encryptor.tag)


def _decrypt_archive(encrypted, plaintext, key):
    with open(encrypted, "rb") as source:
        if source.read(len(MAGIC)) != MAGIC:
            raise BackupError("Unknown backup envelope")
        nonce = source.read(12)
        source.seek(0, os.SEEK_END)
        length = source.tell()
        minimum = len(MAGIC) + 12 + 16
        if length < minimum:
            raise BackupError("Truncated backup")
        source.seek(length - 16)
        tag = source.read(16)
        source.seek(len(MAGIC) + 12)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(AAD)
        left = length - minimum
        try:
            with open(plaintext, "xb") as target:
                while left:
                    buf = source.read(min(CHUNK, left))
                    if not buf:
                        raise BackupError("Truncated backup ciphertext")
                    target.write(decryptor.update(buf))
                    left -= len(buf)
                target.write(decryptor.finalize())
        except ValueError:
            raise BackupError("Backup authentication failed: incorrect key or modified file") from None


def create_encrypted_backup(output, *, key=None):
    """Make a consistent snapshot per DB; caller must quiesce both DBs for a
    jointly point-in-time pair. Cross-DB referential integrity is checked.
    """
    key = key if key is not None else key_from_env()
    if len(key) != 32:
        raise BackupError("Invalid backup encryption key")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise BackupError("Backup output already exists")
    with tempfile.TemporaryDirectory(prefix="gilberto-snapshot-") as temporary:
        folder = Path(temporary)
        paths = _db_paths()
        counts = {}
        for name in DATABASES:
            _snapshot(paths[name], folder / name)
            counts[name] = _validate_db(folder / name, name)
        _validate_cross_refs(folder / DATABASES[0], folder / DATABASES[1])
        manifest = {
            "format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "databases": {name: {"sha256": _hash(folder / name), "rows": counts[name]}
                          for name in DATABASES},
        }
        (folder / MANIFEST).write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        tar_path = _write_tar(folder, manifest)
        try:
            _encrypt_archive(tar_path, output, key)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return {"sha256": _hash(output), "bytes": output.stat().st_size,
            "rows": counts, "encrypted_file": str(output)}


def restore_to_isolated_directory(encrypted, destination, *, key=None):
    """Fail-closed, no overwrite, never touch configured live DB paths.

    Both DBs are integrity checked and compared before atomic destination rename.
    """
    key = key if key is not None else key_from_env()
    if len(key) != 32:
        raise BackupError("Invalid backup encryption key")
    encrypted = Path(encrypted).resolve(strict=True)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError("Restore destination must not exist")
    live = {path.resolve() for path in _db_paths().values()}
    if any(destination == item or destination in item.parents for item in live):
        raise BackupError("Restore destination overlaps a live database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gilberto-isolated-restore-",
                                     dir=destination.parent) as temp:
        folder = Path(temp)
        _decrypt_archive(encrypted, folder / "decrypted.tar", key)
        with tarfile.open(folder / "decrypted.tar", "r:") as tar:
            members = tar.getmembers()
            if len(members) != 3 or {m.name for m in members} != set(DATABASES + (MANIFEST,)):
                raise BackupError("Backup has unexpected archive members")
            for member in members:
                if not member.isfile() or member.size > 2 * 1024**3:
                    raise BackupError("Backup archive member is unsafe")
                source = tar.extractfile(member)
                if source is None:
                    raise BackupError("Backup archive is incomplete")
                with open(folder / member.name, "xb") as target:
                    shutil.copyfileobj(source, target, CHUNK)
        try:
            manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
            if manifest["format"] != 1:
                raise BackupError("Unsupported backup format")
            for name in DATABASES:
                if _hash(folder / name) != manifest["databases"][name]["sha256"]:
                    raise BackupError("Database checksum mismatch")
                if _validate_db(folder / name, name) != manifest["databases"][name]["rows"]:
                    raise BackupError("Database row-count mismatch")
            _validate_cross_refs(folder / DATABASES[0], folder / DATABASES[1])
        except (ValueError, KeyError, TypeError):
            raise BackupError("Backup manifest is invalid") from None
        os.mkdir(destination, 0o700)
        try:
            for name in DATABASES:
                shutil.copy2(folder / name, destination / name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {"directory": str(destination), "rows": {
        name: manifest["databases"][name]["rows"] for name in DATABASES}}


def _s3_client():
    # boto3 is an established, SigV4-supporting client. Never use public ACLs.
    import boto3
    from botocore.config import Config
    required = ("BACKUP_S3_BUCKET", "BACKUP_S3_ACCESS_KEY", "BACKUP_S3_SECRET_KEY")
    if not all(os.environ.get(x) for x in required):
        raise BackupError("Backup object storage is not configured")
    endpoint = os.environ.get("BACKUP_S3_ENDPOINT", "")
    if endpoint:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise BackupError("S3 endpoint must be an approved HTTPS URL")
    return boto3.client(
        "s3", endpoint_url=endpoint or None,
        region_name=os.environ.get("BACKUP_S3_REGION", "us-east-1"),
        aws_access_key_id=os.environ["BACKUP_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["BACKUP_S3_SECRET_KEY"],
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60,
                      retries={"mode": "standard", "max_attempts": 3}),
    )


def backup_to_s3():
    key = key_from_env()
    bucket = os.environ.get("BACKUP_S3_BUCKET")
    if not bucket:
        raise BackupError("Backup destination not configured")
    prefix = os.environ.get("BACKUP_S3_PREFIX", "gilberto/staging").strip("/")
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    obj_key = f"{prefix}/{name}-{secrets.token_hex(8)}.glbk"
    with tempfile.TemporaryDirectory(prefix="gilberto-upload-") as temp:
        output = Path(temp) / "encrypted.glbk"
        summary = create_encrypted_backup(output, key=key)
        client = _s3_client()
        with open(output, "rb") as file:
            client.upload_fileobj(file, bucket, obj_key,
                                  ExtraArgs={"ContentType": "application/octet-stream",
                                             "Metadata": {"sha256": summary["sha256"]}})
    return {"bucket": bucket, "object": obj_key,
            "sha256": summary["sha256"], "rows": summary["rows"]}


def download_and_verify_s3(obj_key, isolated_dir):
    bucket = os.environ.get("BACKUP_S3_BUCKET")
    if not bucket:
        raise BackupError("Backup destination not configured")
    if not obj_key or ".." in obj_key or not obj_key.endswith(".glbk"):
        raise BackupError("Invalid backup object name")
    with tempfile.TemporaryDirectory(prefix="gilberto-download-") as temp:
        encrypted = Path(temp) / "download.glbk"
        client = _s3_client()
        client.download_file(bucket, obj_key, str(encrypted))
        return restore_to_isolated_directory(encrypted, isolated_dir)


def main():
    parser = argparse.ArgumentParser(description="Offline encrypted Gilbertos backups")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("upload")
    local = sub.add_parser("create")
    local.add_argument("--output", required=True)
    restore = sub.add_parser("restore-isolated")
    restore.add_argument("--input", required=True)
    restore.add_argument("--directory", required=True)
    remote = sub.add_parser("restore-from-s3-isolated")
    remote.add_argument("--key", required=True)
    remote.add_argument("--directory", required=True)
    args = parser.parse_args()
    try:
        if args.command == "upload":
            data = backup_to_s3()
        elif args.command == "create":
            data = create_encrypted_backup(args.output)
        elif args.command == "restore-isolated":
            data = restore_to_isolated_directory(args.input, args.directory)
        else:
            data = download_and_verify_s3(args.key, args.directory)
        print(json.dumps(data, sort_keys=True))
    except (BackupError, OSError, sqlite3.Error) as exc:
        print("Backup operation failed:", type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
