"""Client Vault Manager — namespace + project CRUD with workspace isolation.

Every namespace gets a workspace dir:
  vault/workspaces/{slug}/context/
  vault/workspaces/{slug}/memory/
  vault/workspaces/{slug}/outputs/

Namespace isolation rule: agents receive only their namespace context.
Cross-namespace reads are blocked here — never query another namespace's path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from core.database import get_db
from core.utils import new_id, utcnow_str
from vault.schemas import Namespace, NamespaceCreate, Project, ProjectCreate

logger = logging.getLogger("claudeos.vault.manager")

VAULT_ROOT = Path(__file__).parent / "workspaces"
WORKSPACE_SUBDIRS = ("context", "memory", "outputs")


# ── Namespace ─────────────────────────────────────────────────────────────────

def create_namespace(data: NamespaceCreate) -> Namespace:
    ns_id = new_id()
    now = utcnow_str()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO namespaces
               (id, slug, display_name, description, type, color, icon,
                parent_id, metadata, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                ns_id, data.slug, data.display_name, data.description,
                data.type, data.color, data.icon, data.parent_id,
                json.dumps(data.metadata), now,
            ),
        )
    _provision_workspace(data.slug)
    logger.info("Created namespace: %s", data.slug)
    return get_namespace_by_slug(data.slug)


def get_namespace(ns_id: str) -> Optional[Namespace]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM namespaces WHERE id = ?", (ns_id,)).fetchone()
    return _row_to_namespace(row) if row else None


def get_namespace_by_slug(slug: str) -> Optional[Namespace]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM namespaces WHERE slug = ?", (slug,)).fetchone()
    return _row_to_namespace(row) if row else None


def list_namespaces(ns_type: Optional[str] = None, enabled_only: bool = True) -> list[Namespace]:
    conditions, params = [], []
    if enabled_only:
        conditions.append("enabled = 1")
    if ns_type:
        conditions.append("type = ?")
        params.append(ns_type)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM namespaces {where} ORDER BY display_name", params
        ).fetchall()
    return [_row_to_namespace(r) for r in rows]


def update_namespace(ns_id: str, updates: dict) -> Optional[Namespace]:
    allowed = {"display_name", "description", "color", "icon", "metadata", "enabled"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_namespace(ns_id)
    if "metadata" in fields and isinstance(fields["metadata"], dict):
        fields["metadata"] = json.dumps(fields["metadata"])
    set_clause = ", ".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [ns_id]
    with get_db() as conn:
        conn.execute(f"UPDATE namespaces SET {set_clause} WHERE id=?", params)
    return get_namespace(ns_id)


def delete_namespace(ns_id: str) -> bool:
    ns = get_namespace(ns_id)
    if not ns:
        return False
    with get_db() as conn:
        # Soft-delete: disable rather than destroy
        conn.execute("UPDATE namespaces SET enabled=0 WHERE id=?", (ns_id,))
    logger.info("Disabled namespace: %s", ns.slug)
    return True


# ── Projects ──────────────────────────────────────────────────────────────────

def create_project(data: ProjectCreate) -> Project:
    proj_id = new_id()
    now = utcnow_str()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO projects
               (id, namespace_id, name, slug, description, status, priority,
                tech_stack, path, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                proj_id, data.namespace_id, data.name, data.slug,
                data.description, data.status, data.priority,
                json.dumps(data.tech_stack), data.path,
                json.dumps(data.metadata), now, now,
            ),
        )
    logger.info("Created project: %s/%s", data.namespace_id, data.slug)
    return get_project(proj_id)


def get_project(proj_id: str) -> Optional[Project]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (proj_id,)).fetchone()
    return _row_to_project(row) if row else None


def list_projects(
    namespace_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Project]:
    conditions, params = [], []
    if namespace_id:
        conditions.append("namespace_id = ?")
        params.append(namespace_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM projects {where} ORDER BY priority, name", params
        ).fetchall()
    return [_row_to_project(r) for r in rows]


def update_project(proj_id: str, updates: dict) -> Optional[Project]:
    allowed = {"name", "description", "status", "priority", "tech_stack", "path", "metadata"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_project(proj_id)
    for list_field in ("tech_stack", "metadata"):
        if list_field in fields and not isinstance(fields[list_field], str):
            fields[list_field] = json.dumps(fields[list_field])
    fields["updated_at"] = utcnow_str()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [proj_id]
    with get_db() as conn:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id=?", params)
    return get_project(proj_id)


def delete_project(proj_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id=?", (proj_id,))
    return cursor.rowcount > 0


# ── Workspace file isolation ──────────────────────────────────────────────────

def workspace_path(slug: str, subdir: str = "") -> Path:
    """Return path to namespace workspace dir (or subdir). Never cross namespaces."""
    base = VAULT_ROOT / slug
    if subdir:
        return base / subdir
    return base


def write_context(slug: str, filename: str, content: str) -> Path:
    """Write a context file into the namespace workspace. Enforces slug isolation."""
    _validate_slug(slug)
    _validate_filename(filename)
    path = workspace_path(slug, "context") / filename
    # Resolve and confirm path stays inside the context dir (defence-in-depth)
    context_dir = (VAULT_ROOT / slug / "context").resolve()
    resolved = path.resolve()
    if not str(resolved).startswith(str(context_dir)):
        raise ValueError(f"Invalid filename — path escapes workspace: {filename!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_context(slug: str, filename: str) -> Optional[str]:
    _validate_slug(slug)
    path = workspace_path(slug, "context") / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def list_context_files(slug: str) -> list[str]:
    _validate_slug(slug)
    ctx_dir = workspace_path(slug, "context")
    if not ctx_dir.exists():
        return []
    return [f.name for f in sorted(ctx_dir.iterdir()) if f.is_file()]


def get_workspace_stats(slug: str) -> dict:
    """Return file counts and sizes for a namespace workspace (shallow scan)."""
    _validate_slug(slug)
    stats = {}
    for subdir in WORKSPACE_SUBDIRS:
        d = workspace_path(slug, subdir)
        if d.exists():
            file_list = [f for f in d.iterdir() if f.is_file()]
            stats[subdir] = {
                "file_count": len(file_list),
                "size_bytes": sum(f.stat().st_size for f in file_list),
            }
        else:
            stats[subdir] = {"file_count": 0, "size_bytes": 0}
    return stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _provision_workspace(slug: str) -> None:
    for subdir in WORKSPACE_SUBDIRS:
        (VAULT_ROOT / slug / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("Provisioned workspace: vault/workspaces/%s/", slug)


def _validate_slug(slug: str) -> None:
    """Prevent path traversal. Slug must be alphanumeric + hyphens only."""
    import re
    if not re.match(r'^[a-z0-9][a-z0-9\-]*$', slug):
        raise ValueError(f"Invalid namespace slug: {slug!r}")


def _validate_filename(filename: str) -> None:
    """Prevent path traversal in context filenames. Allow safe chars only."""
    import re
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError(f"Invalid filename: {filename!r}")
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$', filename):
        raise ValueError(f"Filename contains disallowed characters: {filename!r}")


def _row_to_namespace(row) -> Namespace:
    d = dict(row)
    d["metadata"] = json.loads(d.get("metadata") or "{}")
    d["enabled"] = bool(d.get("enabled", 1))
    return Namespace(**d)


def _row_to_project(row) -> Project:
    d = dict(row)
    d["tech_stack"] = json.loads(d.get("tech_stack") or "[]")
    d["metadata"] = json.loads(d.get("metadata") or "{}")
    return Project(**d)
