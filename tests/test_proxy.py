"""Hidden proxy buttons must not depend on st-key-* classes (streamlit==1.38.0 has none)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dashboard.components.proxy import COS_CLICK_PROXY_JS, PROXY_CSS, ZONE_CLASS

DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard"


def test_no_dashboard_code_depends_on_st_key_classes():
    offenders = [
        f"{p.relative_to(DASHBOARD)}:{i}"
        for p in DASHBOARD.rglob("*.py")
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "st-key-" in line and "byKey" not in line      # theme toggle keeps an optional fast path
    ]
    assert not offenders, f"st-key-* selectors never match on streamlit 1.38: {offenders}"


def test_pinned_streamlit_has_no_key_classes_assumption():
    pin = re.search(r"^streamlit==([\d.]+)", (DASHBOARD.parent / "requirements.txt").read_text(encoding="utf-8"), re.M)
    assert pin, "streamlit must stay pinned"


def test_css_hides_marker_containers_with_display_none():
    assert f".{ZONE_CLASS}" in PROXY_CSS and "display: none !important" in PROXY_CSS
    assert PROXY_CSS.count("{") == PROXY_CSS.count("}")


def test_css_is_injected_into_theme_css():
    from dashboard.components.brand import _build_css
    assert ZONE_CLASS in _build_css("dark") and ZONE_CLASS in _build_css("light")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_click_helper_finds_button_by_label_only_inside_marked_block(tmp_path):
    harness = COS_CLICK_PROXY_JS + """
function mkBtn(text){ return {textContent:' '+text+' ', clicked:false, click(){this.clicked=true;}}; }
var inZone = mkBtn('nav:Agents'), outside = mkBtn('nav:Agents');
var block = {querySelectorAll:()=>[mkBtn('other'), inZone]};
var zone = {closest:()=>block};
var doc = {querySelectorAll:(s)=> s==='.cos-proxy-zone' ? [zone] : []};
if (!cosClickProxy(doc,'nav:Agents') || !inZone.clicked) throw new Error('did not click zone button');
if (cosClickProxy(doc,'nav:Missing')) throw new Error('clicked a missing label');
if (cosClickProxy({querySelectorAll:()=>[]},'nav:Agents')) throw new Error('no zones should be false');
console.log('ok');
"""
    f = tmp_path / "h.js"
    f.write_text(harness, encoding="utf-8")
    r = subprocess.run(["node", str(f)], capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr
