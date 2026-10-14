import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "app.db"


def get_db():
    """One connection per request, closed automatically afterwards."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables from schema.sql (safe to run repeatedly)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript((BASE_DIR / "schema.sql").read_text())
