"""Real local-auth security tests. No mocked identity dependency or auth bypass."""
import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx

import main
from config import settings
from security import local_identity


class LocalIdentityStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.dict(os.environ, {"IDENTITY_DB_PATH": self.tmp.name + "/identity.db"})
        p.start()
        self.addCleanup(p.stop)
        self.user_id = local_identity.create_user("Lawyer@Example.COM", "Secure#Example!2026")

    def test_argon2id_storage_and_unique_account(self):
        with local_identity.connect() as db:
            record = db.execute("SELECT * FROM identity_users WHERE id=?", (self.user_id,)).fetchone()
            self.assertEqual(record["email"], "lawyer@example.com")
            self.assertTrue(record["password_hash"].startswith("$argon2id$"))
            self.assertNotIn("Secure#Example!2026", record["password_hash"])
            self.assertIsNone(db.execute("SELECT token_hash FROM identity_sessions").fetchone())
        with self.assertRaises(Exception):
            local_identity.create_user("lawyer@example.com", "Different!Example2026")

    def test_bad_credentials_are_throttled_and_success_can_login(self):
        for _ in range(5):
            with self.assertRaises(local_identity.LoginRejected):
                local_identity.login("lawyer@example.com", "wrong pass", "remote-a")
        with self.assertRaises(local_identity.LoginRejected) as cm:
            local_identity.login("lawyer@example.com", "Secure#Example!2026", "remote-a")
        self.assertTrue(cm.exception.throttled)
        with patch.object(local_identity.time, "time", return_value=time.time()+901):
            token, account = local_identity.login("lawyer@example.com",
                                                  "Secure#Example!2026", "remote-a")
        self.assertEqual(account["id"], self.user_id)
        self.assertTrue(token)
        with local_identity.connect() as db:
            stored = db.execute("SELECT * FROM identity_sessions WHERE user_id=?",
                                (self.user_id,)).fetchone()
            self.assertNotEqual(token, stored["token_hash"])
            self.assertEqual(local_identity._digest(token), stored["token_hash"])

    def test_expiry_idle_timeout_revocation_deactivation(self):
        token, _ = local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-1")
        self.assertEqual(local_identity.resolve_session(token)["id"], self.user_id)
        # Simulate 31 minutes without touching the session.
        with patch.object(local_identity.time, "time", return_value=time.time()+31*60):
            self.assertIsNone(local_identity.resolve_session(token))
        other, _ = local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-2")
        local_identity.revoke_session(other)
        self.assertIsNone(local_identity.resolve_session(other))
        third, _ = local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-3")
        local_identity.deactivate_user("lawyer@example.com")
        self.assertIsNone(local_identity.resolve_session(third))
        with self.assertRaises(local_identity.LoginRejected):
            local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-4")

    def test_admin_reset_revokes_every_session(self):
        token, _ = local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-1")
        local_identity.reset_password("lawyer@example.com", "Brand-New-Strong-2026!")
        self.assertIsNone(local_identity.resolve_session(token))
        with self.assertRaises(local_identity.LoginRejected):
            local_identity.login("lawyer@example.com", "Secure#Example!2026", "ip-2")
        new_token, _ = local_identity.login("lawyer@example.com",
                                            "Brand-New-Strong-2026!", "ip-2")
        self.assertIsNotNone(local_identity.resolve_session(new_token))

    def test_password_minimum_and_no_default_accounts(self):
        with self.assertRaises(local_identity.PasswordRejected):
            local_identity.create_user("other@example.com", "123456")
        with self.assertRaises(local_identity.PasswordRejected):
            local_identity.create_user("other@example.com", " " * 12)


class LocalIdentityAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in [
            patch.dict(os.environ, {
                "IDENTITY_DB_PATH": self.tmp.name + "/identity.db",
                "SESSION_DB_PATH": self.tmp.name + "/reviews.db",
            }),
            patch.object(settings, "AUTH_MODE", "local"),
            patch.object(settings, "LOCAL_AUTH_PROXY_SECRET", "a" * 48),
            patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", "https://gilberto.example.test"),
            patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", True),
        ]:
            p.start()
            self.addCleanup(p.stop)
        main.sessions.clear()
        main.app.dependency_overrides.pop(main.current_principal, None)
        self.addCleanup(main.sessions.clear)
        local_identity.create_user("a@example.com", "Strong!Password-2026A")
        local_identity.create_user("b@example.com", "Strong!Password-2026B")
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                        base_url="https://gilberto.example.test",
                                        headers={"X-Gilberto-Proxy-Auth": "a" * 48})
        self.other = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                       base_url="https://gilberto.example.test",
                                       headers={"X-Gilberto-Proxy-Auth": "a" * 48})
        self.addAsyncCleanup(self.client.aclose)
        self.addAsyncCleanup(self.other.aclose)
        self.origin = {"Origin": "https://gilberto.example.test"}

    async def login(self, client=None, email="a@example.com", password="Strong!Password-2026A"):
        return await (client or self.client).post("/api/auth/login",
            json={"email": email, "password": password}, headers=self.origin)

    async def test_login_cookie_session_and_identity_isolation(self):
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)
        login = await self.login()
        self.assertEqual(login.status_code, 200, login.text)
        cookie = login.headers["set-cookie"]
        for flag in ("__Host-gilberto_session=", "Secure", "HttpOnly", "SameSite=strict", "Path=/"):
            self.assertIn(flag.lower(), cookie.lower())
        self.assertNotIn("password", login.text)
        who = await self.client.get("/api/auth/me")
        self.assertEqual(who.status_code, 200)
        self.assertEqual(who.json()["user"]["email"], "a@example.com")
        own = await self.client.post("/api/sessions", json={"num_rounds": 1,
                 "user_id": "spoofed"}, headers=self.origin)
        self.assertEqual(own.status_code, 200, own.text)
        sid = own.json()["session_id"]
        self.assertEqual(main.sessions[sid]["owner_issuer"], local_identity.LOCAL_ISSUER)
        self.assertEqual(main.sessions[sid]["owner_subject"], who.json()["user"]["id"])
        self.assertNotIn("user_id", main.sessions[sid]["config"])
        await self.login(self.other, "b@example.com", "Strong!Password-2026B")
        for path in ("status", "results", "gates", "stream?cursor=0"):
            r = await self.other.get("/api/sessions/" + sid + "/" + path)
            self.assertEqual(r.status_code, 404, path)
        self.assertEqual((await self.other.post("/api/sessions/" + sid + "/cancel",
                                               headers=self.origin)).status_code, 404)
        self.assertEqual((await self.client.get("/api/sessions/" + sid + "/status")).status_code, 200)
        await self.client.post("/api/auth/logout", headers=self.origin)
        self.assertEqual((await self.client.get("/api/sessions/" + sid + "/status")).status_code, 401)
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)

    async def test_proxy_secret_and_csrf_origin_are_required(self):
        denied = await self.client.post("/api/auth/login",
            json={"email": "a@example.com", "password": "Strong!Password-2026A"},
            headers={"X-Gilberto-Proxy-Auth": "wrong", **self.origin})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual((await self.client.get("/api/auth/me",
              headers={"X-Gilberto-Proxy-Auth": ""})).status_code, 403)
        no_origin = await self.client.post("/api/auth/login",
            json={"email": "a@example.com", "password": "Strong!Password-2026A"})
        self.assertEqual(no_origin.status_code, 403)
        cross_site = await self.client.post("/api/auth/login",
            json={"email": "a@example.com", "password": "Strong!Password-2026A"},
            headers={"Origin": "https://evil.example"})
        self.assertEqual(cross_site.status_code, 403)
        self.assertEqual((await self.client.get("/api/health")).status_code, 200)
        with patch.object(settings, "LOCAL_AUTH_PROXY_SECRET", ""):
            self.assertEqual((await self.client.get("/api/auth/me")).status_code, 503)

    async def test_server_side_password_change_rotates_and_revokes(self):
        login = await self.login()
        self.assertEqual(login.status_code, 200)
        original = self.client.cookies.get(local_identity.COOKIE_NAME)
        self.assertTrue(original)
        change = await self.client.post("/api/auth/change-password",
            headers=self.origin, json={
                "current_password": "Strong!Password-2026A",
                "new_password": "Even-StrongER!2026"
            })
        self.assertEqual(change.status_code, 200, change.text)
        latest = self.client.cookies.get(local_identity.COOKIE_NAME)
        self.assertNotEqual(latest, original)
        self.assertIsNone(local_identity.resolve_session(original))
        self.assertIsNotNone(local_identity.resolve_session(latest))
        with self.assertRaises(local_identity.LoginRejected):
            local_identity.login("a@example.com", "Strong!Password-2026A", "test")
        self.assertEqual((await self.client.post("/api/auth/change-password",
            headers=self.origin, json={"current_password": "wrong",
            "new_password": "Another-Strong!2026"})).status_code, 400)

    async def test_no_cookie_or_bearer_auth_and_legacy_quarantine(self):
        unauthorized = await self.client.post("/api/sessions",
            headers={**self.origin, "Authorization": "Bearer forged"}, json={})
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)
        await self.login()
        created = await self.client.post("/api/sessions", json={"num_rounds": 1},
                                         headers=self.origin)
        sid = created.json()["session_id"]
        session = main.sessions[sid]
        del session["owner_issuer"], session["owner_subject"]
        main.session_store.save(session)
        main.sessions.clear()
        denied = await self.client.get(f"/api/sessions/{sid}/results")
        self.assertEqual(denied.status_code, 404)

    async def test_cookie_is_not_issued_for_invalid_password(self):
        r = await self.login(password="wrong password")
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("set-cookie", r.headers)
        self.assertEqual((await self.client.get("/api/auth/me")).status_code, 401)

    async def test_loopback_development_cookie_is_not_host_prefixed(self):
        with patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", "http://127.0.0.1:5173"), \
             patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", False):
            dev = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app),
                base_url="http://127.0.0.1:5173",
                headers={"X-Gilberto-Proxy-Auth": "a" * 48})
            try:
                response = await dev.post("/api/auth/login", json={
                    "email": "a@example.com", "password": "Strong!Password-2026A"},
                    headers={"Origin": "http://127.0.0.1:5173"})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(local_identity.DEV_COOKIE_NAME, response.headers["set-cookie"])
                self.assertNotIn("__Host-", response.headers["set-cookie"])
                self.assertEqual((await dev.get("/api/auth/me")).status_code, 200)
            finally:
                await dev.aclose()

    async def test_insecure_cookie_must_not_run_on_public_host(self):
        with patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", False):
            response = await self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 503)


class LocalBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        p = patch.dict(os.environ, {"IDENTITY_DB_PATH": self.folder.name + "/identity.db"})
        p.start()
        self.addCleanup(p.stop)
        self.secret = "A" * 40
        self.digest = local_identity._digest(self.secret)

    def test_first_administrator_created_once_and_admin_permissions_enforced(self):
        token, user = local_identity.bootstrap_first_admin(
            "owner@example.test", "Strong-Initial-Passphrase!2026", self.secret,
            token_hash=self.digest, expires_at=int(time.time()) + 900)
        self.assertEqual(user["role"], "admin")
        self.assertEqual(local_identity.resolve_session(token)["role"], "admin")
        self.assertEqual(local_identity.list_users_for_admin(user["id"])[0]["email"], "owner@example.test")
        with self.assertRaises(local_identity.LoginRejected):
            local_identity.bootstrap_first_admin("other@example.test",
                "Strong-Initial-Passphrase!2026", self.secret,
                token_hash=self.digest, expires_at=int(time.time())+900)
        staff = local_identity.create_user("staff@example.test", "Strong-Staff-Password!2026")
        with self.assertRaises(PermissionError):
            local_identity.list_users_for_admin(staff)

    def test_wrong_expired_or_missing_secret_prevents_admin_creation(self):
        for token, expires in [("wrong" * 10, int(time.time()) + 900),
                               (self.secret, int(time.time()) - 1)]:
            with self.assertRaises(local_identity.LoginRejected):
                local_identity.bootstrap_first_admin("owner@example.test",
                    "Strong-Initial-Passphrase!2026", token,
                    token_hash=self.digest, expires_at=expires)
        self.assertFalse(local_identity.has_bootstrapped())


class LocalBootstrapAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_one_time_and_csrf(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            values = [
                patch.dict(os.environ, {
                    "IDENTITY_DB_PATH": folder + "/identity.sqlite3",
                    "SESSION_DB_PATH": folder + "/sessions.sqlite3"}),
                patch.object(settings, "AUTH_MODE", "local"),
                patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", "https://staging.example.test"),
                patch.object(settings, "LOCAL_AUTH_PROXY_SECRET", "x" * 48),
                patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", True),
                patch.object(settings, "LOCAL_BOOTSTRAP_TOKEN_SHA256",
                             hashlib.sha256(("U" * 50).encode()).hexdigest()),
                patch.object(settings, "LOCAL_BOOTSTRAP_EXPIRES_AT", int(time.time())+900),
            ]
            for p in values: p.start()
            try:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app),
                    base_url="https://staging.example.test",
                    headers={"X-Gilberto-Proxy-Auth": "x" * 48}) as client:
                    status = await client.get("/api/auth/bootstrap-status")
                    self.assertEqual(status.json()["available"], True)
                    body = {"email": "admin@example.test",
                            "password": "Secure-Admin-Passphrase2026!",
                            "bootstrap_token": "U" * 50}
                    wrong_origin = await client.post("/api/auth/bootstrap", json=body,
                         headers={"Origin": "https://malicious.example"})
                    self.assertEqual(wrong_origin.status_code, 403)
                    wrong = await client.post("/api/auth/bootstrap", json={**body,
                         "bootstrap_token": "different"+("U"*45)},
                         headers={"Origin": "https://staging.example.test"})
                    self.assertEqual(wrong.status_code, 403)
                    good = await client.post("/api/auth/bootstrap", json=body,
                         headers={"Origin": "https://staging.example.test"})
                    self.assertEqual(good.status_code, 200, good.text)
                    self.assertEqual(good.json()["user"]["role"], "admin")
                    listed = await client.get("/api/admin/users")
                    self.assertEqual(listed.status_code, 200)
                    self.assertEqual(len(listed.json()["users"]), 1)
                    self.assertFalse((await client.get("/api/auth/bootstrap-status")).json()["available"])
                    repeated = await client.post("/api/auth/bootstrap", json=body,
                         headers={"Origin": "https://staging.example.test"})
                    self.assertEqual(repeated.status_code, 409)
            finally:
                for p in reversed(values): p.stop()
