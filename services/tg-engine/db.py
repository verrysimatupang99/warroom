import os
import json
import sqlite3
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "trading_signals.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                channel_name TEXT,
                category TEXT,            -- 'FOREX', 'SAHAM', 'CRYPTO', 'GENERAL'
                message_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                views INTEGER DEFAULT 0,
                forwards INTEGER DEFAULT 0,
                raw_metadata TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_cat ON signals(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);")
    conn.close()

def insert_signal(channel_id: str, channel_name: str, category: str, message_text: str, views: int = 0, forwards: int = 0, metadata: dict = None):
    conn = get_db()
    raw_meta = json.dumps(metadata or {}, ensure_ascii=False)
    with conn:
        cursor = conn.execute("""
            INSERT INTO signals (channel_id, channel_name, category, message_text, timestamp, views, forwards, raw_metadata)
            VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)
        """, (str(channel_id), channel_name, category, message_text, views, forwards, raw_meta))
        sig_id = cursor.lastrowid
    conn.close()
    return sig_id

def get_signals(limit: int = 50, category: str = None, search: str = None):
    conn = get_db()
    query = "SELECT * FROM signals WHERE 1=1"
    params = []
    if category and category.upper() != "ALL":
        query += " AND category = ?"
        params.append(category.upper())
    if search:
        query += " AND (message_text LIKE ? OR channel_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    forex = conn.execute("SELECT COUNT(*) FROM signals WHERE category = 'FOREX'").fetchone()[0]
    saham = conn.execute("SELECT COUNT(*) FROM signals WHERE category = 'SAHAM'").fetchone()[0]
    crypto = conn.execute("SELECT COUNT(*) FROM signals WHERE category = 'CRYPTO'").fetchone()[0]
    general = conn.execute("SELECT COUNT(*) FROM signals WHERE category = 'GENERAL'").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "forex": forex,
        "saham": saham,
        "crypto": crypto,
        "general": general
    }

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
