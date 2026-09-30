"""Couche SQLite - historique append-only, jamais surcharge."""
import sqlite3, json
from datetime import datetime, timezone
from .config import DB_PATH

def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        indicator TEXT NOT NULL,
        value REAL,
        previous REAL,
        unit TEXT,
        source TEXT,
        status TEXT,
        score REAL,
        published_date TEXT,
        collected_at TEXT,
        extra TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        regimes TEXT,
        global_score REAL,
        transition_score REAL,
        conclusion TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT,
        message TEXT,
        confidence REAL,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def insert_indicator(cat, ind, value, prev, unit, source, pub, extra=None):
    conn = _conn()
    c = conn.cursor()
    c.execute("""INSERT INTO indicators (category, indicator, value, previous, unit, source, published_date, collected_at, extra)
               VALUES (?,?,?,?,?,?,?,?,?)""",
              (cat, ind, value, prev, unit, source, pub, datetime.now(timezone.utc).isoformat(), json.dumps(extra, ensure_ascii=False) if extra else ""))
    conn.commit()
    conn.close()

def latest(cat, ind):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT * FROM indicators WHERE category=? AND indicator=? ORDER BY id DESC LIMIT 1", (cat, ind))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def history(cat, ind, limit=12):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT value, published_date FROM indicators WHERE category=? AND indicator=? ORDER BY id DESC LIMIT ?", (cat, ind, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def save_snapshot(period, regimes, gscore, tscore, conclusion):
    conn = _conn()
    c = conn.cursor()
    c.execute("INSERT INTO snapshots (period, regimes, global_score, transition_score, conclusion, created_at) VALUES (?,?,?,?,?,?)",
              (period, json.dumps(regimes, ensure_ascii=False), gscore, tscore, conclusion, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def recent_snapshots(n=12):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (n,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def add_alert(level, message, confidence):
    conn = _conn()
    c = conn.cursor()
    c.execute("INSERT INTO alerts (level, message, confidence, created_at) VALUES (?,?,?,?)",
              (level, message, confidence, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def recent_alerts(n=20):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (n,))
    return [dict(r) for r in c.fetchall()]
