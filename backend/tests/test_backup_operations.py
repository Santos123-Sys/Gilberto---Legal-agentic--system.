import base64
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import backup_operations
import recovery
from security import local_identity

class MemoryS3:
    def __init__(self):
        self.objects = {}
    def upload_fileobj(self, fp, bucket, key, ExtraArgs=None):
        assert ExtraArgs and ExtraArgs["ContentType"] == "application/octet-stream"
        self.objects[(bucket,key)] = fp.read()
    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[(bucket,key)])

class OffsiteEncryptedRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.s3 = MemoryS3()
        env = patch.dict(os.environ, {
            "IDENTITY_DB_PATH": str(root / "identity.sqlite3"),
            "SESSION_DB_PATH": str(root / "sessions.sqlite3"),
            "BACKUP_STATUS_PATH": str(root / "backup-status.json"),
            "BACKUP_ENCRYPTION_KEY_B64": base64.b64encode(os.urandom(32)).decode(),
            "BACKUP_ENABLED": "true",
            "BACKUP_S3_BUCKET": "test-backup-project",
            "BACKUP_S3_ACCESS_KEY": "fake-key",
            "BACKUP_S3_SECRET_KEY": "fake-secret"})
        env.start()
        self.addCleanup(env.stop)
        mock = patch.object(recovery, "_s3_client", return_value=self.s3)
        mock.start()
        self.addCleanup(mock.stop)
        self.root = root
        self.user_id = local_identity.create_user("agent@example.test", "Secure-Password-for-Test2026")
        with sqlite3.connect(str(root / "sessions.sqlite3")) as db:
            db.execute("CREATE TABLE sessions(id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
            db.execute("INSERT INTO sessions VALUES(?,?)", ("run-1",json.dumps({
                "id":"run-1","owner_issuer":local_identity.LOCAL_ISSUER,
                "owner_subject":self.user_id,"status":"completed"})))

    async def test_remote_upload_download_and_isolated_restore(self):
        uploaded = await backup_operations.run_backup()
        self.assertEqual(uploaded["status"], "uploaded")
        self.assertIn(("test-backup-project",uploaded["object"]), self.s3.objects)
        self.assertNotIn(b"agent@example.test", self.s3.objects[("test-backup-project",uploaded["object"])])
        verified = await backup_operations.verify_latest_offsite()
        self.assertEqual(verified["status"], "restored_and_verified")
        state=backup_operations.get_status()
        self.assertEqual(state["last_verify_object"], uploaded["object"])
        self.assertEqual(state["last_verify_rows"]["sessions.sqlite3"], 1)
        with sqlite3.connect(str(self.root/"sessions.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],1)

    async def test_corruption_cannot_be_reported_verified(self):
        item = await backup_operations.run_backup()
        key = ("test-backup-project",item["object"])
        data = bytearray(self.s3.objects[key]);data[90] ^= 1
        self.s3.objects[key] = bytes(data)
        with self.assertRaises(recovery.BackupError):
            await backup_operations.verify_latest_offsite()
        self.assertIsNotNone(backup_operations.get_status()["last_verify_failed_at"])

    async def test_disabled_backup_fails_closed(self):
        with patch.dict(os.environ, {"BACKUP_ENABLED":"false"}):
            with self.assertRaises(RuntimeError): await backup_operations.run_backup()
            with self.assertRaises(RuntimeError): await backup_operations.verify_latest_offsite()
