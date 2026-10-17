"""Bootstrap the first admin user. Run once after migration 006.

Usage:
    python scripts/create_admin.py --username admin --password YourSecurePassword1!
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def main():
    parser = argparse.ArgumentParser(description="Create the first ClaudeOS admin user")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password (min 10 chars, upper+lower+digit)")
    args = parser.parse_args()

    from core.auth import (
        create_user, get_user_by_username, validate_password_strength
    )
    from core.database import get_db

    # Check migration was applied
    try:
        with get_db() as conn:
            conn.execute("SELECT 1 FROM users LIMIT 1")
    except Exception:
        print("ERROR: users table not found. Run migration 006 first:")
        print("  python -c \"from pathlib import Path; from core.database import run_migration; run_migration(Path('memory/db/migrations/006_auth_users.sql'))\"")
        sys.exit(1)

    # Prevent duplicate admins
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()
    if existing:
        print("ERROR: An admin user already exists. Use the Admin panel to manage users.")
        sys.exit(1)

    # Validate
    err = validate_password_strength(args.password, args.username)
    if err:
        print(f"ERROR: {err}")
        sys.exit(1)

    if get_user_by_username(args.username):
        print(f"ERROR: Username '{args.username}' already taken.")
        sys.exit(1)

    user = create_user(args.username, args.password, role="admin", namespace=None)
    print(f"Admin user created successfully.")
    print(f"  Username : {user['username']}")
    print(f"  Role     : {user['role']}")
    print(f"  ID       : {user['id']}")
    print()
    print("Start the server and log in at http://localhost:8501")


if __name__ == "__main__":
    main()
