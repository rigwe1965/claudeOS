"""Overview page — Phase 13.3: Live activity feed with real-time polling."""
import os
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import escape as _esc
from zoneinfo import ZoneInfo
from dashboard.components.brand import aurora_hero, PRIMARY
from dashboard.components.proxy import proxy_button, COS_CLICK_PROXY_JS

_DISPLAY_TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "UTC"))


_KPI_PAGE_MAP = {
    "Memory":       "Memory",
    "Agents":       "Agents",
    "Runs":         "Agents",
    "Workflows":    "Workflows",
    "Outputs":      "Outputs",
    "Open Tickets": "Tickets",
    "Projects":     "Projects",
}


def _make_nav_cb(target: str):
    """Factory returning on_click callback that sets nav_page before radio re-renders."""
    def _cb():
        st.session_state["nav_page"] = target
    return _cb


# KPI label -> key in /system/trends "series"
_KPI_TREND_KEY = {
    "Memory":       "memory",
    "Runs":         "runs",
    "Outputs":      "outputs",
    "Open Tickets": "open_tickets",
    "Workflows":    "workflows",
}


def _sparkline_svg(values: list, color: str, width: int = 84, height: int = 28) -> str:
    """Inline SVG area sparkline. Empty string when there is nothing to draw (no data / all zero)."""
    if not values or len(values) < 2 or not any(values):
        return ""
    peak = max(values)
    pad = 2
    step = (width - 2 * pad) / (len(values) - 1)
    pts = [
        (pad + i * step, height - pad - (v / peak) * (height - 2 * pad))
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad:.1f},{height - pad} {line} {pts[-1][0]:.1f},{height - pad}"
    last_x, last_y = pts[-1]
    return (
        f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'aria-hidden="true">'
        f'<polygon points="{area}" fill="{color}" fill-opacity="0.15"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2" fill="{color}"/></svg>'
    )


def _render_kpi_grid(kpis: list, trends: dict | None = None) -> None:
    from dashboard.components.brand import get_theme_vars, get_ns_brand, get_theme, _mix, PRIMARY
    import streamlit.components.v1 as _cv1
    t = get_theme_vars()
    brand = get_ns_brand()
    _theme = get_theme()
    _color = (brand.get("color") or "").strip()

    if _color and _theme == "dark":
        # Derive dark palette from brand primary — same logic as _ns_brand_css()
        _card_bg     = _mix(_color, False, 0.78)              # dark plum surface
        _card_hover  = _mix(_color, False, 0.65)              # slightly lighter for hover
        _card_border = _mix(_color, False, 0.52)              # mid-dark border
        _card_text   = "#FAF8F7"                              # brand ivory
        _card_muted  = (brand.get("accent_color") or "#C8A96E").strip()
        _accent      = _color                                 # brand primary for glow/border
    elif _color:
        # Light mode — brand tokens directly
        _card_bg     = (brand.get("surface_color") or "").strip() or t["SURFACE"]
        _card_hover  = (brand.get("surface2_color") or "").strip() or _mix(_color, True, 0.88)
        _card_border = (brand.get("border_color") or "").strip() or t["BORDER"]
        _card_text   = (brand.get("text_color") or "").strip() or t["TEXT"]
        _card_muted  = (brand.get("text_muted_color") or "").strip() or t["TEXT_MUTED"]
        _accent      = _color
    else:
        # No brand — theme defaults
        _card_bg     = t["SURFACE"]
        _card_hover  = t["SURFACE2"]
        _card_text   = t["TEXT"]
        _card_muted  = t["TEXT_MUTED"]
        _accent      = PRIMARY
        _card_border = f"{PRIMARY if _theme == 'light' else '#5a9e56'}8C"   # thin brand-green outline (~55%)

    _card_fill = _card_bg if _theme == "light" else "transparent"
    cols_per_row = 3
    for row_start in range(0, len(kpis), cols_per_row):
        row_kpis = kpis[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col_idx, (label, value, delta) in enumerate(row_kpis):
            target_page = _KPI_PAGE_MAP.get(label, "")
            _safe = label.replace(" ", "_").replace("-", "_").lower()
            _btn_key = f"kpi_nav_{_safe}"
            delta_html = f'<div class="delta">{delta}</div>' if delta else ""
            _series = ((trends or {}).get("series") or {}).get(_KPI_TREND_KEY.get(label, ""), [])
            spark_html = _sparkline_svg(_series, _accent)
            spark_title = f"{sum(_series)} new in last {len(_series)} days" if spark_html else ""
            cursor = "pointer" if target_page else "default"
            onclick = f"cosClickProxy(window.parent.document,'kpi:{_btn_key}')" if target_page else ""
            with cols[col_idx]:
                _cv1.html(f"""<!DOCTYPE html><html><head>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
body{{background:transparent;padding:0 0 8px 0;}}
.card{{position:relative;background:{_card_fill};border:1px solid {_card_border};border-radius:10px;
       padding:14px 16px;cursor:{cursor};
       transition:border-color 0.15s,box-shadow 0.15s;user-select:none;}}
.card:hover{{border-color:{_accent};box-shadow:0 0 0 2px {_accent}44;}}
.card:active{{background:{_accent}28;}}
.label{{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:0.68rem;color:{_card_muted};font-weight:500;margin-bottom:4px;
        letter-spacing:0.04em;text-transform:uppercase;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.value{{font-size:1.75rem;font-weight:700;color:{_card_text};line-height:1.1;}}
.delta{{font-size:0.72rem;color:#f87171;margin-top:2px;}}
.spark{{position:absolute;right:14px;bottom:12px;}}
</style></head><body><script>{COS_CLICK_PROXY_JS}</script>
<div class="card" onclick="{onclick}" title="{spark_title}">
  {spark_html}
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  {delta_html}
</div>
</body></html>""", height=90, scrolling=False)
                if target_page:
                    # on_click runs at start of next rerun — before sidebar radio instantiated
                    proxy_button(f"kpi:{_btn_key}", key=_btn_key, on_click=_make_nav_cb(target_page))


def render(api_get, api_post, bulk_delete=None):
    role      = st.session_state.get("user_role", "viewer")
    username  = st.session_state.get("username", "")
    user_ns   = st.session_state.get("user_namespace")
    is_scoped = role in ("client", "viewer") and bool(user_ns)
    is_admin  = role in ("admin", "operator")

    ns_brand = st.session_state.get("ns_brand", {})
    hero_title = (ns_brand.get("company_name") or "ClaudeOS") if is_scoped and ns_brand else "ClaudeOS"
    aurora_hero(
        title=hero_title,
        subtitle="AI Operating System — coordination layer for all agents, memory, and workflows.",
        pill="v8.0 · All Systems",
    )
    from dashboard.components.command_palette import search_trigger
    from dashboard.components.brand import get_theme_vars as _gtv
    search_trigger(_gtv())

    if is_scoped:
        _wp = (ns_brand.get("color") or PRIMARY).strip() or PRIMARY
        st.markdown(
            f'<div style="display:inline-flex;align-items:center;gap:8px;'
            f'background:{_wp}1F;border:1px solid {_wp};'
            f'border-radius:8px;padding:6px 14px;margin-bottom:12px;font-size:0.85rem;">'
            f'<span style="color:{_wp};font-weight:700;">Workspace</span>'
            f'<span style="color:inherit;">{_esc(user_ns)}</span></div>',
            unsafe_allow_html=True,
        )

    # Parallel data fetch
    _runs_url = (
        f"/agents/runs?limit=10&namespace={user_ns}" if is_scoped and user_ns
        else "/agents/runs?limit=10"
    )
    # /system/stats MUST be called on the main Streamlit thread — ThreadPoolExecutor
    # workers don't inherit st.session_state, causing JWT to be missing and the
    # dev API key (namespace=global) to be used instead → global counts for clients.
    stats = api_get("/system/stats")
    trends = api_get("/system/trends?days=14")   # main thread too — same session_state/JWT reason

    _calls = {
        "status":     "/system/status",
        "agents":     "/agents?enabled_only=false",
        "runs":       _runs_url,
        "namespaces": "/memory/namespaces",
    }
    results: dict = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(api_get, path): key for key, path in _calls.items()}
        for f in as_completed(futures):
            results[futures[f]] = f.result()

    status      = results.get("status")
    agents_data = results.get("agents")
    runs_data   = results.get("runs")
    counts = stats.get("counts", {}) if stats else {}
    open_tickets = counts.get("open_tickets", 0)

    # KPI grid
    if is_scoped:
        kpis = [
            ("Memory",      counts.get("memory_entries", 0), None),
            ("Agents",      counts.get("agents", 0),         None),
            ("Runs",        counts.get("agent_runs", 0),     None),
            ("Outputs",     counts.get("outputs", 0),        None),
            ("Projects",    counts.get("projects", 0),       None),
            ("Open Tickets",open_tickets, f"{open_tickets} active" if open_tickets else None),
        ]
    else:
        kpis = [
            ("Memory",      counts.get("memory_entries", 0), None),
            ("Agents",      counts.get("agents", 0),         None),
            ("Runs",        counts.get("agent_runs", 0),     None),
            ("Workflows",   counts.get("workflows", 0),      None),
            ("Outputs",     counts.get("outputs", 0),        None),
            ("Open Tickets",open_tickets, f"{open_tickets} active" if open_tickets else None),
        ]
    _render_kpi_grid(kpis, trends if isinstance(trends, dict) else None)

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        if is_admin:
            st.subheader("System Status")
            if status:
                services = status.get("services", {})
                for svc, info in services.items():
                    icon = "[ok]" if info.get("status") == "ok" else "[!]"
                    detail = ""
                    if svc == "database":
                        detail = f"  `{info.get('path','?')}` · {info.get('size_kb',0)} KB"
                    elif svc == "api":
                        detail = f"  port :{info.get('port','?')}"
                    st.markdown(f"{icon} **{svc.upper()}**{detail}")
            else:
                st.error("API unreachable — run `start.ps1`")
                st.code(".\\scripts\\start.ps1", language="powershell")

        # Live activity feed
        _render_live_feed(runs_data, is_scoped, username, api_post)

    with col_right:
        st.subheader("Quick Dispatch")
        if agents_data and agents_data.get("agents"):
            agent_names = [a["name"] for a in agents_data["agents"]]
            selected_agent = st.selectbox("Agent", agent_names, key="quick_agent")

            if is_scoped:
                selected_ns = user_ns
                st.caption(f"Namespace: **{user_ns}**")
            else:
                # Dynamic namespace list from already-fetched /memory/namespaces
                ns_data_q = results.get("namespaces")
                _ns_opts = sorted(ns_data_q["namespaces"].keys()) if ns_data_q and ns_data_q.get("namespaces") else ["global"]
                selected_ns = st.selectbox("Namespace", _ns_opts, key="quick_ns")

            prompt = st.text_area("Prompt", height=100, key="quick_prompt",
                                  placeholder="What should this agent do?")

            if st.button("Run Agent", use_container_width=True):
                if prompt.strip():
                    result = api_post(f"/agents/{selected_agent}/run", {
                        "prompt": prompt,
                        "namespace": selected_ns,
                    })
                    if result:
                        st.success(f"Dispatched! Run ID: `{result.get('run_id','?')[:8]}...`")
                    else:
                        st.error("Dispatch failed — check API logs")
                else:
                    st.warning("Enter a prompt first")

        # Memory breakdown
        ns_data = results.get("namespaces")
        if ns_data and ns_data.get("namespaces"):
            if is_scoped:
                own_cnt = ns_data["namespaces"].get(user_ns, 0)
                st.subheader("Your Memory")
                st.markdown(f"**{user_ns}** — {own_cnt} entries")
            else:
                st.subheader("Memory by Namespace")
                for ns, cnt in sorted(ns_data["namespaces"].items(), key=lambda x: -x[1]):
                    st.markdown(f"**{ns}** — {cnt} entries")

    # Live refresh toggle
    st.markdown("---")
    _render_live_refresh_toggle()


def _render_live_feed(runs_data, is_scoped: bool, username: str, api_post=None) -> None:
    """Live activity feed — auto-refreshes every 8 seconds when live mode is on."""
    from dashboard.components.brand import get_theme_vars as _tv, get_ns_brand, get_theme, _mix
    _t = _tv()
    _brand = get_ns_brand()
    _theme = get_theme()
    if _brand and (_bc := (_brand.get("color") or "").strip()):
        if _theme == "dark":
            _muted  = (_brand.get("accent_color") or "#D4859A").strip()
            _surf2  = _mix(_bc, False, 0.70)
            _txt    = "#FAF8F7"
            _brd    = _mix(_bc, False, 0.52)
        else:
            _muted  = (_brand.get("text_muted_color") or _t["TEXT_MUTED"]).strip()
            _surf2  = (_brand.get("surface2_color")   or _t["SURFACE2"]).strip()
            _txt    = (_brand.get("text_color")        or _t["TEXT"]).strip()
            _brd    = (_brand.get("border_color")      or _t["BORDER"]).strip()
    else:
        _muted, _surf2, _txt, _brd = _t["TEXT_MUTED"], _t["SURFACE2"], _t["TEXT"], _t["BORDER"]

    col_title, col_toggle = st.columns([3, 1])
    with col_title:
        st.subheader("Live Activity")
    with col_toggle:
        live_on = st.toggle("Auto-refresh", value=st.session_state.get("live_mode", False),
                            key="live_toggle")
        st.session_state["live_mode"] = live_on

    runs = (runs_data or {}).get("runs", [])

    # Error alert strip
    recent_errors = [r for r in runs[:5] if r.get("status") == "failed"]
    if recent_errors:
        st.markdown(
            f'<div style="background:#ef444422;border:1px solid #ef4444;border-radius:8px;'
            f'padding:8px 14px;margin-bottom:8px;font-size:0.82rem;color:#ef4444;">'
            f'{len(recent_errors)} recent failure{"s" if len(recent_errors)>1 else ""} — '
            f'check run history</div>',
            unsafe_allow_html=True,
        )

    # Running now indicator
    running_now = [r for r in runs if r.get("status") in ("running", "pending")]
    if running_now:
        st.markdown(
            f'<div style="background:#f59e0b22;border:1px solid #f59e0b;border-radius:8px;'
            f'padding:6px 14px;margin-bottom:8px;font-size:0.82rem;color:#f59e0b;">'
            f'{len(running_now)} agent{"s" if len(running_now)>1 else ""} running now</div>',
            unsafe_allow_html=True,
        )

    if runs:
        st.markdown("""<style>
[data-testid="stVerticalBlock"] [data-testid="stMarkdownContainer"] > div { border-bottom: none !important; }
[data-testid="stHorizontalBlock"] { border-bottom: none !important; }
</style>""", unsafe_allow_html=True)
        feed_placeholder = st.empty()
        with feed_placeholder.container():
            for run in runs[:10]:
                _status = run.get("status", "?")
                _run_id = run.get("id", "")
                _icon = {"done": "done", "failed": "failed", "running": "running", "pending": "pending"}.get(_status, "•")
                _agent = _esc(run.get("agent_name") or run.get("agent_display_name") or (run.get("agent_id") or "")[:12])
                _ns    = _esc(run.get("namespace", "global"))
                _raw   = run.get("created_at", "")
                eval_score = run.get("eval_score")
                score_pill = ""
                if eval_score is not None:
                    sc_color = "#5a9e56" if eval_score >= 4 else ("#f59e0b" if eval_score >= 2.5 else "#ef4444")
                    score_pill = f'<span style="background:{sc_color}22;color:{sc_color};border:1px solid {sc_color}44;padding:1px 6px;border-radius:8px;font-size:0.7rem;">{eval_score:.1f}</span>'
                try:
                    _parsed = datetime.fromisoformat(_raw.replace("Z", "+00:00"))
                    if _parsed.tzinfo is None:
                        _parsed = _parsed.replace(tzinfo=timezone.utc)
                    _local = _parsed.astimezone(_DISPLAY_TZ)
                    _created = f"{_local.day} {_local.strftime('%b')} · {_local.strftime('%H:%M')}"
                except Exception:
                    _created = _raw[:16]
                _ns_part = "" if is_scoped else f'<span style="color:{_muted};font-size:0.75rem;"> · {_ns}</span>'
                _color = {"done": "#5a9e56", "failed": "#ef4444", "running": "#f59e0b", "pending": "#6b7280"}.get(_status, "#6b7280")
                _pill = f"background:{_surf2};color:{_txt};padding:1px 6px;border-radius:4px;font-size:0.78rem;font-family:monospace;"
                if _status == "failed" and _run_id:
                    _col_main, _col_btn = st.columns([10, 1])
                    with _col_main:
                        st.markdown(
                            f'<div style="padding:7px 0;font-size:0.82rem;">'
                            f'<span style="color:{_color};font-weight:600;">{_icon} {_status}</span>'
                            f'&nbsp;&nbsp;·&nbsp;&nbsp;<span style="{_pill}">{_agent}</span>{_ns_part}'
                            f'&nbsp;&nbsp;{score_pill}'
                            f'&nbsp;&nbsp;&nbsp;<span style="color:{_muted};font-size:0.75rem;">{_created}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with _col_btn:
                        _confirm_key = f"confirm_del_{_run_id}"
                        if st.session_state.get(_confirm_key):
                            if st.button("OK", key=f"del_confirm_{_run_id}", help="Confirm delete"):
                                resp = api_post(f"/agents/runs/{_run_id}", method="DELETE")
                                st.session_state.pop(_confirm_key, None)
                                if resp is not None:
                                    st.rerun()
                                else:
                                    st.error("Delete failed")
                        else:
                            if st.button("Del", key=f"del_run_{_run_id}", help="Delete this failed run"):
                                st.session_state[_confirm_key] = True
                                st.rerun()
                else:
                    st.markdown(
                        f'<div style="padding:7px 0;font-size:0.82rem;">'
                        f'<span style="color:{_color};font-weight:600;">{_icon} {_status}</span>'
                        f'&nbsp;&nbsp;·&nbsp;&nbsp;<span style="{_pill}">{_agent}</span>{_ns_part}'
                        f'&nbsp;&nbsp;{score_pill}'
                        f'&nbsp;&nbsp;&nbsp;<span style="color:{_muted};font-size:0.75rem;">{_created}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        from dashboard.components.brand import empty_state
        empty_state(
            icon="◈",
            title=f"Welcome, {username}!",
            body="No agent runs yet. Use Quick Dispatch on the right or go to Agents → Chat.",
        )

    if live_on:
        # st.fragment(run_every=8) fires from JS every 8s — no thread blocking
        @st.fragment(run_every=8)
        def _live_ticker():
            st.rerun(scope="app")
        _live_ticker()


def _render_live_refresh_toggle() -> None:
    """Token burn rate mini-chart."""
    from dashboard.components.brand import get_theme_vars, get_ns_brand, get_theme
    t = get_theme_vars()
    brand = get_ns_brand()
    theme = get_theme()
    _color = (brand.get("color") or "").strip()
    if _color:
        # Use brand muted (accent in dark, text_muted in light) — avoid inheriting green
        if theme == "dark":
            _muted = (brand.get("accent_color") or "#C8A96E").strip()
        else:
            _muted = (brand.get("text_muted_color") or "#4A4A4C").strip()
    else:
        _muted = t["TEXT_MUTED"]
    st.markdown(
        f'<div style="color:{_muted};font-size:0.75rem;text-align:center;">'
        f'Auto-refresh: toggle "Live Activity" above · Quality scores powered by LLM-as-Judge</div>',
        unsafe_allow_html=True,
    )
