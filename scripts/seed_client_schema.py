"""Seed client onboarding schema for a namespace.

Usage:
    python scripts/seed_client_schema.py --namespace website-portal

Creates blank placeholder memory entries for all 14 standard client keys.
Skips any key that already exists (no overwrite).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db
from core.utils import new_id

CLIENT_SCHEMA = [
    ("client.business_name", "fact",       "Full business name",                          ""),
    ("client.industry",      "fact",       "Industry / sector",                            ""),
    ("client.location",      "fact",       "City, country",                                ""),
    ("client.owner_name",    "fact",       "Primary contact name",                         ""),
    ("client.owner_email",   "fact",       "Contact email",                                ""),
    ("client.primary_goal",  "context",    "Main reason for using ClaudeOS",               ""),
    ("client.active_projects","context",   "Current projects (comma-separated)",           ""),
    ("client.ai_use_cases",  "context",    "What agents are used for",                     ""),
    ("client.brand_colors",  "preference", "Primary hex color(s)",                         ""),
    ("client.tone",          "preference", "Communication tone (formal/casual/technical)", ""),
    ("client.language",      "preference", "Preferred language",                           "English"),
    ("client.timezone",      "preference", "e.g. Africa/Lagos",                            ""),
    ("client.avoid",         "preference", "Topics/styles agents should avoid",            ""),
    ("client.sla_tier",      "fact",       "Default ticket priority P1/P2/P3/P4",          "P3"),
]


def seed(namespace: str) -> None:
    with get_db() as conn:
        existing = {
            row["key"]
            for row in conn.execute(
                "SELECT key FROM memory_entries WHERE namespace=? AND archived=0", (namespace,)
            ).fetchall()
        }

        created = 0
        skipped = 0
        for key, category, description, default_value in CLIENT_SCHEMA:
            if key in existing:
                print(f"  skip   {key}")
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO memory_entries
                   (id, namespace, category, key, value, confidence, tags, archived, is_consolidated)
                   VALUES (?,?,?,?,?,?,?,0,0)""",
                (new_id(), namespace, category, key, default_value, 0.9, "onboarding,client-schema"),
            )
            print(f"  create {key}  ({description})")
            created += 1

    print(f"\nDone — {created} created, {skipped} skipped for namespace '{namespace}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed client onboarding schema")
    parser.add_argument("--namespace", required=True, help="Target namespace slug")
    args = parser.parse_args()
    seed(args.namespace)
