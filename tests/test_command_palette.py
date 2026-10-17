"""Command palette: generated injector script is well-formed and covers every nav page."""
import json
import re
import shutil
import subprocess

import pytest

from dashboard.components.brand import THEMES
from dashboard.components.command_palette import PAGE_HINTS, build_palette_script

PAGES = list(PAGE_HINTS)


def _script(pages=PAGES, theme="dark", current="Overview") -> str:
    return build_palette_script(pages, THEMES[theme], current)


def _config(html: str) -> dict:
    return json.loads(re.search(r"var cfg = (\{.*?\});\n", html, re.S).group(1))


def test_config_lists_every_page_with_hint():
    cfg = _config(_script())
    assert [i["name"] for i in cfg["items"]] == PAGES
    assert all(i["hint"] for i in cfg["items"])
    assert cfg["current"] == "Overview"


def test_only_visible_pages_are_offered():
    # role-filtered nav (e.g. client) must not leak hidden pages into the palette
    cfg = _config(_script(pages=["Overview", "Usage"]))
    assert [i["name"] for i in cfg["items"]] == ["Overview", "Usage"]


def test_theme_colors_are_applied():
    assert _config(_script(theme="light"))["bg"] == THEMES["light"]["SURFACE"]
    assert _config(_script(theme="dark"))["bg"] == THEMES["dark"]["SURFACE"]


def test_script_cannot_be_broken_out_of_by_page_name():
    html = _script(pages=["</script><b>x"])
    assert html.count("</script>") == 1      # only the real closing tag


def test_navigation_targets_hidden_proxy_buttons():
    html = _script()
    assert "cosClickProxy(doc, 'nav:' + it.name)" in html   # must match app.py's label f"nav:{page}"
    assert "function cosClickProxy" in html                  # helper is embedded in the iframe
    assert "st-key-" not in html                             # st-key-* classes don't exist in streamlit 1.38


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_generated_javascript_parses(tmp_path):
    js = re.search(r"<script>(.*)</script>", _script(), re.S).group(1)
    f = tmp_path / "palette.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── Overview search box (opens the palette) ─────────────────────────────────

def test_palette_exposes_open_for_the_search_box():
    assert "win.__cosPaletteOpen = open" in _script()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_search_trigger_uses_theme_colors_and_opens_palette(theme):
    from dashboard.components.command_palette import build_search_trigger_html
    t = THEMES[theme]
    html = build_search_trigger_html(t)
    assert t["SURFACE"] in html and t["BORDER"] in html
    assert "__cosPaletteOpen" in html and "Ctrl K" in html
    assert "aria-label" in html and 'role="button"' in html    # keyboard/AT accessible
