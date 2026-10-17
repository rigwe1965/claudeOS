"""Memory page — namespace tabs, FTS+semantic search, add entry form."""
import requests as _req
import streamlit as st
from dashboard.components.brand import get_theme_vars

_API_BASE = "http://127.0.0.1:5000/api/v1"

NAMESPACES: list[str] = []  # populated dynamically from API
CATEGORIES = ["fact", "decision", "context", "preference", "reminder", "insight"]


def _auth_headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _available_namespaces(all_ns: list[str] | None = None) -> list[str]:
    role    = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")
    if role in ("client", "viewer") and user_ns:
        return [user_ns]
    return sorted(all_ns or NAMESPACES)


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
    st.title("Memory")

    role = st.session_state.get("user_role", "admin")

    ns_data = api_get("/memory/namespaces")
    counts  = ns_data.get("namespaces", {}) if ns_data else {}
    available_ns = _available_namespaces(all_ns=list(counts.keys()))
    total   = sum(counts.get(ns, 0) for ns in available_ns)
    st.markdown(f"**{total} total entries** across {len(available_ns)} namespace(s)")

    if available_ns:
        cols = st.columns(min(len(available_ns), 6))
        for col, ns in zip(cols, available_ns):
            col.metric(ns, counts.get(ns, 0))

    st.markdown("---")

    tab_search, tab_browse, tab_add = st.tabs(["Search", "Browse", "Add Entry"])

    # ── Search ──────────────────────────────────────────────────────────────
    with tab_search:
        s_col1, s_col2, s_col3 = st.columns([3, 1, 1])
        with s_col1:
            query = st.text_input("Search memory", placeholder="e.g. brand color, RECI fleet, client contact...", label_visibility="collapsed")
        with s_col2:
            mode = st.selectbox("Mode", ["text", "semantic", "both"], label_visibility="collapsed")
        with s_col3:
            search_ns = st.selectbox("Namespace", ["(any)"] + available_ns, label_visibility="collapsed")

        if query.strip():
            payload = {"query": query, "mode": mode, "top_k": 10}
            if search_ns != "(any)":
                payload["namespace"] = search_ns

            result = api_post("/memory/search", payload)
            if result:
                entries = result.get("results", [])
                st.markdown(f"**{len(entries)} results** for `{query}` (mode: {mode})")
                for e in entries:
                    _render_entry_card(e)
            else:
                st.error("Search failed")

    # ── Browse ───────────────────────────────────────────────────────────────
    with tab_browse:
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            browse_ns = st.selectbox("Namespace", ["(all)"] + available_ns, key="browse_ns")
        with b_col2:
            browse_cat = st.selectbox("Category", ["(all)"] + CATEGORIES, key="browse_cat")
        with b_col3:
            min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.1)

        params = f"?limit=50&min_confidence={min_conf}"
        if browse_ns != "(all)":
            params += f"&namespace={browse_ns}"
        if browse_cat != "(all)":
            params += f"&category={browse_cat}"

        data = api_get(f"/memory{params}")
        if data:
            entries = data.get("entries", [])
            all_ids = [e.get("id", "") for e in entries]
            st.markdown(f"**{len(entries)} entries**")
            _bulk_toolbar(all_ids, "memory entries", bulk_delete, "/memory/bulk")
            st.markdown("---")
            for e in entries:
                eid = e.get("id", "")
                col_check, col_card = st.columns([0.05, 0.95])
                with col_check:
                    st.checkbox("", key=f"sel_{eid}", label_visibility="collapsed")
                with col_card:
                    _render_entry_card(e, show_delete=True)
        else:
            st.error("Failed to load entries")

    # ── Add Entry ────────────────────────────────────────────────────────────
    with tab_add:
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            add_ns   = st.selectbox("Namespace", available_ns, key="add_ns")
            add_cat  = st.selectbox("Category", CATEGORIES, key="add_cat")
            add_key  = st.text_input("Key", placeholder="e.g. client.contact_email")
            add_conf = st.slider("Confidence", 0.0, 1.0, 1.0, 0.05)
        with a_col2:
            add_value   = st.text_area("Value", height=150)
            add_tags    = st.text_input("Tags (comma-separated)", placeholder="e.g. client, contact, email")
            add_expires = None
            if add_cat == "reminder":
                import datetime as _dt
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    reminder_date = st.date_input("Remind on (date)", value=_dt.date.today() + _dt.timedelta(days=1))
                with r_col2:
                    reminder_time = st.time_input("Time", value=_dt.time(9, 0))
                add_expires = _dt.datetime.combine(reminder_date, reminder_time).strftime("%Y-%m-%dT%H:%M:%S")

        if st.button("Save to Memory", type="primary"):
            if add_key.strip() and add_value.strip():
                tags    = [t.strip() for t in add_tags.split(",") if t.strip()]
                payload = {
                    "namespace": add_ns, "category": add_cat, "key": add_key,
                    "value": add_value, "tags": tags, "confidence": add_conf, "source": "dashboard",
                }
                if add_expires:
                    payload["expires_at"] = add_expires
                result = api_post("/memory", payload)
                if result:
                    st.success(f"Saved: `{add_key}` → `{add_value[:60]}...`" if len(add_value) > 60 else f"Saved: `{add_key}`")
                else:
                    st.error("Save failed")
            else:
                st.warning("Key and Value are required")

    st.markdown("---")
    if st.button("Import from .claude/memory/"):
        result = api_post("/memory/import", {})
        if result:
            st.success(f"Imported {result.get('imported',0)}/{result.get('total_files',0)} files")
        else:
            st.error("Import failed")


def _render_entry_card(e: dict, show_delete: bool = False):
    cat_colors = {
        "fact": "#407E3C", "decision": "#3b82f6", "context": "#f59e0b",
        "preference": "#8b5cf6", "reminder": "#ef4444", "insight": "#14b8a6",
    }
    cat   = e.get("category", "fact")
    color = cat_colors.get(cat, "#407E3C")
    conf  = e.get("confidence", 1.0)
    tags  = e.get("tags", [])
    eid   = e.get("id", "")
    value_preview = (e.get("value", "") or "")[:200]

    with st.expander(f"**{e.get('key','?')}** · `{e.get('namespace','?')}`", expanded=False):
        st.markdown(f"""
<div style="display:flex;gap:8px;margin-bottom:8px;align-items:center;">
  <span style="background:{color}33;color:{color};border:1px solid {color}55;
               padding:1px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">{cat.upper()}</span>
  <span style="color:{get_theme_vars()['TEXT_MUTED']};font-size:0.8rem;">confidence: {conf:.0%}</span>
  {' '.join(f'<span class="tag-chip">{t}</span>' for t in tags)}
</div>
""", unsafe_allow_html=True)
        st.markdown(value_preview + ("..." if len(e.get("value","")) > 200 else ""))
        created = (e.get("created_at") or "")[:16]
        st.caption(f"ID: `{eid[:8]}...` · Created: {created}")

        if show_delete and eid:
            if st.button("Delete", key=f"mem_del_{eid}"):
                st.session_state[f"confirm_mem_del_{eid}"] = True
            if st.session_state.get(f"confirm_mem_del_{eid}"):
                st.warning("Delete this memory entry?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key=f"mem_yes_{eid}"):
                    _req.delete(
                        f"{_API_BASE}/memory/{eid}",
                        headers=_auth_headers(), timeout=5,
                    )
                    st.session_state.pop(f"confirm_mem_del_{eid}", None)
                    st.rerun()
                if c2.button("Cancel", key=f"mem_cancel_{eid}"):
                    st.session_state.pop(f"confirm_mem_del_{eid}", None)
                    st.rerun()
