"""Dump all namespaces from DB to diagnose missing faiyke.
Run from ClaudeOS root: python scripts/debug_namespaces.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db

with get_db() as conn:
    rows = conn.execute("SELECT id, slug, display_name, type, enabled, color, icon FROM namespaces ORDER BY display_name").fetchall()

print(f"{'SLUG':<20} {'DISPLAY NAME':<20} {'TYPE':<12} {'ENABLED':<8} {'COLOR':<10} {'ICON'}")
print("-" * 80)
for r in rows:
    d = dict(r)
    print(f"{d['slug']:<20} {d['display_name']:<20} {d['type']:<12} {str(d['enabled']):<8} {d['color']:<10} {d['icon']}")
