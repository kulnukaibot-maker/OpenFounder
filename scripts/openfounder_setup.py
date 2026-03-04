#!/usr/bin/env python3
"""One-time database setup for OpenFounder.

Runs the migration SQL against the configured database.
Safe to run multiple times (uses IF NOT EXISTS / idempotent SQL).

Usage:
    python3 scripts/openfounder_setup.py
    python3 scripts/openfounder_setup.py --check   # verify tables exist
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psycopg2
from openfounder.config import config

MIGRATIONS_DIR = Path(__file__).parent.parent / "openfounder" / "migrations"

EXPECTED_TABLES = [
    "ventures", "features", "bugs", "decisions",
    "metrics", "campaigns", "approvals",
]


def run_migrations():
    """Run all migration files in order."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        cur = conn.cursor()

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found!")
            sys.exit(1)

        for mf in migration_files:
            print(f"Running: {mf.name}...")
            sql = mf.read_text()
            cur.execute(sql)
            print(f"  Done.")

        conn.commit()
        print(f"\nAll {len(migration_files)} migration(s) applied successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def check_tables():
    """Verify all expected tables exist."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        existing = {row[0] for row in cur.fetchall()}

        all_ok = True
        for table in EXPECTED_TABLES:
            status = "OK" if table in existing else "MISSING"
            print(f"  {table}: {status}")
            if table not in existing:
                all_ok = False

        if all_ok:
            print(f"\nAll {len(EXPECTED_TABLES)} tables present.")
        else:
            print("\nSome tables are missing. Run without --check to apply migrations.")
            sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        prog="openfounder-setup",
        description="Set up the OpenFounder database.",
    )
    parser.add_argument("--check", action="store_true", help="Only check if tables exist")
    args = parser.parse_args()

    print(f"Database: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else config.DATABASE_URL}")

    if args.check:
        check_tables()
    else:
        run_migrations()
        print("\nVerifying...")
        check_tables()


if __name__ == "__main__":
    main()
