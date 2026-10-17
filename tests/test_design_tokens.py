"""Design system guards: fonts, glow token, serif headings, proxy/iframe hiding present in built CSS."""
import pytest

from dashboard.components.brand import THEMES, _build_css


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_themes_define_every_token_the_css_uses(theme):
    for key in ("BG", "SURFACE", "SURFACE2", "TEXT", "TEXT_MUTED", "BORDER", "BTN_BG", "BTN_TEXT", "GLOW"):
        assert THEMES[theme][key], key


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_built_css_has_new_type_system_and_layout_fixes(theme):
    css = _build_css(theme)
    assert "'Source Serif 4'" in css and "'Inter'" in css
    assert "Poppins" not in css
    assert "radial-gradient" in css and THEMES[theme]["GLOW"] in css      # static top glow, no animation
    assert "animation" not in css.split("radial-gradient")[1][:200]
    assert '[height="0px"]' in css and "cos-proxy-zone" in css            # Streamlit 1.56 + 1.38 hiding rules
    assert ".cos-pill" in css


def test_no_font_other_than_the_design_system_is_requested_in_dashboard_python():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "dashboard"
    offenders = [p.name for p in root.rglob("*.py")
                 if "Poppins" in p.read_text(encoding="utf-8") and not p.name.startswith("brand_v1")]
    assert not offenders, offenders
