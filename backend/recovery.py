"""Consistent, non-destructive SQLite checkpoint snapshots and offline validation.

Not a backup service. The operator must separately encrypt, replicate offsite,
retain and exercise disaster restoration. Never point the output at live /data.
"""
import argparse
import hashlib
import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3


class RecoveryValidationError(RuntimeError):
    """A checkpoint snapshot cannot be trusted for restoration."""


def verify_snapshot(snapshot_path: str) -> dict:
    path = Path(snapshot_path).resolve(strict=True)
    if not path.is_file() or not path.stat().st_size:
        raise RecoveryValidationError("Checkpoint snapshot is empty or unavailable")
    # Read-only avoids "helpfully" creating a missing or damaged checkpoint.
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    count = 0
    try:
        with closing(connection) as db:
            ok = db.execute("PRAGMA integrity_check").fetchone()
            if ok != ("ok",):
                raise RecoveryValidationError("SQLite integrity check failed")
            table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
            if table is None:
                raise RecoveryValidationError("Snapshot has no session checkpoint table")
            for ident, raw in db.execute("SELECT id, payload FROM sessions"):
                try:
                    data = json.loads(raw)
                except (TypeError, ValueError) as exc:
                    raise RecoveryValidationError("Snapshot has an invalid checkpoint") from None
                if not isinstance(data, dict) or data.get("id") != ident:
                    raise RecoveryValidationError("Snapshot has mismatched session identity")
                if not isinstance(data.get("events"), list) or not isinstance(data.get("config"), dict):
                    raise RecoveryValidationError("Snapshot has an incomplete checkpoint")
                count += 1
    except sqlite3.DatabaseError as exc:
        raise RecoveryValidationError("SQLite snapshot is damaged or unavailable") from None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"sessions_validated": count, "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def create_snapshot(source_path: str, destination_path: str) -> dict:
    src = Path(source_path).resolve(strict=True)
    dst = Path(destination_path).resolve()
    if src == dst or not src.is_file() or not dst.parent.is_dir():
        raise RecoveryValidationError("A separate existing destination directory is required")
    # No overwrite: an operator must never clobber the only known-good copy.
    try:
        fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except FileExistsError:
        raise RecoveryValidationError("Snapshot destination already exists") from None
    try:
        # SQLite's online backup API reads a transactionally consistent view,
        # including committed WAL content. A raw cp of the .db file does not.
        with closing(sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(str(dst))) as target:
                source.backup(target, pages=128, sleep=0.05)
        result = verify_snapshot(str(dst))
        with dst.open("rb") as handle:
            os.fsync(handle.fileno())
        return result
    except Exception:
        dst.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Check a separate SQLite snapshot without altering production")
    cli.add_argument("--snapshot", required=True, help="A separate snapshot path")
    cli.add_argument("--source", help="Source database; omit to validate an existing snapshot only")
    args = cli.parse_args()
    try:
        report = (create_snapshot(args.source, args.snapshot) if args.source
                  else verify_snapshot(args.snapshot))
        print(json.dumps(report, sort_keys=True))
    except (RecoveryValidationError, sqlite3.DatabaseError, FileNotFoundError) as exc:
        cli.error("Recovery validation failed; inspect the backup in isolation")
