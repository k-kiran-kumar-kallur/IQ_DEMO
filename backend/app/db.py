"""SQLite: settings overrides, question history with traces, ingestion runs, document registry and fact tables."""
import json
import re
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, SETTINGS, env_default

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, asked_at TEXT, user TEXT, question TEXT,
    answer TEXT, status TEXT, total_ms INTEGER, trace_json TEXT);
CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, status TEXT,
    files INTEGER, chunks INTEGER, entities INTEGER, tables_loaded INTEGER, message TEXT);
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY, path TEXT, title TEXT, iq TEXT, format TEXT, classification TEXT,
    checksum TEXT, raw_path TEXT, chunks INTEGER, ingested_at TEXT);
CREATE TABLE IF NOT EXISTS catalog (
    table_name TEXT PRIMARY KEY, source_path TEXT, sheet TEXT, iq TEXT, columns_json TEXT, row_count INTEGER);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with session() as c:
        c.executescript(SCHEMA)


# ------------------------------------------------------------------ settings
def get_setting(key):
    with session() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row and row["value"] not in (None, ""):
        return row["value"]
    return env_default(key)


def settings_source(key):
    with session() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row and row["value"] not in (None, ""):
        return "settings screen"
    import os
    return ".env" if os.getenv(SETTINGS[key][0]) else "default"


def save_settings(values: dict):
    with session() as c:
        for k, v in values.items():
            if k not in SETTINGS:
                continue
            if SETTINGS[k][2] and not v:          # blank secret = keep current value
                continue
            c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (k, v))


# ------------------------------------------------------------------ fact tables
def sanitize(name):
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()
    return s or "col"


def load_table(conn, table, headers, rows):
    cols, seen = [], {}
    for h in headers:
        c = sanitize(h)
        if c in seen:
            seen[c] += 1
            c = f"{c}_{seen[c]}"
        else:
            seen[c] = 0
        cols.append(c)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    col_sql = ", ".join(f'"{c}"' for c in cols)
    conn.execute(f'CREATE TABLE "{table}" ({col_sql})')
    conn.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" * len(cols))})',
                     [tuple(r[i] if i < len(r) else None for i in range(len(cols))) for r in rows])
    return cols


def query(sql, params=()):
    conn = connect()
    try:
        conn.execute("PRAGMA query_only = ON")           # the facts agent can only read
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, [list(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_question(q):
    with session() as c:
        cur = c.execute("INSERT INTO questions(asked_at, user, question, answer, status, total_ms, trace_json) "
                        "VALUES(?,?,?,?,?,?,?)", (q["asked_at"], q["user"], q["question"], q["answer"], q["status"],
                                                   q["total_ms"], json.dumps(q, default=str)))
        return cur.lastrowid
