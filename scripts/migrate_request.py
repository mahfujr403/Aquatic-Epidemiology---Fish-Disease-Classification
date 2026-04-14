"""
scripts/migrate_add_request_logs.py
────────────────────────────────────
One-time migration: creates the `request_logs` table (and any other
missing tables) without touching existing data.

Run once after deploying the updated code:

    python scripts/migrate_add_request_logs.py

Safe to run multiple times — SQLAlchemy's create_all() is a no-op
for tables that already exist.
"""

import sys
import os

# Make sure the project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app, db
import aquadiag.models  # ensures all models are registered with SQLAlchemy


def run():
    with app.app_context():
        print("[migrate] Connecting to:", app.config["SQLALCHEMY_DATABASE_URI"][:60], "…")
        db.create_all()
        print("[migrate] ✓ All tables verified / created.")

        # Confirm request_logs specifically
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "request_logs" in tables:
            cols = [c["name"] for c in inspector.get_columns("request_logs")]
            print(f"[migrate] ✓ request_logs columns: {cols}")
        else:
            print("[migrate] ✗ request_logs table NOT found — check models.py import.")


if __name__ == "__main__":
    run()