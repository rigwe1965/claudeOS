"""Brand CSS injection — dark (deep forest) / light (clean white) themes.

Design tokens match CustomCommand reference project exactly.
Dark:  near-black green bg (#0A1F0A) with green-tinted surfaces.
Light: clean white bg with gray borders, near-black text.
"""
import streamlit as st

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
    },
    "light": {
        "BG":          "#ffffff",
        "SURFACE":     "#F9FAFB",
        "SURFACE2":    "#F3F4F6",
        "TEXT":        "#1A1A1A",
        "TEXT_MUTED":  "#6B7280",
        "BORDER":      "#E5E7EB",
        "BTN_BG":      "#407E3C",
        "BTN_TEXT":    "#ffffff",
        "BTN_HOVER_BG":"#5a9e56",
        "INPUT_BG":    "#ffffff",
        "INPUT_TEXT":  "#1A1A1A",
        "LOGO1":       "#407E3C",
        "LOGO2":       "#5a9e56",
        "CARD_TOP":    "#407E3C",
        "PLOT_BG":     "#ffffff",
        "GRID":        "#F3F4F6",
    },
}

# Module-level refs updated on each inject() call — importable by pages
TEXT_MUTED = THEMES["dark"]["TEXT_MUTED"]
_CURRENT_THEME: dict = THEMES["dark"]


def get_theme() -> str:
    return st.session_state.get("theme", "dark")


def get_theme_vars() -> dict:
    """Return current theme token dict. Call after inject() or at render time."""
    return THEMES[get_theme()]


def inject():
    global TEXT_MUTED, _CURRENT_THEME, SURFACE
    t = THEMES[get_theme()]
    TEXT_MUTED = t["TEXT_MUTED"]
    _CURRENT_THEME = t
    SURFACE = t["SURFACE"]

    st.markdown(f"""
<style>
/* ── Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');

html, body, .stApp, [class*="css"] {{
    font-family: 'Poppins', sans-serif;
    background-color: {t['BG']} !important;
    color: {t['TEXT']} !important;
}}

/* ── App shell ── */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {{
    background-color: {t['BG']} !important;
}}

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {{
    background-color: {t['SURFACE2']} !important;
    border-right: 1px solid {t['BORDER']} !important;
}}

/* ── Text — semantic elements ── */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
    font-family: 'Poppins', sans-serif;
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
button[data-testid="baseButton-secondary"],
button[data-testid="baseButton-primary"],
button[kind="primary"],
button[kind="secondary"] {{
    background-color: {t['BTN_BG']} !important;
    color: {t['BTN_TEXT']} !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-family: 'Poppins', sans-serif !important;
}}
.stButton > button p,
.stButton > button span,
button[data-testid="baseButton-secondary"] p,
button[data-testid="baseButton-primary"] p {{
    color: {t['BTN_TEXT']} !important;
}}
.stButton > button:hover,
button[data-testid="baseButton-secondary"]:hover,
button[data-testid="baseButton-primary"]:hover {{
    background-color: {t['BTN_HOVER_BG']} !important;
    color: {t['BTN_TEXT']} !important;
}}

/* ── Inputs / selects / textareas ── */
input, textarea,
.stTextInput input,
.stTextArea textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {{
    background-color: {t['INPUT_BG']} !important;
    color: {t['INPUT_TEXT']} !important;
    border-color: {t['BORDER']} !important;
    font-family: 'Poppins', sans-serif !important;
}}

/* ── Selectbox dropdown options ── */
ul[data-testid="stSelectboxVirtualDropdown"] li,
li[role="option"] {{
    background-color: {t['SURFACE']} !important;
    color: {t['TEXT']} !important;
}}

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
.stDataFrame, iframe {{
    background-color: {t['SURFACE']} !important;
}}

/* ── Dividers ── */
hr {{ border-color: {t['BORDER']} !important; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: {t['BG']}; }}
::-webkit-scrollbar-thumb {{ background: {t['BORDER']}; border-radius: 3px; }}

/* ── Status badges ── */
.status-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    font-family: 'Poppins', sans-serif;
}}
.badge-ok      {{ background: {PRIMARY}33; color: {t['TEXT']}; border: 1px solid {PRIMARY}66; }}
.badge-error   {{ background: {DANGER}22;  color: {DANGER};    border: 1px solid {DANGER}44; }}
.badge-pending {{ background: {WARNING}22; color: {WARNING};   border: 1px solid {WARNING}44; }}

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
        padding-top: 1rem !important;
    }}
    /* Smaller headings */
    .stApp h1 {{ font-size: 1.4rem !important; }}
    .stApp h2 {{ font-size: 1.1rem !important; }}
    .stApp h3 {{ font-size: 1rem !important; }}
    /* Metric cards compact */
    [data-testid="metric-container"] {{
        padding: 0.5rem 0.75rem !important;
    }}
    .metric-value {{ font-size: 1.2rem !important; }}
    /* Sidebar auto-collapse — handled by Streamlit config */
    /* Expanders full-width */
    .streamlit-expanderHeader {{ font-size: 0.85rem !important; }}
    /* Download/action buttons touch-friendly */
    .stButton > button {{
        min-height: 44px !important;
        font-size: 0.9rem !important;
    }}
    /* Dataframe scroll on mobile */
    .stDataFrame {{ overflow-x: auto !important; }}
    /* Tabs scrollable */
    [data-testid="stHorizontalBlock"] {{
        overflow-x: auto !important;
    }}
}}
</style>
""", unsafe_allow_html=True)


def sidebar_logo():
    t = THEMES[get_theme()]
    st.sidebar.markdown(f"""
<div style="padding:1rem 0.5rem;text-align:center;">
  <div style="font-size:1.5rem;font-weight:800;color:{t['LOGO1']};letter-spacing:2px;font-family:'Poppins',sans-serif;">
    CLAUDE<span style="color:{t['LOGO2']};">OS</span>
  </div>
  <div style="font-size:0.7rem;color:{t['TEXT_MUTED']};letter-spacing:1px;">AI OPERATING SYSTEM</div>
</div>
""", unsafe_allow_html=True)


def theme_toggle():
    current = get_theme()
    label = "☀️  Light mode" if current == "dark" else "🌙  Dark mode"
    if st.sidebar.button(label, width='stretch'):
        st.session_state.theme = "light" if current == "dark" else "dark"
        st.rerun()


def badge(text: str, kind: str = "ok") -> str:
    return f'<span class="status-badge badge-{kind}">{text}</span>'
