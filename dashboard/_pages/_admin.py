"""Admin page — user management, API keys, audit log, sessions, security."""
import os
from urllib.parse import urlencode

import requests as _req
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
from dashboard.components.brand import aurora_hero, badge

load_dotenv(Path(__file__).parent.parent.parent / ".env")
_FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
_API_BASE = f"http://localhost:{_FLASK_PORT}/api/v1"


def _auth_headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def render(api_get, api_post, bulk_delete=None):
    if st.session_state.get("user_role") != "admin":
        st.error("Admin access only.")
        return

    aurora_hero("Admin Panel", subtitle="Users · API Keys · Audit · Security", pill="Admin")

    # Fetch namespaces once — shared by Users + API Keys tabs
    ns_data = api_get("/namespaces") or []

    tab_users, tab_keys, tab_audit, tab_sessions, tab_security, tab_branding, tab_onboarding = st.tabs([
        "Users", "API Keys", "Audit Log", "Sessions", "Security", "Branding", "Client Onboarding"
    ])

    with tab_users:
        _render_users(api_get, api_post, ns_data)

    with tab_keys:
        _render_api_keys(api_get, api_post, ns_data)

    with tab_audit:
        _render_audit(api_get)

    with tab_sessions:
        _render_sessions(api_get, api_post)

    with tab_security:
        _render_security(api_get, api_post)

    with tab_branding:
        _render_branding(api_get, api_post, ns_data)

    with tab_onboarding:
        _render_client_onboarding(api_get, api_post, ns_data)


# ── User dialogs ──────────────────────────────────────────────────────────────

@st.dialog("Delete User")
def _delete_user_dialog(uid: str, username: str):
    st.warning(f"Permanently delete **{username}**?")
    st.caption("Removes the user, all their sessions, and auth events. This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, delete permanently", type="primary", use_container_width=True):
        resp = _req.delete(
            f"{_API_BASE}/admin/users/{uid}/permanent",
            headers=_auth_headers(), timeout=5,
        )
        if resp.ok:
            st.toast(f"User '{username}' permanently deleted.")
            st.rerun()
        else:
            err = (resp.json().get("error", f"HTTP {resp.status_code}") if resp.content else f"HTTP {resp.status_code}")
            st.error(f"Delete failed: {err}")
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Edit User")
def _edit_user_dialog(uid: str, user: dict, ns_data: list):
    st.markdown(f"**Editing:** `{user['username']}`")
    roles = ["admin", "operator", "client", "viewer", "staff"]
    cur_role = user.get("role", "viewer")
    ns_opts  = ["(none)"] + [n["slug"] for n in ns_data]
    cur_ns   = user.get("namespace") or "(none)"

    new_email = st.text_input("Email", value=user.get("email") or "", key="edit_email")
    new_role  = st.selectbox("Role", roles, index=roles.index(cur_role) if cur_role in roles else 0, key="edit_role")
    new_ns    = st.selectbox("Namespace", ns_opts,
                             index=ns_opts.index(cur_ns) if cur_ns in ns_opts else 0, key="edit_ns")
    new_active = st.checkbox("Account active", value=bool(user.get("is_active", True)), key="edit_active")
    force_pw   = st.checkbox("Force password change on next login",
                             value=bool(user.get("must_change_password", False)), key="edit_force_pw")

    if st.button("Save changes", type="primary", use_container_width=True, key="edit_save"):
        payload = {
            "email":     new_email or None,
            "role":      new_role,
            "namespace": None if new_ns == "(none)" else new_ns,
            "is_active": new_active,
            "must_change_password": force_pw,
        }
        resp = _req.patch(
            f"{_API_BASE}/admin/users/{uid}",
            json=payload, headers=_auth_headers(), timeout=5,
        )
        if resp.ok:
            st.toast(f"User '{user['username']}' updated.")
            st.rerun()
        else:
            err = (resp.json().get("error", f"HTTP {resp.status_code}") if resp.content else f"HTTP {resp.status_code}")
            st.error(f"Update failed: {err}")


# ── Users ─────────────────────────────────────────────────────────────────────

def _render_users(api_get, api_post, ns_data=None):
    st.subheader("User Accounts")

    users = api_get("/admin/users") or []

    if users:
        rows = []
        for u in users:
            rows.append({
                "Username":   u.get("username", ""),
                "Role":       u.get("role", ""),
                "Namespace":  u.get("namespace") or "—",
                "Active":     "Yes" if u.get("is_active") else "No",
                "Pwd Change": "Required" if u.get("must_change_password") else "Set",
                "Locked":     "Yes" if u.get("locked_until") else "—",
                "Last Login": (u.get("last_login_at") or "Never")[:16],
                "Created":    (u.get("created_at") or "")[:10],
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No users yet.")

    st.markdown("---")

    if users:
        user_names = [u["username"] for u in users]
        sel_usernames = st.multiselect("Select user(s) for actions", user_names, key="admin_sel_users")

        if len(sel_usernames) >= 2:
            # ── Bulk actions ──
            sel_users = [u for u in users if u["username"] in sel_usernames]
            sel_uids  = [u["id"] for u in sel_users]
            st.caption(f"{len(sel_usernames)} users selected")
            if st.button(f"Deactivate {len(sel_usernames)} users", key="bulk_deact_users"):
                st.session_state["bulk_confirm_users"] = True
            if st.session_state.get("bulk_confirm_users"):
                st.warning(f"Deactivate {len(sel_usernames)} accounts? This cannot be undone.")
                c1, c2 = st.columns(2)
                if c1.button("Yes, deactivate all", key="bulk_users_yes"):
                    resp = _req.delete(
                        f"{_API_BASE}/admin/users/bulk",
                        json={"ids": sel_uids},
                        headers=_auth_headers(), timeout=10,
                    )
                    st.session_state.pop("bulk_confirm_users", None)
                    if resp.ok:
                        st.success(f"Deactivated {resp.json().get('count', 0)} users.")
                    else:
                        st.error(f"Failed: {resp.json().get('error', f'HTTP {resp.status_code}')}")
                    st.rerun()
                if c2.button("Cancel", key="bulk_users_cancel"):
                    st.session_state.pop("bulk_confirm_users", None)
                    st.rerun()

        elif len(sel_usernames) == 1:
            # ── Single-user actions ──
            sel_user = next((u for u in users if u["username"] == sel_usernames[0]), None)
            if sel_user:
                uid = sel_user["id"]
                is_locked = bool(sel_user.get("locked_until"))
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    if is_locked:
                        st.warning(f"Locked until {str(sel_user['locked_until'])[:16]}")
                        if st.button("Unlock account", key=f"unlock_{uid}", use_container_width=True, type="primary"):
                            r = api_post(f"/admin/users/{uid}/unlock", {})
                            st.success("Account unlocked." if r else "Failed to unlock.")
                            st.rerun()
                    else:
                        st.info("Account is not locked.")
                with col2:
                    if sel_user.get("is_active"):
                        if st.button("Deactivate", key=f"deact_{uid}", use_container_width=True):
                            _resp = _req.delete(
                                f"{_API_BASE}/admin/users/{uid}",
                                headers=_auth_headers(), timeout=5,
                            )
                            if _resp.ok:
                                st.success("Deactivated.")
                            else:
                                _err = (_resp.json().get("error", f"HTTP {_resp.status_code}") if _resp.content else f"HTTP {_resp.status_code}")
                                st.error(f"Failed: {_err}")
                            st.rerun()
                    else:
                        if st.button("Reactivate", key=f"react_{uid}", use_container_width=True):
                            _resp = _req.patch(
                                f"{_API_BASE}/admin/users/{uid}",
                                json={"is_active": True}, headers=_auth_headers(), timeout=5,
                            )
                            st.success("Reactivated." if _resp.ok else "Failed.")
                            st.rerun()
                with col3:
                    with st.expander("Reset password"):
                        new_pw = st.text_input("New password", type="password", key=f"rpw_{uid}")
                        if st.button("Reset", key=f"rset_{uid}"):
                            r = api_post(f"/admin/users/{uid}/reset-password", {"new_password": new_pw})
                            st.success("Password reset." if r else "Failed (check strength).")
                with col4:
                    if st.button("Edit", key=f"edit_{uid}", use_container_width=True):
                        _edit_user_dialog(uid, sel_user, ns_data or [])
                with col5:
                    if st.button("Delete", key=f"del_{uid}", use_container_width=True, type="secondary"):
                        _delete_user_dialog(uid, sel_user["username"])

    st.markdown("---")

    with st.expander("+ Create User"):
        _create_user_form(api_get, api_post, ns_data=ns_data)


def _create_user_form(api_get, api_post, ns_data=None):
    st.caption(
        "Password rules: **min 10 chars · uppercase · lowercase · digit**. "
        "User will be forced to change password on first login."
    )
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("Username", key="nu_username")
        new_email    = st.text_input("Email (optional)", key="nu_email")
        new_role     = st.selectbox("Role", ["operator", "viewer", "client", "admin"], key="nu_role")
    with col2:
        new_password  = st.text_input("Temporary password", type="password", key="nu_pw",
                                      help="Min 10 chars · upper + lower + digit")
        new_password2 = st.text_input("Confirm password", type="password", key="nu_pw2")
        if ns_data is None:
            ns_data = api_get("/namespaces") or []
        ns_opts = ["(none)"] + [n["slug"] for n in ns_data]
        new_ns  = st.selectbox("Namespace", ns_opts, key="nu_ns")

    if st.button("Create User", type="primary", use_container_width=True, key="nu_btn"):
        if not new_username or not new_password:
            st.warning("Username and password required.")
        elif new_password != new_password2:
            st.error("Passwords do not match.")
        else:
            payload = {
                "username": new_username, "password": new_password,
                "role": new_role, "email": new_email or None,
                "namespace": None if new_ns == "(none)" else new_ns,
                "must_change_password": True,
            }
            try:
                r = _req.post(
                    f"{_API_BASE}/admin/users",
                    json=payload, headers=_auth_headers(), timeout=5,
                )
                if r.status_code == 201:
                    st.success(f"User `{new_username}` created. They must change password on first login.")
                    st.rerun()
                else:
                    st.error(f"Failed: {r.json().get('error', f'HTTP {r.status_code}')}")
            except Exception as e:
                st.error(f"Cannot reach API: {e}")


# ── API Keys ──────────────────────────────────────────────────────────────────

def _render_api_keys(api_get, api_post, ns_data=None):
    st.subheader("API Keys")

    keys = api_get("/admin/api-keys") or []
    if keys:
        rows = [{
            "ID":          k["id"][:8] + "...",
            "Name":        k.get("name", ""),
            "Namespace":   k.get("namespace", "global"),
            "Permissions": ", ".join(k.get("permissions") if isinstance(k.get("permissions"), list) else ["?"]),
            "Last Used":   (k.get("last_used") or "Never")[:16],
            "Created":     (k.get("created_at") or "")[:10],
        } for k in keys]
        st.dataframe(rows, use_container_width=True)

        key_ids    = [k["id"] for k in keys]
        key_labels = [f"{k['name']} ({k['id'][:8]})" for k in keys]

        # Per-key actions: Regenerate
        st.markdown("**Per-key actions**")
        regen_label = st.selectbox("Select key to regenerate", ["—"] + key_labels, key="sel_key_regen")
        if regen_label != "—":
            regen_idx = key_labels.index(regen_label)
            regen_id  = key_ids[regen_idx]
            if st.button("Regenerate Secret", key="regen_key_btn"):
                resp = _req.post(
                    f"{_API_BASE}/admin/api-keys/{regen_id}/regenerate",
                    headers=_auth_headers(), timeout=10,
                )
                if resp.ok:
                    d = resp.json()
                    st.success("Key regenerated. Copy the new secret — it won't be shown again.")
                    st.code(d.get("raw_key", ""))
                else:
                    st.error(f"Failed: {resp.json().get('error', f'HTTP {resp.status_code}')}")
                st.rerun()

        st.markdown("---")
        sel_labels = st.multiselect("Select key(s) to revoke", key_labels, key="sel_keys_revoke")
        if sel_labels:
            sel_indices = [key_labels.index(l) for l in sel_labels]
            sel_key_ids = [key_ids[i] for i in sel_indices]
            verb = f"Revoke {len(sel_labels)} key(s)"
            if st.button(verb, key="revoke_keys_btn"):
                st.session_state["bulk_confirm_keys"] = True
            if st.session_state.get("bulk_confirm_keys"):
                st.warning(f"Permanently revoke {len(sel_labels)} key(s)?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, revoke all", key="bulk_keys_yes"):
                    resp = _req.delete(
                        f"{_API_BASE}/admin/api-keys/bulk",
                        json={"ids": sel_key_ids},
                        headers=_auth_headers(), timeout=10,
                    )
                    st.session_state.pop("bulk_confirm_keys", None)
                    if resp.ok:
                        st.success(f"Revoked {resp.json().get('count', 0)} key(s).")
                    else:
                        st.error(f"Failed: {resp.json().get('error', f'HTTP {resp.status_code}')}")
                    st.rerun()
                if c2.button("Cancel", key="bulk_keys_cancel"):
                    st.session_state.pop("bulk_confirm_keys", None)
                    st.rerun()
    else:
        st.info("No API keys.")

    st.markdown("---")
    with st.expander("+ Create API Key"):
        _create_key_form(api_get, api_post, ns_data=ns_data)


def _create_key_form(api_get, api_post, ns_data=None):
    key_name = st.text_input("Key name", key="nk_name", placeholder="e.g. my-script")
    if ns_data is None:
        ns_data = api_get("/namespaces") or []
    ns_opts  = [n["slug"] for n in ns_data] or ["global"]
    key_ns   = st.selectbox("Namespace", ns_opts, key="nk_ns")
    perms    = st.multiselect("Permissions", ["read", "write"], default=["read", "write"], key="nk_perms")

    if st.button("Generate Key", type="primary", use_container_width=True, key="nk_btn"):
        r = api_post("/admin/api-keys", {"name": key_name, "namespace": key_ns, "permissions": perms})
        if r and r.get("raw_key"):
            st.success("Key created. Copy it now — it won't be shown again.")
            st.code(r["raw_key"])
        else:
            st.error("Create failed.")


# ── Audit Log ─────────────────────────────────────────────────────────────────

def _render_audit(api_get):
    st.subheader("Auth Audit Log")

    col1, col2 = st.columns(2)
    with col1:
        event_types = ["", "login_success", "login_failure", "logout", "user_created",
                       "user_deactivated", "lockout_triggered", "password_change",
                       "password_reset", "api_key_created", "api_key_revoked",
                       "token_refresh", "register", "session_revoked"]
        et_filter = st.selectbox("Filter event type", event_types, key="audit_et")
    with col2:
        un_filter = st.text_input("Filter username", key="audit_un", placeholder="(any)")

    params = {"limit": 100}
    if et_filter:
        params["event_type"] = et_filter
    if un_filter.strip():
        params["username"] = un_filter.strip()
    url = f"/admin/audit?{urlencode(params)}"

    _audit_resp = api_get(url) or {}
    events = _audit_resp.get("events", []) if isinstance(_audit_resp, dict) else (_audit_resp or [])
    if events:
        rows = [{
            "Time":      (e.get("created_at") or "")[:16],
            "Event":     e.get("event_type", ""),
            "Username":  e.get("username") or "—",
            "IP":        e.get("ip_address") or "—",
            "Namespace": e.get("namespace") or "—",
        } for e in events]
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No events found.")


# ── Sessions ──────────────────────────────────────────────────────────────────

def _render_sessions(api_get, api_post):
    st.subheader("Active Sessions")

    sessions = api_get("/admin/sessions?limit=100") or []
    if sessions:
        # ── User filter ───────────────────────────────────────────────────────
        all_users = sorted({s.get("username", "") for s in sessions if s.get("username")})
        filter_users = st.multiselect(
            "Filter by user", all_users, default=[], key="sess_filter_users",
            placeholder="All users"
        )
        visible = [s for s in sessions if not filter_users or s.get("username") in filter_users]

        rows = [{
            "ID":        s["id"][:8] + "...",
            "User":      s.get("username", ""),
            "IP":        s.get("ip_address") or "—",
            "Created":   (s.get("created_at") or "")[:16],
            "Last Used": (s.get("last_used_at") or "")[:16],
            "Expires":   (s.get("expires_at") or "")[:16],
        } for s in visible]
        st.caption(f"{len(visible)} of {len(sessions)} session(s)")
        st.dataframe(rows, use_container_width=True)

        sess_labels = [
            f"{s.get('username','')} — {s['id'][:8]} ({s.get('ip_address') or 'no IP'})"
            for s in visible
        ]
        sel_sess_labels = st.multiselect("Select session(s) to revoke", sess_labels, key="sel_sess_multi")
        if sel_sess_labels:
            sel_indices = [sess_labels.index(l) for l in sel_sess_labels]
            sel_sess_ids = [visible[i]["id"] for i in sel_indices]
            verb = f"Revoke {len(sel_sess_labels)} session(s)"
            if st.button(verb, key="revoke_sess_btn"):
                st.session_state["bulk_confirm_sess"] = True
            if st.session_state.get("bulk_confirm_sess"):
                st.warning(f"Revoke {len(sel_sess_labels)} session(s)?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, revoke all", key="bulk_sess_yes"):
                    resp = _req.delete(
                        f"{_API_BASE}/admin/sessions/bulk",
                        json={"ids": sel_sess_ids},
                        headers=_auth_headers(), timeout=10,
                    )
                    st.session_state.pop("bulk_confirm_sess", None)
                    if resp.ok:
                        st.success(f"Revoked {resp.json().get('count', 0)} session(s).")
                    else:
                        st.error(f"Failed: {resp.json().get('error', f'HTTP {resp.status_code}')}")
                    st.rerun()
                if c2.button("Cancel", key="bulk_sess_cancel"):
                    st.session_state.pop("bulk_confirm_sess", None)
                    st.rerun()
    else:
        st.info("No active sessions.")


# ── Security Settings ─────────────────────────────────────────────────────────

def _render_security(api_get, api_post):
    st.subheader("Security Settings")

    cfg = api_get("/admin/security-settings") or {}

    max_attempts   = st.slider("Max failed login attempts before lockout", 3, 10,
                                int(cfg.get("max_failed_attempts", 5)), key="sec_max")
    lockout_mins   = st.selectbox("Lockout duration (minutes)", [5, 10, 15, 30, 60],
                                   index=[5,10,15,30,60].index(int(cfg.get("lockout_minutes", 15)))
                                         if int(cfg.get("lockout_minutes", 15)) in [5,10,15,30,60] else 2,
                                   key="sec_lock")
    token_mins     = st.selectbox("Access token lifetime (minutes)", [15, 30, 60, 120],
                                   index=[15,30,60,120].index(int(cfg.get("access_token_minutes", 60)))
                                         if int(cfg.get("access_token_minutes", 60)) in [15,30,60,120] else 2,
                                   key="sec_tok")
    refresh_days   = st.selectbox("Refresh token lifetime (days)", [1, 7, 14, 30],
                                   index=[1,7,14,30].index(int(cfg.get("refresh_token_days", 7)))
                                         if int(cfg.get("refresh_token_days", 7)) in [1,7,14,30] else 1,
                                   key="sec_ref")
    allow_register = st.toggle("Allow client self-registration", value=cfg.get("allow_self_register", "0") == "1",
                                key="sec_reg")

    if st.button("Save Security Settings", type="primary", use_container_width=True, key="sec_save"):
        r = api_post("/admin/security-settings", {
            "max_failed_attempts": max_attempts,
            "lockout_minutes":     lockout_mins,
            "access_token_minutes": token_mins,
            "refresh_token_days":  refresh_days,
            "allow_self_register": "1" if allow_register else "0",
        }, method="PATCH")
        if r:
            st.success("Settings saved.")
        else:
            st.error("Save failed.")


# ── Namespace Branding ────────────────────────────────────────────────────────

def _render_branding(api_get, api_post, ns_data=None):
    """Per-client namespace branding — company name, colors, icon."""
    from dashboard.components.brand import get_theme_vars
    t = get_theme_vars()

    st.subheader("Namespace Branding")
    st.caption("Customize each client workspace — company name, brand colors, and icon. "
               "Clients see their own branding when they log in.")

    # Reuse ns_data fetched at top of render() — include disabled namespaces too
    ns_list = ns_data if ns_data is not None else (api_get("/namespaces?enabled=false") or [])
    if not ns_list:
        st.info("No namespaces found.")
        return

    ns_names = [n["slug"] for n in ns_list]
    sel_slug = st.selectbox("Select namespace to brand", ns_names, key="brand_ns_sel")
    ns_obj = next((n for n in ns_list if n["slug"] == sel_slug), None)
    if not ns_obj:
        return

    current_meta = ns_obj.get("metadata") or {}
    current_color = ns_obj.get("color") or "#407E3C"

    st.markdown("---")
    col_form, col_preview = st.columns([3, 2])

    with col_form:
        st.markdown("**Brand Settings**")
        company_name  = st.text_input("Company name", value=current_meta.get("company_name", ""),
                                       key="brand_company", placeholder="e.g. Reci Transport")
        icon_emoji    = st.text_input("Icon (text, optional)", value=ns_obj.get("icon") or "",
                                       key="brand_icon", max_chars=4)
        brand_color   = st.color_picker("Primary brand color", value=current_color,
                                         key="brand_color")
        accent_color  = st.color_picker("Accent color", value=current_meta.get("accent_color", brand_color),
                                         key="brand_accent")
        use_custom_bg = st.checkbox("Custom page background",
                                     value=bool(current_meta.get("bg_color")),
                                     key="brand_use_bg")
        bg_color = ""
        if use_custom_bg:
            bg_color = st.color_picker("Background color",
                                        value=current_meta.get("bg_color") or "#0A1F0A",
                                        key="brand_bg")
            st.caption("Text colors auto-adjust for readability.")

        if st.button("Save Branding", type="primary", use_container_width=True, key="brand_save"):
            new_meta = {**current_meta,
                        "company_name": company_name.strip(),
                        "accent_color": accent_color,
                        "bg_color":     bg_color if use_custom_bg else ""}
            r = api_post(f"/namespaces/{sel_slug}", {
                "color":    brand_color,
                "icon":     icon_emoji.strip(),
                "metadata": new_meta,
            }, method="PATCH")
            if r:
                st.success(f"Branding saved for **{sel_slug}**. Clients will see it on next login.")
            else:
                st.error("Save failed — check API.")

    with col_preview:
        st.markdown("**Live Preview**")
        _c = brand_color if "brand_color" in st.session_state else current_color
        _a = st.session_state.get("brand_accent", current_meta.get("accent_color", _c))
        _icon = st.session_state.get("brand_icon", ns_obj.get("icon") or "")
        _name = st.session_state.get("brand_company", current_meta.get("company_name", sel_slug))
        # Preview background: custom bg if set, else theme surface
        _use_bg_now = st.session_state.get("brand_use_bg", bool(current_meta.get("bg_color")))
        _bg_now = st.session_state.get("brand_bg", current_meta.get("bg_color", "")) if _use_bg_now else ""
        from dashboard.components.brand import _luminance
        if _bg_now and _bg_now.startswith("#"):
            _surf = _bg_now
            _text_on_bg = "#1A1A1A" if _luminance(_bg_now) > 0.45 else "#E8F5E8"
            _muted = "#6B7280" if _luminance(_bg_now) > 0.45 else "#9CA3AF"
        else:
            _surf = t["SURFACE"]
            _text_on_bg = t["TEXT"]
            _muted = t["TEXT_MUTED"]
        _bord = t["BORDER"]
        import html as _html
        _preview_html = (
            f'<div style="background:{_surf};border:1px solid {_bord};'
            f'border-radius:10px;padding:16px 20px;">'
            f'<div style="font-size:1.2rem;font-weight:800;color:{_c};'
            f'font-family:Inter,sans-serif;letter-spacing:1px;">'
            f'{_html.escape(str(_icon))} {_html.escape(str(_name))}</div>'
            f'<div style="font-size:0.6rem;color:{_muted};letter-spacing:1px;margin-top:2px;">'
            f'POWERED BY <span style="color:{_a};font-weight:700;">CLAUDEOS</span></div>'
            f'<div style="margin-top:8px;font-size:0.78rem;color:{_text_on_bg};">Sample text — readable on this background.</div>'
            f'<div style="margin-top:10px;">'
            f'<span style="background:{_c};color:#fff;border-radius:6px;'
            f'padding:6px 14px;font-size:0.8rem;font-weight:600;">Button</span>'
            f'&nbsp;&nbsp;'
            f'<span style="background:{_c}33;color:{_a};border:1px solid {_c}55;'
            f'border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:600;">Badge</span>'
            f'</div></div>'
        )
        st.markdown(_preview_html, unsafe_allow_html=True)


# ── Client Onboarding ─────────────────────────────────────────────────────────

_CLIENT_SCHEMA = [
    ("client.business_name",  "fact",       "Business Name",         "Full legal or trading name"),
    ("client.industry",       "fact",       "Industry / Sector",     "e.g. Beauty, Logistics, Tech"),
    ("client.location",       "fact",       "Location",              "City, Country"),
    ("client.owner_name",     "fact",       "Owner / Contact Name",  "Primary person to address"),
    ("client.owner_email",    "fact",       "Contact Email",         "For notifications and follow-up"),
    ("client.primary_goal",   "context",    "Primary Goal",          "Main reason for using ClaudeOS"),
    ("client.active_projects","context",    "Active Projects",       "Current projects (comma-separated)"),
    ("client.ai_use_cases",   "context",    "AI Use Cases",          "What agents are used for"),
    ("client.brand_colors",   "preference", "Brand Colors",          "Primary hex color(s), e.g. #407E3C"),
    ("client.tone",           "preference", "Communication Tone",    "formal / casual / technical"),
    ("client.language",       "preference", "Language",              "Preferred language for responses"),
    ("client.timezone",       "preference", "Timezone",              "e.g. Africa/Lagos, Europe/London"),
    ("client.avoid",          "preference", "Avoid",                 "Topics or styles agents should avoid"),
    ("client.sla_tier",       "fact",       "Default SLA Tier",      "P1 / P2 / P3 / P4"),
]


def _render_client_onboarding(api_get, api_post, ns_data=None):
    st.subheader("Client Onboarding Schema")
    st.caption("Fill in the standard profile for each client namespace. Agents use this context automatically.")

    # Build namespace list (client namespaces only)
    namespaces = ns_data if isinstance(ns_data, list) else []
    client_ns = [n["slug"] for n in namespaces if n.get("type") == "client" and n.get("slug")]
    if not client_ns:
        # Fallback: all namespaces
        client_ns = [n["slug"] for n in namespaces if n.get("slug")]
    if not client_ns:
        st.info("No client namespaces found.")
        return

    sel_ns = st.selectbox("Select namespace", client_ns, key="ob_ns_sel")

    # Fetch existing entries for this namespace
    existing_data = api_get(f"/memory?namespace={sel_ns}&limit=200") or {}
    entries = existing_data.get("entries", [])
    existing = {e["key"]: e for e in entries if e["key"].startswith("client.")}

    st.markdown("---")
    st.markdown(f"**{sel_ns}** — {len(existing)}/{len(_CLIENT_SCHEMA)} fields populated")

    with st.form(key=f"ob_form_{sel_ns}"):
        field_vals: dict[str, str] = {}
        for key, category, label, placeholder in _CLIENT_SCHEMA:
            current = existing.get(key, {}).get("value", "")
            field_vals[key] = st.text_input(
                label,
                value=current,
                placeholder=placeholder,
                key=f"ob_{sel_ns}_{key}",
            )

        submitted = st.form_submit_button("Save All Fields", type="primary", use_container_width=True)

    if submitted:
        saved = 0
        for key, category, label, _ in _CLIENT_SCHEMA:
            val = field_vals[key].strip()
            if not val:
                continue
            if key in existing:
                # Update existing entry
                entry_id = existing[key]["id"]
                r = api_post(f"/memory/{entry_id}", {"value": val, "category": category}, method="PUT")
            else:
                # Create new entry
                r = api_post("/memory", {
                    "namespace": sel_ns,
                    "category": category,
                    "key": key,
                    "value": val,
                    "confidence": 0.9,
                    "tags": "onboarding,client-schema",
                })
            if r:
                saved += 1
        st.success(f"Saved {saved} field(s) for **{sel_ns}**.")
        st.rerun()
