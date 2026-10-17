"""Hidden "proxy" buttons: real st.button widgets that only JavaScript clicks.

Custom HTML (the sidebar nav, KPI cards, catalog cards, command palette) lives in iframes and
cannot call Python. It clicks a hidden Streamlit button instead, whose on_click/return value runs
the Python side. Streamlit >= 1.39 tags keyed widgets with a key-derived CSS class, but this
project pins streamlit==1.38.0, so nothing may depend on that class. Instead:

  * proxy_button() renders the button inside its own st.container() together with a marker
    element (<span class="cos-proxy-zone">);
  * PROXY_CSS hides any container holding that marker (display:none keeps JS .click() working);
  * COS_CLICK_PROXY_JS finds the button by its exact label text inside a marked container.

Labels are the lookup key, so they must be unique per page and stable across reruns.
"""
import streamlit as st

ZONE_CLASS = "cos-proxy-zone"

# Hide the innermost container that directly holds the marker. The wrapper is hidden (not just the
# block) so the parent's flex `gap` does not leave an empty row. Both the 1.38 layout
# (element-container / BorderWrapper) and the 1.5x layout (stElementContainer / stLayoutWrapper) are
# listed; unmatched selectors are harmless.
PROXY_CSS = """
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] .cos-proxy-zone),
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .cos-proxy-zone),
[data-testid="stLayoutWrapper"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .cos-proxy-zone),
[data-testid="stVerticalBlock"]:has(> [data-testid="element-container"] .cos-proxy-zone),
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .cos-proxy-zone) {
    display: none !important;
}
"""

# Plain-JS helper, embedded verbatim in every iframe script that needs to click a proxy.
COS_CLICK_PROXY_JS = """
function cosClickProxy(doc, label) {
  var zones = doc.querySelectorAll('.cos-proxy-zone');
  for (var i = 0; i < zones.length; i++) {
    var block = zones[i].closest('[data-testid="stVerticalBlock"]');
    if (!block) continue;
    var btns = block.querySelectorAll('button');
    for (var j = 0; j < btns.length; j++) {
      if (btns[j].textContent.trim() === label) { btns[j].click(); return true; }
    }
  }
  return false;
}
"""


def proxy_button(label: str, *, key: str, **kwargs) -> bool:
    """Render a hidden button that JavaScript clicks via cosClickProxy(doc, label)."""
    with st.container():
        st.markdown(f'<span class="{ZONE_CLASS}"></span>', unsafe_allow_html=True)
        return st.button(label, key=key, **kwargs)
