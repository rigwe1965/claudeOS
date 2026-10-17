"""Tickets REST API routes."""
from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from core.auth import require_auth, effective_namespace
from core.database import get_db
from core.utils import new_id, utcnow, utcnow_str
from datetime import timedelta

tickets_bp = Blueprint("tickets", __name__, url_prefix="/api/v1/tickets")
logger = logging.getLogger("claudeos.tickets")

SLA_HOURS = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
VALID_STATUSES    = {"open", "assigned", "work_in_progress", "completed", "closed"}
VALID_CATEGORIES  = {"bug", "billing", "access", "feature", "other"}
VALID_SLA_TIERS   = set(SLA_HOURS.keys())
STAFF_ROLES       = {"admin", "operator", "staff"}

# Forward-only transitions allowed for non-admin users (staff/assignees).
# Admin and operator can set any status freely.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open":             {"assigned", "work_in_progress"},
    "assigned":         {"work_in_progress"},
    "work_in_progress": {"completed", "closed"},
    "completed":        {"closed"},
    "closed":           set(),
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_assignees(ticket_id: str, conn=None) -> list[str]:
    """Return list of usernames assigned to this ticket."""
    def _query(c):
        rows = c.execute(
            "SELECT username FROM ticket_assignees WHERE ticket_id = ? ORDER BY assigned_at ASC",
            (ticket_id,),
        ).fetchall()
        return [r["username"] for r in rows]

    if conn is not None:
        return _query(conn)
    with get_db() as c:
        return _query(c)


def _ticket_dict(row, assignees: list[str] | None = None) -> dict:
    return {
        "id":          row["id"],
        "namespace":   row["namespace"],
        "created_by":  row["created_by"],
        "title":       row["title"],
        "description": row["description"],
        "status":      row["status"],
        "category":    row["category"],
        "priority":    row["priority"],
        "sla_tier":    row["sla_tier"],
        "sla_due_at":  row["sla_due_at"],
        "assigned_to": row["assigned_to"],   # primary assignee (first one)
        "assignees":   assignees if assignees is not None else [],
        "resolution":  row["resolution"],
        "created_at":  row["created_at"],
        "updated_at":  row["updated_at"],
    }


def _can_access_ticket(ticket: dict) -> bool:
    """True if current user may read this ticket."""
    if g.user_role in ("admin", "operator"):
        return True
    if ticket["created_by"] == g.username:
        return True
    if ticket.get("assigned_to") == g.username:
        return True
    if g.username in ticket.get("assignees", []):
        return True
    return False


def _get_ticket_by_id(ticket_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            return None
        assignees = _get_assignees(ticket_id, conn)
    return _ticket_dict(row, assignees)


def _is_assignee(ticket_id: str) -> bool:
    """True if the current user is in this ticket's assignees list."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM ticket_assignees WHERE ticket_id = ? AND username = ? LIMIT 1",
            (ticket_id, g.username),
        ).fetchone()
    return row is not None


# ── Bulk delete ────────────────────────────────────────────────────────────────

@tickets_bp.delete("/bulk")
@require_auth
def bulk_delete_tickets():
    if g.user_role != "admin":
        return jsonify({"error": "Admin only"}), 403
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids list required"}), 422
    placeholders = ",".join("?" * len(ids))
    with get_db() as conn:
        existing = conn.execute(
            f"SELECT id FROM tickets WHERE id IN ({placeholders})", ids
        ).fetchall()
        deleted = [r["id"] for r in existing]
        if deleted:
            ph2 = ",".join("?" * len(deleted))
            conn.execute(f"DELETE FROM tickets WHERE id IN ({ph2})", deleted)
    return jsonify({"deleted": deleted, "failed": [i for i in ids if i not in set(deleted)], "count": len(deleted)})


# ── List ───────────────────────────────────────────────────────────────────────

@tickets_bp.get("")
@require_auth
def list_tickets():
    role     = g.user_role
    username = g.username

    status_filter   = request.args.get("status")
    priority_filter = request.args.get("priority")
    ns_filter       = request.args.get("namespace")
    assigned_filter = request.args.get("assigned_to")
    since           = request.args.get("since")   # ISO datetime e.g. "2026-01-01T00:00:00"
    until           = request.args.get("until")
    limit  = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    conditions: list[str] = []
    params: list = []

    if role in ("client", "viewer"):
        ns = effective_namespace()
        conditions.append("namespace = ?")
        params.append(ns)
        conditions.append("created_by = ?")
        params.append(username)
    elif role == "staff":
        # Staff see tickets where they appear in ticket_assignees
        conditions.append(
            "id IN (SELECT ticket_id FROM ticket_assignees WHERE username = ?)"
        )
        params.append(username)
    else:
        # admin/operator — full access with optional filters
        if ns_filter:
            conditions.append("namespace = ?")
            params.append(ns_filter)
        if assigned_filter:
            target = username if assigned_filter == "me" else assigned_filter
            conditions.append(
                "id IN (SELECT ticket_id FROM ticket_assignees WHERE username = ?)"
            )
            params.append(target)

    if status_filter and status_filter in VALID_STATUSES:
        conditions.append("status = ?")
        params.append(status_filter)
    if priority_filter:
        try:
            conditions.append("priority = ?")
            params.append(int(priority_filter))
        except ValueError:
            pass
    if since:
        conditions.append("created_at >= ?")
        params.append(since)
    if until:
        conditions.append("created_at <= ?")
        params.append(until)

    where  = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql    = f"SELECT * FROM tickets {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        if not rows:
            return jsonify([])
        # Batch-fetch all assignees in one query instead of N+1
        ids = [r["id"] for r in rows]
        ph = ",".join("?" * len(ids))
        asgn_rows = conn.execute(
            f"SELECT ticket_id, username FROM ticket_assignees WHERE ticket_id IN ({ph}) ORDER BY assigned_at ASC",
            ids,
        ).fetchall()
        asgn_map: dict[str, list[str]] = {}
        for ar in asgn_rows:
            asgn_map.setdefault(ar["ticket_id"], []).append(ar["username"])
        result = [_ticket_dict(row, asgn_map.get(row["id"], [])) for row in rows]

    return jsonify(result)


# ── Create ─────────────────────────────────────────────────────────────────────

@tickets_bp.post("")
@require_auth
def create_ticket():
    body        = request.get_json(silent=True) or {}
    title       = (body.get("title") or "").strip()
    description = (body.get("description") or "").strip()
    category    = body.get("category", "other")
    priority    = body.get("priority", 3)

    if not title or not description:
        return jsonify({"error": "title and description required"}), 422
    if category not in VALID_CATEGORIES:
        category = "other"
    try:
        priority = int(priority)
        if priority not in (1, 2, 3, 4):
            priority = 3
    except (ValueError, TypeError):
        priority = 3

    ns = effective_namespace(body.get("namespace")) or g.user_namespace or "global"

    ticket_id = new_id()
    now       = utcnow_str()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO tickets
               (id, namespace, created_by, title, description, status, category, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
            (ticket_id, ns, g.username, title, description, category, priority, now, now),
        )

    # Notify any pre-assigned staff (not common on create, but future-proof)
    _maybe_notify_assignment(ticket_id, title, g.username, ns, priority, [])

    return jsonify({
        "id": ticket_id, "namespace": ns, "created_by": g.username,
        "title": title, "description": description, "status": "open",
        "category": category, "priority": priority, "sla_tier": None,
        "sla_due_at": None, "assigned_to": None, "assignees": [],
        "resolution": None, "created_at": now, "updated_at": now,
    }), 201


# ── Get single ─────────────────────────────────────────────────────────────────

@tickets_bp.get("/<ticket_id>")
@require_auth
def get_ticket(ticket_id: str):
    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if not _can_access_ticket(ticket):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(ticket)


# ── Update ─────────────────────────────────────────────────────────────────────

@tickets_bp.patch("/<ticket_id>")
@require_auth
def update_ticket(ticket_id: str):
    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if not _can_access_ticket(ticket):
        return jsonify({"error": "Access denied"}), 403

    body    = request.get_json(silent=True) or {}
    role    = g.user_role
    sets: list[str] = []
    params: list    = []

    if role in ("client", "viewer"):
        if ticket["status"] not in ("open", "assigned"):
            return jsonify({"error": "Cannot edit ticket in current status"}), 403
        if "description" in body:
            sets.append("description = ?")
            params.append(body["description"])

    elif role == "staff":
        # Staff/assignee: forward-only status transitions + resolution
        if "status" in body:
            new_status = body["status"]
            current    = ticket["status"]
            allowed    = ALLOWED_TRANSITIONS.get(current, set())
            is_assignee = g.username in ticket.get("assignees", [])
            if not is_assignee:
                return jsonify({"error": "You are not assigned to this ticket"}), 403
            if new_status not in allowed:
                return jsonify({
                    "error": f"Cannot transition from '{current}' to '{new_status}'",
                    "allowed": sorted(allowed),
                }), 422
            sets.append("status = ?")
            params.append(new_status)
        if "resolution" in body:
            sets.append("resolution = ?")
            params.append(body["resolution"])

    else:
        # admin/operator: all fields
        if "title" in body:
            sets.append("title = ?")
            params.append(body["title"])
        if "description" in body:
            sets.append("description = ?")
            params.append(body["description"])
        if "status" in body and body["status"] in VALID_STATUSES:
            sets.append("status = ?")
            params.append(body["status"])
        if "category" in body and body["category"] in VALID_CATEGORIES:
            sets.append("category = ?")
            params.append(body["category"])
        if "priority" in body:
            try:
                p = int(body["priority"])
                if p in (1, 2, 3, 4):
                    sets.append("priority = ?")
                    params.append(p)
            except (ValueError, TypeError):
                pass
        if "assigned_to" in body:
            sets.append("assigned_to = ?")
            params.append(body["assigned_to"] or None)
        if "resolution" in body:
            sets.append("resolution = ?")
            params.append(body["resolution"])
        if "sla_tier" in body:
            tier = body["sla_tier"]
            if tier in VALID_SLA_TIERS:
                due = (utcnow() + timedelta(hours=SLA_HOURS[tier])).strftime("%Y-%m-%d %H:%M:%S")
                sets.append("sla_tier = ?")
                params.append(tier)
                sets.append("sla_due_at = ?")
                params.append(due)
            elif tier is None or tier == "":
                sets.append("sla_tier = ?")
                params.append(None)
                sets.append("sla_due_at = ?")
                params.append(None)

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 422

    now = utcnow_str()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(ticket_id)

    with get_db() as conn:
        conn.execute(f"UPDATE tickets SET {', '.join(sets)} WHERE id = ?", params)

    updated = _get_ticket_by_id(ticket_id)

    # Email creator when ticket reaches completed or closed
    new_status = body.get("status") if body else None
    if new_status in ("completed", "closed") and updated:
        _maybe_notify_resolution(
            ticket=updated,
            resolved_by=g.username,
            resolution=body.get("resolution", ""),
        )

    # Email new assignees when assigned_to changes
    if "assigned_to" in body and body["assigned_to"] and updated:
        _maybe_notify_assignment(
            ticket_id=ticket_id,
            title=updated["title"],
            creator=updated["created_by"],
            namespace=updated["namespace"],
            priority=updated["priority"],
            new_assignees=[body["assigned_to"]],
        )

    return jsonify(updated)


# ── Self-assign ────────────────────────────────────────────────────────────────

@tickets_bp.post("/<ticket_id>/assign-me")
@require_auth
def assign_me(ticket_id: str):
    """Any staff/admin/operator can claim a ticket for themselves."""
    if g.user_role not in STAFF_ROLES:
        return jsonify({"error": "Staff or admin role required"}), 403

    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] == "closed":
        return jsonify({"error": "Cannot assign a closed ticket"}), 422

    now = utcnow_str()
    with get_db() as conn:
        # Add to assignees (ignore if already there)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO ticket_assignees (id, ticket_id, username, assigned_at, assigned_by) VALUES (?, ?, ?, ?, ?)",
                (new_id(), ticket_id, g.username, now, g.username),
            )
        except Exception as e:
            logger.warning("assign_me insert failed for ticket %s: %s", ticket_id, e)

        # Set primary assigned_to if unset
        if not ticket.get("assigned_to"):
            conn.execute(
                "UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (g.username, now, ticket_id),
            )

        # Auto-advance status: open → assigned
        if ticket["status"] == "open":
            conn.execute(
                "UPDATE tickets SET status = 'assigned', updated_at = ? WHERE id = ?",
                (now, ticket_id),
            )

    return jsonify(_get_ticket_by_id(ticket_id))


# ── Multi-assignee management ──────────────────────────────────────────────────

@tickets_bp.get("/<ticket_id>/assignees")
@require_auth
def list_assignees(ticket_id: str):
    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if not _can_access_ticket(ticket):
        return jsonify({"error": "Access denied"}), 403
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM ticket_assignees WHERE ticket_id = ? ORDER BY assigned_at ASC",
            (ticket_id,),
        ).fetchall()
    return jsonify([{
        "username":    r["username"],
        "assigned_at": r["assigned_at"],
        "assigned_by": r["assigned_by"],
    } for r in rows])


@tickets_bp.post("/<ticket_id>/assignees")
@require_auth
def add_assignees(ticket_id: str):
    """Admin/operator assigns one or more users to a ticket."""
    if g.user_role not in ("admin", "operator"):
        return jsonify({"error": "Admin or operator required"}), 403

    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] == "closed":
        return jsonify({"error": "Cannot assign to a closed ticket"}), 422

    body      = request.get_json(silent=True) or {}
    usernames = body.get("usernames") or []
    if isinstance(usernames, str):
        usernames = [usernames]
    usernames = [u.strip() for u in usernames if u and u.strip()]
    if not usernames:
        return jsonify({"error": "usernames list required"}), 422

    now   = utcnow_str()
    added = []
    with get_db() as conn:
        # Batch-verify all usernames in one query
        ph = ",".join("?" * len(usernames))
        valid_rows = conn.execute(
            f"SELECT username FROM users WHERE username IN ({ph}) AND is_active = 1",
            usernames,
        ).fetchall()
        valid_set = {r["username"] for r in valid_rows}
        for uname in usernames:
            if uname not in valid_set:
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO ticket_assignees (id, ticket_id, username, assigned_at, assigned_by) VALUES (?, ?, ?, ?, ?)",
                    (new_id(), ticket_id, uname, now, g.username),
                )
                added.append(uname)
            except Exception as e:
                logger.warning("Failed to insert assignee %s for ticket %s: %s", uname, ticket_id, e)

        # Set primary assigned_to if unset and we added someone
        if added and not ticket.get("assigned_to"):
            conn.execute(
                "UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (added[0], now, ticket_id),
            )
        # Auto-advance status: open → assigned
        if added and ticket["status"] == "open":
            conn.execute(
                "UPDATE tickets SET status = 'assigned', updated_at = ? WHERE id = ?",
                (now, ticket_id),
            )

    return jsonify({"added": added, "ticket": _get_ticket_by_id(ticket_id)})


@tickets_bp.delete("/<ticket_id>/assignees/<username>")
@require_auth
def remove_assignee(ticket_id: str, username: str):
    """Admin/operator removes a specific assignee."""
    if g.user_role not in ("admin", "operator"):
        return jsonify({"error": "Admin or operator required"}), 403

    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    now = utcnow_str()
    with get_db() as conn:
        conn.execute(
            "DELETE FROM ticket_assignees WHERE ticket_id = ? AND username = ?",
            (ticket_id, username),
        )
        # If primary assigned_to was this user, reset to next assignee or null
        if ticket.get("assigned_to") == username:
            remaining = conn.execute(
                "SELECT username FROM ticket_assignees WHERE ticket_id = ? ORDER BY assigned_at ASC LIMIT 1",
                (ticket_id,),
            ).fetchone()
            new_primary = remaining["username"] if remaining else None
            conn.execute(
                "UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (new_primary, now, ticket_id),
            )

    return jsonify({"removed": username, "ticket": _get_ticket_by_id(ticket_id)})


# ── Delete ─────────────────────────────────────────────────────────────────────

@tickets_bp.delete("/<ticket_id>")
@require_auth
def delete_ticket(ticket_id: str):
    if g.user_role != "admin":
        return jsonify({"error": "Admin only"}), 403
    with get_db() as conn:
        row = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            return jsonify({"error": "Ticket not found"}), 404
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    return jsonify({"deleted": ticket_id})


# ── Comments ───────────────────────────────────────────────────────────────────

@tickets_bp.get("/<ticket_id>/comments")
@require_auth
def list_comments(ticket_id: str):
    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if not _can_access_ticket(ticket):
        return jsonify({"error": "Access denied"}), 403
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM ticket_comments WHERE ticket_id = ? ORDER BY created_at ASC",
            (ticket_id,),
        ).fetchall()
    return jsonify([{
        "id": r["id"], "ticket_id": r["ticket_id"],
        "author": r["author"], "body": r["body"], "created_at": r["created_at"],
    } for r in rows])


@tickets_bp.post("/<ticket_id>/comments")
@require_auth
def add_comment(ticket_id: str):
    ticket = _get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if not _can_access_ticket(ticket):
        return jsonify({"error": "Access denied"}), 403

    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "body required"}), 422

    cid = new_id()
    now = utcnow_str()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ticket_comments (id, ticket_id, author, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (cid, ticket_id, g.username, body, now),
        )
    return jsonify({"id": cid, "ticket_id": ticket_id, "author": g.username, "body": body, "created_at": now}), 201


# ── Stats ──────────────────────────────────────────────────────────────────────

@tickets_bp.get("/stats")
@require_auth
def ticket_stats():
    if g.user_role not in ("admin", "operator"):
        return jsonify({"error": "Insufficient permissions"}), 403

    now_str = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        by_status   = conn.execute("SELECT status, COUNT(*) as cnt FROM tickets GROUP BY status").fetchall()
        by_priority = conn.execute("SELECT priority, COUNT(*) as cnt FROM tickets GROUP BY priority").fetchall()
        # Merge sla_breached + unassigned_open into one pass
        agg = conn.execute(
            """SELECT
                SUM(CASE WHEN sla_due_at IS NOT NULL AND sla_due_at < ? AND status NOT IN ('completed','closed') THEN 1 ELSE 0 END) AS sla_breached,
                SUM(CASE WHEN assigned_to IS NULL AND status NOT IN ('completed','closed') THEN 1 ELSE 0 END) AS unassigned
               FROM tickets""",
            (now_str,),
        ).fetchone()
        by_ns = conn.execute(
            "SELECT namespace, COUNT(*) as cnt FROM tickets GROUP BY namespace ORDER BY cnt DESC"
        ).fetchall()

    return jsonify({
        "by_status":       {r["status"]: r["cnt"] for r in by_status},
        "by_priority":     {r["priority"]: r["cnt"] for r in by_priority},
        "sla_breached":    agg["sla_breached"] or 0,
        "by_namespace":    {r["namespace"]: r["cnt"] for r in by_ns},
        "unassigned_open": agg["unassigned"] or 0,
    })


# ── Assignable staff ───────────────────────────────────────────────────────────

@tickets_bp.get("/assignable-staff")
@require_auth
def assignable_staff():
    if g.user_role not in ("admin", "operator"):
        return jsonify({"error": "Insufficient permissions"}), 403
    with get_db() as conn:
        rows = conn.execute(
            "SELECT username, role, namespace FROM users WHERE role IN ('admin','operator','staff') AND is_active = 1 ORDER BY username",
        ).fetchall()
    return jsonify([{"username": r["username"], "role": r["role"], "namespace": r["namespace"]} for r in rows])


# ── Notification helpers ───────────────────────────────────────────────────────

def _get_user_email(username: str) -> str | None:
    """Fetch email for a username. Returns None if not found or no email."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
        return row["email"] if row and row["email"] else None
    except Exception:
        return None


def _maybe_notify_assignment(
    ticket_id: str,
    title: str,
    creator: str,
    namespace: str,
    priority: int,
    new_assignees: list[str],
) -> None:
    """Fire-and-forget email to each new assignee."""
    try:
        from core.notifications import notify_ticket_created
        for assignee in new_assignees:
            if assignee == creator:
                continue  # skip self-assignment notification
            email = _get_user_email(assignee)
            if email:
                notify_ticket_created(
                    assignee_email=email,
                    ticket_id=ticket_id,
                    title=title,
                    creator=creator,
                    namespace=namespace,
                    priority=priority,
                )
    except Exception as e:
        logger.warning("Assignment notification failed: %s", e)


def _maybe_notify_resolution(ticket: dict, resolved_by: str, resolution: str) -> None:
    """Fire-and-forget email to ticket creator on resolution."""
    try:
        from core.notifications import notify_ticket_resolved
        creator = ticket.get("created_by", "")
        if creator and creator != resolved_by:
            email = _get_user_email(creator)
            if email:
                notify_ticket_resolved(
                    creator_email=email,
                    ticket_id=ticket["id"],
                    title=ticket["title"],
                    resolved_by=resolved_by,
                    resolution=resolution or "",
                )
    except Exception as e:
        logger.warning("Resolution notification failed: %s", e)
