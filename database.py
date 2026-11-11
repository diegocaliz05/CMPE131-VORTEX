"""Data Storage entry point: connection factory and schema initialisation."""
import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE = "vortex.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db_connection(db_path=None):
    conn = sqlite3.connect(db_path or DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Create all tables/indexes if they do not exist (idempotent)."""
    with closing(get_db_connection(db_path)) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
