"""Skills routes: list the skills installed on this machine, read one, approve or un-approve it.

  GET    /api/v1/skills                 admin, operator  inventory + scan + approval status
  GET    /api/v1/skills/<id>            admin, operator  one skill, with its files and SKILL.md text
  POST   /api/v1/skills/<id>/approve    admin            record "I reviewed this exact content"
  DELETE /api/v1/skills/<id>/approve    admin            take the approval back

Read-only with respect to the skills themselves: nothing here runs or edits a skill. The caller never supplies a path; an id is
matched against the folders core.skill_scan discovers itself (see skill_scan.locate).
"""
import logging
import re

from flask import Blueprint, g, jsonify, request

from core import skill_scan
from core.api.limiter import limiter
from core.auth import audit_log, require_auth, require_role, require_write
from core.config import get_settings
from core.database import get_db

_log = logging.getLogger("claudeos.skills")
skills_bp = Blueprint("skills", __name__, url_prefix="/api/v1")

_ID = re.compile(r"^[0-9a-f]{16}$")
_NOTE_MAX = 500


def _approvals() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT skill_id, fingerprint, verdict, note, approved_by, approved_at FROM skill_approvals").fetchall()
    return {r["skill_id"]: dict(r) for r in rows}


def _bad_id(sid):
    return None if _ID.match(sid or "") else (jsonify({"error": "Invalid skill id"}), 400)


@skills_bp.get("/skills")
@require_auth
@require_role("admin", "operator")
@limiter.limit("30 per minute")
def list_skills():
    skills, roots = skill_scan.inventory(get_settings().SKILL_ROOTS)
    skill_scan.apply_approvals(skills, _approvals())
    for s in skills:          # the list stays small: file lists and notes are in the one-skill view
        s.pop("files", None)
        s.pop("notes", None)
    counts = {"total": len(skills),
              "approved": sum(1 for s in skills if s["status"] == "approved"),
              "changed": sum(1 for s in skills if s["status"] == "changed"),
              "unreviewed": sum(1 for s in skills if s["status"] == "unreviewed"),
              "risky": sum(1 for s in skills if s["verdict"] == "risky"),
              "review": sum(1 for s in skills if s["verdict"] == "review")}
    return jsonify({"skills": skills, "roots": roots, "counts": counts,
                    "note": "The scan looks for common warning signs with simple text patterns. A clean result is not proof that a skill is safe."})


@skills_bp.get("/skills/<sid>")
@require_auth
@require_role("admin", "operator")
@limiter.limit("60 per minute")
def get_skill(sid):
    bad = _bad_id(sid)
    if bad:
        return bad
    found = skill_scan.locate(sid, get_settings().SKILL_ROOTS)
    if not found:
        return jsonify({"error": "Skill not found"}), 404
    skill, folder = found
    skill_scan.apply_approvals([skill], _approvals())
    text, truncated = skill_scan.read_skill_md(folder)
    return jsonify({**skill, "skill_md": text, "skill_md_truncated": truncated})


@skills_bp.post("/skills/<sid>/approve")
@require_auth
@require_role("admin")
@require_write
@limiter.limit("20 per minute")
def approve_skill(sid):
    bad = _bad_id(sid)
    if bad:
        return bad
    body = request.get_json(silent=True) or {}
    found = skill_scan.locate(sid, get_settings().SKILL_ROOTS)
    if not found:
        return jsonify({"error": "Skill not found"}), 404
    skill, _folder = found
    # The owner approves what they looked at. If the skill was edited between looking and clicking, refuse.
    if body.get("fingerprint") != skill["fingerprint"]:
        return jsonify({"error": "This skill changed since you opened it. Reload the page and review it again."}), 409
    if skill["verdict"] == "risky" and body.get("acknowledge_risk") is not True:
        return jsonify({"error": "The scan found serious warning signs. Approving it anyway needs acknowledge_risk: true."}), 422
    note = str(body.get("note") or "").strip()[:_NOTE_MAX]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO skill_approvals(skill_id, name, source, location, fingerprint, verdict, note, approved_by, approved_at) "
            "VALUES (?,?,?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now')) "
            "ON CONFLICT(skill_id) DO UPDATE SET name=excluded.name, source=excluded.source, location=excluded.location, "
            "fingerprint=excluded.fingerprint, verdict=excluded.verdict, note=excluded.note, approved_by=excluded.approved_by, "
            "approved_at=excluded.approved_at",
            (sid, skill["name"], skill["source"], skill["location"], skill["fingerprint"], skill["verdict"], note, g.username),
        )
    audit_log("skill_approved", user_id=g.user_id, username=g.username, ip=request.remote_addr or "",
              detail={"skill": skill["name"], "source": skill["source"], "fingerprint": skill["fingerprint_short"], "verdict": skill["verdict"]})
    return jsonify({"approved": True, "id": sid, "fingerprint": skill["fingerprint"]})


@skills_bp.delete("/skills/<sid>/approve")
@require_auth
@require_role("admin")
@require_write
@limiter.limit("20 per minute")
def revoke_skill_approval(sid):
    bad = _bad_id(sid)
    if bad:
        return bad
    with get_db() as conn:
        row = conn.execute("SELECT name FROM skill_approvals WHERE skill_id = ?", (sid,)).fetchone()
        if not row:
            return jsonify({"error": "This skill is not approved"}), 404
        conn.execute("DELETE FROM skill_approvals WHERE skill_id = ?", (sid,))
    audit_log("skill_approval_revoked", user_id=g.user_id, username=g.username, ip=request.remote_addr or "", detail={"skill": row["name"]})
    return jsonify({"approved": False, "id": sid})
