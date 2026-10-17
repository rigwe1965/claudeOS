"""Settings page — Phase 7: Supabase Cloud Sync controls."""
from __future__ import annotations

import streamlit as st
from dashboard.components.brand import PRIMARY, get_theme_vars


def render(api_get, api_post, bulk_delete=None):
    st.title("Settings")
    st.markdown("---")

    # ── Email Notifications ────────────────────────────────────
    _render_email_settings()

    st.markdown("---")

    # ── Supabase Sync ──────────────────────────────────────────
    st.subheader("Supabase Cloud Sync")

    status = api_get("/sync/status", timeout=5)
    if status is None:
        st.error("Could not fetch sync status — API may be rate-limited or temporarily unavailable. Refresh to retry.")
        return

    configured = status.get("configured", False)
    last_sync = status.get("last_sync_at")
    table_states = status.get("table_states", {})
    auto_enabled = status.get("auto_sync_enabled", False)
    interval = status.get("auto_sync_interval_min", 15)

    # Connection status badge
    if configured:
        st.markdown(
            f'<span class="cos-pill" style="background:{PRIMARY};">● Connected</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="cos-pill" style="background:#B42318;">● Not Configured</span>',
            unsafe_allow_html=True,
        )
        st.info("Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to your `.env` file, then restart the server.")
        st.markdown("**Supabase schema** — run this SQL in your Supabase dashboard:")
        _show_schema_snippet()
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    total_pushed = sum(t.get("rows_pushed", 0) for t in table_states.values())
    total_failed = sum(t.get("rows_failed", 0) for t in table_states.values())
    col1.metric("Total Pushed", f"{total_pushed:,}")
    col2.metric("Total Failed", f"{total_failed:,}", delta=f"-{total_failed}" if total_failed else None, delta_color="inverse")
    col3.metric("Auto-sync", f"Every {interval}m" if auto_enabled else "Off")

    if last_sync:
        st.markdown(f'<div style="color:{get_theme_vars()["TEXT_MUTED"]};font-size:0.8rem;">Last sync: {last_sync}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Manual sync controls ───────────────────────────────────
    st.markdown("**Manual Controls**")
    c1, c2, c3 = st.columns(3)

    if c1.button("Push All Now", width='stretch', type="primary"):
        with st.spinner("Syncing…"):
            result = api_post("/sync/push", {})
        if result:
            pushed = result.get("total_pushed", 0)
            failed = result.get("total_failed", 0)
            ms = result.get("duration_ms", 0)
            if failed == 0:
                st.success(f"Pushed {pushed} rows in {ms}ms")
            else:
                st.warning(f"Pushed {pushed} rows, {failed} failed — check log below")
            st.rerun()
        else:
            st.error("Push failed — API error")

    table_options = list(table_states.keys())
    selected_table = c2.selectbox("Table", table_options, label_visibility="collapsed")
    if c3.button("Push Table", width='stretch'):
        with st.spinner(f"Syncing {selected_table}…"):
            result = api_post("/sync/push", {"table": selected_table})
        if result:
            st.success(f"Pushed {result.get('rows_pushed', 0)} rows")
            st.rerun()
        else:
            st.error("Push failed")

    # ── Per-table state ────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Table Sync State**")
    rows = []
    for tname, ts in table_states.items():
        rows.append({
            "Table": tname,
            "Last Synced": ts.get("last_synced_at") or "Never",
            "Pushed": ts.get("rows_pushed", 0),
            "Failed": ts.get("rows_failed", 0),
            "Last Error": (ts.get("last_error") or "")[:60],
        })
    if rows:
        st.dataframe(rows, width='stretch', hide_index=True)

    # ── Reset watermark ────────────────────────────────────────
    with st.expander("Reset Watermark (re-sync all)"):
        st.warning("Resetting forces a full re-push of all rows on next sync. Use only to recover from errors.")
        rc1, rc2 = st.columns(2)
        reset_table = rc1.selectbox("Table to reset", ["(all)"] + table_options, key="reset_sel")
        if rc2.button("Reset", type="secondary"):
            payload = {} if reset_table == "(all)" else {"table": reset_table}
            result = api_post("/sync/reset-watermark", payload)
            if result and result.get("ok"):
                st.success(f"Watermark reset for: {result.get('table', 'all')}")
                st.rerun()
            else:
                st.error("Reset failed")

    # ── Sync Log ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Sync Log** (last 50 runs)")
    log = api_get("/sync/log?limit=50", timeout=5)
    if log:
        _render_sync_log(log, api_post)
    else:
        st.info("No sync runs yet.")

    # ── Schema helper ──────────────────────────────────────────
    st.markdown("---")
    with st.expander("Supabase SQL Schema"):
        _show_schema_snippet()


def _sync_api_base() -> str:
    try:
        from core.config import get_settings
        return f"http://127.0.0.1:{get_settings().FLASK_PORT}/api/v1"
    except Exception:
        return "http://127.0.0.1:5000/api/v1"


def _sync_headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _render_sync_log(log: list, api_post):
    """Render sync log table with checkbox selection and bulk/single delete."""
    import pandas as pd

    rows = []
    for r in log:
        rows.append({
            "id": r.get("id", ""),
            "Started": (r.get("started_at") or "")[:19].replace("T", " "),
            "Table": r.get("table_name", ""),
            "OK": r.get("rows_ok", 0),
            "Fail": r.get("rows_fail", 0),
            "ms": r.get("duration_ms", 0),
            "Error": (r.get("error") or "")[:80],
        })

    df = pd.DataFrame(rows)
    # Store all IDs in session_state so on_change callback can look them up
    st.session_state["_synclog_all_ids"] = df["id"].tolist()

    display_df = df.drop(columns=["id"]).copy()
    display_df.insert(0, "Select", False)

    # Select All flag must be applied BEFORE data_editor instantiates — cannot set
    # st.session_state["sync_log_editor"] after the widget renders (Streamlit raises).
    if st.session_state.pop("_synclog_select_all_pending", False):
        display_df["Select"] = True
        st.session_state["_synclog_sel_ids"] = df["id"].tolist()
        st.session_state.pop("sync_log_editor", None)  # clear stale widget state

    def _on_editor_change():
        """Fires when user checks/unchecks a box — stores selected IDs in stable state key.
        Guard: empty edited_rows = Streamlit widget state reset (not a user action).
        Preserve existing selection in that case rather than clearing it.
        """
        state = st.session_state.get("sync_log_editor") or {}
        edited_rows = state.get("edited_rows", {}) if isinstance(state, dict) else {}
        if not edited_rows:
            return  # widget reset, not a real user change — keep existing selection
        all_ids = st.session_state.get("_synclog_all_ids", [])
        selected = []
        for k, v in edited_rows.items():
            if isinstance(v, dict) and v.get("Select", False):
                idx = int(k)
                if idx < len(all_ids):
                    selected.append(all_ids[idx])
        st.session_state["_synclog_sel_ids"] = selected

    edited = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("", width="small"),
            "Started": st.column_config.TextColumn("Started", width="medium"),
            "Table": st.column_config.TextColumn("Table", width="medium"),
            "OK": st.column_config.NumberColumn("OK", width="small"),
            "Fail": st.column_config.NumberColumn("Fail", width="small"),
            "ms": st.column_config.NumberColumn("ms", width="small"),
            "Error": st.column_config.TextColumn("Error", width="large"),
        },
        key="sync_log_editor",
        on_change=_on_editor_change,
        disabled=["Started", "Table", "OK", "Fail", "ms", "Error"],
    )

    # Use the stable on_change state as source of truth for selected IDs.
    # Falls back to reading the post-render edited df (first interaction before on_change fires).
    selected_ids = st.session_state.get("_synclog_sel_ids")
    if selected_ids is None:
        _curr_idx = edited.index[edited["Select"]].tolist()
        selected_ids = df.loc[_curr_idx, "id"].tolist()
    n = len(selected_ids)

    # ── Persistent feedback (survives rerun) ──────────────────
    _del_msg = st.session_state.pop("_synclog_del_msg", None)
    if _del_msg:
        st.success(_del_msg)

    # ── Action bar ────────────────────────────────────────────
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    a1, a2, _ = st.columns([2, 3, 5])

    with a1:
        if st.button("Select All", key="synclog_sel_all", use_container_width=True):
            st.session_state["_synclog_select_all_pending"] = True
            st.rerun()

    with a2:
        del_label = f"Delete Selected ({n})" if n else "Delete Selected"
        if st.button(del_label, key="synclog_bulk_del", type="primary",
                     disabled=(n == 0), use_container_width=True):
            if not selected_ids:
                st.warning("Select rows first.")
            else:
                import requests
                try:
                    resp = requests.delete(
                        f"{_sync_api_base()}/sync/log",
                        json={"ids": selected_ids},
                        headers=_sync_headers(),
                        timeout=10,
                    )
                    data = resp.json()
                    if resp.ok:
                        deleted = data.get("deleted", n)
                        st.session_state.pop("sync_log_editor", None)
                        st.session_state.pop("_synclog_sel_ids", None)
                        st.session_state["_synclog_del_msg"] = f"Deleted {deleted} log {'entry' if deleted == 1 else 'entries'}."
                        st.rerun()
                    else:
                        st.error(data.get("error", "Delete failed"))
                except Exception as e:
                    st.error(f"Request error: {e}")

    if n:
        st.caption(f"{n} row{'s' if n > 1 else ''} selected — click **Delete Selected** to remove.")


def _render_email_settings():
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    st.subheader("Email Notifications")
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")

    if smtp_host and smtp_user:
        st.markdown(
            f'<span class="cos-pill" style="background:#407E3C;">● Configured ({smtp_user})</span>',
            unsafe_allow_html=True,
        )
        st.caption("Ticket assignment + resolution emails are active.")
        notify_email = os.environ.get("NOTIFY_EMAIL", smtp_user)
        if st.button("Send test email", key="smtp_test"):
            try:
                from core.notifications import send_test_email
                ok = send_test_email(notify_email)
                if ok:
                    st.success(f"Test email sent to {notify_email}")
                else:
                    st.error("Send failed — check SMTP credentials in .env")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.markdown(
            '<span class="cos-pill" style="background:#5F6673;">● Not Configured</span>',
            unsafe_allow_html=True,
        )
        st.info(
            "Add these to your `.env` to enable ticket email notifications:\n\n"
            "```\nSMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\n"
            "SMTP_USER=you@gmail.com\nSMTP_PASSWORD=your-app-password\n"
            "NOTIFY_EMAIL=you@gmail.com\n```"
        )


def _show_schema_snippet():
    try:
        from pathlib import Path
        sql_path = Path(__file__).parent.parent.parent / "sync" / "supabase_schema.sql"
        if sql_path.exists():
            sql = sql_path.read_text(encoding="utf-8")
            st.code(sql, language="sql")
        else:
            st.warning("sync/supabase_schema.sql not found")
    except Exception as e:
        st.error(f"Could not load schema: {e}")
