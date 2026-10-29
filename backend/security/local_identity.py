"""Invite-only, server-side local identity for a single trusted backend worker.

No homemade crypto: Argon2id (argon2-cffi) passwords, OS-CSPRNG session tokens,
SHA256-at-rest token digests, SQLite transactional persistence. Never expose
password hashes or bearer/session tokens in application logs or API responses.
"""
import argparse
from contextlib import closing
import getpass
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

COOKIE_NAME = "__Host-gilberto_session"
LOCAL_ISSUER = "urn:gilberto:local:v1"
SESSION_TTL = 8 * 3600
IDLE_TTL = 30 * 60
LOGIN_WINDOW = 15 * 60
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2,
                                 hash_len=32, salt_len=16, type=Type.ID)
# A fixed valid Argon2id hash avoids skipping verification work for unknown users.
DUMMY_HASH = PASSWORD_HASHER.hash("synthetic-only-unknown-account-validation")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class LoginRejected(Exception):
    def __init__(self, throttled=False):
        self.throttled = throttled


class PasswordRejected(ValueError):
    pass


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError("Invalid email address")
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("Invalid email address")
    return email


def validate_new_password(password):
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        raise PasswordRejected("Password must contain 12 to 256 characters")
    if len(password.encode("utf-8")) > 1024 or "\x00" in password:
        raise PasswordRejected("Password is too long or contains an unsupported character")
    if password.isspace():
        raise PasswordRejected("Password cannot consist entirely of whitespace")


def connect():
    path = Path(os.environ.get("IDENTITY_DB_PATH", "data/identity.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        pass
    db = sqlite3.connect(str(path), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=15000")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS identity_users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            password_changed_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES identity_users(id),
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL,
            revoked_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS identity_sessions_user
            ON identity_sessions(user_id);
        CREATE TABLE IF NOT EXISTS identity_login_attempts (
            key_hash TEXT PRIMARY KEY,
            failures INTEGER NOT NULL,
            first_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event TEXT NOT NULL,
            at INTEGER NOT NULL
        );
    """)
    return db


def _audit(db, user_id, action, now):
    db.execute("INSERT INTO identity_audit(user_id,event,at) VALUES(?,?,?)",
               (user_id, action, now))


def _verify(password, hash_value):
    try:
        return PASSWORD_HASHER.verify(hash_value, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _throttle_key(category, value):
    return _digest(category + ":" + value)


def _is_throttled(db, key, limit, now):
    row = db.execute("SELECT failures,first_at FROM identity_login_attempts "
                     "WHERE key_hash=?", (key,)).fetchone()
    return bool(row and now - row["first_at"] < LOGIN_WINDOW and row["failures"] >= limit)


def _record_failure(db, key, now):
    row = db.execute("SELECT failures,first_at FROM identity_login_attempts "
                     "WHERE key_hash=?", (key,)).fetchone()
    if row and now - row["first_at"] < LOGIN_WINDOW:
        db.execute("UPDATE identity_login_attempts SET failures=failures+1 "
                   "WHERE key_hash=?", (key,))
    else:
        db.execute("INSERT OR REPLACE INTO identity_login_attempts "
                   "VALUES(?,?,?)", (key, 1, now))


def _new_session(db, user_id, now):
    token = secrets.token_urlsafe(32)
    digest = _digest(token)
    db.execute("DELETE FROM identity_sessions WHERE user_id=? AND "
               "(revoked_at IS NOT NULL OR expires_at<=?)", (user_id, now))
    # Cap number of live simultaneous sessions.
    db.execute("""DELETE FROM identity_sessions WHERE token_hash IN (
        SELECT token_hash FROM identity_sessions WHERE user_id=?
        ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET 4
    )""", (user_id,))
    db.execute("INSERT INTO identity_sessions VALUES (?,?,?,?,?,NULL)",
               (digest, user_id, now, now + SESSION_TTL, now))
    return token


def create_user(email, password):
    email = normalize_email(email)
    validate_new_password(password)
    now = int(time.time())
    user_id = str(uuid.uuid4())
    pwd_hash = PASSWORD_HASHER.hash(password)
    with closing(connect()) as db:
        with db:
            db.execute("INSERT INTO identity_users VALUES(?,?,?,?,?,?)",
                       (user_id, email, pwd_hash, 1, now, now))
            _audit(db, user_id, "USER_CREATED", now)
    return user_id


def login(email, password, remote_address):
    now = int(time.time())
    try:
        normalized = normalize_email(email)
    except ValueError:
        normalized = ""  # Still run constant-work dummy Argon2 verification.
    if not isinstance(password, str) or len(password.encode("utf-8")) > 1024:
        raise LoginRejected()
    email_key = _throttle_key("email", normalized)
    remote_key = _throttle_key("remote", remote_address or "unknown")
    with closing(connect()) as db:
        with db:
            if _is_throttled(db, email_key, 5, now) or _is_throttled(db, remote_key, 100, now):
                raise LoginRejected(throttled=True)
            user = db.execute("SELECT * FROM identity_users WHERE email=?",
                              (normalized,)).fetchone() if normalized else None
            verified = _verify(password, user["password_hash"] if user else DUMMY_HASH)
            if not verified or not user or user["active"] != 1:
                _record_failure(db, email_key, now)
                _record_failure(db, remote_key, now)
                db.commit()  # Preserve rate-limit state despite the rejected login.
                raise LoginRejected()
            if PASSWORD_HASHER.check_needs_rehash(user["password_hash"]):
                db.execute("UPDATE identity_users SET password_hash=? WHERE id=?",
                           (PASSWORD_HASHER.hash(password), user["id"]))
            db.execute("DELETE FROM identity_login_attempts WHERE key_hash=?",
                       (email_key,))
            token = _new_session(db, user["id"], now)
            _audit(db, user["id"], "LOGIN", now)
            return token, {"id": user["id"], "email": user["email"]}


def resolve_session(token):
    if not token or not isinstance(token, str) or not 20 < len(token) < 128:
        return None
    now = int(time.time())
    with closing(connect()) as db:
        with db:
            row = db.execute("""
              SELECT s.user_id, s.expires_at, s.last_seen_at, u.email
              FROM identity_sessions AS s
              JOIN identity_users AS u ON u.id=s.user_id
              WHERE s.token_hash=? AND s.revoked_at IS NULL AND u.active=1
            """, (_digest(token),)).fetchone()
            if not row or row["expires_at"] <= now or row["last_seen_at"] + IDLE_TTL <= now:
                return None
            if now - row["last_seen_at"] >= 60:
                db.execute("UPDATE identity_sessions SET last_seen_at=? "
                           "WHERE token_hash=? AND revoked_at IS NULL",
                           (now, _digest(token)))
            return {"id": row["user_id"], "email": row["email"],
                    "expires_at": row["expires_at"]}


def revoke_session(token):
    if not token:
        return
    with closing(connect()) as db:
        with db:
            row = db.execute("SELECT user_id FROM identity_sessions WHERE token_hash=?",
                             (_digest(token),)).fetchone()
            if row:
                now = int(time.time())
                db.execute("UPDATE identity_sessions SET revoked_at=? WHERE token_hash=?",
                           (now, _digest(token)))
                _audit(db, row["user_id"], "LOGOUT", now)


def change_password(user_id, old_password, new_password):
    validate_new_password(new_password)
    now = int(time.time())
    with closing(connect()) as db:
        with db:
            user = db.execute("SELECT password_hash,active FROM identity_users WHERE id=?",
                              (user_id,)).fetchone()
            if not user or user["active"] != 1 or not _verify(old_password, user["password_hash"]):
                raise PasswordRejected("Current password is incorrect")
            db.execute("UPDATE identity_users SET password_hash=?,password_changed_at=? WHERE id=?",
                       (PASSWORD_HASHER.hash(new_password), now, user_id))
            db.execute("DELETE FROM identity_sessions WHERE user_id=?", (user_id,))
            token = _new_session(db, user_id, now)
            _audit(db, user_id, "PASSWORD_CHANGED", now)
            return token


def reset_password(email, new_password):
    email = normalize_email(email)
    validate_new_password(new_password)
    now = int(time.time())
    with closing(connect()) as db:
        with db:
            row = db.execute("SELECT id FROM identity_users WHERE email=?", (email,)).fetchone()
            if not row:
                raise ValueError("Account not found")
            db.execute("UPDATE identity_users SET password_hash=?,password_changed_at=? "
                       "WHERE id=?", (PASSWORD_HASHER.hash(new_password), now, row["id"]))
            db.execute("DELETE FROM identity_sessions WHERE user_id=?", (row["id"],))
            _audit(db, row["id"], "ADMIN_PASSWORD_RESET", now)


def deactivate_user(email):
    email = normalize_email(email)
    with closing(connect()) as db:
        with db:
            row = db.execute("SELECT id FROM identity_users WHERE email=?", (email,)).fetchone()
            if not row:
                raise ValueError("Account not found")
            db.execute("UPDATE identity_users SET active=0 WHERE id=?", (row["id"],))
            db.execute("DELETE FROM identity_sessions WHERE user_id=?", (row["id"],))
            _audit(db, row["id"], "USER_DEACTIVATED", int(time.time()))


def main():
    parser = argparse.ArgumentParser(description="Gilberto local identity admin CLI; no public signup")
    sub = parser.add_subparsers(dest="command", required=True)
    for action in ("create-user", "reset-password", "deactivate-user"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--email", required=True)
    sub.add_parser("list-users")
    args = parser.parse_args()
    try:
        if args.command == "list-users":
            with closing(connect()) as db:
                for row in db.execute("SELECT id,email,active FROM identity_users ORDER BY email"):
                    print(row["id"], row["email"], "active" if row["active"] else "disabled")
        elif args.command == "deactivate-user":
            deactivate_user(args.email)
            print("Account disabled; sessions revoked")
        else:
            password = getpass.getpass("New password (not echoed): ")
            confirm = getpass.getpass("Confirm new password: ")
            if password != confirm:
                raise PasswordRejected("Passwords do not match")
            if args.command == "create-user":
                user_id = create_user(args.email, password)
                print("Account created:", user_id)
            else:
                reset_password(args.email, password)
                print("Password reset; all sessions revoked")
    except (ValueError, sqlite3.Error) as exc:
        print("Identity operation failed:", str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
