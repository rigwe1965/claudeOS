"""Delete the old empty faiyke-ai namespace.
Run from ClaudeOS root: python scripts/delete_faiyke_ai.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db

with get_db() as conn:
    row = conn.execute("SELECT id, slug, display_name FROM namespaces WHERE slug = 'faiyke-ai'").fetchone()

if not row:
    print("[SKIP] faiyke-ai namespace not found — already deleted.")
    sys.exit(0)

d = dict(row)
print(f"Found: {d['display_name']} (slug={d['slug']}, id={d['id']})")

# Confirm no projects attached
with get_db() as conn:
    proj_count = conn.execute("SELECT COUNT(*) FROM projects WHERE namespace_id = ?", (d['id'],)).fetchone()[0]

if proj_count > 0:
    print(f"[ABORT] {proj_count} project(s) still attached. Move them first.")
    sys.exit(1)

with get_db() as conn:
    conn.execute("DELETE FROM namespaces WHERE slug = 'faiyke-ai'")

print("[OK]   Deleted faiyke-ai namespace.")
print("Refresh dashboard → Client Vault → Namespaces.")
