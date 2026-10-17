"""Agents catalog: marketplace-style card renderer."""
import re
import shutil
import subprocess

import pytest

from dashboard._pages._agents import CATALOG_CARD_HEIGHT, _catalog_card_html

AGENT = {
    "name": "analysis-agent", "display_name": "Analysis Agent", "category": "analysis",
    "description": "Turns business data into findings.", "model": "claude-sonnet-4-6",
    "max_tokens": 4096, "enabled": True, "namespace_lock": None,
}
KW = dict(card_bg="#163A17", card_border="#2D5C2E", card_text="#E8F5E8",
          card_muted="#7DBF7E", enabled_color="#5a9e56")


def _card(**over):
    return _catalog_card_html({**AGENT, **over}, "#407E3C", "card_chat_analysis_agent", **KW)


def test_card_shows_name_initial_and_chips():
    html = _card()
    assert "Analysis Agent" in html
    assert '<div class="avatar">A<i></i></div>' in html
    assert "sonnet-4-6" in html and "claude-sonnet" not in html     # model shortened
    assert "4096 tok" in html and "analysis</span>" in html


def test_card_click_targets_the_proxy_button():
    html = _card()
    assert "cosClickProxy(window.parent.document,'card:card_chat_analysis_agent')" in html
    assert "function cosClickProxy" in html
    assert "st-key-" not in html


def test_namespace_lock_chip_only_when_locked():
    assert "locked:" not in _card()
    assert "locked: faiyke-ai" in _card(namespace_lock="faiyke-ai")


def test_agent_fields_are_html_escaped():
    html = _card(display_name="<img src=x onerror=alert(1)>", description="</div><script>x()</script>",
                 namespace_lock='"><b>')
    assert "<img" not in html and "<script>x()" not in html and "<b>" not in html
    assert "&lt;img" in html


def test_card_fits_its_iframe_height():
    # card is 120px + 8px body padding; iframe must not clip it
    assert f"height:120px" in _card() and CATALOG_CARD_HEIGHT >= 128


def test_disabled_agent_uses_muted_status_dot():
    html = _catalog_card_html({**AGENT, "enabled": False}, "#407E3C", "k", **{**KW, "enabled_color": "#6b7280"})
    assert "background:#6b7280" in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_inline_onclick_is_valid_javascript(tmp_path):
    js = re.search(r'onclick="([^"]+)"', _card()).group(1)
    f = tmp_path / "onclick.js"
    f.write_text(js, encoding="utf-8")
    assert subprocess.run(["node", "--check", str(f)], capture_output=True).returncode == 0
