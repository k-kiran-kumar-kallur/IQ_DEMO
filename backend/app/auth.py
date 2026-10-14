"""Local logins stored in SQLite: salted scrypt password hashes, server-side sessions in an HttpOnly cookie,
lockout after repeated failures, and a login audit trail."""
import datetime as dt
import hashlib
import hmac
import json
import secrets

from fastapi import HTTPException, Request

from . import db
from .permissions import DEMO_USERS, IQS, ROLES

COOKIE = "iq_session"
SESSION_HOURS = 12
MAX_FAILED = 5
LOCK_MINUTES = 10
DEMO_PASSWORD = "Demo@123"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY, display_name TEXT, title TEXT, role TEXT, accounts_json TEXT, partners_json TEXT,
    password_hash TEXT, active INTEGER DEFAULT 1, failed_attempts INTEGER DEFAULT 0, locked_until TEXT,
    created_at TEXT, last_login TEXT);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, username TEXT, created_at TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS login_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, username TEXT, success INTEGER, reason TEXT, ip TEXT);
"""


def now():
    return dt.datetime.now(dt.timezone.utc)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, n, r, p, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                              dklen=len(bytes.fromhex(digest)))
        return hmac.compare_digest(calc.hex(), digest)
    except Exception:
        return False


def init():
    with db.session() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
            for username, name, title, role, accounts, partners in DEMO_USERS:
                c.execute("INSERT INTO users(username, display_name, title, role, accounts_json, partners_json, "
                          "password_hash, created_at) VALUES(?,?,?,?,?,?,?,?)",
                          (username, name, title, role, json.dumps(accounts), json.dumps(partners),
                           hash_password(DEMO_PASSWORD), now().isoformat()))


PARTNER_NAMES = {"PRT-01": "Microsoft", "PRT-02": "AWS", "PRT-03": "Databricks", "PRT-04": "Snowflake",
                 "PRT-05": "ServiceNow", "PRT-06": "Guidewire"}


def account_names():
    """Account ID -> name from the loaded fact tables (empty until documents are loaded)."""
    try:
        _, rows = db.query("SELECT DISTINCT account_id, account FROM v_revenue UNION SELECT DISTINCT account_id, account FROM v_pipeline")
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _row_to_user(row):
    if not row:
        return None
    role = ROLES.get(row["role"], {})
    names = account_names()
    return dict(username=row["username"], display_name=row["display_name"], title=row["title"], role=row["role"],
                role_name=role.get("name", row["role"]), note=role.get("note", ""), is_admin=bool(role.get("admin")),
                accounts=json.loads(row["accounts_json"] or "[]"), partners=json.loads(row["partners_json"] or "[]"),
                account_names=[names.get(a, a) for a in json.loads(row["accounts_json"] or "[]")],
                partner_names=[PARTNER_NAMES.get(p, p) for p in json.loads(row["partners_json"] or "[]")],
                grants={IQS[k]: v for k, v in role.get("grants", {}).items()}, active=bool(row["active"]),
                last_login=row["last_login"])


def get_user(username):
    with db.session() as c:
        return _row_to_user(c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone())


def list_users():
    with db.session() as c:
        return [_row_to_user(r) for r in c.execute("SELECT * FROM users ORDER BY role, username").fetchall()]


def _audit(c, username, success, reason, ip):
    c.execute("INSERT INTO login_audit(at, username, success, reason, ip) VALUES(?,?,?,?,?)",
              (now().isoformat(), username, 1 if success else 0, reason, ip))


def login(username, password, ip):
    """Returns (session token, user) or raises HTTPException(401/423). Failed attempts and the audit row are committed
    before the error is raised, so lockout and auditing survive the failure."""
    username = (username or "").strip().lower()
    error = None
    token = None
    with db.session() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not row["active"]:
            hash_password(password or "x")                   # same work either way, so timing does not reveal usernames
            _audit(c, username, False, "unknown or inactive user", ip)
            error = (401, "Invalid username or password")
        elif row["locked_until"] and dt.datetime.fromisoformat(row["locked_until"]) > now():
            _audit(c, username, False, "locked", ip)
            error = (423, f"Account locked after {MAX_FAILED} failed attempts. Try again in {LOCK_MINUTES} minutes.")
        elif not verify_password(password or "", row["password_hash"]):
            failed = (row["failed_attempts"] or 0) + 1
            locked = (now() + dt.timedelta(minutes=LOCK_MINUTES)).isoformat() if failed >= MAX_FAILED else None
            c.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE username=?",
                      (0 if locked else failed, locked, username))
            _audit(c, username, False, "wrong password" + (" - account locked" if locked else ""), ip)
            error = (423, f"Account locked after {MAX_FAILED} failed attempts. Try again in {LOCK_MINUTES} minutes.") \
                if locked else (401, "Invalid username or password")
        else:
            token = secrets.token_urlsafe(32)
            c.execute("INSERT INTO sessions VALUES(?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username,
                                                              now().isoformat(),
                                                              (now() + dt.timedelta(hours=SESSION_HOURS)).isoformat()))
            c.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=? WHERE username=?",
                      (now().isoformat(), username))
            c.execute("DELETE FROM sessions WHERE expires_at < ?", (now().isoformat(),))
            _audit(c, username, True, "ok", ip)
    if error:                                                 # raised only after the transaction has committed
        raise HTTPException(*error)
    return token, get_user(username)


def logout(token):
    if token:
        with db.session() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def current_user(request: Request):
    """FastAPI dependency: the logged-in user, or 401."""
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    with db.session() as c:
        s = c.execute("SELECT * FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not s or dt.datetime.fromisoformat(s["expires_at"]) < now():
        raise HTTPException(401, "Session expired, please sign in again")
    user = get_user(s["username"])
    if not user or not user["active"]:
        raise HTTPException(401, "User is inactive")
    return user


def require_admin(request: Request):
    user = current_user(request)
    if not user["is_admin"]:
        raise HTTPException(403, "Only a platform admin can do this")
    return user
