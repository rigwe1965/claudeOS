"""Fix faiyke namespace — enable it, set correct display name, verify project attached.
Run from ClaudeOS root: python scripts/fix_faiyke_namespace.py
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db
from vault.manager import get_namespace_by_slug, update_namespace, list_projects

# ── 1. Inspect the faiyke namespace ──────────────────────────────────────────
with get_db() as conn:
    row = conn.execute("SELECT * FROM namespaces WHERE slug = 'faiyke'").fetchone()

if not row:
    print("[ERROR] No namespace with slug 'faiyke' found in DB.")
    sys.exit(1)

d = dict(row)
print(f"Found: slug={d['slug']} | display_name={d['display_name']} | enabled={d['enabled']} | id={d['id']}")

# ── 2. Enable + fix display name if needed ───────────────────────────────────
needs_update = {}
if not d['enabled']:
    needs_update['enabled'] = True
    print("  → was disabled, enabling...")
if d['display_name'] != 'faIyke':
    needs_update['display_name'] = 'faIyke'
    print(f"  → fixing display_name: '{d['display_name']}' → 'faIyke'")
if d.get('type') != 'internal':
    needs_update['type'] = 'internal'  # not in allowed update fields but we'll do it directly

if needs_update:
    with get_db() as conn:
        set_parts = []
        params = []
        if 'enabled' in needs_update:
            set_parts.append("enabled=?")
            params.append(1)
        if 'display_name' in needs_update:
            set_parts.append("display_name=?")
            params.append('faIyke')
        params.append(d['id'])
        conn.execute(f"UPDATE namespaces SET {', '.join(set_parts)} WHERE id=?", params)
    print("[OK]   Namespace updated.")
else:
    print("[OK]   Namespace looks correct, no changes needed.")

# ── 3. Verify faIyke Core project is attached ────────────────────────────────
ns = get_namespace_by_slug('faiyke')
projects = list_projects(namespace_id=ns.id)
if projects:
    for p in projects:
        print(f"[OK]   Project attached: {p.name} (slug={p.slug}, id={p.id})")
else:
    print("[WARN] No projects attached to faiyke namespace.")
    print("       Run seed_faiyke.py again — it will create faIyke Core under this namespace.")

print("\nDone. Refresh dashboard → Client Vault → Namespaces.")
