"""Apply ClaudeOS schema to Supabase via Management API.

Usage:
    python scripts/apply_supabase_schema.py

Requires SUPABASE_ACCESS_TOKEN in .env (personal access token from
https://supabase.com/dashboard/account/tokens — NOT the service key).
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from core.config import get_settings


def main():
    settings = get_settings()

    pat = getattr(settings, "SUPABASE_ACCESS_TOKEN", "")
    if not pat:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set in .env")
        print("  1. Go to https://supabase.com/dashboard/account/tokens")
        print("  2. Generate a new token")
        print("  3. Add to .env:  SUPABASE_ACCESS_TOKEN=sbp_...")
        sys.exit(1)

    if not settings.SUPABASE_URL:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)

    ref = settings.SUPABASE_URL.replace("https://", "").split(".")[0]
    api_url = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }

    schema_path = Path(__file__).parent.parent / "sync" / "supabase_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    # Split into individual statements (split on semicolon + newline)
    statements = [s.strip() for s in re.split(r";\s*\n", sql) if s.strip() and not s.strip().startswith("--")]

    print(f"Applying {len(statements)} SQL statements to project {ref}...")
    print()

    passed = 0
    failed = 0
    for i, stmt in enumerate(statements, 1):
        if not stmt:
            continue
        # Add semicolon back
        query = stmt if stmt.endswith(";") else stmt + ";"
        short = query[:60].replace("\n", " ")
        try:
            r = requests.post(api_url, headers=headers, json={"query": query}, timeout=15)
            if r.status_code in (200, 201):
                print(f"  OK  [{i:02d}] {short}...")
                passed += 1
            else:
                err = r.json().get("message", r.text[:100])
                # Ignore "already exists" errors
                if "already exists" in err.lower():
                    print(f"  --  [{i:02d}] {short}... (already exists)")
                    passed += 1
                else:
                    print(f"  FAIL[{i:02d}] {short}...")
                    print(f"       {err}")
                    failed += 1
        except Exception as e:
            print(f"  ERR [{i:02d}] {short}... {e}")
            failed += 1

    print()
    print(f"Done: {passed} OK, {failed} failed")
    if failed == 0:
        print("Schema applied. Run sync from Settings page to push all data.")
    else:
        print("Some statements failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
