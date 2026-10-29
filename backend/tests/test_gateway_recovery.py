import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import httpx
import recovery
from security import local_identity

class GatewayBackendTests(unittest.TestCase):
    def test_client_gateway_roundtrip_encrypted_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            key=base64.b64encode(os.urandom(32)).decode()
            env=patch.dict(os.environ,{
              "IDENTITY_DB_PATH":str(root/"identity.db"),
              "SESSION_DB_PATH":str(root/"sessions.db"),
              "BACKUP_ENCRYPTION_KEY_B64":key,
              "BACKUP_GATEWAY_URL":"https://backup.example.test",
              "BACKUP_GATEWAY_SECRET":"gateway-key-"+("x"*50),
              "BACKUP_S3_PREFIX":"gilberto/staging"})
            with env:
                user=local_identity.create_user("example@example.test","Strong-Password-2026!")
                with sqlite3.connect(str(root/"sessions.db")) as db:
                    db.execute("CREATE TABLE sessions(id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
                    db.execute("INSERT INTO sessions VALUES (?,?)",("case-1",json.dumps({
                      "owner_issuer":local_identity.LOCAL_ISSUER,"owner_subject":user})))
                saved={}
                def handle(req):
                    self.assertEqual(req.headers["X-Gilberto-Backup-Key"],
                                     "gateway-key-"+("x"*50))
                    if req.method=="POST":
                        data=req.read()
                        self.assertEqual(req.headers["X-Gilberto-Cipher-SHA256"],
                                         hashlib.sha256(data).hexdigest())
                        saved["body"]=data
                        return httpx.Response(201,json={"object":"gilberto/staging/20261029T140000Z-0123456789abcdef.glbk",
                                                  "sha256":hashlib.sha256(data).hexdigest()})
                    if req.method=="GET":
                        return httpx.Response(200,content=saved["body"])
                    return httpx.Response(404)
                transport=httpx.MockTransport(handle)
                with patch.object(recovery,"_backup_gateway_client",
                      side_effect=lambda:httpx.Client(transport=transport)):
                    backup=recovery.backup_to_s3()
                    self.assertEqual(backup["bucket"],"backup-gateway")
                    self.assertNotIn(b"example@example.test",saved["body"])
                    destination=root/"isolated"
                    verified=recovery.download_and_verify_s3(backup["object"],destination)
                    self.assertEqual(verified["rows"]["identity.sqlite3"],1)
                    self.assertTrue((destination/"sessions.sqlite3").exists())

    def test_gateway_rejects_http_and_missing_secret(self):
        with patch.dict(os.environ,{"BACKUP_GATEWAY_URL":"http://untrusted.example"}):
            with self.assertRaises(recovery.BackupError):
                recovery._backup_gateway_origin()
        with patch.dict(os.environ,{"BACKUP_GATEWAY_SECRET":""}):
            with self.assertRaises(recovery.BackupError):
                recovery._backup_gateway_headers()
