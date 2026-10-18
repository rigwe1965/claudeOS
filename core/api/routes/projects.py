"""Client Vault REST API — namespaces + projects."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from core.auth import require_auth, require_role, require_write, effective_namespace, can_access_namespace
require_api_key = require_auth  # alias — all existing @require_api_key decorators now use require_auth

projects_bp = Blueprint("projects", __name__, url_prefix="/api/v1")


# ── Namespaces ────────────────────────────────────────────────────────────────

@projects_bp.get("/namespaces")
@require_api_key
def list_namespaces():
    from vault.manager import list_namespaces as _list, get_namespace_by_slug
    ns_type = request.args.get("type")
    enabled_only = request.args.get("enabled", "true").lower() == "true"
    scoped_ns = effective_namespace()  # None for admin/operator, slug for client/viewer
    if scoped_ns:
        ns = get_namespace_by_slug(scoped_ns)
        namespaces = [ns] if ns else []
    else:
        namespaces = _list(ns_type=ns_type, enabled_only=enabled_only)
    return jsonify([_ns_dict(n) for n in namespaces])


@projects_bp.post("/namespaces")
@require_api_key
@require_role("admin", "operator")
def create_namespace():
    from vault.manager import create_namespace as _create
    from vault.schemas import NamespaceCreate
    body = request.get_json(silent=True) or {}
    try:
        data = NamespaceCreate(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422
    try:
        ns = _create(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_ns_dict(ns)), 201


@projects_bp.get("/namespaces/<slug>")
@require_api_key
def get_namespace(slug: str):
    if not can_access_namespace(slug):
        return jsonify({"error": "Namespace not found"}), 404
    from vault.manager import get_namespace_by_slug
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    return jsonify(_ns_dict(ns))


@projects_bp.patch("/namespaces/<slug>")
@require_api_key
@require_role("admin", "operator")
def update_namespace(slug: str):
    from vault.manager import get_namespace_by_slug, update_namespace as _update
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    updates = request.get_json(silent=True) or {}
    from vault.schemas import validate_brand_fields
    meta = updates.get("metadata", {})
    if not isinstance(meta, dict):
        return jsonify({"error": "metadata must be an object"}), 422
    err = validate_brand_fields(updates.get("color"), updates.get("icon"), metadata=meta)
    if err:
        return jsonify({"error": err}), 422
    updated = _update(ns.id, updates)
    return jsonify(_ns_dict(updated))


@projects_bp.delete("/namespaces/<slug>")
@require_api_key
@require_role("admin", "operator")
def delete_namespace(slug: str):
    from vault.manager import get_namespace_by_slug, delete_namespace as _delete
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    _delete(ns.id)
    return jsonify({"deleted": slug})


@projects_bp.get("/namespaces/<slug>/workspace")
@require_api_key
def workspace_stats(slug: str):
    if not can_access_namespace(slug):
        return jsonify({"error": "Namespace not found"}), 404
    from vault.manager import get_workspace_stats, get_namespace_by_slug
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    stats = get_workspace_stats(slug)
    return jsonify({"namespace": slug, "workspace": stats})


@projects_bp.get("/namespaces/<slug>/context")
@require_api_key
def list_context(slug: str):
    if not can_access_namespace(slug):
        return jsonify({"error": "Namespace not found"}), 404
    from vault.manager import list_context_files, get_namespace_by_slug
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    files = list_context_files(slug)
    return jsonify({"namespace": slug, "files": files})


@projects_bp.post("/namespaces/<slug>/context")
@require_api_key
@require_role("admin", "operator")
def write_context(slug: str):
    if not can_access_namespace(slug):
        return jsonify({"error": "Namespace not found"}), 404
    from vault.manager import write_context as _write, get_namespace_by_slug
    ns = get_namespace_by_slug(slug)
    if not ns:
        return jsonify({"error": "Namespace not found"}), 404
    body = request.get_json(silent=True) or {}
    filename = body.get("filename")
    content = body.get("content", "")
    if not filename:
        return jsonify({"error": "filename required"}), 400
    try:
        path = _write(slug, filename, content)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"written": filename}), 201


# ── Projects ──────────────────────────────────────────────────────────────────

@projects_bp.get("/projects")
@require_api_key
def list_projects():
    from vault.manager import list_projects as _list, get_namespace_by_slug
    namespace_slug = effective_namespace(request.args.get("namespace"))  # clients always scoped
    status = request.args.get("status")
    namespace_id = None
    if namespace_slug:
        ns = get_namespace_by_slug(namespace_slug)
        if not ns:
            return jsonify({"error": "Namespace not found"}), 404
        namespace_id = ns.id
    projects = _list(namespace_id=namespace_id, status=status)
    return jsonify([_proj_dict(p) for p in projects])


@projects_bp.post("/projects")
@require_api_key
@require_role("admin", "operator")
def create_project():
    from vault.manager import create_project as _create
    from vault.schemas import ProjectCreate
    body = request.get_json(silent=True) or {}
    try:
        data = ProjectCreate(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422
    try:
        proj = _create(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_proj_dict(proj)), 201


@projects_bp.get("/projects/<proj_id>")
@require_api_key
def get_project(proj_id: str):
    from vault.manager import get_project as _get
    proj = _get(proj_id)
    if not proj or not _project_visible(proj):
        return jsonify({"error": "Project not found"}), 404
    return jsonify(_proj_dict(proj))


@projects_bp.patch("/projects/<proj_id>")
@require_api_key
@require_role("admin", "operator")
def update_project(proj_id: str):
    from vault.manager import update_project as _update
    updates = request.get_json(silent=True) or {}
    proj = _update(proj_id, updates)
    if not proj:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(_proj_dict(proj))


@projects_bp.delete("/projects/<proj_id>")
@require_api_key
@require_role("admin", "operator")
def delete_project(proj_id: str):
    from vault.manager import delete_project as _delete
    if not _delete(proj_id):
        return jsonify({"error": "Project not found"}), 404
    return jsonify({"deleted": proj_id})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _project_visible(proj) -> bool:
    from vault.manager import get_namespace
    ns = get_namespace(proj.namespace_id)
    return bool(ns) and can_access_namespace(ns.slug)


def _ns_dict(ns) -> dict:
    return {
        "id": ns.id,
        "slug": ns.slug,
        "display_name": ns.display_name,
        "description": ns.description,
        "type": ns.type,
        "color": ns.color,
        "icon": ns.icon,
        "metadata": ns.metadata if isinstance(ns.metadata, dict) else {},
        "enabled": ns.enabled,
        "created_at": ns.created_at,
    }


def _proj_dict(p) -> dict:
    return {
        "id": p.id,
        "namespace_id": p.namespace_id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "status": p.status,
        "priority": p.priority,
        "tech_stack": p.tech_stack,
        "path": p.path,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
