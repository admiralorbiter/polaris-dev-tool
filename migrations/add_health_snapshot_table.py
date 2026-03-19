"""Migration: add health_snapshot table.

Run this script ONCE to add the HealthSnapshot table to an existing database
that was created before Phase 4c. If you're initializing a fresh database,
this is not needed — db.create_all() handles it automatically.

Usage:
    python migrations/add_health_snapshot_table.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


DDL = """
CREATE TABLE IF NOT EXISTS health_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    score INTEGER,
    label TEXT,
    color TEXT,
    components_json TEXT,
    trigger TEXT DEFAULT 'briefing',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def run():
    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        try:
            cursor = conn.cursor()
            cursor.executescript(DDL)
            conn.commit()
            print("✅ health_snapshot table created (or already existed).")
        except Exception as exc:
            print(f"❌ Migration failed: {exc}")
            sys.exit(1)
        finally:
            conn.close()


if __name__ == "__main__":
    run()
