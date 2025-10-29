# app/models/storage.py
from __future__ import annotations

import os
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional
from datetime import datetime, timezone

# ---------- helpers ----------

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@contextmanager
def get_conn(db_path: str):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit
    conn.row_factory = _dict_factory
    try:
        yield conn
    finally:
        conn.close()

# ---------- schema / init ----------

DDL_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
  id                TEXT PRIMARY KEY,
  tenant_id         TEXT NOT NULL,
  phone             TEXT NOT NULL,
  direction         TEXT NOT NULL,              -- inbound | outbound
  text              TEXT,
  attachments_meta  TEXT,
  external_msg_id   TEXT UNIQUE,                -- wamid (quando existir)
  status            TEXT,                       -- sent | delivered | read | failed
  raw_payload       TEXT,
  created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_phone_created ON messages(phone, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_created ON messages(tenant_id, created_at);
"""

DDL_PROCESSED = """
CREATE TABLE IF NOT EXISTS processed_ids (
  external_msg_id TEXT PRIMARY KEY,
  seen_at         TEXT NOT NULL
);
"""

DDL_BOOKINGS = """
CREATE TABLE IF NOT EXISTS bookings (
  id                  TEXT PRIMARY KEY,
  tenant_id           TEXT NOT NULL,
  phone               TEXT NOT NULL,
  start_at            TEXT NOT NULL,
  end_at              TEXT,
  status              TEXT NOT NULL,            -- pending | confirmed | cancelled
  created_by          TEXT NOT NULL,            -- bot | human
  external_calendar_id TEXT,
  meta                TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_phone ON bookings(phone);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_at);
"""

def ensure_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        cur = conn.cursor()
        for ddl in (DDL_MESSAGES, DDL_PROCESSED, DDL_BOOKINGS):
            cur.executescript(ddl)

# ---------- messages ----------

def insert_message(
    db_path: str,
    *,
    id: str,
    tenant_id: str,
    phone: str,
    direction: str,
    text: Optional[str],
    attachments_meta: Optional[Dict[str, Any]] = None,
    external_msg_id: Optional[str] = None,
    status: Optional[str] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
) -> None:
    created_at = created_at or iso_now()
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO messages
               (id, tenant_id, phone, direction, text, attachments_meta, external_msg_id, status, raw_payload, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                id,
                tenant_id,
                phone,
                direction,
                text,
                json.dumps(attachments_meta) if attachments_meta else None,
                external_msg_id,
                status,
                json.dumps(raw_payload, ensure_ascii=False) if raw_payload else None,
                created_at,
            ),
        )

def update_message_status_by_external_id(db_path: str, external_msg_id: str, status: str) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE messages SET status=? WHERE external_msg_id=?",
            (status, external_msg_id),
        )
        return cur.rowcount

def list_messages_by_phone(db_path: str, phone: str, *, limit: int = 50, before: Optional[str] = None) -> List[Dict[str, Any]]:
    q = "SELECT * FROM messages WHERE phone=?"
    args: List[Any] = [phone]
    if before:
        q += " AND created_at < ?"
        args.append(before)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(int(limit))
    with get_conn(db_path) as conn:
        return conn.execute(q, tuple(args)).fetchall()

def list_recent_contacts(db_path: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    q = """
    SELECT phone, tenant_id, MAX(created_at) as last_message_at
    FROM messages
    GROUP BY phone, tenant_id
    ORDER BY last_message_at DESC
    LIMIT ?
    """
    with get_conn(db_path) as conn:
        return conn.execute(q, (int(limit),)).fetchall()

# ---------- processed_ids (dedupe) ----------

def add_processed_id(db_path: str, external_msg_id: str, *, when: Optional[str] = None) -> bool:
    when = when or iso_now()
    try:
        with get_conn(db_path) as conn:
            conn.execute(
                "INSERT INTO processed_ids (external_msg_id, seen_at) VALUES (?,?)",
                (external_msg_id, when),
            )
        return True
    except sqlite3.IntegrityError:
        return False  # já existia

def has_processed_id(db_path: str, external_msg_id: str) -> bool:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_ids WHERE external_msg_id=?",
            (external_msg_id,),
        ).fetchone()
        return bool(row)

# ---------- bookings (básico) ----------

def insert_booking(
    db_path: str,
    *,
    id: str,
    tenant_id: str,
    phone: str,
    start_at: str,
    end_at: Optional[str],
    status: str,
    created_by: str,
    external_calendar_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    now = iso_now()
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO bookings
               (id, tenant_id, phone, start_at, end_at, status, created_by, external_calendar_id, meta, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                id,
                tenant_id,
                phone,
                start_at,
                end_at,
                status,
                created_by,
                external_calendar_id,
                json.dumps(meta) if meta else None,
                now,
                now,
            ),
        )
