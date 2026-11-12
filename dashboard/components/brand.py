"""Brand CSS injection — dark (deep forest) / light (clean white) themes.

Design tokens match CustomCommand reference project exactly.
Dark:  near-black green bg (#0A1F0A) with green-tinted surfaces.
Light: clean white bg with gray borders, near-black text.
"""
from html import escape as _esc
import streamlit as st
import streamlit.components.v1 as _components
from dashboard.components.proxy import PROXY_CSS
from vault.schemas import safe_brand_colors

PRIMARY       = "#407E3C"
ACCENT        = "#5a9e56"
PRIMARY_LIGHT = "#5a9e56"   # alias kept for page imports
PRIMARY_LT    = "#5a9e56"
PRIMARY_DK    = "#2d5a29"
WHITE         = "#FFFFFF"
DANGER        = "#ef4444"
WARNING       = "#f59e0b"
SURFACE       = "#163A17"   # dark-mode default; pages should use get_theme_vars()

THEMES = {
    "dark": {
        "BG":          "#0A1F0A",
        "SURFACE":     "#163A17",
        "SURFACE2":    "#0F2D10",
        "TEXT":        "#E8F5E8",
        "TEXT_MUTED":  "#7DBF7E",
        "BORDER":      "#2D5C2E",
        "BTN_BG":      "#407E3C",
        "BTN_TEXT":    "#ffffff",
        "BTN_HOVER_BG":"#5a9e56",
        "INPUT_BG":    "#163A17",
        "INPUT_TEXT":  "#E8F5E8",
        "LOGO1":       "#ffffff",
        "LOGO2":       "#7DBF7E",
        "CARD_TOP":    "#5a9e56",
        "PLOT_BG":     "#163A17",
        "GRID":        "#2D5C2E",
        "GLOW":        "rgba(90,158,86,0.14)",
    },
    "light": {
        "BG":          "#FBF8F3",   # warm off-white (marketplace-style); tests/test_contrast.py guards text on it
        "SURFACE":     "#FFFFFF",
        "SURFACE2":    "#F3EFE8",
        "TEXT":        "#1C1B18",
        "TEXT_MUTED":  "#5C574E",
        "BORDER":      "#E3DDD2",
        "BTN_BG":      "#407E3C",
        "BTN_TEXT":    "#ffffff",
        "BTN_HOVER_BG":"#5a9e56",
        "INPUT_BG":    "#ffffff",
        "INPUT_TEXT":  "#1A1A1A",
        "LOGO1":       "#407E3C",
        "LOGO2":       "#5a9e56",
        "CARD_TOP":    "#407E3C",
        "PLOT_BG":     "#ffffff",
        "GRID":        "#EEE9DF",
        "GLOW":        "rgba(64,126,60,0.13)",
    },
}

# Module-level refs updated on each inject() call — importable by pages
TEXT_MUTED = THEMES["dark"]["TEXT_MUTED"]
_CURRENT_THEME: dict = THEMES["dark"]


def nav_palette(is_dark: bool) -> dict:
    """Sidebar nav colors. Text alphas are chosen so every text tier is >= 4.5:1 (WCAG AA)
    against `bg`; tests/test_contrast.py enforces this."""
    if is_dark:
        return {
            "bg": "#0F2D10", "fg": "#ffffff",
            "group": "rgba(255,255,255,0.60)", "item": "rgba(255,255,255,0.75)",
            "divider": "rgba(255,255,255,0.08)", "hover": "rgba(255,255,255,0.05)",
            "active_bg": "rgba(255,255,255,0.07)", "active_text": "#ffffff",
            "accent": "#7DBF7E", "badge_bg": "#407E3C",
        }
    return {
        "bg": "#F3EFE8", "fg": "#000000",
        "group": "rgba(0,0,0,0.60)", "item": "rgba(0,0,0,0.70)",
        "divider": "rgba(0,0,0,0.08)", "hover": "rgba(0,0,0,0.04)",
        "active_bg": "rgba(64,126,60,0.08)", "active_text": "#1A1A1A",
        "accent": "#407E3C", "badge_bg": "#407E3C",
    }


def get_theme() -> str:
    return st.session_state.get("theme", "dark")


def get_theme_vars() -> dict:
    """Return current theme token dict. Call after inject() or at render time."""
    return THEMES[get_theme()]


def get_ns_brand() -> dict:
    """Return namespace branding overrides stored in session_state.
    Keys: color, icon, company_name, accent_color, bg_color.
    Empty dict when admin/operator or no branding configured."""
    return safe_brand_colors(st.session_state.get("ns_brand") or {})


# ── Custom background helpers ─────────────────────────────────────────────────

def _luminance(hex_color: str) -> float:
    """WCAG 2.1 relative luminance (0 = black, 1 = white)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
        def lin(c):
            return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
        return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
    except Exception:
        return 0.0


def _mix(hex_color: str, with_white: bool, amount: float) -> str:
    """Mix hex_color toward white (with_white=True) or black (False) by amount 0-1."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if with_white:
            r = min(255, int(r + (255-r)*amount))
            g = min(255, int(g + (255-g)*amount))
            b = min(255, int(b + (255-b)*amount))
        else:
            r = max(0, int(r*(1-amount)))
            g = max(0, int(g*(1-amount)))
            b = max(0, int(b*(1-amount)))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _custom_bg_css(bg_hex: str) -> str:
    """CSS override for custom background with auto-derived contrast text/surface colors."""
    if not bg_hex or not bg_hex.startswith("#") or len(bg_hex) not in (4, 7):
        return ""
    lum = _luminance(bg_hex)
    is_light = lum > 0.45  # bias toward dark text for ambiguous mid-tones

    if is_light:
        TEXT      = "#1A1A1A"
        T_MUTED   = "#6B7280"
        SURFACE   = _mix(bg_hex, False, 0.05)
        SURFACE2  = _mix(bg_hex, False, 0.09)
        BORDER    = "rgba(0,0,0,0.13)"
        INP_BG    = bg_hex
        INP_TEXT  = "#1A1A1A"
    else:
        TEXT      = "#E8F5E8"
        T_MUTED   = "#9CA3AF"
        SURFACE   = _mix(bg_hex, True, 0.08)
        SURFACE2  = _mix(bg_hex, True, 0.04)
        BORDER    = "rgba(255,255,255,0.12)"
        INP_BG    = SURFACE
        INP_TEXT  = "#E8F5E8"

    return f"""<style>
/* ── Custom background override ── */
html, body, .stApp, [class*="css"] {{
    background-color: {bg_hex} !important;
    color: {TEXT} !important;
}}
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {{
    background-color: {bg_hex} !important;
}}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {{
    background-color: {SURFACE2} !important;
    border-right: 1px solid {BORDER} !important;
}}
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] *:not(button):not(button *):not(svg):not(svg *) {{
    color: {TEXT} !important;
    -webkit-text-fill-color: {TEXT} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
    color: {TEXT} !important;
    -webkit-text-fill-color: {TEXT} !important;
    opacity: 1 !important;
}}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6 {{
    color: {TEXT} !important;
}}
.stApp p, .stApp li, .stApp label,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stText"] {{
    color: {TEXT} !important;
}}
[data-testid="stCaptionContainer"] p {{
    color: {T_MUTED} !important;
}}
[data-testid="metric-container"],
[data-testid="metric-container"] * {{
    background-color: {SURFACE} !important;
    color: {TEXT} !important;
}}
label[data-testid="stMetricLabel"],label[data-testid="stMetricLabel"] *,
div[data-testid="stMetricLabel"],div[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"],[data-testid="stMetricValue"] * {{
    color: {TEXT} !important;
    -webkit-text-fill-color: {TEXT} !important;
    opacity: 1 !important;
    filter: none !important;
}}
input, textarea,
.stTextInput input, .stTextArea textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {{
    background-color: {INP_BG} !important;
    color: {INP_TEXT} !important;
    border-color: {BORDER} !important;
}}
ul[data-testid="stSelectboxVirtualDropdown"] li, li[role="option"] {{
    background-color: {SURFACE} !important;
    color: {TEXT} !important;
}}
button[data-baseweb="tab"] {{ color: {T_MUTED} !important; }}
.aurora-hero-card {{
    background: {SURFACE} !important;
    border-color: {BORDER} !important;
}}
[data-testid="stMarkdownContainer"] pre,
[data-testid="stMarkdownContainer"] pre code,
[data-testid="stMarkdownContainer"] code {{
    background-color: {SURFACE2} !important;
    color: {TEXT} !important;
    border-color: {BORDER} !important;
}}
.stDataFrame, iframe {{ background-color: {SURFACE} !important; }}
hr {{ border-color: {BORDER} !important; }}
::-webkit-scrollbar-track {{ background: {bg_hex}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; }}
div[data-testid="stToggle"] {{
    background: {SURFACE} !important;
    border-color: {BORDER} !important;
}}
div[data-testid="stToggle"] p {{ color: {T_MUTED} !important; }}
div[data-testid="stToggle"] span[data-testid="stToggleSlider"] {{
    background-color: {BORDER} !important;
    border-color: {BORDER} !important;
}}
</style>"""


@st.cache_data(ttl=300, max_entries=20)
def _ns_brand_css_cached(color: str, accent_color: str, theme: str) -> str:
    """Cached wrapper — keyed on brand color + accent + theme (stable per session)."""
    return _ns_brand_css({"color": color, "accent_color": accent_color}, _theme_override=theme)


def _ns_brand_css(brand: dict, _theme_override: str | None = None) -> str:
    """Full theme override using namespace brand tokens.
    Light mode: uses brand tokens directly (ivory/plum palette).
    Dark mode: derives a deep dark variant from the brand primary color.
    """
    brand = safe_brand_colors(brand)
    color = (brand.get("color") or "").strip()
    if not color or not color.startswith("#"):
        return ""

    theme   = _theme_override if _theme_override else get_theme()
    is_dark = (theme == "dark")

    def _v(key: str, fallback: str) -> str:
        raw = (brand.get(key) or "").strip()
        return raw if (raw and raw.startswith("#")) else fallback

    accent = _v("accent_color", color)
    hover  = _v("hover_color",  color)

    if is_dark:
        # Derive dark-mode palette from brand primary — preserves brand identity in dark
        bg       = _mix(color, False, 0.88)   # near-black tinted with brand hue
        surface  = _mix(color, False, 0.78)   # dark surface
        surface2 = _mix(color, False, 0.70)   # slightly lighter surface
        text     = "#FAF8F7"                  # brand ivory — high contrast on dark
        muted    = _v("accent_color", "#C8A96E")  # accent color as muted text on dark
        border   = _mix(color, False, 0.52)   # mid-dark border
        inp_bg   = _mix(color, False, 0.78)
    else:
        bg       = _v("bg_color",         "")
        surface  = _v("surface_color",    "")
        surface2 = _v("surface2_color",   "")
        text     = _v("text_color",       "")
        muted    = _v("text_muted_color", "")
        border   = _v("border_color",     "")
        inp_bg   = _v("input_bg",         "")

    sf2 = surface2 or surface
    has_palette = bool(bg and surface and text and muted and border)

    # compute a visible toggle-off track color for light mode
    # brand border (#E8DDE5) is near-white — use accent color at 40% opacity or
    # a mid-tone derived from brand primary
    _toggle_off_track = accent if not is_dark else border

    # ── Base CSS: always applied regardless of palette completeness ───────────
    css = f"""
/* ── NS Brand: override Streamlit --primary-color CSS var.
   html body .stApp has specificity (0,1,2)=12 > :root (0,1,0)=10,
   so this beats config.toml primaryColor without needing !important on vars ── */
html body .stApp,
html body [data-testid="stAppViewContainer"] {{
    --primary-color: {color};
    --primaryColor: {color};
}}
/* ── NS Brand: iframe transparent — prevents green SURFACE bleed ── */
iframe {{
    background-color: transparent !important;
}}
/* ── NS Brand: buttons ── */
html body .stButton > button,
html body .stFormSubmitButton > button,
html body button[data-testid="baseButton-secondary"],
html body button[data-testid="baseButton-primary"],
html body button[kind="primary"],
html body button[kind="secondary"] {{
    background-color: {color} !important;
    color: #ffffff !important;
    border: none !important;
}}
html body .stButton > button p,
html body .stButton > button span,
html body .stButton > button div,
html body .stFormSubmitButton > button p,
html body .stFormSubmitButton > button span,
html body .stFormSubmitButton > button div,
html body button[data-testid="baseButton-secondary"] p,
html body button[data-testid="baseButton-primary"] p {{
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}}
html body .stButton > button:hover,
html body .stFormSubmitButton > button:hover,
html body button[data-testid="baseButton-secondary"]:hover,
html body button[data-testid="baseButton-primary"]:hover {{
    background-color: {hover} !important;
}}
/* ── NS Brand: sidebar button text — explicit override; *:not(button *) is
   invalid CSS3 (compound arg) so browsers silently ignore it, causing dark
   sidebar text to bleed onto button children via the wildcard rule.
   This high-specificity rule corrects that. ── */
html body section[data-testid="stSidebar"] .stButton > button,
html body section[data-testid="stSidebar"] .stButton > button p,
html body section[data-testid="stSidebar"] .stButton > button span,
html body section[data-testid="stSidebar"] .stButton > button div {{
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}}
/* ── NS Brand: tabs ── */
html body button[data-baseweb="tab"][aria-selected="true"] {{
    color: {color} !important;
    border-bottom: 3px solid {color} !important;
}}
html body button[data-baseweb="tab"] {{
    background: transparent !important;
}}
/* ── NS Brand: metrics border accent ── */
html body [data-testid="metric-container"] {{
    border-left: 4px solid {color} !important;
}}
/* ── NS Brand: radio dots — sidebar nav + inline st.radio widgets ── */
/* ALL radio divs: brand border */
html body section[data-testid="stSidebar"] [role="radio"] div,
html body [data-baseweb="radio-group"] [role="radio"] div,
html body [data-baseweb="radio"] [role="radio"] div,
html body [data-testid="stRadio"] [role="radio"] div {{
    border-color: {color} !important;
}}
/* INACTIVE radio: transparent fill (both background shorthand and background-color) */
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] div,
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] div div,
html body [data-baseweb="radio-group"] [role="radio"][aria-checked="false"] div,
html body [data-baseweb="radio-group"] [role="radio"][aria-checked="false"] div div,
html body [data-baseweb="radio"] [role="radio"][aria-checked="false"] div,
html body [data-baseweb="radio"] [role="radio"][aria-checked="false"] div div {{
    background: transparent !important;
    background-color: transparent !important;
}}
/* ACTIVE radio: brand fill */
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] div,
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] div div,
html body [data-baseweb="radio-group"] [role="radio"][aria-checked="true"] div,
html body [data-baseweb="radio-group"] [role="radio"][aria-checked="true"] div div,
html body [data-baseweb="radio"] [role="radio"][aria-checked="true"] div,
html body [data-baseweb="radio"] [role="radio"][aria-checked="true"] div div,
html body [data-testid="stRadio"] [role="radio"][aria-checked="true"] div {{
    background: {color} !important;
    background-color: {color} !important;
    border-color: {color} !important;
}}
/* SVG dot fallback */
html body [data-baseweb="radio"] svg circle,
html body [data-baseweb="radio"] svg path,
html body section[data-testid="stSidebar"] [role="radio"] svg circle,
html body section[data-testid="stSidebar"] [role="radio"] svg path,
html body [data-testid="stRadio"] svg circle,
html body [data-testid="stRadio"] svg path {{ fill: {color} !important; }}
/* ── NS Brand: sidebar active nav row highlight + bold text ── */
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] {{
    background-color: {color}22 !important;
    border-radius: 8px !important;
    padding: 4px 6px !important;
}}
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] p,
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] span {{
    font-weight: 700 !important;
    color: {color} !important;
    -webkit-text-fill-color: {color} !important;
}}
/* inactive nav items */
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] p,
html body section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] span {{
    font-weight: 400 !important;
}}
/* ── NS Brand: links ── */
html body a {{ color: {color} !important; }}
.badge-ok {{
    background: {color}33 !important;
    border-color: {color}66 !important;
    color: {color} !important;
    -webkit-text-fill-color: {color} !important;
}}
"""

    # ── Full palette: applied when we have all color tokens ──────────────────
    if has_palette:
        css += f"""
/* ── NS Brand: page backgrounds ── */
html {{
    background-color: {bg} !important;
    color: {text} !important;
}}
html body,
html body .stApp,
html body [class*="css"] {{
    background-color: {bg} !important;
    color: {text} !important;
    font-family: 'Inter', system-ui, sans-serif !important;
}}
html body [data-testid="stAppViewContainer"],
html body [data-testid="stAppViewBlockContainer"] {{
    background-color: {bg} !important;
}}
html body header[data-testid="stHeader"],
html body [data-testid="stToolbar"],
html body [data-testid="stDecoration"] {{
    background-color: {bg} !important;
    border-bottom: 1px solid {border} !important;
}}

/* ── NS Brand: sidebar ── */
html body section[data-testid="stSidebar"],
html body section[data-testid="stSidebar"] > div {{
    background-color: {sf2} !important;
    border-right: 1px solid {border} !important;
}}
/* Only non-button, non-svg elements get the text color override */
html body section[data-testid="stSidebar"] *:not(button):not(svg) {{
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
}}
html body section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
html body section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
    opacity: 1 !important;
}}

/* ── NS Brand: typography ── */
html body .stApp h1,
html body .stApp h2,
html body .stApp h3,
html body .stApp h4,
html body .stApp h5,
html body .stApp h6 {{
    color: {text} !important;
    font-family: 'Inter', system-ui, sans-serif !important;
    font-weight: 700 !important;
}}
html body .stApp p,
html body .stApp li,
html body .stApp label,
html body [data-testid="stMarkdownContainer"] p,
html body [data-testid="stMarkdownContainer"] li,
html body [data-testid="stMarkdownContainer"] span,
html body [data-testid="stText"] {{
    color: {text} !important;
}}
html body [data-testid="stCaptionContainer"] p {{ color: {muted} !important; }}

/* ── NS Brand: metric cards ── */
html body [data-testid="metric-container"],
html body [data-testid="metric-container"] * {{
    background-color: {surface} !important;
    color: {text} !important;
}}
html body label[data-testid="stMetricLabel"],
html body label[data-testid="stMetricLabel"] *,
html body div[data-testid="stMetricLabel"],
html body div[data-testid="stMetricLabel"] * {{
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
    opacity: 1 !important;
    filter: none !important;
}}
html body [data-testid="stMetricValue"],
html body [data-testid="stMetricValue"] * {{
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
    opacity: 1 !important;
}}

/* ── NS Brand: widget labels (Prompt, Agent, etc.) ── */
html body [data-testid="stWidgetLabel"],
html body [data-testid="stWidgetLabel"] *,
html body [data-testid="stWidgetLabel"] p,
html body label[data-testid] {{
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
}}
/* ── NS Brand: inputs — target both element and BaseUI wrapper ── */
html body input,
html body textarea,
html body .stTextInput input,
html body .stTextArea textarea,
html body div[data-baseweb="select"] > div,
html body div[data-baseweb="input"] > div,
html body div[data-baseweb="textarea"],
html body div[data-baseweb="input"] {{
    background-color: {inp_bg or surface} !important;
    color: {text} !important;
    border-color: {border} !important;
}}
html body input:focus,
html body textarea:focus,
html body .stTextInput input:focus,
html body div[data-baseweb="textarea"]:focus-within,
html body div[data-baseweb="input"]:focus-within {{
    border-color: {color} !important;
    box-shadow: 0 0 0 2px {color}33 !important;
    outline: none !important;
}}
html body input::placeholder,
html body textarea::placeholder {{ color: {muted} !important; }}
html body ul[data-testid="stSelectboxVirtualDropdown"] li,
html body li[role="option"] {{
    background-color: {surface} !important;
    color: {text} !important;
}}

/* ── NS Brand: surfaces / cards ── */
html body .stDataFrame,
html body .stDataFrame * {{ background-color: {surface} !important; color: {text} !important; }}
html body hr {{ border-color: {border} !important; }}
::-webkit-scrollbar-track {{ background: {bg}; }}
::-webkit-scrollbar-thumb {{ background: {border}; }}
html body [data-testid="stMarkdownContainer"] pre,
html body [data-testid="stMarkdownContainer"] pre code,
html body [data-testid="stMarkdownContainer"] code {{
    background-color: {sf2} !important;
    color: {text} !important;
    border: 1px solid {border} !important;
}}
html body .aurora-hero-card {{
    background: {surface} !important;
    border-color: {border} !important;
}}
html body .agent-card,
html body .metric-card {{
    background: {surface} !important;
    border-color: {border} !important;
}}
html body .metric-label {{ color: {muted} !important; }}
html body .metric-value {{ color: {text} !important; }}

/* ── NS Brand: toggle ── */
html body div[data-testid="stToggle"] {{
    background: {surface} !important;
    border: 1px solid {border} !important;
}}
html body div[data-testid="stToggle"] p {{ color: {muted} !important; }}
html body div[data-testid="stToggle"] span[data-testid="stToggleSlider"] {{
    background-color: {_toggle_off_track} !important;
    border-color: {_toggle_off_track} !important;
}}
html body div[data-testid="stToggle"] input:checked + span[data-testid="stToggleSlider"] {{
    background-color: {color} !important;
    border-color: {color} !important;
}}

/* ── NS Brand: expanders ── */
html body [data-testid="stExpander"] {{
    background: {surface} !important;
    border: 1px solid {border} !important;
}}
html body [data-testid="stExpander"] summary,
html body [data-testid="stExpander"] summary * {{
    color: {text} !important;
    background: {surface} !important;
}}

/* ── NS Brand: chat input ── */
html body [data-testid="stChatInputContainer"],
html body [data-testid="stChatInputContainer"] > div,
html body [data-testid="stChatInputContainer"] > div > div {{
    background-color: {inp_bg or surface} !important;
    border-color: {border} !important;
    box-shadow: none !important;
}}
html body [data-testid="stChatInputContainer"] textarea {{
    background-color: {inp_bg or surface} !important;
    color: {text} !important;
    border: none !important;
}}
html body [data-testid="stChatInputContainer"]:focus-within,
html body [data-testid="stChatInputContainer"] > div:focus-within {{
    border-color: {color} !important;
    box-shadow: 0 0 0 2px {color}33 !important;
}}
html body [data-testid="stChatInputSubmitButton"] button,
html body [data-testid="stChatInputSubmitButton"] button:hover {{
    background-color: {color} !important;
    border-color: {color} !important;
}}
html body [data-testid="stChatInputSubmitButton"] button svg * {{
    fill: #ffffff !important;
}}

/* ── NS Brand: file uploader ── */
html body [data-testid="stFileUploaderDropzone"],
html body [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"],
html body section[data-testid="stFileUploader"] > div {{
    background-color: {color}22 !important;
    border-color: {color}66 !important;
    border-style: dashed !important;
}}
html body [data-testid="stFileUploaderDropzone"] *,
html body [data-testid="stFileUploaderDropzone"] span,
html body [data-testid="stFileUploaderDropzone"] p,
html body [data-testid="stFileUploaderDropzone"] small {{
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}}
html body [data-testid="stFileUploaderDropzone"] button,
html body [data-testid="stFileUploader"] button,
html body [data-testid="stFileUploaderDropzone"] button span {{
    background-color: {color} !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-color: {color} !important;
}}

/* ── NS Brand: audio input recorder ── */
html body [data-testid="stAudioInput"] {{
    background-color: {surface} !important;
    border: 1px solid {border} !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
}}
html body [data-testid="stAudioInput"] > div,
html body [data-testid="stAudioInput"] > div > div {{
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}
html body [data-testid="stAudioInput"] button,
html body [data-testid="stAudioInput"] button:hover,
html body [data-testid="stAudioInput"] button:focus {{
    background-color: {color} !important;
    background: {color} !important;
    border-color: {color} !important;
    border-radius: 50% !important;
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    flex-shrink: 0 !important;
}}
html body [data-testid="stAudioInput"] button svg path,
html body [data-testid="stAudioInput"] button svg polyline,
html body [data-testid="stAudioInput"] button svg polygon,
html body [data-testid="stAudioInput"] button svg circle,
html body [data-testid="stAudioInput"] button svg line,
html body [data-testid="stAudioInput"] button svg ellipse {{
    fill: #FAF8F7 !important;
    stroke: #FAF8F7 !important;
}}
html body [data-testid="stAudioInput"] button svg rect {{
    fill: none !important;
    background-color: transparent !important;
}}
/* Clear any white wrapper div/span inside button so mic SVG shows on purple bg */
html body [data-testid="stAudioInput"] button div,
html body [data-testid="stAudioInput"] button span {{
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}}
/* Kill green timer pill background — target all spans/elements inside */
html body [data-testid="stAudioInput"] span,
html body [data-testid="stAudioInput"] label {{
    background-color: transparent !important;
    color: {muted} !important;
    font-size: 0.8rem !important;
}}
/* Any element with an explicit background (Emotion green pill) → transparent */
html body [data-testid="stAudioInput"] [class*="css-"]:not(button) {{
    background-color: transparent !important;
    color: {text} !important;
}}
html body [data-testid="stAudioInput"] * {{ color: {text} !important; }}
"""

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Cormorant+Garamond:ital,wght@0,300;0,500;1,300&display=swap');
{css}
</style>"""


@st.cache_data(max_entries=2)
def _build_css(theme_key: str) -> str:
    t = THEMES[theme_key]
    invert  = "invert(0)" if theme_key == "dark" else "invert(1)"
    blend   = "difference" if theme_key == "dark" else "overlay"
    return f"""
<style>
/* Inter loaded via <link> in inject() — not @import (avoids render-block) */

html, body, .stApp, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: {t['BG']} !important;
    color: {t['TEXT']} !important;
}}

/* ── App shell ── */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {{
    background-color: {t['BG']} !important;
}}
/* soft brand-green glow at the top of the page (static — no animation) */
[data-testid="stAppViewContainer"] {{
    background-image: radial-gradient(ellipse 70% 340px at 50% 0%, {t['GLOW']}, transparent) !important;
    background-repeat: no-repeat !important;
}}

/* ── Streamlit header bar (Deploy / ⋮ settings) — override config.toml dark default ── */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {{
    background-color: {t['BG']} !important;
    border-bottom: 1px solid {t['BORDER']} !important;
}}
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] button span,
header[data-testid="stHeader"] button p,
[data-testid="stToolbar"] button,
[data-testid="stToolbar"] button span,
[data-testid="stToolbarActions"] button span,
[data-testid="stToolbarActions"] button p {{
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
    background-color: transparent !important;
    opacity: 1 !important;
}}
header[data-testid="stHeader"] button svg path:not([fill="none"]),
header[data-testid="stHeader"] button svg circle,
header[data-testid="stHeader"] button svg polyline,
header[data-testid="stHeader"] button svg polygon,
header[data-testid="stHeader"] button svg line,
header[data-testid="stHeader"] button svg ellipse,
[data-testid="stToolbar"] button svg path:not([fill="none"]),
[data-testid="stToolbar"] button svg circle,
[data-testid="stToolbarActions"] button svg path:not([fill="none"]),
[data-testid="stToolbarActions"] button svg circle {{
    fill: {t['TEXT']} !important;
    stroke: {t['TEXT']} !important;
    opacity: 1 !important;
}}
header[data-testid="stHeader"] button svg path[fill="none"],
header[data-testid="stHeader"] button svg rect,
[data-testid="stToolbar"] button svg path[fill="none"],
[data-testid="stToolbar"] button svg rect,
[data-testid="stToolbarActions"] button svg path[fill="none"],
[data-testid="stToolbarActions"] button svg rect {{
    fill: none !important;
}}


/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {{
    background-color: {t['SURFACE2']} !important;
    border-right: 1px solid {t['BORDER']} !important;
}}

/* ── Sidebar text — force theme color, cover webkit override ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] *:not(button):not(button *):not(svg):not(svg *) {{
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] div,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {{
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
    opacity: 1 !important;
}}

/* ── Toolbar header buttons (Deploy, ⋮ settings) — always visible ── */
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] button span,
header[data-testid="stHeader"] button p,
[data-testid="stToolbar"] button,
[data-testid="stToolbar"] button span,
[data-testid="stToolbar"] button p,
[data-testid="stToolbarActions"] button,
[data-testid="stToolbarActions"] button span {{
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
    background-color: transparent !important;
    opacity: 1 !important;
}}
header[data-testid="stHeader"] button svg path:not([fill="none"]),
header[data-testid="stHeader"] button svg circle,
header[data-testid="stHeader"] button svg polyline,
header[data-testid="stHeader"] button svg polygon,
header[data-testid="stHeader"] button svg line,
header[data-testid="stHeader"] button svg ellipse,
[data-testid="stToolbar"] button svg path:not([fill="none"]),
[data-testid="stToolbar"] button svg circle,
[data-testid="stToolbarActions"] button svg path:not([fill="none"]),
[data-testid="stToolbarActions"] button svg circle {{
    fill: {t['TEXT']} !important;
    stroke: {t['TEXT']} !important;
    opacity: 1 !important;
}}
header[data-testid="stHeader"] button svg path[fill="none"],
header[data-testid="stHeader"] button svg rect,
[data-testid="stToolbar"] button svg path[fill="none"],
[data-testid="stToolbar"] button svg rect,
[data-testid="stToolbarActions"] button svg path[fill="none"],
[data-testid="stToolbarActions"] button svg rect {{
    fill: none !important;
}}

/* ── Toolbar action button icon wrapper (Streamlit 1.30+) ── */
/* Icon is a CSS background-image (url) on a div — use filter to colorize, not fill */
[data-testid="stAppDeployButton"],
[data-testid="stAppDeployButton"] button,
[data-testid="stAppToolbar"],
[data-testid="stToolbarActionButton"],
[data-testid="stToolbarActionButtonLabel"],
[data-testid="stToolbarItems"] {{
    background-color: transparent !important;
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
}}
[data-testid="stToolbarActionButtonIcon"] {{
    display: none !important;
}}

/* ── Sidebar collapse icon — broad selector sweep ── */
button[data-testid="stBaseButton-header"] svg,
button[data-testid="stBaseButton-header"] svg *,
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg *,
[data-testid="stSidebarCollapsedControl"] button svg,
[data-testid="stSidebarCollapsedControl"] button svg *,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebarCollapseButton"] svg *,
[data-testid="collapsedControl"] svg,
[data-testid="collapsedControl"] svg *,
[data-testid="stSidebarNavCollapseButton"] svg,
[data-testid="stSidebarNavCollapseButton"] svg *,
section[data-testid="stSidebar"] > div > div > button svg,
section[data-testid="stSidebar"] > div > div > button svg * {{
    fill: {t['TEXT']} !important;
    stroke: {t['TEXT']} !important;
    color: {t['TEXT']} !important;
}}

/* ── Text — semantic elements ── */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
    font-family: 'Inter', sans-serif;
    color: {t['TEXT']} !important;
}}
.stApp p, .stApp li, .stApp label {{
    color: {t['TEXT']} !important;
}}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stText"] {{
    color: {t['TEXT']} !important;
}}
[data-testid="stCaptionContainer"] p {{
    color: {t['TEXT_MUTED']} !important;
}}

/* ── Code blocks ── */
[data-testid="stMarkdownContainer"] pre,
[data-testid="stMarkdownContainer"] pre code {{
    background-color: {t['SURFACE2']} !important;
    color: {t['TEXT']} !important;
    border: 1px solid {t['BORDER']} !important;
    border-radius: 6px !important;
}}
[data-testid="stMarkdownContainer"] code {{
    background-color: {t['SURFACE2']} !important;
    color: {t['TEXT']} !important;
}}

/* ── Metric values ── */
[data-testid="metric-container"],
[data-testid="metric-container"] * {{
    background-color: {t['SURFACE']} !important;
    color: {t['TEXT']} !important;
}}
[data-testid="metric-container"] {{
    border-left: 4px solid {PRIMARY} !important;
    padding: 0.8rem 1rem !important;
    border-radius: 8px !important;
}}
label[data-testid="stMetricLabel"],
label[data-testid="stMetricLabel"] *,
div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] * {{
    color: {t['TEXT']} !important;
    opacity: 1 !important;
    filter: none !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
}}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {{
    color: {t['TEXT']} !important;
    opacity: 1 !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
}}

/* ── Input placeholders ── */
input::placeholder, textarea::placeholder {{
    color: {t['TEXT_MUTED']} !important;
    opacity: 0.8 !important;
}}

/* ── Buttons ── */
.stButton > button,
.stButton > button:focus,
.stButton > button:active,
.stFormSubmitButton > button,
.stFormSubmitButton > button:focus,
.stFormSubmitButton > button:active,
button[data-testid="baseButton-secondary"],
button[data-testid="baseButton-primary"],
button[kind="primary"],
button[kind="secondary"] {{
    background-color: {t['BTN_BG']} !important;
    color: {t['BTN_TEXT']} !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
}}
.stButton > button p,
.stButton > button span,
.stFormSubmitButton > button p,
.stFormSubmitButton > button span,
button[data-testid="baseButton-secondary"] p,
button[data-testid="baseButton-primary"] p {{
    color: {t['BTN_TEXT']} !important;
}}
.stButton > button:hover,
.stFormSubmitButton > button:hover,
button[data-testid="baseButton-secondary"]:hover,
button[data-testid="baseButton-primary"]:hover {{
    background-color: {t['BTN_HOVER_BG']} !important;
    color: {t['BTN_TEXT']} !important;
}}

/* ── Toolbar / header buttons — transparent, never catch brand color ── */
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] button:hover,
header[data-testid="stHeader"] button:focus,
header[data-testid="stHeader"] button:active,
[data-testid="stToolbar"] button,
[data-testid="stToolbar"] button:hover,
[data-testid="stMainMenuButton"],
[data-testid="stMainMenuButton"]:hover {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* ── Password eye toggle — target by input container, not brittle testid ── */
[data-testid="stTextInput"] button,
[data-testid="stTextInput"] button:hover,
[data-testid="stTextInput"] button:focus,
[data-testid="stTextInput"] button:active {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 4px !important;
}}
[data-testid="stTextInput"] button svg path,
[data-testid="stTextInput"] button svg rect,
[data-testid="stTextInput"] button svg circle,
[data-testid="stTextInput"] button svg * {{
    fill: {t['TEXT']} !important;
    stroke: {t['TEXT']} !important;
    color: {t['TEXT']} !important;
}}

/* ── Inputs / selects / textareas — kill all dark grey ── */
input, textarea,
.stTextInput input,
.stTextArea textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div > div,
div[data-baseweb="select"] > div > div > div,
div[data-baseweb="select"] div[data-baseweb="select-dropdown"],
div[data-baseweb="popover"] > div,
div[data-baseweb="input"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div * {{
    background-color: {t['INPUT_BG']} !important;
    color: {t['INPUT_TEXT']} !important;
    border-color: {t['BORDER']} !important;
    font-family: 'Inter', sans-serif !important;
}}
/* Selectbox chevron / icon */
[data-testid="stSelectbox"] svg, [data-testid="stSelectbox"] svg path {{
    fill: {t['TEXT_MUTED']} !important;
}}
/* Selectbox open dropdown list */
[data-baseweb="menu"], [data-baseweb="menu"] ul,
[data-baseweb="list"], [data-baseweb="list-item"] {{
    background-color: {t['SURFACE']} !important;
    border-color: {t['BORDER']} !important;
}}
[data-baseweb="list-item"]:hover, [data-baseweb="list-item"]:focus {{
    background-color: {PRIMARY}22 !important;
}}
/* Voice input — kill grey progress/timer bar */
[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div,
[data-testid="stAudioInput"] > div > div {{
    background-color: {t['INPUT_BG']} !important;
    border: 1.5px solid {t['BORDER']} !important;
    border-radius: 10px !important;
}}
[data-testid="stAudioInput"] [class*="progress"],
[data-testid="stAudioInput"] [class*="timer"],
[data-testid="stAudioInput"] div:not(button):not(:has(button)) {{
    background-color: transparent !important;
    color: {PRIMARY} !important;
}}
.stTextInput input:focus,
.stTextArea textarea:focus,
div[data-baseweb="input"]:focus-within > div {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 2px {PRIMARY}22 !important;
    outline: none !important;
}}

/* ── Chat input — floating card ── */

/* stBottom wrapper: transparent, no chrome */
html body div[data-testid="stBottom"],
html body div[data-testid="stBottom"] > div,
html body div[data-testid="stBottom"] > div > div {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding-bottom: 12px !important;
}}

/* Floating card */
html body [data-testid="stChatInputContainer"],
html body [data-testid="stChatInputContainer"] > div {{
    background: {'#0f1f10' if t['BG'] < '#888' else '#ffffff'} !important;
    background-color: {'#0f1f10' if t['BG'] < '#888' else '#ffffff'} !important;
    border: 1px solid {'rgba(90,158,86,0.22)' if t['BG'] < '#888' else 'rgba(64,126,60,0.18)'} !important;
    border-radius: 20px !important;
    box-shadow: {'0 0 0 1px rgba(64,126,60,0.12), 0 8px 40px rgba(0,0,0,0.45)' if t['BG'] < '#888' else '0 0 0 1px rgba(64,126,60,0.10), 0 4px 24px rgba(0,0,0,0.10)'} !important;
    max-width: 700px !important;
    width: 100% !important;
    margin: 0 auto !important;
    transition: border-color .2s, box-shadow .2s !important;
    padding: 4px 6px !important;
}}
html body [data-testid="stChatInputContainer"]:focus-within,
html body [data-testid="stChatInputContainer"] > div:focus-within {{
    border-color: rgba(90,158,86,0.60) !important;
    box-shadow: {'0 0 0 3px rgba(64,126,60,0.22), 0 8px 40px rgba(0,0,0,0.50)' if t['BG'] < '#888' else '0 0 0 3px rgba(64,126,60,0.18), 0 4px 24px rgba(0,0,0,0.12)'} !important;
}}

/* Textarea */
html body [data-testid="stChatInputContainer"] textarea {{
    background: transparent !important;
    background-color: transparent !important;
    color: {'#d4edda' if t['BG'] < '#888' else '#1a1a1a'} !important;
    border: none !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.6 !important;
    caret-color: {PRIMARY} !important;
    padding: 14px 56px 14px 16px !important;
    min-height: 52px !important;
    resize: none !important;
}}
html body [data-testid="stChatInputContainer"] textarea::placeholder {{
    color: {'rgba(255,255,255,0.30)' if t['BG'] < '#888' else 'rgba(0,0,0,0.35)'} !important;
    opacity: 1 !important;
}}

/* Submit button — green circle */
html body button[data-testid="stChatInputSubmitButton"],
html body [data-testid="stChatInputSubmitButton"],
html body [data-testid="stChatInputSubmitButton"] button {{
    background-color: {PRIMARY} !important;
    background: {PRIMARY} !important;
    border: none !important;
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    box-shadow: 0 2px 10px rgba(64,126,60,0.50) !important;
    transition: background .15s, transform .12s, box-shadow .15s !important;
}}
html body button[data-testid="stChatInputSubmitButton"]:hover,
html body [data-testid="stChatInputSubmitButton"]:hover {{
    background-color: #5a9e56 !important;
    background: #5a9e56 !important;
    transform: scale(1.07) !important;
    box-shadow: 0 4px 16px rgba(64,126,60,0.65) !important;
}}
html body button[data-testid="stChatInputSubmitButton"] svg path:not([fill="none"]),
html body button[data-testid="stChatInputSubmitButton"] svg line,
html body button[data-testid="stChatInputSubmitButton"] svg polyline,
html body button[data-testid="stChatInputSubmitButton"] svg circle,
html body button[data-testid="stChatInputSubmitButton"] svg rect,
html body button[data-testid="stChatInputSubmitButton"] svg *,
html body [data-testid="stChatInputSubmitButton"] svg * {{
    fill: #ffffff !important;
    stroke: #ffffff !important;
}}

/* Attach "+" action button */
html body button[data-testid="stChatInputActionButton"],
html body [data-testid="stChatInputActionButton"] {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 50% !important;
    transition: background .15s !important;
}}
html body button[data-testid="stChatInputActionButton"]:hover {{
    background-color: {'rgba(64,126,60,0.15)' if t['BG'] < '#888' else 'rgba(64,126,60,0.08)'} !important;
}}
html body button[data-testid="stChatInputActionButton"] svg *,
html body [data-testid="stChatInputActionButton"] svg * {{
    fill: {PRIMARY} !important;
    stroke: {PRIMARY} !important;
}}

/* ── File uploader — neutral, not green ── */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {{
    background-color: {t['SURFACE']} !important;
    border: 1.5px dashed {t['BORDER']} !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: {PRIMARY} !important;
    background-color: {t['SURFACE2']} !important;
}}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {{
    color: {t['TEXT_MUTED']} !important;
    -webkit-text-fill-color: {t['TEXT_MUTED']} !important;
}}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploader"] button {{
    background-color: transparent !important;
    background: transparent !important;
    border: 1px solid {t['BORDER']} !important;
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
    box-shadow: none !important;
}}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploader"] button:hover {{
    border-color: {PRIMARY} !important;
    color: {PRIMARY} !important;
    -webkit-text-fill-color: {PRIMARY} !important;
}}

/* ── Dataframe / table — kill dark grey header ── */
[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] thead th,
[data-testid="stDataFrame"] [role="columnheader"],
.stDataFrame thead tr th,
table thead tr th {{
    background-color: {t['SURFACE2']} !important;
    color: {t['TEXT']} !important;
    border-color: {t['BORDER']} !important;
}}
[data-testid="stDataFrame"] td,
[data-testid="stDataFrame"] [role="gridcell"],
.stDataFrame tbody tr td,
table tbody tr td {{
    background-color: {t['SURFACE']} !important;
    color: {t['TEXT']} !important;
    border-color: {t['BORDER']} !important;
}}
[data-testid="stDataFrame"] tr:hover td,
.stDataFrame tbody tr:hover td {{
    background-color: {t['SURFACE2']} !important;
}}

/* ── Selectbox dropdown options ── */
ul[data-testid="stSelectboxVirtualDropdown"] li,
li[role="option"] {{
    background-color: {t['SURFACE']} !important;
    color: {t['TEXT']} !important;
}}

/* ── Proxy buttons (nav, KPI cards, catalog cards) — clicked via JS, never shown ── */
{PROXY_CSS}

/* ── Script-only iframes (components.html height=0): out of flow so they add no 26px row + 16px gap each ── */
[data-testid="element-container"]:has(> iframe[height="0"]),
[data-testid="stElementContainer"]:has(> iframe[height="0"]),
[data-testid="stElementContainer"][height="0px"],
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stElementContainer"]:has(> [data-testid="stButton"][style*="display: none"]) {{
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
}}

/* ── Sidebar nav — brand-colored radio dots ── */
section[data-testid="stSidebar"] [role="radio"] {{
    border: none !important;
    background: transparent !important;
    border-radius: 6px !important;
    padding: 3px 8px !important;
    margin: 1px 0 !important;
    transition: background 0.12s ease !important;
    border-left: 3px solid transparent !important;
}}
section[data-testid="stSidebar"] [role="radio"]:hover {{
    background-color: {t['SURFACE']} !important;
}}
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] {{
    background-color: {PRIMARY}15 !important;
    border-left: 3px solid {PRIMARY} !important;
    border-radius: 0 6px 6px 0 !important;
}}
/* Active dot: green */
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] > div:first-child div {{
    border-color: {PRIMARY} !important;
    background: {PRIMARY} !important;
    background-color: {PRIMARY} !important;
}}
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] > div:first-child div div {{
    background: #ffffff !important;
    background-color: #ffffff !important;
}}
/* SVG active: green */
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] svg circle,
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] svg path {{
    fill: {PRIMARY} !important;
    stroke: {PRIMARY} !important;
}}
/* Inactive dot: white border, transparent fill */
section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] > div:first-child div {{
    border-color: rgba(255,255,255,0.55) !important;
    background: transparent !important;
    background-color: transparent !important;
}}
/* SVG inactive: white */
section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] svg circle,
section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] svg path {{
    fill: transparent !important;
    stroke: rgba(255,255,255,0.55) !important;
}}
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] p,
section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] span {{
    font-weight: 700 !important;
    color: {PRIMARY} !important;
    -webkit-text-fill-color: {PRIMARY} !important;
}}
section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] p,
section[data-testid="stSidebar"] [role="radio"][aria-checked="false"] span {{
    font-weight: 400 !important;
    color: {t['TEXT']} !important;
    -webkit-text-fill-color: {t['TEXT']} !important;
}}
/* ── Inline radio (non-sidebar forms) — clean dots ── */
[data-baseweb="radio-group"] [role="radio"] div,
[data-baseweb="radio"] [role="radio"] div,
[data-testid="stRadio"] [role="radio"] div {{
    border-color: {PRIMARY} !important;
}}
[data-baseweb="radio"] [role="radio"][aria-checked="true"] div,
[data-baseweb="radio"] [role="radio"][aria-checked="true"] div div,
[data-testid="stRadio"] [role="radio"][aria-checked="true"] div,
[data-testid="stRadio"] [role="radio"][aria-checked="true"] div div {{
    background: {PRIMARY} !important;
    background-color: {PRIMARY} !important;
    border-color: {PRIMARY} !important;
}}
[data-baseweb="radio"] svg circle,
[data-baseweb="radio"] svg path,
[data-testid="stRadio"] svg circle,
[data-testid="stRadio"] svg path {{ fill: {PRIMARY} !important; }}

/* ── Tabs ── */
button[data-baseweb="tab"] {{
    color: {t['TEXT_MUTED']} !important;
    background: transparent !important;
    font-weight: 500 !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {PRIMARY} !important;
    border-bottom: 3px solid {PRIMARY} !important;
}}

/* ── DataFrames / tables ── */
.stDataFrame {{
    background-color: {t['SURFACE']} !important;
    {('filter: invert(1) hue-rotate(180deg) !important;' if theme_key == 'light' else '')}
    border-radius: 6px !important;
    overflow: hidden !important;
}}
/* ── Iframes must be transparent — avoids green bleed behind cv1 components ── */
iframe {{
    background-color: transparent !important;
}}

/* ── Dividers ── */
hr {{ border-color: {t['BORDER']} !important; }}

/* ── Audio Input recorder (mic button) ── */
[data-testid="stAudioInput"] {{
    background-color: {t['SURFACE']} !important;
    border: 1px solid {t['BORDER']} !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
}}
[data-testid="stAudioInput"] > div,
[data-testid="stAudioInput"] > div > div {{
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}
[data-testid="stAudioInput"] button,
[data-testid="stAudioInput"] button:hover,
[data-testid="stAudioInput"] button:focus {{
    background-color: {PRIMARY} !important;
    background: {PRIMARY} !important;
    border-color: {PRIMARY} !important;
    border-radius: 50% !important;
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    flex-shrink: 0 !important;
}}
[data-testid="stAudioInput"] button svg path,
[data-testid="stAudioInput"] button svg polyline,
[data-testid="stAudioInput"] button svg polygon,
[data-testid="stAudioInput"] button svg circle,
[data-testid="stAudioInput"] button svg line,
[data-testid="stAudioInput"] button svg ellipse {{
    fill: #ffffff !important;
    stroke: #ffffff !important;
}}
[data-testid="stAudioInput"] button svg rect {{
    fill: none !important;
}}
[data-testid="stAudioInput"] button div,
[data-testid="stAudioInput"] button span {{
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}}
[data-testid="stAudioInput"] span,
[data-testid="stAudioInput"] label {{
    background-color: transparent !important;
    font-size: 0.8rem !important;
}}
[data-testid="stAudioInput"] [class*="css-"]:not(button) {{
    background-color: transparent !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: {t['BG']}; }}
::-webkit-scrollbar-thumb {{ background: {t['BORDER']}; border-radius: 3px; }}


/* ── KPI grid — 3-col desktop, 2-col mobile ── */
.cos-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 16px;
}}
@media (max-width: 480px) {{
    .cos-kpi-grid {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
}}

/* ── aurora_hero() card (optional, used per-page) ── */
.aurora-hero-card {{
    position: relative;
    margin: 0.5rem 0 0.75rem;
    border: 0 !important;
    background: transparent !important;
    text-align: center;
}}

.aurora-hero-content {{
    position: relative;
    z-index: 1;
    max-width: 760px;
    margin: 0 auto;
    padding: 1.25rem 1rem 0.25rem;
}}

/* ── Theme Toggle Switch (V1.0.1) — single pill ── */
div[data-testid="stToggle"] {{
    background: {t['SURFACE']} !important;
    border: 1px solid {t['BORDER']} !important;
    border-radius: 50px !important;
    padding: 0.42rem 0.75rem !important;
    margin: 0.4rem 0 0 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
    min-height: unset !important;
    transition: border-color 0.2s, background 0.2s !important;
}}
div[data-testid="stToggle"]:hover {{
    border-color: {PRIMARY} !important;
    background: {t['SURFACE2']} !important;
}}
/* Label row: icon+text left, slider right */
div[data-testid="stToggle"] > label {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: space-between !important;
    width: 100% !important;
    gap: 0.5rem !important;
    cursor: pointer !important;
    padding: 0 !important;
}}
/* Label text */
div[data-testid="stToggle"] p {{
    display: block !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: {t['TEXT_MUTED']} !important;
    margin: 0 !important;
    font-family: 'Inter', sans-serif !important;
    flex: 1 !important;
    line-height: 1.2 !important;
}}
/* Slider track — OFF (dark mode) */
div[data-testid="stToggle"] span[data-testid="stToggleSlider"] {{
    background-color: {t['BORDER']} !important;
    border: 1.5px solid {t['BORDER']} !important;
    transition: background-color 0.25s ease !important;
    flex-shrink: 0 !important;
}}
/* Slider track — ON (light mode) */
div[data-testid="stToggle"] input:checked + span[data-testid="stToggleSlider"] {{
    background-color: {PRIMARY} !important;
    border-color: {PRIMARY} !important;
}}

/* ── Status badges ── */
.status-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    font-family: 'Inter', sans-serif;
}}
.badge-ok      {{ background: {PRIMARY}33; color: {t['TEXT']}; border: 1px solid {PRIMARY}66; }}
.badge-error   {{ background: {DANGER}22;  color: {DANGER};    border: 1px solid {DANGER}44; }}
.badge-pending {{ background: {WARNING}22; color: {WARNING};   border: 1px solid {WARNING}44; }}

/* ── Solid status pills (Settings): white text must beat the global span colour rule ── */
.cos-pill {{
    display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem;
    color: #fff !important; -webkit-text-fill-color: #fff !important;
}}
.cos-pill a {{ color: #fff !important; -webkit-text-fill-color: #fff !important; }}

/* ── Toggle tracks: keep the off state visible on the warm light background ── */
[data-testid="stToggle"] label > div:first-of-type {{
    border: 1px solid {t['BORDER']} !important;
}}

/* ── Type scale (desktop): serif headings, Inter body, mono meta ── */
.stApp h1, .stApp h2, .stApp h3 {{
    font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
}}
.stApp h1 {{ font-size: 2rem !important; line-height: 1.2 !important; }}
.stApp h2 {{ font-size: 1.4rem !important; line-height: 1.3 !important; margin-top: 0.5rem !important; }}
.stApp h3 {{ font-size: 1.15rem !important; line-height: 1.3 !important; }}
.stApp [data-testid="stMarkdownContainer"] p {{ font-size: 0.875rem; }}
.stApp [data-testid="stCaptionContainer"] {{ font-size: 0.75rem !important; }}

/* ── Agent / metric cards ── */
.agent-card {{
    background: {t['SURFACE']};
    border: 1px solid {t['BORDER']};
    border-top: 4px solid {t['CARD_TOP']};
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
}}
.metric-card {{
    background: {t['SURFACE']};
    border: 1px solid {t['BORDER']};
    border-left: 4px solid {PRIMARY};
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.metric-label {{
    font-size: 0.78rem;
    font-weight: 600;
    color: {t['TEXT_MUTED']};
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.metric-value {{
    font-size: 1.9rem;
    font-weight: 700;
    color: {t['TEXT']};
    margin-top: 4px;
}}
.metric-delta {{
    font-size: 0.75rem;
    color: {ACCENT};
    font-weight: 600;
}}

/* ── Tag chips ── */
.tag-chip {{
    background: {t['SURFACE2']};
    color: {t['TEXT_MUTED']};
    border: 1px solid {t['BORDER']};
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 0.7rem;
    font-family: 'JetBrains Mono', monospace;
}}

/* ── Responsive — Tablet (≤900px) ── */
@media (max-width: 900px) {{
    /* Stack Streamlit columns vertically */
    [data-testid="column"] {{
        width: 100% !important;
        min-width: 100% !important;
        flex: 0 0 100% !important;
    }}
    /* Reduce main padding */
    .block-container {{
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }}
    /* Shrink metric values */
    .metric-value {{ font-size: 1.4rem !important; }}
    /* Full-width buttons */
    .stButton > button {{ width: 100% !important; }}
    /* Full-width inputs */
    .stTextInput, .stTextArea, .stSelectbox {{ width: 100% !important; }}
}}

/* ── Responsive — Mobile (≤600px) ── */
@media (max-width: 600px) {{
    /* Tighter padding */
    .block-container {{
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 4.5rem !important;   /* clear the fixed 56px top bar */
    }}
    /* Smaller headings */
    .stApp h1 {{ font-size: 1.4rem !important; }}
    .stApp h2 {{ font-size: 1.1rem !important; }}
    .stApp h3 {{ font-size: 1rem !important; }}
    /* All columns stack full-width on mobile.
       KPI grid uses 3-col Python layout (two rows of 3) so 3 per row
       is the natural desktop view; on mobile each stacks cleanly. */
    [data-testid="column"] {{
        width: 100% !important;
        min-width: 100% !important;
        flex: 0 0 100% !important;
    }}
    /* Metric cards compact */
    [data-testid="metric-container"] {{
        padding: 0.4rem 0.5rem !important;
    }}
    [data-testid="metric-container"] label {{
        font-size: 0.7rem !important;
    }}
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        font-size: 1.3rem !important;
    }}
    /* Expanders full-width */
    .streamlit-expanderHeader {{ font-size: 0.85rem !important; }}
    /* Download/action buttons touch-friendly */
    .stButton > button {{
        min-height: 44px !important;
        font-size: 0.9rem !important;
        width: 100% !important;
    }}
    /* Dataframe scroll on mobile */
    .stDataFrame {{ overflow-x: auto !important; }}
    /* Tabs scrollable */
    [data-testid="stHorizontalBlock"] {{
        overflow-x: auto !important;
    }}
    /* Namespace pill compact */
    .cos-login-card {{ padding: 24px 20px 20px !important; }}
}}
</style>
"""


def _inject_chat_input_js(theme_key: str) -> None:
    """Always-on JS: injects a <style> tag into parent <head> for the chat input.
    CSS in st.markdown is scoped by Streamlit/Emotion and loses to React inline styles.
    This bypasses both by writing directly to parent document head + setProperty.
    """
    _dark = theme_key == "dark"
    _bg   = "#0f1f10" if _dark else "#ffffff"
    _text = "#d4edda" if _dark else "#1a1a1a"
    _ph   = "rgba(255,255,255,0.32)" if _dark else "rgba(0,0,0,0.35)"
    _border = "rgba(90,158,86,0.25)" if _dark else "rgba(64,126,60,0.20)"
    _shadow = "0 0 0 1px rgba(64,126,60,0.12),0 8px 40px rgba(0,0,0,0.45)" if _dark else "0 0 0 1px rgba(64,126,60,0.10),0 4px 24px rgba(0,0,0,0.10)"
    _components.html(f"""<script>
(function(){{
  var doc = window.parent.document;
  var STYLE_ID = 'cos-chat-input-style';

  function injectStyle() {{
    var old = doc.getElementById(STYLE_ID);
    if (old) old.remove();
    var s = doc.createElement('style');
    s.id = STYLE_ID;
    s.textContent = `
      div[data-testid="stBottom"],
      div[data-testid="stBottom"] > div,
      div[data-testid="stBottom"] > div > div {{
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding-bottom: 10px !important;
      }}
      [data-testid="stChatInputContainer"] {{
        background: {_bg} !important;
        background-color: {_bg} !important;
        border: 1px solid {_border} !important;
        border-radius: 20px !important;
        box-shadow: {_shadow} !important;
        max-width: 700px !important;
        width: 100% !important;
        margin: 0 auto !important;
        transition: border-color .2s, box-shadow .2s !important;
        padding: 4px 6px !important;
      }}
      [data-testid="stChatInputContainer"]:focus-within {{
        border-color: rgba(90,158,86,0.60) !important;
        box-shadow: 0 0 0 3px rgba(64,126,60,0.22),0 8px 40px rgba(0,0,0,0.50) !important;
      }}
      [data-testid="stChatInputContainer"] textarea {{
        background: transparent !important;
        background-color: transparent !important;
        color: {_text} !important;
        caret-color: #407E3C !important;
        border: none !important;
        min-height: 52px !important;
        padding: 14px 56px 14px 16px !important;
        font-size: 14.5px !important;
        line-height: 1.6 !important;
        resize: none !important;
      }}
      [data-testid="stChatInputContainer"] textarea::placeholder {{
        color: {_ph} !important;
        opacity: 1 !important;
      }}
      button[data-testid="stChatInputSubmitButton"] {{
        background: #407E3C !important;
        background-color: #407E3C !important;
        border: none !important;
        border-radius: 50% !important;
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        box-shadow: 0 2px 10px rgba(64,126,60,0.50) !important;
      }}
      button[data-testid="stChatInputSubmitButton"]:hover {{
        background: #5a9e56 !important;
        background-color: #5a9e56 !important;
        transform: scale(1.07) !important;
      }}
      button[data-testid="stChatInputSubmitButton"] svg path:not([fill="none"]),
      button[data-testid="stChatInputSubmitButton"] svg line,
      button[data-testid="stChatInputSubmitButton"] svg polyline,
      button[data-testid="stChatInputSubmitButton"] svg circle {{
        fill: #ffffff !important;
        stroke: #ffffff !important;
      }}
      button[data-testid="stChatInputActionButton"] {{
        background: transparent !important;
        border: none !important;
        border-radius: 50% !important;
      }}
      button[data-testid="stChatInputActionButton"] svg * {{
        fill: #407E3C !important;
        stroke: #407E3C !important;
      }}
    `;
    doc.head.appendChild(s);
  }}

  injectStyle();
  setTimeout(injectStyle, 300);
  setTimeout(injectStyle, 800);

  if (window.parent.__cosObsStyle) window.parent.__cosObsStyle.disconnect();
  var obs = new MutationObserver(function() {{
    if (!doc.getElementById(STYLE_ID)) injectStyle();
  }});
  window.parent.__cosObsStyle = obs;
  if (doc.body) obs.observe(doc.body, {{childList: true, subtree: false}});
}})();
</script>""", height=0)


def _inject_brand_colors_js(color: str, accent: str) -> None:
    """JS brand injection — bypasses CSS cascade entirely via setProperty(...,'important').
    Fixes: radio nav dots, chat input border, audio recorder timer.
    Runs on load + MutationObserver so rerenders stay branded.
    """
    _c = color.replace('"', '\\"').replace("'", "\\'")
    _components.html(f"""
<script>
(function() {{
  var doc   = window.parent.document;
  var COLOR = '{_c}';

  // ── 1. Sidebar radio dots — injected <style> in parent <head> ────────────
  // CSS beats Emotion (our specificity > Emotion's single class).
  // :has() is Chrome 105+ — fine for this use case.
  function injectRadioCSS() {{
    var id = 'cos-radio-brand';
    var old = doc.getElementById(id);
    if (old) old.remove();
    var s = doc.createElement('style');
    s.id = id;
    s.textContent = [
      // ── Active row highlight ──
      '[data-testid="stSidebar"] [role="radio"][aria-checked="true"] {{',
      '  background-color:' + COLOR + '22 !important;',
      '  border-radius:8px !important;',
      '}}',
      // ── Active text ──
      '[data-testid="stSidebar"] [role="radio"][aria-checked="true"] p,',
      '[data-testid="stSidebar"] [role="radio"][aria-checked="true"] span {{',
      '  font-weight:700 !important;',
      '  color:' + COLOR + ' !important;',
      '  -webkit-text-fill-color:' + COLOR + ' !important;',
      '}}',
      // ── Active dot: outer ring border + inner fill ──
      '[data-testid="stSidebar"] [role="radio"][aria-checked="true"] div:has(>div) {{',
      '  border-color:' + COLOR + ' !important;',
      '}}',
      '[data-testid="stSidebar"] [role="radio"][aria-checked="true"] div:not(:has(div)) {{',
      '  background-color:' + COLOR + ' !important;',
      '  border-color:' + COLOR + ' !important;',
      '}}',
      // ── Inactive dot: plum border ring, transparent fill ──
      '[data-testid="stSidebar"] [role="radio"][aria-checked="false"] div:has(>div) {{',
      '  border-color:' + COLOR + '66 !important;',
      '}}',
      '[data-testid="stSidebar"] [role="radio"][aria-checked="false"] div:not(:has(div)) {{',
      '  background-color: transparent !important;',
      '}}',
      // ── Chat input: plum border, transparent background, no glow ──
      '[data-testid="stChatInputContainer"],',
      '[data-testid="stChatInputContainer"] > div,',
      '[data-testid="stChatInputContainer"] > div > div {{',
      '  border-color:' + COLOR + '55 !important;',
      '  box-shadow: none !important;',
      '  background-color: transparent !important;',
      '}}',
      '[data-testid="stChatInputContainer"]:focus-within,',
      '[data-testid="stChatInputContainer"] > div:focus-within {{',
      '  border-color:' + COLOR + ' !important;',
      '  box-shadow: 0 0 0 2px ' + COLOR + '33 !important;',
      '}}',
    ].join('\\n');
    if (doc.head) doc.head.appendChild(s);
  }}
  injectRadioCSS();

  // ── Also apply direct inline styles for elements Emotion overrides with inline style ──
  function applyRadio() {{
    doc.querySelectorAll('[data-testid="stSidebar"] [role="radio"]').forEach(function(radio) {{
      var checked = radio.getAttribute('aria-checked') === 'true';
      radio.style.setProperty('background-color', checked ? COLOR + '22' : 'transparent', 'important');
      radio.style.setProperty('border-radius', '8px', 'important');
      radio.querySelectorAll('p, span').forEach(function(el) {{
        if (checked) {{
          el.style.setProperty('font-weight', '700', 'important');
          el.style.setProperty('color', COLOR, 'important');
          el.style.setProperty('-webkit-text-fill-color', COLOR, 'important');
        }} else {{
          el.style.setProperty('font-weight', '400', 'important');
          el.style.removeProperty('color');
          el.style.removeProperty('-webkit-text-fill-color');
        }}
      }});
      radio.querySelectorAll('div').forEach(function(div) {{
        var hasChildDiv = !!div.querySelector('div');
        if (hasChildDiv) {{
          // Outer ring container
          div.style.setProperty('border-color', checked ? COLOR : COLOR + '66', 'important');
        }} else {{
          // Inner fill
          div.style.setProperty('background-color', checked ? COLOR : 'transparent', 'important');
          div.style.setProperty('border-color', checked ? COLOR : COLOR + '66', 'important');
        }}
      }});
      radio.querySelectorAll('svg *').forEach(function(el) {{
        el.style.setProperty('fill', checked ? COLOR : 'none', 'important');
        el.style.setProperty('stroke', COLOR, 'important');
      }});
    }});
  }}

  // ── 2. Chat input — floating card enforcement via JS ────────────────────
  function fixChatInput() {{
    // Container: floating card shape + border tint from ns color
    doc.querySelectorAll('[data-testid="stChatInputContainer"]').forEach(function(c) {{
      c.style.setProperty('border-radius', '20px', 'important');
      c.style.setProperty('border-color', COLOR + '55', 'important');
      c.style.setProperty('max-width', '700px', 'important');
      c.style.setProperty('margin', '0 auto', 'important');
    }});
    // Submit button: green circle
    doc.querySelectorAll('button[data-testid="stChatInputSubmitButton"]').forEach(function(btn) {{
      btn.style.setProperty('background-color', COLOR, 'important');
      btn.style.setProperty('background', COLOR, 'important');
      btn.style.setProperty('border-radius', '50%', 'important');
      btn.style.setProperty('width', '36px', 'important');
      btn.style.setProperty('height', '36px', 'important');
      btn.style.setProperty('min-width', '36px', 'important');
      btn.style.setProperty('box-shadow', '0 2px 10px ' + COLOR + '80', 'important');
      btn.querySelectorAll('svg path, svg line, svg polyline, svg circle, svg rect').forEach(function(p) {{
        if (p.getAttribute('fill') === 'none') return;
        p.style.setProperty('fill', '#ffffff', 'important');
        p.style.setProperty('stroke', '#ffffff', 'important');
      }});
    }});
    // Attach button: brand tint
    doc.querySelectorAll('button[data-testid="stChatInputActionButton"]').forEach(function(btn) {{
      btn.style.setProperty('border-radius', '50%', 'important');
      btn.querySelectorAll('svg *').forEach(function(p) {{
        p.style.setProperty('fill', COLOR, 'important');
        p.style.setProperty('stroke', COLOR, 'important');
      }});
    }});
  }}

  // ── 3. Audio recorder — kill green timer pill, preserve mic icon ────────
  function fixAudioInput() {{
    doc.querySelectorAll('[data-testid="stAudioInput"]').forEach(function(container) {{
      container.style.setProperty('border-radius', '10px', 'important');
      // Non-button elements: clear any green background
      container.querySelectorAll('*').forEach(function(el) {{
        // Skip button and EVERYTHING inside a button (mic SVG paths etc.)
        if (el.tagName === 'BUTTON' || el.closest('button')) return;
        var bg = window.getComputedStyle(el).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {{
          el.style.setProperty('background-color', 'transparent', 'important');
        }}
        // Only set text color on text-bearing elements, not SVG
        var tag = el.tagName.toLowerCase();
        if (tag === 'span' || tag === 'p' || tag === 'div' || tag === 'label') {{
          el.style.setProperty('color', COLOR, 'important');
        }}
      }});
      // Mic/stop button — brand color, white icon
      container.querySelectorAll('button').forEach(function(btn) {{
        btn.style.setProperty('background-color', COLOR, 'important');
        btn.style.setProperty('border-color', COLOR, 'important');
        btn.style.setProperty('border-radius', '50%', 'important');
        btn.querySelectorAll('svg path, svg polyline, svg polygon, svg circle, svg line, svg ellipse').forEach(function(p) {{
          p.style.setProperty('fill', '#ffffff', 'important');
          p.style.setProperty('stroke', '#ffffff', 'important');
        }});
        btn.querySelectorAll('svg rect').forEach(function(r) {{
          r.style.setProperty('fill', 'none', 'important');
        }});
      }});
    }});
  }}

  // ── Run all fixes ─────────────────────────────────────────────────────────
  function runAll() {{
    injectRadioCSS();  // re-inject CSS (Streamlit may remove injected styles on rerun)
    applyRadio();
    fixChatInput();
    fixAudioInput();
  }}

  runAll();
  setTimeout(runAll, 200);
  setTimeout(runAll, 600);
  setTimeout(runAll, 1500);

  // MutationObserver — re-apply on any DOM change (navigation, rerenders)
  if (window.parent.__cosObsRadio) window.parent.__cosObsRadio.disconnect();
  var obs = new MutationObserver(function() {{
    clearTimeout(obs._t);
    obs._t = setTimeout(runAll, 80);
  }});
  window.parent.__cosObsRadio = obs;
  if (doc.body) obs.observe(doc.body, {{
    childList: true, subtree: true,
    attributes: true, attributeFilter: ['aria-checked']
  }});
}})();
</script>
""", height=0)


def inject():
    global TEXT_MUTED, _CURRENT_THEME, SURFACE
    theme_key = get_theme()
    t = THEMES[theme_key]
    TEXT_MUTED = t["TEXT_MUTED"]
    _CURRENT_THEME = t
    SURFACE = t["SURFACE"]
    # Inject Google Fonts via <link> (non-blocking) — only once per session
    if not st.session_state.get("_fonts_injected"):
        st.markdown(
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&family=JetBrains+Mono:wght@400;500&display=swap">',
            unsafe_allow_html=True,
        )
        st.session_state["_fonts_injected"] = True
    st.markdown(_build_css(theme_key), unsafe_allow_html=True)
    _inject_chat_input_js(theme_key)
    # Namespace brand color override (client/viewer workspaces)
    brand = get_ns_brand()
    if brand:
        _bc = (brand.get("color") or "").strip()
        _ba = (brand.get("accent_color") or "").strip()
        override = _ns_brand_css_cached(_bc, _ba, theme_key) if _bc else ""
        if override:
            st.markdown(override, unsafe_allow_html=True)
        # JS injection for radio dots + toggle tracks — CSS can't beat React inline styles
        _color = (brand.get("color") or "").strip()
        _accent = (brand.get("accent_color") or _color or "").strip()
        if _color:
            _inject_brand_colors_js(_color, _accent)
    # Custom background — personal (session) takes priority.
    # Brand bg_color only applied in LIGHT mode — dark mode derives its own
    # dark palette inside _ns_brand_css(); forcing ivory on dark = broken UX.
    _bg = st.session_state.get("custom_bg", "").strip()
    if not _bg and brand and get_theme() == "light":
        _bg = (brand.get("bg_color") or "").strip()
    if _bg and _bg.startswith("#"):
        bg_css = _custom_bg_css(_bg)
        if bg_css:
            st.markdown(bg_css, unsafe_allow_html=True)
    # Universal header fix — runs for all roles/themes
    _inject_header_fix_js(t["BG"], t["TEXT"])


def _inject_header_fix_js(header_bg: str, text_color: str) -> None:
    """JS fix for Streamlit header toolbar — removes dark backgrounds from
    any non-button element in the header (status widget, decoration, etc.)
    that our CSS can't target without knowing the exact testid."""
    _bg  = header_bg.replace("'", "\\'")
    _txt = text_color.replace("'", "\\'")
    _components.html(f"""
<script>
(function() {{
  var doc = window.parent.document;
  var HDR_BG  = '{_bg}';
  var HDR_TXT = '{_txt}';

  function fixHeader() {{
    var header = doc.querySelector('header[data-testid="stHeader"]');
    if (!header) return;

    // Force header container background
    header.style.setProperty('background-color', HDR_BG, 'important');

    // Walk every descendant — clear dark backgrounds on non-button elements
    header.querySelectorAll('*').forEach(function(el) {{
      var tag = el.tagName.toLowerCase();
      // Skip buttons (we want them styled separately) and SVG internals
      if (tag === 'button' || el.closest('button') || tag === 'svg'
          || tag === 'path' || tag === 'circle' || tag === 'rect'
          || tag === 'g' || tag === 'polyline' || tag === 'polygon') return;

      var bg = window.getComputedStyle(el).backgroundColor;
      // Clear any non-transparent background
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent'
          && bg !== 'rgba(0,0,0,0)') {{
        el.style.setProperty('background-color', 'transparent', 'important');
        el.style.setProperty('background', 'transparent', 'important');
      }}
      // Ensure text is visible
      if (tag === 'span' || tag === 'p' || tag === 'div' || tag === 'a') {{
        el.style.setProperty('color', HDR_TXT, 'important');
      }}
    }});

    // Buttons: transparent bg, preserve text visibility
    header.querySelectorAll('button').forEach(function(btn) {{
      btn.style.setProperty('background-color', 'transparent', 'important');
      btn.style.setProperty('background', 'transparent', 'important');
      btn.style.setProperty('border', 'none', 'important');
      btn.style.setProperty('box-shadow', 'none', 'important');
      // Clear backgrounds on button child divs/spans — skip icon wrapper (uses background-image)
      btn.querySelectorAll('div, span').forEach(function(child) {{
        var svgTags = ['svg','path','circle','rect','g','polyline','polygon','ellipse','line'];
        var testid = child.getAttribute('data-testid') || '';
        if (svgTags.indexOf(child.tagName.toLowerCase()) !== -1) return;
        if (testid === 'stToolbarActionButtonIcon') return; // background-image div — leave it
        child.style.setProperty('background-color', 'transparent', 'important');
        child.style.setProperty('background', 'transparent', 'important');
      }});
      // Fix SVG icon paths — skip bounding-box paths with fill="none" (e.g. MoreVert 24x24 rect path)
      btn.querySelectorAll('svg path, svg circle, svg polyline, svg polygon, svg line, svg ellipse').forEach(function(p) {{
        if (p.getAttribute('fill') === 'none') return;
        p.style.setProperty('fill', HDR_TXT, 'important');
        p.style.setProperty('stroke', HDR_TXT, 'important');
      }});
      btn.querySelectorAll('svg path[fill="none"], svg rect').forEach(function(r) {{
        r.style.setProperty('fill', 'none', 'important');
      }});
    }});
  }}

  // ── Chat submit button — inject white arrow SVG directly ───────────────
  // Arrow SVG from Streamlit 1.56 ArrowUpward icon (fill:currentColor bypassed)
  var ARROW_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" style="display:block;pointer-events:none"><path fill="#ffffff" d="M13 19V7.83l4.88 4.88c.39.39 1.03.39 1.42 0a.996.996 0 000-1.41l-6.59-6.59a.996.996 0 00-1.41 0l-6.6 6.58a.996.996 0 101.41 1.41L11 7.83V19c0 .55.45 1 1 1s1-.45 1-1z"/></svg>';
  function fixChatSubmit() {{
    function applySubmit(btn) {{
      btn.style.setProperty('background-color', '#407E3C', 'important');
      btn.style.setProperty('border', 'none', 'important');
      btn.style.setProperty('border-radius', '6px', 'important');
      btn.style.setProperty('display', 'flex', 'important');
      btn.style.setProperty('align-items', 'center', 'important');
      btn.style.setProperty('justify-content', 'center', 'important');
      // Replace inner content with explicit white arrow — bypasses fill:currentColor
      if (!btn.getAttribute('data-cos-styled')) {{
        btn.setAttribute('data-cos-styled', '1');
        btn.innerHTML = ARROW_SVG;
      }}
    }}
    doc.querySelectorAll('button[data-testid="stChatInputSubmitButton"]').forEach(applySubmit);
    // Fallback: last button in container
    doc.querySelectorAll('[data-testid="stChatInputContainer"]').forEach(function(c) {{
      var btns = c.querySelectorAll('button');
      if (btns.length) applySubmit(btns[btns.length - 1]);
    }});
    // Attach "+" — transparent bg, green icon
    doc.querySelectorAll('button[data-testid="stChatInputActionButton"]').forEach(function(el) {{
      el.style.setProperty('background-color', 'transparent', 'important');
      el.style.setProperty('border', 'none', 'important');
      el.style.setProperty('box-shadow', 'none', 'important');
      el.querySelectorAll('svg path, svg line, svg polyline, svg circle').forEach(function(p) {{
        p.style.setProperty('fill', '#407E3C', 'important');
        p.style.setProperty('stroke', '#407E3C', 'important');
      }});
    }});
  }}

  // ── Voice input — kill grey bar ──────────────────────────────────────────
  function fixAudioInput() {{
    doc.querySelectorAll('[data-testid="stAudioInput"]').forEach(function(container) {{
      container.querySelectorAll('*').forEach(function(el) {{
        if (el.tagName === 'BUTTON' || el.closest('button')) return;
        var svgTags = ['svg','path','circle','rect','g','polyline','polygon','ellipse','line'];
        if (svgTags.indexOf(el.tagName.toLowerCase()) !== -1) return;
        var bg = window.getComputedStyle(el).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' && bg !== 'rgba(0,0,0,0)') {{
          el.style.setProperty('background-color', 'transparent', 'important');
          el.style.setProperty('background', 'transparent', 'important');
        }}
      }});
    }});
  }}

  function runAllFixes() {{
    fixHeader();
    fixChatSubmit();
    fixAudioInput();
  }}

  runAllFixes();
  setTimeout(runAllFixes, 200);
  setTimeout(runAllFixes, 800);

  if (window.parent.__cosObsHeader) window.parent.__cosObsHeader.disconnect();
  var obs = new MutationObserver(function() {{
    clearTimeout(obs._ht);
    obs._ht = setTimeout(runAllFixes, 80);
  }});
  window.parent.__cosObsHeader = obs;
  if (doc.body) obs.observe(doc.body, {{ childList: true, subtree: true }});
}})();
</script>
""", height=0)


def sidebar_logo():
    t = THEMES[get_theme()]
    brand = get_ns_brand()
    company = (brand.get("company_name") or "").strip()
    icon = (brand.get("icon") or "").strip()
    b_color = (brand.get("color") or "").strip()
    b_accent = (brand.get("accent_color") or b_color or "").strip()

    if company:
        # Namespace-branded workspace — show client company identity
        c1 = b_color if b_color else t["LOGO1"]
        c2 = b_accent if b_accent else t["LOGO2"]
        st.sidebar.markdown(f"""
<div style="padding:1rem 0.5rem;text-align:center;">
  <div style="font-size:1.35rem;font-weight:800;color:{_esc(c1)};
              letter-spacing:1px;font-family:'Inter',sans-serif;line-height:1.2;">
    {icon + " " if icon else ""}{_esc(company)}
  </div>
  <div style="font-size:0.62rem;color:{t['TEXT_MUTED']};letter-spacing:1px;margin-top:3px;">
    POWERED BY <span style="color:{_esc(c2)};font-weight:700;">CLAUDEOS</span>
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"""
<div style="padding:1rem 0.5rem;text-align:center;">
  <div style="font-size:1.5rem;font-weight:800;color:{t['LOGO1']};letter-spacing:2px;font-family:'Inter',sans-serif;">
    CLAUDE<span style="color:{t['LOGO2']};">OS</span>
  </div>
  <div style="font-size:0.7rem;color:{t['TEXT_MUTED']};letter-spacing:1px;">AI OPERATING SYSTEM</div>
</div>
""", unsafe_allow_html=True)


def theme_toggle():
    """Fixed-position circular icon toggle — dark navy sun (dark mode) / light gray moon (light mode)."""
    _MARKER = "COS-THEME-FLIP-TRIGGER"
    if st.button(_MARKER, key="_cos_theme_flip_btn"):
        current = get_theme()
        # Preserve nav page — st.rerun() interrupts the run before the sidebar
        # radio renders, which causes Streamlit to prune its widget state key.
        if "nav_page" in st.session_state:
            st.session_state["_nav_page_bak"] = st.session_state["nav_page"]
        st.session_state.theme = "dark" if current == "light" else "light"
        st.query_params["theme"] = st.session_state.theme  # survives browser refresh
        st.rerun()

    current = get_theme()
    is_dark = current == "dark"

    if is_dark:
        btn_bg     = "#111827"
        btn_border = "none"
        btn_shadow = "0 2px 12px rgba(0,0,0,0.55)"
        icon_svg = (
            "<svg width='22' height='22' viewBox='0 0 24 24' fill='none' "
            "xmlns='http://www.w3.org/2000/svg'>"
            "<circle cx='12' cy='12' r='3.5' fill='white'/>"
            "<line x1='12' y1='1.5' x2='12' y2='5.5' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='12' y1='18.5' x2='12' y2='22.5' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='1.5' y1='12' x2='5.5' y2='12' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='18.5' y1='12' x2='22.5' y2='12' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='4.22' y1='4.22' x2='7.05' y2='7.05' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='16.95' y1='16.95' x2='19.78' y2='19.78' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='19.78' y1='4.22' x2='16.95' y2='7.05' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "<line x1='7.05' y1='16.95' x2='4.22' y2='19.78' stroke='white' stroke-width='2' stroke-linecap='round'/>"
            "</svg>"
        )
        dot_html = (
            "<span style='position:absolute;width:6px;height:6px;"
            "background:rgba(255,255,255,0.75);border-radius:50%;"
            "bottom:7px;right:7px;'></span>"
        )
    else:
        btn_bg     = "#f0f0f0"
        btn_border = "1.5px solid #d9d9d9"
        btn_shadow = "0 2px 8px rgba(0,0,0,0.13)"
        icon_svg = (
            "<svg width='20' height='20' viewBox='0 0 24 24' fill='none' "
            "xmlns='http://www.w3.org/2000/svg'>"
            "<path d='M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' "
            "fill='#374151' stroke='#374151' stroke-width='0.5'/>"
            "</svg>"
        )
        dot_html = ""

    _btn_bg_js     = btn_bg.replace("'", "\\'")
    _btn_border_js = btn_border.replace("'", "\\'")
    _btn_shadow_js = btn_shadow.replace("'", "\\'")

    _components.html(f"""
<script>
(function() {{
  var doc = window.parent.document;
  var old = doc.getElementById('cos-theme-btn');
  if (old) old.remove();

  // ── dynamic sidebar-aware position ──────────────────────────────────
  function getSidebarWidth() {{
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (!sb) return 260;
    var w = sb.getBoundingClientRect().width;
    return w > 10 ? w : 260;
  }}

  // ── right-align button on same row as bottom status text ────────────
  function positionBtn() {{
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    var sbW = sb ? sb.getBoundingClientRect().width : 260;
    // 12px padding from right edge of sidebar
    var leftPx = Math.max(8, Math.round(sbW - 44 - 12));
    btn.style.left   = leftPx + 'px';
    // 20px from bottom — same row as "API online" text
    btn.style.bottom = '20px';
  }}

  var btn = doc.createElement('button');
  btn.id = 'cos-theme-btn';
  btn.title = 'Toggle dark / light mode';
  btn.type = 'button';
  btn.style.cssText = [
    'position:fixed',
    'bottom:20px',
    'left:204px',
    'z-index:2147483647',
    'width:44px', 'height:44px', 'border-radius:50%',
    'display:flex', 'align-items:center', 'justify-content:center',
    'background:{_btn_bg_js}',
    'border:{_btn_border_js}',
    'box-shadow:{_btn_shadow_js}',
    'cursor:pointer', 'outline:none',
    'transition:transform 0.15s ease,box-shadow 0.15s ease'
  ].join(';');
  btn.innerHTML = `{icon_svg}{dot_html}`;

  var MARKER = '{_MARKER}';
  function findTrigger() {{
    // Key-based selector (reliable even when wrapper is display:none)
    var byKey = doc.querySelector('[class*="st-key-_cos_theme_flip_btn"] button');
    if (byKey) return byKey;
    // Fallback: textContent search (works on hidden elements unlike innerText)
    var all = doc.querySelectorAll('button');
    for (var i = 0; i < all.length; i++) {{
      if ((all[i].textContent || '').indexOf(MARKER) !== -1) return all[i];
    }}
    return null;
  }}
  function hideTrigger() {{
    var t = findTrigger();
    if (t) {{
      var wrap = t.closest('[data-testid="stButton"]') || t.parentElement;
      if (wrap) wrap.style.cssText = 'display:none!important;height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;';
    }}
  }}
  btn.onmouseenter = function() {{ this.style.transform = 'scale(1.1)'; }};
  btn.onmouseleave = function() {{ this.style.transform = 'scale(1)'; }};
  btn.onclick = function() {{
    var t = findTrigger();
    if (t) {{ t.click(); return; }}
    // retry once — trigger may have been re-rendered
    setTimeout(function() {{ var t2 = findTrigger(); if (t2) t2.click(); }}, 80);
  }};

  // hide trigger now and on every DOM mutation (Streamlit re-renders restore it)
  hideTrigger();
  setTimeout(hideTrigger, 150);
  setTimeout(hideTrigger, 600);
  if (window.parent.__cosObsTrigger) window.parent.__cosObsTrigger.disconnect();
  var obs = new MutationObserver(hideTrigger);
  window.parent.__cosObsTrigger = obs;
  obs.observe(doc.body, {{childList: true, subtree: true}});
  // keep observer alive for lifetime of page — Streamlit re-renders repeatedly
  // restore the trigger button visibility; we must always re-hide it
  doc.body.appendChild(btn);

  // Apply exact centered position after append (sidebar width now measurable)
  positionBtn();
  setTimeout(positionBtn, 300);
  // Re-center if sidebar is toggled open/closed
  try {{
    var sbEl = doc.querySelector('section[data-testid="stSidebar"]');
    if (sbEl) {{
      var ro = new ResizeObserver(positionBtn);
      ro.observe(sbEl);
    }}
  }} catch(e) {{}}
}})();
</script>
""", height=0)


def theme_toggle_topbar() -> None:
    """Alias — delegates to theme_toggle() which has the canonical implementation."""
    theme_toggle()


def empty_state(icon: str, title: str, body: str = "") -> None:
    """Render a centered empty-state card — use when a list/feed has no items."""
    t = THEMES[get_theme()]
    brand = get_ns_brand()
    theme = get_theme()
    _color = (brand.get("color") or "").strip()
    if _color and theme == "dark":
        _surf  = _mix(_color, False, 0.78)
        _brd   = _mix(_color, False, 0.52)
        _txt   = "#FAF8F7"
        _muted = (brand.get("accent_color") or "#C8A96E").strip()
    elif _color:
        _surf  = (brand.get("surface_color") or "").strip() or t["SURFACE"]
        _brd   = (brand.get("border_color")  or "").strip() or t["BORDER"]
        _txt   = (brand.get("text_color")    or "").strip() or t["TEXT"]
        _muted = (brand.get("text_muted_color") or "").strip() or t["TEXT_MUTED"]
    else:
        _surf, _brd, _txt, _muted = t["SURFACE"], t["BORDER"], t["TEXT"], t["TEXT_MUTED"]
    body_html = (
        f'<p style="color:{_muted};font-size:0.88rem;margin:6px 0 0;">{_esc(body)}</p>'
        if body else ""
    )
    st.markdown(
        f'<div style="text-align:center;padding:40px 24px;background:{_surf};'
        f'border:1px solid {_brd};border-radius:12px;margin:8px 0;">'
        f'<div style="font-size:2.4rem;margin-bottom:10px;">{icon}</div>'
        f'<div style="font-size:1rem;font-weight:700;color:{_txt};">{_esc(title)}</div>'
        f'{body_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "ok") -> str:
    _SAFE_KINDS = {"ok", "error", "pending", "warning", "info"}
    safe_kind = kind if kind in _SAFE_KINDS else "ok"
    return f'<span class="status-badge badge-{safe_kind}">{_esc(text)}</span>'


def clear_health_bar() -> None:
    """Remove the health bar from the DOM — call on every non-admin render
    so the bar doesn't persist after logout or role change."""
    _components.html("""
<script>
(function() {
  var doc = window.parent.document;
  var bar = doc.getElementById('cos-health-bar');
  var spc = doc.getElementById('cos-health-bar-spc');
  if (bar) bar.remove();
  if (spc) spc.remove();
})();
</script>
""", height=0)


def system_health_bar(api_base: str, token: str) -> None:
    """Fixed-top system health bar — admin/operator only.

    Renders CPU%, RAM, Disk, and Uptime in a compact 42px bar pinned to the
    top of the viewport. Polls GET /system/hardware every 10 seconds via JS.
    Stores last 20 CPU samples in localStorage for the mini sparkline.
    """
    _components.html(f"""
<script>
(function() {{
  var API_BASE = {repr(api_base)};
  var TOKEN    = {repr(token)};
  var doc      = window.parent.document;

  // ── remove stale bar from prior reruns ──────────────────────────────
  var old = doc.getElementById('cos-health-bar');
  if (old) old.remove();
  var oldSpc = doc.getElementById('cos-health-bar-spc');
  if (oldSpc) oldSpc.remove();

  // ── helpers ─────────────────────────────────────────────────────────
  function barColor(pct) {{
    if (pct < 60)  return '#407E3C';
    if (pct < 80)  return '#f59e0b';
    if (pct < 90)  return '#f97316';
    return '#ef4444';
  }}

  function makeBar(pct, width) {{
    var w = Math.max(2, Math.min(100, pct));
    var c = barColor(pct);
    var track = doc.createElement('div');
    track.style.cssText = 'background:rgba(255,255,255,0.12);border-radius:3px;overflow:hidden;height:6px;width:' + width + 'px;display:inline-block;vertical-align:middle;';
    var fill = doc.createElement('div');
    fill.style.cssText = 'height:100%;border-radius:3px;background:' + c + ';width:' + w + '%;transition:width 0.5s ease,background 0.5s ease;';
    track.appendChild(fill);
    return track;
  }}

  function sparkline(points, width, height) {{
    if (!points || points.length < 2) return '';
    var min = Math.min.apply(null, points);
    var max = Math.max.apply(null, points);
    var range = Math.max(max - min, 5);
    var step  = width / (points.length - 1);
    var pts = points.map(function(v, i) {{
      var x = i * step;
      var y = height - ((v - min) / range) * height;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }}).join(' ');
    return '<svg width="' + width + '" height="' + height + '" style="display:inline-block;vertical-align:middle;opacity:0.9;" viewBox="0 0 ' + width + ' ' + height + '">'
      + '<polyline points="' + pts + '" fill="none" stroke="#7DBF7E" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
      + '</svg>';
  }}

  // ── sidebar offset helper ────────────────────────────────────────────
  function getSidebarWidth() {{
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (!sb) return 0;
    var w = sb.getBoundingClientRect().width;
    return w > 10 ? w : 0;
  }}

  function applyOffset() {{
    var lft = getSidebarWidth();
    bar.style.left = lft + 'px';
  }}

  // ── build bar skeleton ───────────────────────────────────────────────
  var bar = doc.createElement('div');
  bar.id = 'cos-health-bar';
  bar.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'right:0', 'height:42px',
    'background:#0d1a0e', 'border-bottom:1px solid #2D5C2E',
    'z-index:99999', 'display:flex', 'align-items:center',
    'justify-content:center', 'gap:28px', 'box-sizing:border-box',
    'font-family:Inter,system-ui,sans-serif', 'font-size:11.5px',
    'color:#E8F5E8', 'user-select:none', 'padding:0 24px'
  ].join(';');

  function label(text) {{
    var s = doc.createElement('span');
    s.style.cssText = 'font-weight:700;font-size:10.5px;letter-spacing:0.07em;color:#7DBF7E;text-transform:uppercase;white-space:nowrap;';
    s.textContent = text;
    return s;
  }}

  // CPU section
  var cpuWrap = doc.createElement('div');
  cpuWrap.id  = 'cos-hb-cpu';
  cpuWrap.style.cssText = 'display:flex;align-items:center;gap:6px;';
  cpuWrap.appendChild(label('CPU'));
  bar.appendChild(cpuWrap);

  // RAM section
  var ramWrap = doc.createElement('div');
  ramWrap.id  = 'cos-hb-ram';
  ramWrap.style.cssText = 'display:flex;align-items:center;gap:6px;';
  ramWrap.appendChild(label('RAM'));
  bar.appendChild(ramWrap);

  // Disk section
  var dskWrap = doc.createElement('div');
  dskWrap.id  = 'cos-hb-dsk';
  dskWrap.style.cssText = 'display:flex;align-items:center;gap:6px;';
  dskWrap.appendChild(label('DISK C:'));
  bar.appendChild(dskWrap);

  // Divider
  function divider() {{
    var d = doc.createElement('div');
    d.style.cssText = 'width:1px;height:20px;background:rgba(255,255,255,0.15);flex-shrink:0;';
    return d;
  }}
  bar.appendChild(divider());

  // Uptime
  var uptWrap = doc.createElement('div');
  uptWrap.id  = 'cos-hb-upt';
  uptWrap.style.cssText = 'display:flex;align-items:center;gap:6px;white-space:nowrap;';
  uptWrap.appendChild(label('UPTIME'));
  bar.appendChild(uptWrap);

  doc.body.appendChild(bar);

  // ── track sidebar width, re-offset on toggle/resize ─────────────────
  applyOffset();
  setTimeout(applyOffset, 300);
  try {{
    if (window.parent.__cosRo) window.parent.__cosRo.disconnect();
    var ro = new ResizeObserver(applyOffset);
    window.parent.__cosRo = ro;
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (sb) ro.observe(sb);
    // also watch for sidebar being added to DOM later
    var mo = new MutationObserver(function() {{
      var s = doc.querySelector('section[data-testid="stSidebar"]');
      if (s) {{ ro.observe(s); mo.disconnect(); }}
      applyOffset();
    }});
    mo.observe(doc.body, {{childList: true, subtree: false}});
  }} catch(e) {{
    // fallback: just use fixed 260px offset
    bar.style.left = '260px';
  }}

  // ── spacing shim (push Streamlit content down) ───────────────────────
  var spc = doc.createElement('style');
  spc.id = 'cos-health-bar-spc';
  spc.textContent = [
    '.main .block-container {{ padding-top: 58px !important; }}',
    '[data-testid="stAppViewContainer"] > section.main {{ padding-top: 42px !important; }}',
    'header[data-testid="stHeader"] {{ top: 42px !important; }}',
    'section[data-testid="stSidebar"] {{ padding-top: 42px !important; }}'
  ].join(' ');
  doc.head.appendChild(spc);

  // ── sparkline history ────────────────────────────────────────────────
  var LS_KEY = 'cos_cpu_history';
  function getCpuHistory() {{
    try {{ return JSON.parse(localStorage.getItem(LS_KEY) || '[]'); }} catch(e) {{ return []; }}
  }}
  function pushCpuHistory(v) {{
    var h = getCpuHistory();
    h.push(v);
    if (h.length > 20) h = h.slice(-20);
    try {{ localStorage.setItem(LS_KEY, JSON.stringify(h)); }} catch(e) {{}}
    return h;
  }}

  // ── section updater ──────────────────────────────────────────────────
  function updateSection(wrap, lbl, barPct, text, sparkHtml) {{
    // remove non-label children
    while (wrap.children.length > 1) wrap.removeChild(wrap.lastChild);
    wrap.appendChild(makeBar(barPct, 72));
    var val = doc.createElement('span');
    val.style.cssText = 'font-size:11.5px;font-weight:600;color:#E8F5E8;white-space:nowrap;';
    val.textContent = text;
    wrap.appendChild(val);
    if (sparkHtml) {{
      var sv = doc.createElement('span');
      sv.innerHTML = sparkHtml;
      wrap.appendChild(sv);
    }}
  }}

  function updateUptime(wrap, serverUp) {{
    while (wrap.children.length > 1) wrap.removeChild(wrap.lastChild);
    var val = doc.createElement('span');
    val.style.cssText = 'font-size:11.5px;font-weight:600;color:#E8F5E8;';
    val.textContent = serverUp;
    wrap.appendChild(val);
  }}

  // ── fetch & render ───────────────────────────────────────────────────
  function fetchStats() {{
    fetch(API_BASE + '/system/hardware', {{
      headers: {{ 'Authorization': 'Bearer ' + TOKEN }}
    }})
    .then(function(r) {{ if (!r.ok) throw new Error(r.status); return r.json(); }})
    .then(function(d) {{
      bar.style.opacity = '1';

      // CPU
      var hist = pushCpuHistory(d.cpu_pct);
      var spark = sparkline(hist, 44, 16);
      updateSection(cpuWrap,  'CPU',    d.cpu_pct,  d.cpu_pct.toFixed(1) + '%', spark);

      // RAM
      updateSection(ramWrap,  'RAM',    d.ram_pct,
        d.ram_used_gb.toFixed(1) + ' / ' + d.ram_total_gb.toFixed(1) + ' GB', null);

      // Disk
      updateSection(dskWrap,  'DISK C:', d.disk_pct,
        d.disk_used_gb.toFixed(1) + ' / ' + d.disk_total_gb.toFixed(1) + ' GB', null);

      // Uptime — server uptime (since Flask start)
      updateUptime(uptWrap, d.server_uptime);
    }})
    .catch(function(e) {{
      bar.style.opacity = '0.4';
    }});
  }}

  fetchStats();
  var _iv = setInterval(fetchStats, 30000);

  // clean up interval when iframe is destroyed
  window.addEventListener('beforeunload', function() {{ clearInterval(_iv); }});
}})();
</script>
""", height=0)


def aurora_hero(title: str, subtitle: str = "", pill: str = "") -> None:
    """Render an animated aurora banner using brand green/white palette.

    Args:
        title:    Large heading text.
        subtitle: Optional smaller description line.
        pill:     Optional small label badge (e.g. "v7.0 · All Systems Go").
    """
    # ME-01: HTML-escape all caller-supplied strings before interpolation
    title    = _esc(title)
    subtitle = _esc(subtitle)
    pill     = _esc(pill)

    t = THEMES[get_theme()]
    brand = get_ns_brand()
    _p = (brand.get("color") or PRIMARY).strip() or PRIMARY
    _a = (brand.get("accent_color") or ACCENT).strip() or ACCENT
    pill_html = (
        f'<span style="display:inline-block;color:{t["TEXT_MUTED"]};'
        f"font-family:'JetBrains Mono',monospace;"
        f'font-size:0.72rem;font-weight:500;letter-spacing:0.04em;margin-bottom:0.75rem;">'
        f'<span style="color:{_p};">●</span> {pill}</span>'
    ) if pill else ""
    sub_html = (
        f'<p style="color:{t["TEXT_MUTED"]};margin:0.6rem auto 0;max-width:620px;font-size:0.95rem;font-weight:400;line-height:1.5;">'
        f'{subtitle}</p>'
    ) if subtitle else ""

    # One blank-line-free block: a blank line (e.g. from an empty title) would end the HTML
    # block in markdown and render the rest as an indented code block.
    h1_html = (
        f'<h1 style="margin:0;font-size:2.5rem;font-weight:600;color:{t["TEXT"]};'
        f"font-family:'Source Serif 4',Georgia,serif;line-height:1.15;letter-spacing:-0.015em;\">"
        f'{title}</h1>'
    ) if title else ""
    st.markdown(
        f'<div class="aurora-hero-card"><div class="aurora-hero-content">'
        f'{pill_html}{h1_html}{sub_html}</div></div>',
        unsafe_allow_html=True,
    )
