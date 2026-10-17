"""Login and register form — rendered before dashboard when not authenticated."""
from __future__ import annotations

import os
from html import escape as _esc

import requests
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")
_FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
_API_BASE = f"http://127.0.0.1:{_FLASK_PORT}/api/v1"


def render_login() -> None:
    """Render a single unified login card (brand header + form in one box)."""
    from dashboard.components.brand import get_theme_vars, PRIMARY, get_theme

    t = get_theme_vars()
    is_dark = get_theme() == "dark"

    # ── Wrapper CSS: hide Streamlit padding, centre card ────────────────────
    st.markdown(f"""
<style>
/* Full-bleed layout reset for login page */
.main .block-container {{
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
}}
/* Card shell */
.cos-login-card {{
    background: {t['SURFACE']};
    border: 1px solid {t['BORDER']};
    border-radius: 16px;
    padding: 40px 44px 36px;
    box-shadow: 0 4px 32px rgba(0,0,0,{'.45' if is_dark else '.10'});
    margin-top: 60px;
}}
/* Brand block inside card */
.cos-brand-pill {{
    display: inline-block;
    background: transparent;
    border: 1px solid {PRIMARY};
    color: {PRIMARY};
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 12px;
    letter-spacing: 0.06em;
    margin-bottom: 18px;
}}
.cos-brand-title {{
    font-size: 2rem;
    font-weight: 800;
    color: {t['TEXT']};
    letter-spacing: 1px;
    line-height: 1.1;
    margin-bottom: 6px;
}}
.cos-brand-sub {{
    font-size: 0.9rem;
    color: {t['TEXT_MUTED']};
    margin-bottom: 28px;
}}
.cos-divider {{
    border: none;
    border-top: 1px solid {t['BORDER']};
    margin: 0 0 24px;
}}
.cos-footer {{
    text-align: center;
    font-size: 0.72rem;
    color: {t['TEXT_MUTED']};
    margin-top: 20px;
}}
</style>
""", unsafe_allow_html=True)

    # ── Centred column ───────────────────────────────────────────────────────
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        # Open card
        st.markdown(f"""
<div class="cos-login-card">
  <div class="cos-brand-pill">Sign in to continue</div>
  <div class="cos-brand-title">ClaudeOS</div>
  <div class="cos-brand-sub">AI Operating System</div>
  <hr class="cos-divider">
</div>
""", unsafe_allow_html=True)

        # Streamlit tabs + form rendered inside same visual column
        # (card background bleeds through via same column; we use CSS padding match)
        with st.container():
            st.markdown(f"""
<style>
/* Give the tab+form area the card look so it merges visually */
section[data-testid="stVerticalBlock"] > div:last-child {{
    background: {t['SURFACE']};
    border: 1px solid {t['BORDER']};
    border-top: none;
    border-radius: 0 0 16px 16px;
    padding: 0 44px 36px;
    margin-top: -18px;
    box-shadow: 0 4px 32px rgba(0,0,0,{'.45' if is_dark else '.10'});
}}
</style>
""", unsafe_allow_html=True)

            tab_login, tab_register, tab_reset = st.tabs(["Sign In", "Register", "Forgot Password"])

            with tab_login:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                with st.form("login_form", border=False):
                    username = st.text_input("Username", key="li_username", placeholder="your username")
                    password = st.text_input("Password", type="password", key="li_password")
                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                    if st.form_submit_button("Sign In", type="primary", use_container_width=True):
                        _do_login(username.strip(), password)

            with tab_register:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.caption("Create a client account for your namespace.")
                r_username  = st.text_input("Username", key="reg_username")
                r_email     = st.text_input("Email (optional)", key="reg_email")
                r_password  = st.text_input("Password", type="password", key="reg_password")
                r_password2 = st.text_input("Confirm password", type="password", key="reg_password2")

                # /namespaces requires auth — use text input instead of dropdown
                r_namespace = st.text_input(
                    "Namespace slug",
                    key="reg_ns",
                    placeholder="e.g. reci-transport",
                    help="Your admin will give you this slug. It's the unique ID for your workspace.",
                )
                st.caption("Ask your administrator for your exact namespace slug before registering.")
                st.markdown("<div style='4px'></div>", unsafe_allow_html=True)
                if st.button("Create Account", use_container_width=True, key="reg_btn"):
                    if not r_namespace.strip():
                        st.error("Namespace slug required — contact your admin to get it.")
                    else:
                        _do_register(r_username.strip(), r_email.strip(), r_password, r_password2, r_namespace.strip())

            with tab_reset:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.info(
                    "To reset your password, contact your administrator. "
                    "They will generate a reset token and share it with you securely."
                )
                st.markdown("---")
                st.caption("Enter the token your admin gave you + your new password.")
                fp_token  = st.text_input("Reset token", key="fp_token")
                fp_newpw  = st.text_input("New password", type="password", key="fp_newpw",
                                          help="Min 10 chars · upper + lower + digit")
                fp_newpw2 = st.text_input("Confirm new password", type="password", key="fp_newpw2")
                if st.button("Reset Password", type="primary", use_container_width=True, key="fp_reset_btn"):
                    _do_reset_password(fp_token.strip(), fp_newpw, fp_newpw2)

            st.markdown(
                f"<div class='cos-footer'>ClaudeOS · Secure access</div>",
                unsafe_allow_html=True,
            )


# ── Internal ─────────────────────────────────────────────────────────────────

def _do_reset_password(token: str, new_pw: str, new_pw2: str) -> None:
    if not token or not new_pw:
        st.warning("Token and new password required.")
        return
    if new_pw != new_pw2:
        st.error("Passwords do not match.")
        return
    try:
        r = requests.post(
            f"{_API_BASE}/auth/reset-password",
            json={"reset_token": token, "new_password": new_pw},
            timeout=5,
        )
        if r.ok:
            st.success("Password reset! Go to Sign In to log in.")
        elif r.status_code == 401:
            st.error("Invalid or expired reset token.")
        elif r.status_code == 422:
            st.error(r.json().get("error", "Password too weak."))
        else:
            st.error(r.json().get("error", f"Failed ({r.status_code})."))
    except Exception:
        st.error("Cannot reach API server.")


def _do_login(username: str, password: str) -> None:
    if not username or not password:
        st.warning("Enter username and password.")
        return
    try:
        r = requests.post(
            f"{_API_BASE}/auth/login",
            json={"username": username, "password": password},
            timeout=5,
        )
    except Exception:
        st.error("Cannot reach API server. Is it running?")
        return

    if r.status_code == 401:
        st.error("Invalid username or password.")
    elif r.status_code == 423:
        secs = r.json().get("retry_after_seconds", 900)
        st.error(f"Account locked. Try again in {secs // 60} min {secs % 60}s.")
    elif r.status_code == 403:
        st.error("Account disabled. Contact your administrator.")
    elif r.status_code == 429:
        st.warning("Too many attempts. Wait a minute and try again.")
    elif r.ok:
        data = r.json()
        user = data["user"]
        st.session_state["jwt_token"]           = data["access_token"]
        st.session_state["refresh_token"]       = data["refresh_token"]
        st.session_state["user_id"]             = user["id"]
        st.session_state["username"]            = user["username"]
        st.session_state["user_role"]           = user["role"]
        st.session_state["user_namespace"]       = user.get("namespace")
        st.session_state["must_change_password"] = data.get("must_change_password", False)
        st.session_state["_onboarding_done"]     = bool(user.get("onboarding_done", False))
        # Persist session to Flask store — key in URL survives page refresh
        try:
            _sr = requests.post(
                f"{_API_BASE}/auth/session",
                json={"refresh_token": data["refresh_token"]},
                headers={"Authorization": f"Bearer {data['access_token']}"},
                timeout=3,
            )
            if _sr.ok:
                st.query_params["_s"] = _sr.json()["session_key"]
        except Exception:
            pass  # non-fatal — user just won't survive page refresh this session
        st.rerun()
    else:
        st.error(f"Login failed ({r.status_code}).")


def _do_register(username: str, email: str, password: str, password2: str, namespace: str) -> None:
    if not username or not password:
        st.warning("Username and password required.")
        return
    if password != password2:
        st.error("Passwords do not match.")
        return
    if not namespace or namespace == "— API offline —":
        st.warning("Select a valid namespace.")
        return
    try:
        r = requests.post(
            f"{_API_BASE}/auth/register",
            json={"username": username, "email": email or None, "password": password, "namespace": namespace},
            timeout=5,
        )
    except Exception:
        st.error("Cannot reach API server.")
        return

    if r.status_code == 201:
        st.success("Account created! Switch to Sign In to log in.")
    elif r.status_code == 409:
        st.error(r.json().get("error", "Username or namespace already taken."))
    elif r.status_code == 403:
        st.error("Self-registration is disabled. Contact your administrator.")
    elif r.status_code == 422:
        st.error(r.json().get("error", "Validation failed."))
    else:
        st.error(f"Registration failed ({r.status_code}).")


# ── Force password change screen ──────────────────────────────────────────────

def render_change_password() -> None:
    """Shown immediately after login when must_change_password=True."""
    from dashboard.components.brand import get_theme_vars, PRIMARY, get_theme
    t = get_theme_vars()
    is_dark = get_theme() == "dark"

    st.markdown(f"""
<style>
.main .block-container {{ padding-top: 0 !important; max-width: 100% !important; }}
.cos-chpw-card {{
    background: {t['SURFACE']}; border: 1px solid {t['BORDER']};
    border-radius: 16px; padding: 40px 44px 36px;
    box-shadow: 0 4px 32px rgba(0,0,0,{'.45' if is_dark else '.10'});
    margin-top: 80px;
}}
.cos-chpw-title {{ font-size:1.5rem; font-weight:800; color:{t['TEXT']}; margin-bottom:6px; }}
.cos-chpw-sub   {{ font-size:0.9rem; color:{t['TEXT_MUTED']}; margin-bottom:24px; }}
</style>
""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        username_safe = _esc(st.session_state.get('username', ''))
        st.markdown(f"""
<div class="cos-chpw-card">
  <div class="cos-chpw-title">Change Password Required</div>
  <div class="cos-chpw-sub">
    You must set a new password before continuing.
    Logged in as <strong>{username_safe}</strong>.
  </div>
</div>
""", unsafe_allow_html=True)

        current_pw = st.text_input("Current (temporary) password", type="password", key="chpw_cur")
        new_pw     = st.text_input("New password", type="password", key="chpw_new",
                                   help="Min 10 chars · upper + lower + digit")
        new_pw2    = st.text_input("Confirm new password", type="password", key="chpw_new2")

        if st.button("Set New Password", type="primary", use_container_width=True, key="chpw_btn"):
            if not current_pw or not new_pw:
                st.warning("All fields required.")
            elif new_pw != new_pw2:
                st.error("Passwords do not match.")
            else:
                try:
                    r = requests.post(
                        f"{_API_BASE}/auth/change-password",
                        json={"current_password": current_pw, "new_password": new_pw},
                        headers={"Authorization": f"Bearer {st.session_state.get('jwt_token','')}"},
                        timeout=5,
                    )
                    if r.ok:
                        st.session_state["must_change_password"] = False
                        _d = r.json()
                        if _d.get("access_token"):
                            st.session_state["jwt_token"] = _d["access_token"]
                            st.session_state["refresh_token"] = _d["refresh_token"]
                        st.success("Password updated. Loading dashboard…")
                        st.rerun()
                    elif r.status_code == 401:
                        st.error("Current password incorrect.")
                    elif r.status_code == 422:
                        st.error(r.json().get("error", "Password too weak."))
                    else:
                        st.error(f"Failed ({r.status_code}).")
                except Exception:
                    st.error("Cannot reach API server.")

        if st.button("Logout instead", key="chpw_logout", use_container_width=False):
            st.session_state.clear()
            st.rerun()
