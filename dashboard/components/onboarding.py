"""First-login onboarding walkthrough — full-page takeover per slide.

Each slide occupies the ENTIRE page. Nothing else renders until the user
clicks through (or skips). Uses st.stop() to block the rest of app.py.

Only shown for client/viewer roles, once ever (persisted to DB).
"""
import os
import requests
import streamlit as st

_FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
_API_BASE = f"http://localhost:{_FLASK_PORT}/api/v1"


def _persist_onboarding_done() -> None:
    """Mark onboarding complete in the DB so it never shows again after re-login."""
    token = st.session_state.get("jwt_token", "")
    if not token:
        return
    try:
        requests.post(
            f"{_API_BASE}/auth/onboarding-done",
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
    except Exception:
        pass
from dashboard.components.brand import get_theme_vars, get_ns_brand, PRIMARY, ACCENT

_SLIDES = [
    {
        "icon": "",
        "step_label": "Welcome",
        "title": "Welcome to your AI Workspace",
        "body": (
            "Your intelligent workspace is now active. Over the next 4 steps, "
            "this tour will walk you through the 4 key areas you'll use every day.\n\n"
            "**Read each step carefully** — by the end you'll know exactly where to go "
            "and what each section does for your business."
        ),
        "action": None,
        "tip": None,
    },
    {
        "icon": "◈",
        "step_label": "Agents",
        "title": "Step 1 — Chat with AI Agents",
        "body": (
            "Go to **Agents → Chat** in the left sidebar to talk with AI agents "
            "built specifically for your business.\n\n"
            "You can:\n"
            "- Ask business questions and get instant answers\n"
            "- Generate reports, emails, summaries, and content\n"
            "- Upload images or screenshots for analysis\n"
            "- Have multi-turn conversations (the agent remembers what you said)"
        ),
        "action": "After this tour → click **Agents** in the sidebar, then **Chat** tab.",
        "tip": "Agents remember context from your Memory page — the more context you store, the smarter they respond.",
    },
    {
        "icon": "◉",
        "step_label": "Memory",
        "title": "Step 2 — Your AI Memory Bank",
        "body": (
            "Go to **Memory** in the sidebar. This is where you store important facts "
            "your agents will automatically use when answering.\n\n"
            "Examples of what to add:\n"
            "- Your business name, location, services, pricing\n"
            "- Key clients and their preferences\n"
            "- Standard operating procedures or policies\n"
            "- Any context you want agents to always know"
        ),
        "action": "After this tour → go to **Memory → Add Entry** and add at least one fact about your business.",
        "tip": "Well-structured memory reduces AI costs by up to 40% by cutting down on repeated context.",
    },
    {
        "icon": "",
        "step_label": "Tickets",
        "title": "Step 3 — Support Tickets",
        "body": (
            "Go to **Tickets** in the sidebar whenever you need help or have a request.\n\n"
            "How it works:\n"
            "1. Click **New Ticket** and describe your issue or request\n"
            "2. Choose a priority (P1 = urgent, P4 = low)\n"
            "3. The support team is notified by email automatically\n"
            "4. You'll be emailed when your ticket is resolved\n\n"
            "**SLA guarantees:** P1 = 4h · P2 = 8h · P3 = 24h · P4 = 72h"
        ),
        "action": "After this tour → go to **Tickets** to see any open issues or create your first ticket.",
        "tip": None,
    },
    {
        "icon": "",
        "step_label": "Usage",
        "title": "Step 4 — Your Usage Dashboard",
        "body": (
            "Go to **Usage** in the sidebar to see how your AI workspace is performing.\n\n"
            "What you'll see:\n"
            "- **AI runs** and estimated cost for the last 30 days\n"
            "- **Namespace Pulse Score** — a 0–100 health score for your workspace\n"
            "- Recent agent activity with quality scores\n"
            "- Memory freshness and consolidation status\n\n"
            "The Pulse Score combines: quality (40%) + ticket resolution (30%) + "
            "memory freshness (20%) + workflow health (10%)."
        ),
        "action": "After this tour → check your **Usage** page to see your current Pulse Score.",
        "tip": "A Pulse Score above 75 means your AI workspace is running optimally.",
    },
]

_TOTAL = len(_SLIDES)


def maybe_show_onboarding(role: str) -> None:
    """Call after auth gate. If active, renders full-page slide and calls st.stop()."""
    if role not in ("client", "viewer"):
        return
    # Allow explicit replay via sidebar "Show Setup Tour" button
    _force = st.session_state.pop("show_onboarding", False)
    if _force:
        # Reset slide counter so tour restarts from slide 0
        st.session_state["_onboarding_slide"] = 0
    elif st.session_state.get("_onboarding_done"):
        return
    _render_slide()
    st.stop()  # nothing else on the page renders until tour is done


def _render_slide() -> None:
    t = get_theme_vars()
    brand = get_ns_brand()
    _p = (brand.get("color") or PRIMARY).strip() or PRIMARY
    _a = (brand.get("accent_color") or ACCENT).strip() or ACCENT
    company = (brand.get("company_name") or "").strip()
    icon_ns = (brand.get("icon") or "").strip()

    slide_idx = st.session_state.get("_onboarding_slide", 0)
    slide = _SLIDES[slide_idx]
    is_last = slide_idx == _TOTAL - 1

    # ── Header ────────────────────────────────────────────────────────────────
    if company:
        st.markdown(
            f'<div style="text-align:center;padding:12px 0 4px;">'
            f'<span style="font-size:1.1rem;font-weight:800;color:{_p};">'
            f'{icon_ns + " " if icon_ns else ""}{company}</span>'
            f'<span style="font-size:0.65rem;color:{t["TEXT_MUTED"]};margin-left:8px;'
            f'letter-spacing:1px;">POWERED BY CLAUDEOS</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="text-align:center;padding:12px 0 4px;">'
            f'<span style="font-size:1.1rem;font-weight:800;color:{_p};letter-spacing:2px;">'
            f'CLAUDE<span style="color:{_a};">OS</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Progress bar + step label ─────────────────────────────────────────────
    st.progress((slide_idx + 1) / _TOTAL)

    _step_labels = [s["step_label"] for s in _SLIDES]
    _dot_row = ""
    for i, lbl in enumerate(_step_labels):
        _active = i == slide_idx
        _done = i < slide_idx
        _dot_color = _p if _active else ("#5a9e56" if _done else t["BORDER"])
        _txt_color = _p if _active else (t["TEXT_MUTED"])
        _weight = "700" if _active else "400"
        _dot_row += (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1;">'
            f'<div style="width:10px;height:10px;border-radius:50%;background:{_dot_color};'
            f'{"box-shadow:0 0 0 3px " + _p + "44;" if _active else ""}"></div>'
            f'<span style="font-size:0.65rem;color:{_txt_color};font-weight:{_weight};'
            f'white-space:nowrap;">{lbl}</span>'
            f'</div>'
        )
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'padding:8px 0 4px;margin-bottom:4px;">{_dot_row}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Slide content ─────────────────────────────────────────────────────────
    _, col_content, _ = st.columns([1, 4, 1])
    with col_content:
        st.markdown(
            f'<div style="text-align:center;padding:8px 0 16px;">'
            f'<span style="font-size:3.5rem;">{slide["icon"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<h2 style="text-align:center;color:{t["TEXT"]};font-size:1.5rem;'
            f'font-weight:800;margin-bottom:20px;">{slide["title"]}</h2>',
            unsafe_allow_html=True,
        )

        # Body text (supports markdown)
        st.markdown(slide["body"])

        # Action callout
        if slide["action"]:
            st.markdown(
                f'<div style="background:{_p}18;border-left:4px solid {_p};'
                f'border-radius:0 8px 8px 0;padding:12px 16px;margin:20px 0 0;'
                f'font-size:0.88rem;color:{t["TEXT"]};">'
                f'<strong style="color:{_p};">What to do next:</strong><br>'
                f'{slide["action"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Tip
        if slide["tip"]:
            st.markdown(
                f'<div style="background:{t["SURFACE2"]};border:1px solid {t["BORDER"]};'
                f'border-radius:8px;padding:10px 14px;margin-top:16px;'
                f'font-size:0.8rem;color:{t["TEXT_MUTED"]};font-style:italic;">'
                f'{slide["tip"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="text-align:center;color:{t["TEXT_MUTED"]};font-size:0.8rem;'
        f'margin-bottom:12px;">Step {slide_idx + 1} of {_TOTAL}</div>',
        unsafe_allow_html=True,
    )

    col_skip, col_prev, col_spacer, col_next = st.columns([2, 1, 2, 2])

    with col_skip:
        if st.button("Skip tour", key="_ob_skip", use_container_width=True):
            _persist_onboarding_done()
            st.session_state["_onboarding_done"] = True
            st.session_state.pop("_onboarding_slide", None)
            st.rerun()

    with col_prev:
        if slide_idx > 0:
            if st.button("← Back", key="_ob_prev", use_container_width=True):
                st.session_state["_onboarding_slide"] = slide_idx - 1
                st.rerun()

    with col_next:
        label = "Enter Dashboard →" if is_last else f"Next: {_SLIDES[slide_idx + 1]['step_label']} →"
        if st.button(label, key="_ob_next", use_container_width=True, type="primary"):
            if is_last:
                _persist_onboarding_done()
                st.session_state["_onboarding_done"] = True
                st.session_state.pop("_onboarding_slide", None)
            else:
                st.session_state["_onboarding_slide"] = slide_idx + 1
            st.rerun()
