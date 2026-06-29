"""Apply SQL migrations to Supabase.

Usage:
    python scripts/setup_db.py

Reads SUPABASE_URL + SUPABASE_SERVICE_KEY from .env and runs every
app/db/migrations/*.sql in filename order via Postgres.

Note: this connects to Postgres directly. Set SUPABASE_DB_URL in your .env
to the connection string from Supabase (Project Settings -> Database), e.g.
    postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres
"""
import os
import pathlib
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars may be exported directly

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "db" / "migrations"


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: set SUPABASE_DB_URL in your environment/.env", file=sys.stderr)
        return 1

    try:
        import psycopg  # psycopg3
    except ImportError:
        print("ERROR: pip install psycopg[binary]", file=sys.stderr)
        return 1

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print(f"No migrations found in {MIGRATIONS_DIR}")
        return 0

    with psycopg.connect(db_url, autocommit=True) as conn:
        for sql_file in sql_files:
            print(f"Applying {sql_file.name} ...")
            conn.execute(sql_file.read_text())
    print(f"Done — {len(sql_files)} migration(s) applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
