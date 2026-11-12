"""ClaudeOS Control Center — Streamlit entry point."""
import sys
import os
import logging
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

import jwt as _jwt
import streamlit as st

st.set_page_config(
    page_title="ClaudeOS",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="auto",
)

from dashboard.components.brand import inject, sidebar_logo, theme_toggle, system_health_bar, clear_health_bar, PRIMARY, get_theme_vars, get_ns_brand

# Restore the chosen theme after a browser refresh (session_state is reset, URL is not).
# Must run BEFORE inject() so the first render already uses the right palette.
if "theme" not in st.session_state and st.query_params.get("theme") in ("light", "dark"):
    st.session_state["theme"] = st.query_params["theme"]

inject()
theme_toggle()  # available on all pages including login

_FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
API_BASE = f"http://127.0.0.1:{_FLASK_PORT}/api/v1"
logger = logging.getLogger("claudeos.dashboard")

_SESSION_PARAM = "_s"  # URL query param key for session persistence


def _restore_session_from_url() -> bool:
    """On page refresh, restore session from URL session_key → Flask session store."""
    sk = st.query_params.get(_SESSION_PARAM)
    if not sk:
        return False
    try:
        r = requests.get(f"{API_BASE}/auth/session/{sk}", timeout=3)
        if r.ok:
            data = r.json()
            st.session_state["jwt_token"]            = data["access_token"]
            st.session_state["refresh_token"]        = data["refresh_token"]
            st.session_state["username"]             = data["username"]
            st.session_state["user_role"]            = data["user_role"]
            st.session_state["user_namespace"]       = data.get("user_namespace") or None
            st.session_state["must_change_password"] = data.get("must_change_password", False)
            # Session restored from URL = user already logged in before = onboarding already seen.
            # Without this, every refresh shows onboarding from slide 1 again.
            st.session_state["_onboarding_done"] = True
            # Restore last active page from URL so browser refresh lands on same page
            _page_from_url = st.query_params.get("page")
            if _page_from_url:
                st.session_state["nav_page"] = _page_from_url
            return True
        # Expired / invalid key — purge from URL so login page shows cleanly
        try:
            del st.query_params[_SESSION_PARAM]
        except Exception:
            pass
    except Exception as e:
        logger.debug("Session restore failed: %s", e)
    return False


# ── Session restore (page refresh) ───────────────────────────────────────────
if not st.session_state.get("jwt_token"):
    _restore_session_from_url()

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.get("jwt_token"):
    clear_health_bar()
    from dashboard.components.login_form import render_login
    render_login()
    st.stop()

# ── Force password change gate ────────────────────────────────────────────────
if st.session_state.get("must_change_password"):
    from dashboard.components.login_form import render_change_password
    render_change_password()
    st.stop()

def _get_headers() -> dict:
    token = st.session_state.get("jwt_token", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    # Fallback for dev/script access (no JWT in session)
    key = os.environ.get("CLAUDEOS_DEV_API_KEY", "")
    return {"X-API-Key": key} if key else {}


def _maybe_refresh_token() -> None:
    """Silently refresh the access token if it expires within 5 minutes.
    Throttled to run at most once per 60 seconds to avoid JWT decode on every rerender.
    """
    import time as _time
    now = _time.time()
    if now - st.session_state.get("_refresh_checked_at", 0) < 60:
        return
    st.session_state["_refresh_checked_at"] = now

    token = st.session_state.get("jwt_token", "")
    refresh = st.session_state.get("refresh_token", "")
    if not token or not refresh:
        return
    try:
        payload = _jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp", 0)
        if exp - now < 300:  # < 5 minutes to expiry
            r = requests.post(
                f"{API_BASE}/auth/refresh",
                json={"refresh_token": refresh},
                timeout=3,
            )
            if r.ok:
                st.session_state["jwt_token"] = r.json()["access_token"]
    except Exception as e:
        logger.debug("Token refresh skipped: %s", e)


_maybe_refresh_token()

# ── Namespace brand loading (client/viewer only) ──────────────────────────────
_role_now = st.session_state.get("user_role", "")
_ns_now   = st.session_state.get("user_namespace")
if _role_now in ("client", "viewer") and _ns_now:
    if not st.session_state.get("_ns_brand_loaded"):
        try:
            _nb = requests.get(
                f"{API_BASE}/namespaces/{_ns_now}",
                headers={"Authorization": f"Bearer {st.session_state.get('jwt_token','')}"},
                timeout=2,
            )
            if _nb.ok:
                _nd = _nb.json()
                _nm = _nd.get("metadata") or {}
                st.session_state["ns_brand"] = {
                    "color":            (_nd.get("color") or "").strip(),
                    "icon":             (_nd.get("icon") or "").strip(),
                    "company_name":     (_nm.get("company_name") or "").strip(),
                    "accent_color":     (_nm.get("accent_color") or "").strip(),
                    "bg_color":         (_nm.get("bg_color") or "").strip(),
                    "hover_color":      (_nm.get("hover_color") or "").strip(),
                    "surface_color":    (_nm.get("surface_color") or "").strip(),
                    "surface2_color":   (_nm.get("surface2_color") or "").strip(),
                    "text_color":       (_nm.get("text_color") or "").strip(),
                    "text_muted_color": (_nm.get("text_muted_color") or "").strip(),
                    "border_color":     (_nm.get("border_color") or "").strip(),
                    "input_bg":         (_nm.get("input_bg") or "").strip(),
                }
                st.session_state["_ns_brand_loaded"] = True
                st.rerun()  # re-render so inject() at top picks up brand
        except Exception:
            st.session_state["_ns_brand_loaded"] = True  # don't retry on failure
elif _role_now in ("admin", "operator"):
    # Admin sees ClaudeOS branding — clear any leftover ns_brand
    st.session_state.pop("ns_brand", None)
    st.session_state.pop("_ns_brand_loaded", None)


def _handle_401() -> None:
    st.session_state.clear()
    st.rerun()


def api_get(path: str, timeout: int = 3) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_get_headers(), timeout=timeout)
        if r.status_code == 401:
            _handle_401()
        if r.status_code == 429:
            logger.warning("api_get %s rate limited (429)", path)
            st.toast("Too many requests — please wait a moment.", icon="⚠️")
            return None
        if r.ok:
            return r.json()
    except Exception as e:
        logger.warning("api_get %s failed: %s", path, e)
    return None


_READ_ONLY_PREFIXES = (
    "/health",
    "/system/status",
    "/system/stats",
    "/system/events",
    "/system/namespace-stats",
    "/agents",
    "/memory",
    "/outputs/stats",
    "/namespaces",
    "/tickets",
    "/sync/status",
    "/workflows",
)
# NOTE: /agents/runs intentionally excluded — user-scoped, must never be cached cross-user


@st.cache_data(ttl=30)
def _cached_api_get(path: str, token: str = "", timeout: int = 3) -> dict | None:
    return api_get(path, timeout=timeout)


def api_get_cached(path: str, timeout: int = 3) -> dict | None:
    """api_get with 30-second TTL cache scoped per user token.
    /agents/runs is explicitly excluded — user-scoped data must not be cached cross-user.
    """
    base = path.split("?")[0]
    if base == "/agents/runs" or base.startswith("/agents/runs/"):
        return api_get(path, timeout)
    if any(path == p or path.startswith(p) for p in _READ_ONLY_PREFIXES):
        tok = st.session_state.get("jwt_token", "")
        return _cached_api_get(path, token=tok, timeout=timeout)
    return api_get(path, timeout)


def bulk_delete(path: str, ids: list, timeout: int = 10) -> dict | None:
    """DELETE with JSON body {"ids": [...]} for bulk endpoints."""
    try:
        r = requests.delete(
            f"{API_BASE}{path}",
            json={"ids": ids},
            headers=_get_headers(),
            timeout=timeout,
        )
        if r.status_code == 401:
            _handle_401()
        if r.ok:
            return r.json()
    except Exception as e:
        logger.warning("bulk_delete %s failed: %s", path, e)
    return None


def api_post(path: str, data: dict = None, timeout: int = 5, method: str = "POST") -> dict | None:
    try:
        fn = {"POST": requests.post, "PATCH": requests.patch, "PUT": requests.put, "DELETE": requests.delete}.get(method, requests.post)
        kwargs = {"headers": _get_headers(), "timeout": timeout}
        if data is not None:
            kwargs["json"] = data
        r = fn(f"{API_BASE}{path}", **kwargs)
        if r.status_code == 401:
            _handle_401()
        if r.ok:
            return r.json()
    except Exception as e:
        logger.warning("api_post %s failed: %s", path, e)
    return None


# ── System health bar (admin only) ───────────────────────────────────────────
if st.session_state.get("user_role") == "admin":
    system_health_bar(API_BASE, st.session_state.get("jwt_token", ""))
else:
    clear_health_bar()

# ── Onboarding modal (client/viewer first-login) ──────────────────────────────
from dashboard.components.onboarding import maybe_show_onboarding
maybe_show_onboarding(st.session_state.get("user_role", "viewer"))

# ── Sidebar ───────────────────────────────────────────────────────────────────
sidebar_logo()
st.sidebar.markdown("---")

role = st.session_state.get("user_role", "viewer")
username = st.session_state.get("username", "")

# Role-based page visibility
pages = {
    "Overview":       "",
    "Agents":         "◈",
    "Memory":         "◉",
    "Workflows":      "",
    "Projects":       "",
    "Outputs":        "",
    "Tickets":        "",
    "Observability":  "",
    "Settings":       "",
}

if role == "admin":
    pages["Admin"] = ""

if role in ("client", "viewer"):
    pages.pop("Settings", None)
    pages.pop("Workflows", None)
    pages.pop("Observability", None)
    pages["Usage"] = ""  # client-facing usage + pulse dashboard

if role == "staff":
    pages.pop("Memory", None)
    pages.pop("Workflows", None)
    pages.pop("Projects", None)
    pages.pop("Settings", None)
    pages.pop("Admin", None)
    pages.pop("Observability", None)

# Ticket badge — fetch before radio so count shows in nav label (cached 30s)
_ticket_stats = _cached_api_get(
    "/tickets?status=open&limit=50",
    token=st.session_state.get("jwt_token", ""),
    timeout=3,
)
# list_tickets returns a JSON array — count its length
_open_ticket_count = (len(_ticket_stats) if isinstance(_ticket_stats, list) else 0)

_page_list = list(pages.keys())

# Restore nav page from backup if theme-toggle rerun pruned it
if "_nav_page_bak" in st.session_state and "nav_page" not in st.session_state:
    st.session_state["nav_page"] = st.session_state.pop("_nav_page_bak")

page = st.session_state.get("nav_page", _page_list[0])
if page not in _page_list:
    page = _page_list[0]
    st.session_state["nav_page"] = page

# Persist to URL
try:
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
except Exception:
    pass

# ── Hidden proxy buttons — clicked by the HTML nav JS ────────────────────────
import streamlit.components.v1 as _cv1
from dashboard.components.proxy import proxy_button as _proxy_button, COS_CLICK_PROXY_JS as _CLICK_JS
for _p in _page_list:
    with st.sidebar:
        _clicked = _proxy_button(f"nav:{_p}", key=f"nav_btn_{_p}")
    if _clicked:
        st.session_state["nav_page"] = _p
        try:
            st.query_params["page"] = _p
        except Exception:
            pass
        st.rerun()

# ── HTML grouped nav ──────────────────────────────────────────────────────────
_NAV_GROUPS = [
    ("CORE",       ["Overview", "Agents", "Memory"]),
    ("OPERATIONS", ["Workflows", "Projects", "Outputs", "Tickets", "Usage"]),
    ("SYSTEM",     ["Observability", "Settings", "Admin"]),
]
_visible_groups = [
    (g, [p for p in ps if p in _page_list])
    for g, ps in _NAV_GROUPS
    if any(p in _page_list for p in ps)
]

from dashboard.components.brand import get_theme as _get_theme, nav_palette as _nav_palette
_np          = _nav_palette(_get_theme() == "dark")
_nav_bg      = _np["bg"]
_grp_clr     = _np["group"]
_div_clr     = _np["divider"]
_item_clr    = _np["item"]
_item_hover  = _np["hover"]
_active_bg   = _np["active_bg"]
_active_text = _np["active_text"]

# 16px stroke icons (Lucide-style paths, drawn in currentColor so they follow active/hover state)
_NAV_ICONS = {
    "Overview":      '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
    "Agents":        '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/>',
    "Memory":        '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "Workflows":     '<circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 6h4a3 3 0 0 1 3 3v6"/>',
    "Projects":      '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "Outputs":       '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    "Tickets":       '<path d="M3 9a2 2 0 0 0 0 6v3h18v-3a2 2 0 0 1 0-6V6H3z"/><path d="M13 6v12"/>',
    "Usage":         '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
    "Observability": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "Settings":      '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "Admin":         '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
}


def _nav_icon(name: str) -> str:
    body = _NAV_ICONS.get(name, '<circle cx="12" cy="12" r="4"/>')
    return (f'<svg class="ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


_items_html = ""
for _gi, (_gname, _gpages) in enumerate(_visible_groups):
    if _gi > 0:
        _items_html += '<div class="divider"></div>'
    _items_html += f'<div class="grp">{_gname}</div>'
    for _p in _gpages:
        _cls = " active" if _p == page else ""
        _bdg = (f'<span class="badge">{_open_ticket_count}</span>'
                if _p == "Tickets" and _open_ticket_count else "")
        _items_html += f'<div class="item{_cls}" onclick="navTo(\'{_p}\')">{_nav_icon(_p)}<span class="lbl">{_p}</span>{_bdg}</div>'

_nav_h = 4 + sum(30 + len(ps) * 38 for _, ps in _visible_groups) + (len(_visible_groups) - 1) * 24 + 4

_nav_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:{_nav_bg};font-family:'Inter','Inter',system-ui,sans-serif;overflow:hidden;padding:4px 0;}}
.grp{{padding:10px 16px 4px;font-size:10px;font-weight:600;letter-spacing:2px;color:{_grp_clr};text-transform:uppercase;}}
.divider{{margin:8px 16px;height:1px;background:linear-gradient(to right,transparent,{_div_clr} 20%,{_div_clr} 80%,transparent);}}
.item{{display:flex;align-items:center;gap:10px;padding:0 20px 0 17px;height:38px;cursor:pointer;font-size:13px;
       color:{_item_clr};border-left:3px solid transparent;transition:background .12s,color .12s;user-select:none;}}
.ico{{flex:none;opacity:.75;}}
.item:hover .ico,.item.active .ico{{opacity:1;}}
.item.active .ico{{color:{_np["accent"]};}}
.lbl{{flex:1;}}
.item:hover{{background:{_item_hover};color:{_active_text};}}
.item.active{{border-left-color:#5a9e56;background:{_active_bg};color:{_active_text};font-weight:500;}}
.badge{{margin-left:7px;background:{_np["badge_bg"]};color:#fff;font-size:10px;border-radius:10px;
        padding:1px 6px;font-weight:600;line-height:16px;}}
</style></head><body>
<div>{_items_html}</div>
<script>
{_CLICK_JS}
function navTo(p){{ cosClickProxy(window.parent.document, 'nav:'+p); }}
</script>
</body></html>"""

with st.sidebar:
    _cv1.html(_nav_html, height=_nav_h, scrolling=False)
    st.caption("Press Ctrl+K to jump to any page")

from dashboard.components.command_palette import render as _render_palette
_render_palette(_page_list, get_theme_vars(), page)

st.sidebar.markdown("---")

# User info + logout
_tv = get_theme_vars()
_sidebar_brand = get_ns_brand()
_brand_primary = (_sidebar_brand.get("color") or "").strip() or PRIMARY
_brand_muted   = (_sidebar_brand.get("text_muted_color") or "").strip() or _tv["TEXT_MUTED"]
_user_ns = st.session_state.get("user_namespace")
st.sidebar.markdown(f"**{username}** ({role})")
if _user_ns and role in ("client", "viewer"):
    st.sidebar.markdown(
        f'<div style="font-size:0.78rem;color:{_brand_primary};margin:-6px 0 4px;">{_user_ns}</div>',
        unsafe_allow_html=True,
    )

if st.sidebar.button("Logout", use_container_width=True):
    try:
        requests.post(
            f"{API_BASE}/auth/logout",
            json={"refresh_token": st.session_state.get("refresh_token", "")},
            headers=_get_headers(),
            timeout=3,
        )
    except Exception:
        pass
    # Delete server-side session so the URL key becomes invalid
    _sk = st.query_params.get(_SESSION_PARAM)
    if _sk:
        try:
            requests.delete(f"{API_BASE}/auth/session/{_sk}", timeout=2)
        except Exception:
            pass
        try:
            del st.query_params[_SESSION_PARAM]
        except Exception:
            pass
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")

# Onboarding replay — client/viewer only
if role in ("client", "viewer"):
    if st.sidebar.button("Show Setup Tour", use_container_width=True, key="sidebar_show_tour"):
        st.session_state["show_onboarding"] = True
        st.rerun()

# Background color picker — all logged-in users
with st.sidebar.expander("Background color", expanded=False):
    _has_bg = bool(st.session_state.get("custom_bg"))
    _use_bg = st.checkbox("Use custom background", value=_has_bg, key="sidebar_use_bg")
    if _use_bg:
        _picked = st.color_picker(
            "Color",
            value=st.session_state.get("custom_bg", "#0A1F0A"),
            key="sidebar_bg_color",
        )
        st.session_state["custom_bg"] = _picked
        st.caption("Text auto-adjusts for readability.")
    else:
        st.session_state.pop("custom_bg", None)

st.sidebar.markdown("---")

health = api_get_cached("/health")
if health and health.get("status") == "ok":
    st.sidebar.markdown(f'<div style="color:{_brand_primary};font-size:0.8rem;">● API online · v{health.get("version","?")}</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div style="color:#ef4444;font-size:0.8rem;">● API offline</div>', unsafe_allow_html=True)

st.sidebar.markdown(f'<div style="color:{_brand_muted};font-size:0.75rem;margin-top:4px;">{datetime.now().strftime("%a %d %b · %H:%M")}</div>', unsafe_allow_html=True)

# ── Page dispatch ─────────────────────────────────────────────────────────────
# Lazy imports — only load the selected page module, not all 9 at once.
# Saves ~2.7s on login page cold load and avoids importing heavy page deps early.
import importlib

_PAGE_MODULES = {
    "Overview":      "dashboard._pages._overview",
    "Agents":        "dashboard._pages._agents",
    "Memory":        "dashboard._pages._memory",
    "Workflows":     "dashboard._pages._workflows",
    "Projects":      "dashboard._pages._projects",
    "Outputs":       "dashboard._pages._outputs",
    "Tickets":       "dashboard._pages._tickets",
    "Observability": "dashboard._pages._observability",
    "Settings":      "dashboard._pages._settings",
    "Admin":         "dashboard._pages._admin",
    "Usage":         "dashboard._pages._usage",
}

_PAGE_GETTERS = {
    "Overview":      api_get_cached,
    "Agents":        api_get_cached,
    "Memory":        api_get_cached,
    "Workflows":     api_get_cached,
    "Projects":      api_get,
    "Outputs":       api_get_cached,
    "Tickets":       api_get,
    "Observability": api_get_cached,
    "Settings":      api_get,
    "Admin":         api_get_cached,
    "Usage":         api_get_cached,
}

_mod = importlib.import_module(_PAGE_MODULES[page])
_mod.render(_PAGE_GETTERS[page], api_post, bulk_delete)
