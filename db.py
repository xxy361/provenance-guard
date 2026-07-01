"""Audit log — structured SQLite store.

One row per submission, keyed by content_id. `/submit` inserts a row with
status "classified"; `/appeal` later updates the same row (creator_reasoning,
appeal_ts, status -> "under_review"). See planning.md § Audit Log.
"""

import sqlite3

from flask import g

DB_PATH = "provenance_guard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    content_id         TEXT PRIMARY KEY,
    creator_id         TEXT NOT NULL,
    content_text       TEXT NOT NULL,
    create_ts          TEXT NOT NULL,
    llm_score          REAL,
    llm_reasoning      TEXT,
    stylometric_score  REAL,
    attribution        TEXT,
    confidence         REAL,
    status             TEXT NOT NULL,
    creator_reasoning  TEXT,
    appeal_ts          TEXT
);
"""


def get_db():
    """Return a per-request SQLite connection (row access by column name)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    """Close the per-request connection. Registered as a teardown handler."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the audit_log table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def init_log(app):
    """Wire the audit log into a Flask app: create the table and register the
    connection-teardown handler."""
    init_db()
    app.teardown_appcontext(close_db)


def get_log(limit=50):
    """Return recent audit-log entries as a list of dicts, newest first."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM audit_log ORDER BY create_ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def submit_log(record):
    """Insert one structured submission entry into the audit log.

    `record` is a dict with keys matching the audit_log columns.
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_log (
            content_id, creator_id, content_text, create_ts,
            llm_score, llm_reasoning, stylometric_score,
            attribution, confidence, status,
            creator_reasoning, appeal_ts
        ) VALUES (
            :content_id, :creator_id, :content_text, :create_ts,
            :llm_score, :llm_reasoning, :stylometric_score,
            :attribution, :confidence, :status,
            :creator_reasoning, :appeal_ts
        )
        """,
        record,
    )
    db.commit()
