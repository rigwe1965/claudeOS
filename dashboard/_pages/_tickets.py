"""Tickets page — create, browse, and manage support tickets."""
from __future__ import annotations

import requests as _req
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import streamlit as st

PRIORITY_ICONS  = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
PRIORITY_LABELS = {1: "Critical", 2: "High", 3: "Medium", 4: "Low"}

STATUS_ICONS = {
    "open":             "○",
    "assigned":         "◎",
    "work_in_progress": "◉",
    "completed":        "✓",
    "closed":           "×",
}
STATUS_LABELS = {
    "open":             "Open",
    "assigned":         "Assigned",
    "work_in_progress": "Work In Progress",
    "completed":        "Completed",
    "closed":           "Closed",
}
# Forward transitions available to assignees/staff
NEXT_STATUS = {
    "open":             None,          # must assign first
    "assigned":         "work_in_progress",
    "work_in_progress": "completed",
    "completed":        "closed",
    "closed":           None,
}
NEXT_STATUS_LABEL = {
    "assigned":         "Start Work",
    "work_in_progress": "Mark Completed",
    "completed":        "Close Ticket",
}

CATEGORIES = ["bug", "billing", "access", "feature", "other"]
SLA_TIERS  = ["P1", "P2", "P3", "P4"]
SLA_LABELS = {"P1": "P1 Critical (4h)", "P2": "P2 High (8h)", "P3": "P3 Medium (24h)", "P4": "P4 Low (72h)"}
SLA_HOURS  = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}


def _sla_overdue(ticket: dict) -> bool:
    due    = ticket.get("sla_due_at")
    status = ticket.get("status", "")
    if not due or status in ("completed", "closed"):
        return False
    try:
        due_dt = datetime.strptime(due[:19], "%Y-%m-%d %H:%M:%S")
        return datetime.utcnow() > due_dt
    except Exception:
        return False


def _api_base() -> str:
    return "http://localhost:5000/api/v1"


def _headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _bulk_toolbar(ids: list, label: str, bulk_delete_fn, endpoint: str):
    if not bulk_delete_fn:
        return
    selected = [i for i in ids if st.session_state.get(f"sel_{i}")]
    slug = endpoint.replace("/", "_")
    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("Select All", key=f"selall{slug}"):
        for i in ids:
            st.session_state[f"sel_{i}"] = True
        st.rerun()
    if c2.button("Clear All", key=f"clrall{slug}"):
        for i in ids:
            st.session_state[f"sel_{i}"] = False
        st.rerun()
    if selected:
        c3.caption(f"{len(selected)} selected")
        if c3.button(f"Delete {len(selected)} {label}", key=f"bulkdel{slug}"):
            st.session_state[f"bulk_confirm{slug}"] = True

    if st.session_state.get(f"bulk_confirm{slug}"):
        st.warning(f"Permanently delete {len(selected)} {label}? Cannot be undone.")
        ca, cb = st.columns(2)
        if ca.button("Yes, delete all selected", key=f"bulkyes{slug}"):
            result = bulk_delete_fn(endpoint, selected)
            if result:
                st.success(f"Deleted {result.get('count', len(selected))}.")
            else:
                st.error("Bulk delete failed — check API.")
            for i in selected:
                st.session_state.pop(f"sel_{i}", None)
            st.session_state.pop(f"bulk_confirm{slug}", None)
            st.rerun()
        if cb.button("Cancel", key=f"bulkcancel{slug}"):
            st.session_state.pop(f"bulk_confirm{slug}", None)
            st.rerun()


def render(api_get, api_post, bulk_delete=None):
    st.title("Tickets")
    role = st.session_state.get("user_role", "viewer")

    if role in ("client", "viewer"):
        _render_client_view(api_get, api_post)
    elif role == "staff":
        _render_staff_view(api_get, api_post)
    else:
        _render_admin_view(api_get, api_post, bulk_delete)


# ── Client view ────────────────────────────────────────────────────────────────

def _render_client_view(api_get, api_post):
    tab_list, tab_new = st.tabs(["My Tickets", "New Ticket"])

    with tab_list:
        tickets = api_get("/tickets") or []
        if not tickets:
            st.info("No tickets yet. Create one in the 'New Ticket' tab.")
        else:
            st.caption(f"{len(tickets)} tickets")
            for t in tickets:
                _render_ticket_card(t, api_get, api_post, can_edit_desc=True)

    with tab_new:
        _render_create_form(api_post, namespace=st.session_state.get("user_namespace"))


# ── Staff view ─────────────────────────────────────────────────────────────────

def _render_staff_view(api_get, api_post):
    tab_assigned, tab_open, tab_new = st.tabs(["My Tickets", "Open (Unassigned)", "New Ticket"])

    with tab_assigned:
        tickets = api_get("/tickets?assigned_to=me") or []
        if not tickets:
            st.info("No tickets assigned to you.")
        else:
            st.caption(f"{len(tickets)} assigned tickets")
            for t in tickets:
                _render_ticket_card(t, api_get, api_post, staff_controls=True)

    with tab_open:
        # Show open tickets staff can self-assign
        all_open = api_get("/tickets?status=open") or []
        username = st.session_state.get("username", "")
        # Filter to tickets not yet assigned to anyone
        unassigned = [t for t in all_open if not t.get("assignees")]
        if not unassigned:
            st.info("No open unassigned tickets.")
        else:
            st.caption(f"{len(unassigned)} unassigned open tickets")
            for t in unassigned:
                _render_ticket_card(t, api_get, api_post, show_assign_me=True)

    with tab_new:
        _render_create_form(api_post)


# ── Admin / Operator view ──────────────────────────────────────────────────────

def _render_admin_view(api_get, api_post, bulk_delete=None):
    tab_all, tab_new, tab_stats = st.tabs(["All Tickets", "New Ticket", "Stats"])

    with tab_all:
        _render_admin_ticket_list(api_get, api_post, bulk_delete)

    with tab_new:
        ns_data    = api_get("/namespaces") or []
        ns_options = [n["slug"] for n in ns_data] if ns_data else []
        _render_create_form(api_post, ns_options=ns_options)

    with tab_stats:
        _render_stats(api_get)


def _render_admin_ticket_list(api_get, api_post, bulk_delete=None):
    results: dict = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(api_get, "/tickets"):                  "tickets",
            ex.submit(api_get, "/tickets/assignable-staff"): "staff",
            ex.submit(api_get, "/namespaces"):               "namespaces",
        }
        for f in as_completed(futures):
            results[futures[f]] = f.result()

    all_tickets = results.get("tickets") or []
    staff_list  = results.get("staff") or []
    ns_data     = results.get("namespaces") or []

    staff_names = [s["username"] for s in staff_list]
    ns_slugs    = [n["slug"] for n in ns_data]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        f_status = st.selectbox("Status", ["all"] + list(STATUS_ICONS.keys()), key="tk_f_status")
    with col2:
        f_priority = st.selectbox("Priority", ["all", "1-Critical", "2-High", "3-Medium", "4-Low"], key="tk_f_priority")
    with col3:
        f_ns = st.selectbox("Namespace", ["all"] + ns_slugs, key="tk_f_ns")
    with col4:
        f_assigned = st.selectbox("Assigned to", ["all"] + staff_names, key="tk_f_assigned")

    tickets = all_tickets
    if f_status != "all":
        tickets = [t for t in tickets if t["status"] == f_status]
    if f_priority != "all":
        p = int(f_priority[0])
        tickets = [t for t in tickets if t["priority"] == p]
    if f_ns != "all":
        tickets = [t for t in tickets if t["namespace"] == f_ns]
    if f_assigned != "all":
        tickets = [t for t in tickets if f_assigned in (t.get("assignees") or [])]

    overdue = [t for t in tickets if _sla_overdue(t)]
    if overdue:
        st.warning(f"{len(overdue)} ticket(s) past SLA deadline")

    all_ids = [t["id"] for t in tickets]
    st.caption(f"{len(tickets)} tickets")
    _bulk_toolbar(all_ids, "tickets", bulk_delete, "/tickets/bulk")
    st.markdown("---")
    for t in tickets:
        col_check, col_card = st.columns([0.05, 0.95])
        with col_check:
            st.checkbox("", key=f"sel_{t['id']}", label_visibility="collapsed")
        with col_card:
            _render_ticket_card(t, api_get, api_post, admin_controls=True, staff_names=staff_names)


# ── Shared card ────────────────────────────────────────────────────────────────

def _render_ticket_card(
    t: dict,
    api_get,
    api_post,
    *,
    can_edit_desc: bool = False,
    staff_controls: bool = False,
    admin_controls: bool = False,
    show_assign_me: bool = False,
    staff_names: list | None = None,
):
    tid        = t["id"]
    prio       = t.get("priority", 3)
    status     = t.get("status", "open")
    sla_tier   = t.get("sla_tier") or ""
    sla_due    = (t.get("sla_due_at") or "")[:16]
    overdue    = _sla_overdue(t)
    overdue_tag = " [OVERDUE]" if overdue else ""
    assignees  = t.get("assignees") or []
    assignee_str = ", ".join(assignees) if assignees else "—"

    status_icon  = STATUS_ICONS.get(status, "?")
    status_label = STATUS_LABELS.get(status, status)

    header = (
        f"{PRIORITY_ICONS.get(prio,'•')} **{t.get('title','?')}**"
        f"  ·  {status_icon} `{status_label}`"
        f"  ·  `{t.get('namespace','')}`"
        f"  ·  {(t.get('created_at') or '')[:10]}"
        f"{overdue_tag}"
    )

    with st.expander(header):
        st.markdown(f"**Description:** {t.get('description','')}")

        meta_cols = st.columns(4)
        meta_cols[0].markdown(f"**Category:** `{t.get('category','?')}`")
        meta_cols[1].markdown(f"**Priority:** {PRIORITY_LABELS.get(prio,'?')}")
        meta_cols[2].markdown(f"**SLA:** `{sla_tier or '—'}`")
        meta_cols[3].markdown(f"**Due:** `{sla_due or '—'}`")

        st.markdown(f"**Assigned to:** `{assignee_str}`")

        if t.get("resolution"):
            st.success(f"**Resolution:** {t['resolution']}")

        st.markdown("---")

        # ── Self-assign button (staff on open/unassigned tickets) ──
        if show_assign_me:
            if st.button("Assign to Me", key=f"assignme_{tid}", use_container_width=True):
                r = _req.post(
                    f"{_api_base()}/tickets/{tid}/assign-me",
                    headers=_headers(), timeout=5,
                )
                if r.ok:
                    st.success("Ticket assigned to you.")
                    st.rerun()
                else:
                    st.error(r.json().get("error", "Failed"))
            st.markdown("---")

        # ── Staff quick-action status buttons ──
        if staff_controls:
            _render_staff_controls(tid, t, api_post)
            st.markdown("---")

        # ── Admin controls ──
        if admin_controls:
            _render_admin_controls(tid, t, api_post, staff_names or [])
            st.markdown("---")

        # ── Client edit description ──
        if can_edit_desc and status in ("open", "assigned"):
            with st.expander("Edit description"):
                new_desc = st.text_area("Description", value=t.get("description", ""), key=f"edit_desc_{tid}")
                if st.button("Save", key=f"save_desc_{tid}"):
                    res = api_post(f"/tickets/{tid}", {"description": new_desc}, method="PATCH")
                    if res:
                        st.success("Updated.")
                        st.rerun()

        # ── Comment thread — lazy load to avoid N+1 HTTP calls per card ──
        if st.button("Comments", key=f"comments_toggle_{tid}"):
            key = f"_show_comments_{tid}"
            st.session_state[key] = not st.session_state.get(key, False)
        if st.session_state.get(f"_show_comments_{tid}", False):
            _render_comments(tid, api_get, api_post)


# ── Staff controls ─────────────────────────────────────────────────────────────

def _render_staff_controls(ticket_id: str, t: dict, api_post):
    status   = t.get("status", "open")
    username = st.session_state.get("username", "")
    assignees = t.get("assignees") or []

    # Self-assign if not yet assigned to this user
    if username not in assignees and status != "closed":
        if st.button("Assign to Me", key=f"sf_assignme_{ticket_id}"):
            r = _req.post(
                f"{_api_base()}/tickets/{ticket_id}/assign-me",
                headers=_headers(), timeout=5,
            )
            if r.ok:
                st.success("Assigned to you.")
                st.rerun()
            else:
                st.error(r.json().get("error", "Failed"))

    # Forward status progression buttons
    next_s = NEXT_STATUS.get(status)
    if next_s and username in assignees:
        btn_label = NEXT_STATUS_LABEL.get(status, f"→ {next_s}")
        c1, c2 = st.columns([2, 1])
        with c1:
            resolution = ""
            if status in ("work_in_progress", "completed"):
                resolution = st.text_area(
                    "Resolution notes", value=t.get("resolution") or "",
                    key=f"sf_res_{ticket_id}", height=80,
                )
        with c2:
            st.write("")
            st.write("")
            if st.button(btn_label, key=f"sf_next_{ticket_id}", use_container_width=True):
                payload: dict = {"status": next_s}
                if resolution:
                    payload["resolution"] = resolution
                res = api_post(f"/tickets/{ticket_id}", payload, method="PATCH")
                if res:
                    st.success(f"Status → {STATUS_LABELS[next_s]}")
                    st.rerun()
                else:
                    st.error("Update failed.")
    elif status == "closed":
        st.caption("Ticket closed.")


# ── Admin controls ─────────────────────────────────────────────────────────────

def _render_admin_controls(ticket_id: str, t: dict, api_post, staff_names: list):
    status    = t.get("status", "open")
    assignees = t.get("assignees") or []

    # ── Multi-assignee management ──
    st.markdown("**Assignees**")
    if assignees:
        for uname in assignees:
            cols = st.columns([4, 1])
            cols[0].markdown(f"`{uname}`")
            if cols[1].button("Remove", key=f"rm_assign_{ticket_id}_{uname}"):
                r = _req.delete(
                    f"{_api_base()}/tickets/{ticket_id}/assignees/{uname}",
                    headers=_headers(), timeout=5,
                )
                if r.ok:
                    st.rerun()
                else:
                    st.error(r.json().get("error", "Failed"))
    else:
        st.caption("No assignees yet.")

    # Add assignees
    add_options = [u for u in staff_names if u not in assignees]
    if add_options:
        sel = st.multiselect("Add assignees", add_options, key=f"adm_add_assign_{ticket_id}")
        if sel and st.button("Add Selected", key=f"adm_do_add_{ticket_id}"):
            r = _req.post(
                f"{_api_base()}/tickets/{ticket_id}/assignees",
                json={"usernames": sel},
                headers=_headers(), timeout=5,
            )
            if r.ok:
                st.success(f"Added: {', '.join(sel)}")
                st.rerun()
            else:
                st.error(r.json().get("error", "Failed"))

    st.markdown("---")

    # ── Status / category / SLA / priority ──
    col1, col2, col3 = st.columns(3)

    with col1:
        status_options = list(STATUS_ICONS.keys())
        new_status = st.selectbox(
            "Status", status_options,
            index=status_options.index(status) if status in status_options else 0,
            key=f"adm_status_{ticket_id}",
        )
        new_cat = st.selectbox(
            "Category", CATEGORIES,
            index=CATEGORIES.index(t.get("category", "other")),
            key=f"adm_cat_{ticket_id}",
        )

    with col2:
        sla_options  = ["— None —"] + SLA_TIERS
        current_sla  = t.get("sla_tier") or "— None —"
        if current_sla not in sla_options:
            current_sla = "— None —"
        new_sla = st.selectbox(
            "SLA Tier", sla_options,
            index=sla_options.index(current_sla),
            key=f"adm_sla_{ticket_id}",
        )
        if new_sla and new_sla != "— None —":
            st.caption(f"Due in {SLA_HOURS[new_sla]}h from now")

        prio_options = [1, 2, 3, 4]
        prio_labels  = [PRIORITY_LABELS[p] for p in prio_options]
        current_prio_idx = prio_options.index(t.get("priority", 3))
        new_prio_label   = st.selectbox("Priority", prio_labels, index=current_prio_idx, key=f"adm_prio_{ticket_id}")
        new_prio         = prio_options[prio_labels.index(new_prio_label)]

    with col3:
        new_resolution = st.text_area(
            "Resolution notes", value=t.get("resolution") or "", key=f"adm_res_{ticket_id}"
        )

    if st.button("Update Ticket", key=f"adm_update_{ticket_id}", use_container_width=True):
        payload: dict = {
            "status":     new_status,
            "category":   new_cat,
            "priority":   new_prio,
            "resolution": new_resolution or None,
        }
        if new_sla and new_sla != "— None —":
            payload["sla_tier"] = new_sla
        res = api_post(f"/tickets/{ticket_id}", payload, method="PATCH")
        if res:
            st.success("Ticket updated.")
            st.rerun()
        else:
            st.error("Update failed.")

    role = st.session_state.get("user_role")
    if role == "admin":
        if st.button("Delete Ticket", key=f"adm_del_{ticket_id}"):
            st.session_state[f"confirm_del_tk_{ticket_id}"] = True
        if st.session_state.get(f"confirm_del_tk_{ticket_id}"):
            st.warning("Permanently delete this ticket and all comments?")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete", key=f"yes_del_tk_{ticket_id}"):
                _req.delete(
                    f"{_api_base()}/tickets/{ticket_id}",
                    headers=_headers(), timeout=5,
                )
                st.session_state.pop(f"confirm_del_tk_{ticket_id}", None)
                st.rerun()
            if c2.button("Cancel", key=f"cancel_del_tk_{ticket_id}"):
                st.session_state.pop(f"confirm_del_tk_{ticket_id}", None)
                st.rerun()


# ── Comments ───────────────────────────────────────────────────────────────────

def _render_comments(ticket_id: str, api_get, api_post):
    comments = api_get(f"/tickets/{ticket_id}/comments") or []
    if comments:
        st.markdown("**Comments:**")
        for c in comments:
            ts = (c.get("created_at") or "")[:16]
            st.markdown(f"`{c['author']}` · {ts}")
            st.markdown(f"> {c['body']}")
    else:
        st.caption("No comments yet.")

    new_comment = st.text_area("Add comment", key=f"comment_{ticket_id}", height=80)
    if st.button("Post Comment", key=f"post_comment_{ticket_id}"):
        if new_comment.strip():
            res = api_post(f"/tickets/{ticket_id}/comments", {"body": new_comment.strip()})
            if res:
                st.rerun()
        else:
            st.warning("Comment cannot be empty.")


# ── Create form ────────────────────────────────────────────────────────────────

def _render_create_form(api_post, namespace: str | None = None, ns_options: list | None = None):
    st.subheader("Create New Ticket")

    with st.form("new_ticket_form", clear_on_submit=True):
        title       = st.text_input("Title *", placeholder="Brief summary of the issue")
        description = st.text_area("Description *", placeholder="Describe the issue in detail...", height=120)
        col1, col2  = st.columns(2)
        with col1:
            category = st.selectbox("Category", CATEGORIES)
        with col2:
            prio_labels = [f"{PRIORITY_ICONS[p]} {PRIORITY_LABELS[p]}" for p in [1, 2, 3, 4]]
            prio_sel    = st.selectbox("Priority", prio_labels, index=2)
            priority    = [1, 2, 3, 4][prio_labels.index(prio_sel)]

        if ns_options:
            ns_sel     = st.selectbox("Namespace", ns_options)
            payload_ns = ns_sel
        elif namespace:
            st.text_input("Namespace", value=namespace, disabled=True)
            payload_ns = namespace
        else:
            payload_ns = None

        submitted = st.form_submit_button("Submit Ticket", use_container_width=True)

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Title and description are required.")
        else:
            payload: dict = {
                "title": title.strip(), "description": description.strip(),
                "category": category, "priority": priority,
            }
            if payload_ns:
                payload["namespace"] = payload_ns
            res = api_post("/tickets", payload)
            if res:
                st.success(f"Ticket created! ID: `{res['id'][:8]}...`")
                st.rerun()
            else:
                st.error("Failed to create ticket. Check API is running.")


# ── Stats ──────────────────────────────────────────────────────────────────────

def _render_stats(api_get):
    stats       = api_get("/tickets/stats") or {}
    by_status   = stats.get("by_status", {})
    by_priority = stats.get("by_priority", {})
    by_ns       = stats.get("by_namespace", {})

    col1, col2, col3, col4 = st.columns(4)
    total = sum(by_status.values())
    col1.metric("Total Tickets",    total)
    col2.metric("SLA Breached",     stats.get("sla_breached", 0))
    col3.metric("Unassigned Open",  stats.get("unassigned_open", 0))
    col4.metric("Completed/Closed", by_status.get("completed", 0) + by_status.get("closed", 0))

    st.markdown("---")
    left, right = st.columns(2)

    with left:
        st.markdown("**By Status:**")
        for s, cnt in sorted(by_status.items()):
            icon  = STATUS_ICONS.get(s, "•")
            label = STATUS_LABELS.get(s, s)
            st.markdown(f"{icon} `{label}` — {cnt}")

        st.markdown("**By Priority:**")
        for p_str, cnt in sorted(by_priority.items()):
            try:
                p = int(p_str)
            except (ValueError, TypeError):
                p = 3
            st.markdown(f"{PRIORITY_ICONS.get(p,'•')} {PRIORITY_LABELS.get(p,'?')} — {cnt}")

    with right:
        if by_ns:
            st.markdown("**By Namespace:**")
            for ns, cnt in sorted(by_ns.items(), key=lambda x: -x[1]):
                st.markdown(f"`{ns}` — {cnt}")
