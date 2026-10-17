"""Outputs page — browse, search, and export agent/workflow outputs."""
import os
import requests
import streamlit as st
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_DISPLAY_TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "UTC"))


def _fmt_ts(raw: str) -> str:
    """Convert UTC ISO timestamp to DISPLAY_TZ, return 'YYYY-MM-DD HH:MM'."""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_DISPLAY_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw[:16]

_API_BASE = "http://localhost:5000/api/v1"


def _auth_headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


TYPE_ICONS = {
    "report":   "R",
    "draft":    "D",
    "analysis": "A",
    "code":     "C",
    "note":     "N",
    "archive":  "X",
}


def _bulk_toolbar(ids: list, label: str, bulk_delete_fn, endpoint: str):
    """Select All / Clear All / Delete Selected toolbar."""
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
    st.title("Output Manager")

    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")
    if role in ("client", "viewer") and user_ns:
        ns_data = []
    else:
        ns_data = api_get("/namespaces") or []

    tab_browse, tab_search, tab_stats = st.tabs(["Browse", "Search", "Stats"])

    with tab_browse:
        _render_browse(api_get, api_post, ns_data, bulk_delete)

    with tab_search:
        _render_search(api_get, ns_data)

    with tab_stats:
        _render_stats(api_get)


def _render_browse(api_get, api_post, ns_data: list, bulk_delete=None):
    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")

    col1, col2, col3 = st.columns(3)
    with col1:
        if role in ("client", "viewer") and user_ns:
            ns_filter = user_ns
            st.selectbox("Namespace", [user_ns], key="out_ns_filter", disabled=True)
        else:
            ns_options = ["all"] + [n["slug"] for n in ns_data]
            ns_filter = st.selectbox("Namespace", ns_options, key="out_ns_filter")
    with col2:
        type_options = ["all", "report", "draft", "analysis", "code", "note", "archive"]
        type_filter = st.selectbox("Type", type_options, key="out_type_filter")
    with col3:
        limit = st.selectbox("Limit", [20, 50, 100], key="out_limit")

    url = f"/outputs?limit={limit}"
    if ns_filter != "all":
        url += f"&namespace={ns_filter}"
    if type_filter != "all":
        url += f"&type={type_filter}"

    outputs = api_get(url) or []

    if not outputs:
        st.info("No outputs found.")
        return

    all_ids = [out.get("id", "") for out in outputs]
    st.caption(f"{len(outputs)} outputs")
    _bulk_toolbar(all_ids, "outputs", bulk_delete, "/outputs/bulk")
    st.markdown("---")

    for out in outputs:
        icon    = TYPE_ICONS.get(out.get("output_type", ""), "•")
        title   = out.get("title", "Untitled")
        ns      = out.get("namespace", "global")
        otype   = out.get("output_type", "?")
        created = _fmt_ts(out.get("created_at") or "")
        size_kb = round(out.get("size_bytes", 0) / 1024, 1)
        tags    = out.get("tags") or []
        summary = out.get("summary") or ""
        oid     = out.get("id", "")

        col_check, col_card = st.columns([0.05, 0.95])
        with col_check:
            st.checkbox("Select", key=f"sel_{oid}", label_visibility="collapsed")
        with col_card:
            with st.expander(f"{icon} **{title}** · `{ns}` · {created}"):
                col_meta, col_actions = st.columns([3, 1])
                with col_meta:
                    st.markdown(f"**Type:** `{otype}` · **Size:** {size_kb} KB · **Created:** `{created}`")
                    if tags:
                        tag_str = " ".join(f"`{t}`" for t in tags[:8])
                        st.markdown(f"**Tags:** {tag_str}")
                    if summary:
                        st.caption(summary)

                with col_actions:
                    if st.button("View", key=f"view_{oid}", width='stretch'):
                        st.session_state[f"show_content_{oid}"] = True
                    if st.button("Download MD", key=f"dl_btn_{oid}", width='stretch'):
                        _r = requests.get(
                            f"{_API_BASE}/outputs/{oid}/export?format=markdown",
                            headers=_auth_headers(), timeout=5,
                        )
                        if _r.ok:
                            fname = f"{title[:40].replace(' ','_')}.md"
                            st.download_button("Save", data=_r.text, file_name=fname,
                                               mime="text/markdown", key=f"dl_{oid}")
                    if st.button("Delete", key=f"del_{oid}", width='stretch'):
                        st.session_state[f"confirm_delete_{oid}"] = True

                if st.session_state.get(f"confirm_delete_{oid}"):
                    st.warning("Confirm delete?")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes, delete", key=f"yes_del_{oid}"):
                        try:
                            _dr = requests.delete(
                                f"{_API_BASE}/outputs/{oid}",
                                headers=_auth_headers(),
                                timeout=5,
                            )
                            if _dr.ok:
                                st.session_state.pop(f"confirm_delete_{oid}", None)
                                st.rerun()
                            else:
                                st.error(f"Delete failed ({_dr.status_code}): {_dr.text[:200]}")
                        except Exception as _e:
                            st.error(f"Delete error: {_e}")
                    if c2.button("Cancel", key=f"cancel_del_{oid}"):
                        st.session_state.pop(f"confirm_delete_{oid}", None)
                        st.rerun()

                if st.session_state.get(f"show_content_{oid}"):
                    content_data = api_get(f"/outputs/{oid}")
                    if content_data:
                        st.markdown("---")
                        st.markdown(content_data.get("content", "*(no content)*"))
                    if st.button("Hide", key=f"hide_{oid}"):
                        st.session_state.pop(f"show_content_{oid}", None)
                        st.rerun()


def _render_search(api_get, ns_data: list):
    st.subheader("Full-Text Search")
    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Search query", key="fts_query", placeholder="morning briefing, client report, ...")
    with col2:
        if role in ("client", "viewer") and user_ns:
            search_ns = user_ns
            st.selectbox("Namespace", [user_ns], key="fts_ns", disabled=True)
        else:
            ns_options = ["all"] + [n["slug"] for n in ns_data]
            search_ns = st.selectbox("Namespace", ns_options, key="fts_ns")

    if st.button("Search", width='stretch') and query.strip():
        url = f"/outputs/search?q={query}&limit=20"
        if search_ns != "all":
            url += f"&namespace={search_ns}"
        results = api_get(url) or []

        if not results:
            st.info("No results.")
        else:
            st.caption(f"{len(results)} results")
            for r in results:
                icon  = TYPE_ICONS.get(r.get("output_type", ""), "•")
                score = abs(r.get("score", 0.0))
                _rts  = _fmt_ts(r.get("created_at") or "")
                st.markdown(
                    f"{icon} **{r.get('title','?')}** · `{r.get('namespace','')}` · "
                    f"`{r.get('output_type','')}` · `{_rts}` · score: `{score:.3f}`"
                )
                if r.get("summary"):
                    st.caption(r["summary"])
                st.markdown("---")


def _render_stats(api_get):
    st.subheader("Output Statistics")
    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")
    is_scoped = role in ("client", "viewer") and user_ns

    col1, col2 = st.columns(2)
    with col1:
        label     = f"Namespace: `{user_ns}`" if is_scoped else "Global"
        st.markdown(f"**{label}**")
        stats_url = f"/outputs/stats?namespace={user_ns}" if is_scoped else "/outputs/stats"
        stats     = api_get(stats_url) or {}
        total     = stats.get("total_count", 0)
        total_kb  = round(stats.get("total_bytes", 0) / 1024, 1)
        st.metric("Total Outputs", total)
        st.metric("Total Size", f"{total_kb} KB")

        by_type = stats.get("by_type", {})
        if by_type:
            st.markdown("**By Type:**")
            for otype, info in sorted(by_type.items()):
                icon = TYPE_ICONS.get(otype, "•")
                st.markdown(f"{icon} `{otype}` — {info['count']} outputs · {round(info['total_bytes']/1024,1)} KB")

    with col2:
        if not is_scoped:
            all_stats = api_get("/outputs/stats/all") or {}
            by_ns     = all_stats.get("by_namespace", {})
            if by_ns:
                st.markdown("**By Namespace:**")
                for slug, info in sorted(by_ns.items()):
                    count = info.get("total_count", 0)
                    if count > 0:
                        kb = round(info.get("total_bytes", 0) / 1024, 1)
                        st.markdown(f"`{slug}` — {count} outputs · {kb} KB")
