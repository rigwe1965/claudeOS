"""Client Usage Dashboard — Namespace Pulse Score + AI activity metrics.

Visible to client/viewer roles only. Shows:
- AI Activity Summary (tokens, cost, runs, outputs)
- Namespace Pulse Score (composite 0–100)
- Recent activity feed
- Memory summary
"""
import streamlit as st
from dashboard.components.brand import aurora_hero, get_theme_vars, get_ns_brand, _mix, get_theme


def render(api_get, api_post, bulk_delete=None):
    ns = st.session_state.get("user_namespace")
    role = st.session_state.get("user_role", "viewer")

    # Admins/operators use Observability page — this page is client-only
    if role in ("admin", "operator"):
        st.info("Admins: use the **Observability** page for full system metrics.")
        return

    brand = get_ns_brand()
    company = (brand.get("company_name") or ns or "Your Workspace").strip()
    aurora_hero(
        title=company,
        subtitle="AI usage analytics — costs, quality, and workspace health.",
        pill="Usage · Last 30 days",
    )

    if not ns:
        st.warning("No namespace assigned to your account. Contact your admin.")
        return

    data = api_get(f"/system/namespace-stats?namespace={ns}")
    if not data:
        st.error("Could not load usage data — API may be offline.")
        return

    t = get_theme_vars()

    # Brand-aware color overrides — replace ClaudeOS green surfaces for namespace clients
    _brand_color = (brand.get("color") or "").strip()
    _is_dark = (get_theme() == "dark")
    if _brand_color:
        _done_color   = _brand_color
        _card_surface = _mix(_brand_color, False, 0.78) if _is_dark else (brand.get("surface_color") or "").strip() or t["SURFACE"]
        _card_border  = _mix(_brand_color, False, 0.52) if _is_dark else (brand.get("border_color") or "").strip() or t["BORDER"]
        _surface2     = _mix(_brand_color, False, 0.72) if _is_dark else (brand.get("surface2_color") or "").strip() or t["SURFACE"]
        _text         = "#FAF8F7" if _is_dark else (brand.get("text_color") or "").strip() or t["TEXT"]
        _text_muted   = (brand.get("accent_color") or "#C8A96E").strip() if _is_dark else (brand.get("text_muted_color") or "").strip() or t["TEXT_MUTED"]
    else:
        _done_color   = "#5a9e56"
        _card_surface = t["SURFACE"]
        _card_border  = t["BORDER"]
        _surface2     = t.get("SURFACE2", t["SURFACE"])
        _text         = t["TEXT"]
        _text_muted   = t["TEXT_MUTED"]

    # ── KPI row ──────────────────────────────────────────────────────────────
    tok_in  = data.get("tokens_in", 0)
    tok_out = data.get("tokens_out", 0)
    cost    = data.get("cost_usd", 0.0)
    runs    = data.get("run_count", 0)
    outputs = data.get("output_count", 0)
    eval_avg = data.get("eval_avg", 0.0)

    kpis = [
        ("AI Runs (30d)",    runs,                          None),
        ("Tokens In",        f"{tok_in:,}",                 None),
        ("Tokens Out",       f"{tok_out:,}",                None),
        ("Est. Cost",        f"${cost:.3f}",                f"USD · {data.get('model_label') or 'est.'}"),
        ("Avg Quality",      f"{eval_avg:.1f}/5",           None),
        ("Outputs",          outputs,                       None),
    ]
    cards = ""
    for label, value, delta in kpis:
        d = (f'<div style="font-size:0.7rem;color:{_text_muted};margin-top:2px;">{delta}</div>'
             if delta else "")
        cards += (
            f'<div style="background:{_card_surface};border:1px solid {_card_border};'
            f'border-radius:10px;padding:14px 16px;min-width:0;">'
            f'<div style="font-size:0.78rem;color:{_text_muted};font-weight:500;'
            f'margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
            f'<div style="font-size:1.9rem;font-weight:700;color:{_text};line-height:1.1;">{value}</div>'
            f'{d}</div>'
        )
    st.markdown(f'<div class="cos-kpi-grid">{cards}</div>', unsafe_allow_html=True)

    st.markdown("---")

    col_pulse, col_feed = st.columns([1, 2])

    # ── Namespace Pulse Score ─────────────────────────────────────────────────
    with col_pulse:
        st.subheader("Namespace Pulse")
        pulse = data.get("pulse_score", 0.0)
        _no_data = runs == 0 and data.get("memory_count", 0) == 0
        _pulse_color = (
            "#6b7280" if _no_data
            else (_done_color if pulse >= 75 else ("#f59e0b" if pulse >= 50 else "#ef4444"))
        )
        _pulse_label = (
            "Getting Started" if _no_data
            else ("Excellent" if pulse >= 85
                  else ("Good" if pulse >= 70 else ("Fair" if pulse >= 50 else "Needs Attention")))
        )

        # Circular gauge (pure HTML/CSS — no chart lib)
        _radius = 54
        _circ   = 2 * 3.14159 * _radius
        _dash   = _circ * (pulse / 100)
        _gap    = _circ - _dash
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'padding:16px 0 8px;">'
            f'<svg width="140" height="140" viewBox="0 0 140 140">'
            f'<circle cx="70" cy="70" r="{_radius}" fill="none" '
            f'stroke="{t["BORDER"]}" stroke-width="12"/>'
            f'<circle cx="70" cy="70" r="{_radius}" fill="none" '
            f'stroke="{_pulse_color}" stroke-width="12" '
            f'stroke-dasharray="{_dash:.1f} {_gap:.1f}" '
            f'stroke-dashoffset="{_circ * 0.25:.1f}" stroke-linecap="round"/>'
            f'<text x="70" y="66" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="22" font-weight="800" fill="{_text}" '
            f'font-family="Inter,sans-serif">{pulse:.0f}</text>'
            f'<text x="70" y="84" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="10" fill="{_text_muted}" font-family="Inter,sans-serif">/ 100</text>'
            f'</svg>'
            f'<div style="font-size:0.95rem;font-weight:700;color:{_text};'
            f'margin-top:4px;">{_pulse_label}</div>'
            f'<div style="font-size:0.72rem;color:{_text_muted};margin-top:2px;'
            f'text-align:center;">Composite workspace health</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Score breakdown
        t_total  = data.get("ticket_total", 0)
        t_closed = data.get("tickets_closed", 0)
        m_total  = data.get("memory_count", 0)
        m_fresh  = data.get("memory_fresh", 0)
        wf_total = data.get("workflow_total", 0)
        wf_ok    = data.get("workflow_ok", 0)

        _dims = [
            ("Quality Score",  f"{eval_avg:.1f}/5",           "40%",
             "Average eval rating of agent responses (scored 0–5 by AI judge)"),
            ("Ticket Resolve", f"{t_closed}/{t_total}",        "30%",
             "Closed tickets ÷ total tickets. Raise by resolving open tickets."),
            ("Memory Fresh",   f"{m_fresh}/{m_total} entries", "20%",
             "Memory entries updated in the last 7 days. Add facts to raise this."),
            ("Workflow OK",    f"{wf_ok}/{wf_total} runs",     "10%",
             "Successful workflow runs this week. Fix failing workflows to improve."),
        ]
        for dim, val, weight, tip in _dims:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;padding:3px 0;font-size:0.78rem;" title="{tip}">'
                f'<span style="color:{_text_muted};">{dim} ℹ</span>'
                f'<span style="color:{_text};font-weight:600;">{val}</span>'
                f'<span style="color:{_text_muted};font-size:0.68rem;">{weight}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with st.expander("How is Pulse Score calculated?", expanded=False):
            st.markdown(
                f"""**Pulse Score** is a composite 0–100 health number for your workspace:

| Dimension | Weight | How to improve |
|-----------|--------|----------------|
| Quality Score | 40% | Use agents for complex tasks; provide clear, detailed prompts |
| Ticket Resolution | 30% | Resolve or close open tickets |
| Memory Freshness | 20% | Add or update facts in **Memory** page |
| Workflow Health | 10% | Check **Workflows** for failing pipelines |

A score ≥ 75 is **Excellent**. Below 50 means attention needed in one or more areas."""
            )

        # ── Actionable alerts when score is low ──────────────────────────────
        if not _no_data and pulse < 60:
            # Each entry: (label, description, nav_page_key)
            _actions = []
            if eval_avg < 3.5:
                _actions.append(("Low agent quality", "Provide more context in your prompts.", "Agents"))
            if t_total > 0 and t_closed < t_total:
                _unresolved = t_total - t_closed
                _actions.append((f"{_unresolved} open ticket{'s' if _unresolved != 1 else ''}", "Resolve or close open tickets.", "Tickets"))
            if m_total == 0 or (m_total > 0 and m_fresh == 0):
                _actions.append(("Stale memory", "Add business facts so agents have context.", "Memory"))
            if wf_total > 0 and wf_ok < wf_total:
                _actions.append(("Workflow failures", "Check pipeline errors and fix failing steps.", "Workflows"))

            if _actions:
                st.markdown(
                    f'<div style="background:#ef444418;border:1px solid #ef444444;'
                    f'border-radius:8px;padding:10px 14px;margin-top:10px;">'
                    f'<div style="font-size:0.78rem;font-weight:700;color:#ef4444;margin-bottom:6px;">'
                    f'Action needed to raise Pulse Score</div></div>',
                    unsafe_allow_html=True,
                )
                for _lbl, _desc, _page in _actions:
                    _ac1, _ac2 = st.columns([4, 1])
                    _ac1.markdown(
                        f'<div style="font-size:0.75rem;color:{_text};padding:2px 0;">'
                        f'· <b>{_lbl}</b>: {_desc}</div>',
                        unsafe_allow_html=True,
                    )
                    if _ac2.button(f"Go →", key=f"_action_{_page}", use_container_width=True):
                        st.session_state["nav_page"] = _page
                        st.rerun()

    # ── Recent Activity Feed ──────────────────────────────────────────────────
    with col_feed:
        st.subheader("Recent AI Activity")
        recent = data.get("recent_runs", [])
        if recent:
            for run in recent:
                _status = run.get("status", "?")
                _icon_map = {"done": "done", "failed": "failed", "running": "running", "pending": "pending"}
                _icon_r = _icon_map.get(_status, "•")
                _color_map = {"done": _done_color, "failed": "#ef4444",
                              "running": "#f59e0b", "pending": "#6b7280"}
                _col = _color_map.get(_status, "#6b7280")
                _agent = (run.get("agent_id") or "")[:14]
                _raw = run.get("created_at", "")
                _dur = run.get("duration_ms")
                _es  = run.get("eval_score")

                try:
                    from datetime import datetime as _dt
                    _p = _dt.fromisoformat(_raw.replace("Z", ""))
                    _ts = f"{_p.day} {_p.strftime('%b')} · {_p.strftime('%H:%M')}"
                except Exception:
                    _ts = _raw[:16]

                _dur_str = f"{_dur / 1000:.1f}s" if _dur else ""
                _score_pill = ""
                if _es is not None:
                    _sc = _done_color if _es >= 4 else ("#f59e0b" if _es >= 2.5 else "#ef4444")
                    _score_pill = (
                        f'<span style="background:{_sc}22;color:{_sc};border:1px solid {_sc}44;'
                        f'padding:1px 6px;border-radius:8px;font-size:0.7rem;">{_es:.1f}</span>'
                    )
                _pill = (
                    f'background:{_surface2};color:{_text};'
                    f'padding:1px 6px;border-radius:4px;font-size:0.78rem;font-family:monospace;'
                )
                st.markdown(
                    f'<div style="padding:7px 0;font-size:0.82rem;'
                    f'border-bottom:1px solid {_card_border};">'
                    f'<span style="color:{_col};font-weight:600;">{_icon_r} {_status}</span>'
                    f'&nbsp;·&nbsp;<span style="{_pill}">{_agent}</span>'
                    f'&nbsp;{_score_pill}'
                    f'<span style="float:right;color:{_text_muted};font-size:0.75rem;">'
                    f'{_ts}{(" · " + _dur_str) if _dur_str else ""}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No AI runs yet. Use **Agents → Chat** to get started.")

        # Memory summary
        st.markdown("---")
        st.subheader("Memory Summary")
        last_cons = data.get("last_consolidated")
        _cons_str = last_cons[:10] if last_cons else "Never"
        st.markdown(
            f'<div style="display:flex;gap:24px;flex-wrap:wrap;">'
            f'<div style="text-align:center;">'
            f'<div style="font-size:1.6rem;font-weight:700;color:{_text};">{m_total}</div>'
            f'<div style="font-size:0.75rem;color:{_text_muted};">Total Entries</div>'
            f'</div>'
            f'<div style="text-align:center;">'
            f'<div style="font-size:1.6rem;font-weight:700;color:{_done_color};">{m_fresh}</div>'
            f'<div style="font-size:0.75rem;color:{_text_muted};">Fresh (7d)</div>'
            f'</div>'
            f'<div style="text-align:center;">'
            f'<div style="font-size:1rem;font-weight:600;color:{_text_muted};">{_cons_str}</div>'
            f'<div style="font-size:0.75rem;color:{_text_muted};">Last Consolidated</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
