from datetime import datetime, timezone
from hmac import compare_digest
import hashlib, os, re, secrets, tempfile
from urllib.parse import urlparse
import boto3
from botocore.config import Config
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
MAX_BYTES = 128 * 1024 * 1024
MAGIC = b"GILBERTO-BACKUP-1\n"
NAME_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{16}\.glbk$")

def authorize(value):
    secret=os.getenv("GILBERTO_BACKUP_GATEWAY_SECRET","")
    if len(secret)<48: raise HTTPException(503,"Backup gateway unconfigured")
    if not value or not compare_digest(secret,value):
        raise HTTPException(403,"Backup access denied")

def prefix():
    p=os.getenv("GILBERTO_BACKUP_PREFIX","gilberto/staging").strip("/")
    if ".." in p or not re.fullmatch(r"[a-zA-Z0-9/_-]{4,90}",p):
        raise HTTPException(503,"Backup namespace invalid")
    return p

def s3():
    names=("BACKUP_S3_BUCKET","BACKUP_S3_ENDPOINT","BACKUP_S3_REGION",
           "BACKUP_S3_ACCESS_KEY","BACKUP_S3_SECRET_KEY")
    if not all(os.getenv(k) for k in names): raise HTTPException(503,"Storage not configured")
    url=urlparse(os.environ["BACKUP_S3_ENDPOINT"])
    if url.scheme!="https" or not url.hostname or url.username or url.password:
        raise HTTPException(503,"Storage endpoint invalid")
    return boto3.client("s3",endpoint_url=os.environ["BACKUP_S3_ENDPOINT"],
        region_name=os.environ["BACKUP_S3_REGION"],
        aws_access_key_id=os.environ["BACKUP_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["BACKUP_S3_SECRET_KEY"],
        config=Config(signature_version="s3v4"))

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/v1/backups",status_code=201)
async def upload(request:Request,x_gilberto_backup_key:str|None=Header(default=None),
                 x_gilberto_cipher_sha256:str|None=Header(default=None)):
    authorize(x_gilberto_backup_key)
    if not x_gilberto_cipher_sha256 or not re.fullmatch(r"[0-9a-f]{64}",x_gilberto_cipher_sha256):
        raise HTTPException(400,"Ciphertext checksum required")
    digest=hashlib.sha256()
    total=0
    head=bytearray()
    with tempfile.TemporaryFile(mode="w+b") as fd:
        async for chunk in request.stream():
            total+=len(chunk)
            if total>MAX_BYTES: raise HTTPException(413,"Backup too large")
            if len(head)<len(MAGIC): head.extend(chunk[:len(MAGIC)-len(head)])
            fd.write(chunk)
            digest.update(chunk)
        if bytes(head)!=MAGIC or total<len(MAGIC)+28:
            raise HTTPException(400,"Encrypted archive required")
        if not compare_digest(digest.hexdigest(),x_gilberto_cipher_sha256):
            raise HTTPException(400,"Ciphertext checksum mismatch")
        fd.seek(0)
        name=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(8)+".glbk"
        object_key=prefix()+"/"+name
        try:
            s3().upload_fileobj(fd,os.environ["BACKUP_S3_BUCKET"],object_key,
                ExtraArgs={"ContentType":"application/octet-stream",
                           "Metadata":{"sha256":digest.hexdigest()}})
        except Exception:
            raise HTTPException(503,"Storage upload failed") from None
        return {"object":object_key,"sha256":digest.hexdigest(),"bytes":total}

@app.get("/v1/backups/{name}")
def download(name:str,x_gilberto_backup_key:str|None=Header(default=None)):
    authorize(x_gilberto_backup_key)
    if not NAME_RE.fullmatch(name): raise HTTPException(404,"Not found")
    try:
        response=s3().get_object(Bucket=os.environ["BACKUP_S3_BUCKET"],
                                 Key=prefix()+"/"+name)
    except Exception:
        raise HTTPException(404,"Not found") from None
    if int(response.get("ContentLength",MAX_BYTES+1))>MAX_BYTES:
        response["Body"].close()
        raise HTTPException(413,"Backup too large")
    def chunks():
        body=response["Body"]
        try:
            yield from body.iter_chunks(chunk_size=1024*1024)
        finally: body.close()
    return StreamingResponse(chunks(),media_type="application/octet-stream",
          headers={"Cache-Control":"no-store"})
