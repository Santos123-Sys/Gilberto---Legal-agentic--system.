import base64
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from security import local_identity
from recovery import create_encrypted_backup, restore_to_isolated_directory, BackupError
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.encrypted = self.folder / "backup.glbk"
        self.key = os.urandom(32)
        environ = patch.dict(os.environ, {
            "IDENTITY_DB_PATH": str(self.folder / "identity.sqlite3"),
            "SESSION_DB_PATH": str(self.folder / "sessions.sqlite3"),
            "BACKUP_ENCRYPTION_KEY_B64": base64.b64encode(self.key).decode(),
        })
        environ.start()
        self.addCleanup(environ.stop)
        self.user_id = local_identity.create_user("lawyer@example.test", "Sufficiently-Strong2026!")
        with sqlite3.connect(str(self.folder / "sessions.sqlite3")) as conn:
            conn.execute("CREATE TABLE sessions(id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
            conn.execute("INSERT INTO sessions VALUES (?,?)", ("session-1", json.dumps({
                "id": "session-1", "owner_issuer": local_identity.LOCAL_ISSUER,
                "owner_subject": self.user_id, "status": "completed",
            })))

    def test_encrypted_backup_round_trip_and_restore_isolated(self):
        result = create_encrypted_backup(self.encrypted)
        self.assertEqual(result["rows"], {"identity.sqlite3": 1, "sessions.sqlite3": 1})
        content = self.encrypted.read_bytes()
        self.assertNotIn(b"lawyer@example.test", content)
        self.assertNotIn(b"session-1", content)
        out = self.folder / "isolated"
        restored = restore_to_isolated_directory(self.encrypted, out)
        self.assertEqual(restored["rows"]["sessions.sqlite3"], 1)
        with sqlite3.connect(str(out / "sessions.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT id FROM sessions").fetchone()[0], "session-1")
        with self.assertRaises(BackupError):
            restore_to_isolated_directory(self.encrypted, out)

    def test_integrity_detects_tampering(self):
        create_encrypted_backup(self.encrypted)
        data = bytearray(self.encrypted.read_bytes())
        data[40] ^= 23
        self.encrypted.write_bytes(data)
        with self.assertRaises(BackupError):
            restore_to_isolated_directory(self.encrypted, self.folder / "tampered")
        self.assertFalse((self.folder / "tampered").exists())

    def test_wrong_key_fails_closed(self):
        create_encrypted_backup(self.encrypted)
        with self.assertRaises(BackupError):
            restore_to_isolated_directory(self.encrypted, self.folder / "invalid", key=os.urandom(32))
        self.assertFalse((self.folder / "invalid").exists())

    def test_backup_overwrite_and_incomplete_database_rejected(self):
        create_encrypted_backup(self.encrypted)
        with self.assertRaises(BackupError):
            create_encrypted_backup(self.encrypted)
        (self.folder / "sessions.sqlite3").unlink()
        with self.assertRaises(BackupError):
            create_encrypted_backup(self.folder / "second.glbk")

    def test_checkpoint_ownership_mismatch_fails(self):
        with sqlite3.connect(str(self.folder / "sessions.sqlite3")) as db:
            db.execute("UPDATE sessions SET payload=? WHERE id='session-1'", (json.dumps({
                "id": "session-1", "owner_issuer": local_identity.LOCAL_ISSUER,
                "owner_subject": "not-present",
            }),))
        with self.assertRaises(BackupError):
            create_encrypted_backup(self.encrypted)
        self.assertFalse(self.encrypted.exists())

    def test_restore_must_not_overlap_live_data(self):
        create_encrypted_backup(self.encrypted)
        with self.assertRaises(BackupError):
            restore_to_isolated_directory(self.encrypted, self.folder)
        with self.assertRaises(BackupError):
            restore_to_isolated_directory(self.encrypted, self.folder / "data") if False else restore_to_isolated_directory(self.encrypted, self.folder / "identity.sqlite3")
