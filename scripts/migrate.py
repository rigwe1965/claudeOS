"""Run database migrations in order."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from core.database import run_migration, get_db

MIGRATIONS_DIR = Path(__file__).parent.parent / "memory" / "db" / "migrations"


def run_all():
    settings = get_settings()
    print(f"DB: {settings.sqlite_path}")

    # Ensure applied_migrations tracking table exists
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applied_migrations (
                filename TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    with get_db() as conn:
        applied = {row[0] for row in conn.execute("SELECT filename FROM applied_migrations")}

    for mf in migration_files:
        if mf.name in applied:
            print(f"  skip  {mf.name}")
            continue
        print(f"  apply {mf.name} ...", end=" ")
        try:
            run_migration(mf)
            with get_db() as conn:
                conn.execute("INSERT INTO applied_migrations(filename) VALUES (?)", (mf.name,))
            print("OK")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column" in err or "already exists" in err:
                # Column/object already present — mark applied and continue
                with get_db() as conn:
                    conn.execute("INSERT OR IGNORE INTO applied_migrations(filename) VALUES (?)", (mf.name,))
                print(f"OK (skipped: {e})")
            else:
                print(f"FAILED: {e}")
                sys.exit(1)

    print("All migrations applied.")


if __name__ == "__main__":
    run_all()
