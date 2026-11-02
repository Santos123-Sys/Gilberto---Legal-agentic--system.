import hashlib
import io
import os
import unittest
from unittest.mock import patch
import httpx
from app import app, MAGIC

class Body:
    def __init__(self,payload): self.source=io.BytesIO(payload)
    def iter_chunks(self,chunk_size): 
        while True:
            buf=self.source.read(chunk_size)
            if not buf: break
            yield buf
    def close(self): self.source.close()

class MemoryS3:
    def __init__(self): self.objects={}
    def upload_fileobj(self,fd,bucket,key,ExtraArgs):
        self.objects[(bucket,key)]=fd.read()
    def get_object(self,Bucket,Key):
        data=self.objects[(Bucket,Key)]
        return {"Body":Body(data),"ContentLength":len(data)}

class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage=MemoryS3()
        self.config=patch.dict(os.environ,{
          "GILBERTO_BACKUP_GATEWAY_SECRET":"correct-secret-"+("y"*55),
          "GILBERTO_BACKUP_PREFIX":"gilberto/staging",
          "BACKUP_S3_BUCKET":"independent-storage",
          "BACKUP_S3_ENDPOINT":"https://s3.example.test",
          "BACKUP_S3_REGION":"auto",
          "BACKUP_S3_ACCESS_KEY":"fake",
          "BACKUP_S3_SECRET_KEY":"fake"})
        self.config.start();self.addCleanup(self.config.stop)
        self.patch=patch("app.s3",return_value=self.storage)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                      base_url="https://backup.example.test")
        self.addAsyncCleanup(self.client.aclose)
        self.blob=MAGIC + os.urandom(12) + b"ciphertext-binary-only" + os.urandom(16)
        self.headers={
          "X-Gilberto-Backup-Key":"correct-secret-"+("y"*55),
          "X-Gilberto-Cipher-SHA256":hashlib.sha256(self.blob).hexdigest()}

    async def test_encrypted_object_upload_and_download_only(self):
        r=await self.client.post("/v1/backups",content=self.blob,headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        key=r.json()["object"]
        self.assertTrue(key.startswith("gilberto/staging/"))
        self.assertEqual(r.json()["sha256"],hashlib.sha256(self.blob).hexdigest())
        received=await self.client.get("/v1/backups/"+key.split("/")[-1],
                        headers={"X-Gilberto-Backup-Key":self.headers["X-Gilberto-Backup-Key"]})
        self.assertEqual(received.status_code,200)
        self.assertEqual(received.content,self.blob)

    async def test_missing_secret_and_invalid_digest_and_path_are_denied(self):
        self.assertEqual((await self.client.post("/v1/backups",content=self.blob)).status_code,403)
        wrong={**self.headers,"X-Gilberto-Cipher-SHA256":"0"*64}
        self.assertEqual((await self.client.post("/v1/backups",content=self.blob,headers=wrong)).status_code,400)
        self.assertEqual((await self.client.get("/v1/backups/../../secret",
           headers={"X-Gilberto-Backup-Key":self.headers["X-Gilberto-Backup-Key"]})).status_code,404)
        self.assertEqual((await self.client.get("/v1/backups/file.glbk",
           headers={"X-Gilberto-Backup-Key":"wrong"})).status_code,403)

    async def test_upload_limit_blocks_large_blob(self):
        with patch("app.MAX_BYTES",48):
            r=await self.client.post("/v1/backups",content=self.blob*4,headers=self.headers)
        self.assertEqual(r.status_code,413)
