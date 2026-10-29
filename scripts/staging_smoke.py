"""Anonymous-only live staging smoke: no credentials or customer data used."""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

APP = "https://gilberto-stage-frontend-staging.up.railway.app"
GATEWAY = "https://gilberto-backup-gateway-backup.up.railway.app"

def request(url, method="GET", data=None, headers=None):
    kwargs = {"method": method, "headers": headers or {}}
    if data is not None:
        kwargs["data"] = data
    req = urllib.request.Request(url, **kwargs)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as response:
            return response.status, response.read(1048576)
    except urllib.error.HTTPError as response:
        return response.code, response.read(1048576)

def check():
    status, html = request(APP + "/")
    assert status == 200 and b'id="root"' in html, ("frontend", status)
    status, data = request(APP + "/api/auth/bootstrap-status")
    assert status == 200 and isinstance(json.loads(data)["available"], bool), ("bootstrap", status, data[:200])
    status, _ = request(APP + "/api/auth/me")
    assert status == 401, ("anonymous identity", status)
    status, _ = request(APP + "/api/sessions", "POST", b'{"num_rounds":1}',
                        {"Content-Type":"application/json","Origin":APP})
    assert status == 401, ("anonymous session", status)
    status, _ = request(APP + "/api/sessions", "POST", b'{"num_rounds":1}',
                        {"Content-Type":"application/json","Origin":"https://untrusted.invalid"})
    assert status == 403, ("CSRF rejected", status)
    status, data = request(GATEWAY + "/health")
    assert status == 200 and json.loads(data)["status"] == "ok", ("gateway health", status)
    status, _ = request(GATEWAY + "/v1/backups","POST",b"notencrypted",
                        {"X-Gilberto-Cipher-SHA256":"0"*64})
    assert status == 403, ("gateway unauthorized", status)

if __name__ == "__main__":
    for retry in range(5):
        try:
            check()
            print("PASS: live staging TLS, local identity, CSRF and independent gateway")
            sys.exit(0)
        except (OSError, AssertionError, ValueError, KeyError) as exc:
            if retry == 4:
                print("FAILED: staged HTTP/security smoke", type(exc).__name__, str(exc)[:300])
                raise
            time.sleep(8)
