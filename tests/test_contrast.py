"""WCAG AA (4.5:1) contrast guard for dashboard text colors."""
import re

import pytest

from dashboard.components.brand import THEMES, nav_palette

AA = 4.5        # text
GRAPHIC = 3.0   # icons and other non-text UI


def _rgb(color: str, over: tuple = (255, 255, 255)) -> tuple:
    """'#rrggbb' or 'rgba(r,g,b,a)' -> opaque (r, g, b), alpha-blended onto `over`."""
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b, a = (float(x) for x in re.findall(r"[\d.]+", color))
    return tuple(round(a * c + (1 - a) * o) for c, o in zip((r, g, b), over))


def _lum(rgb: tuple) -> float:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: tuple, bg: tuple) -> float:
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("fg", ["TEXT", "TEXT_MUTED"])
@pytest.mark.parametrize("bg", ["BG", "SURFACE", "SURFACE2"])
def test_theme_text_meets_aa(theme, fg, bg):
    t = THEMES[theme]
    assert ratio(_rgb(t[fg]), _rgb(t[bg])) >= AA, f"{theme}: {fg} on {bg}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_button_text_meets_aa(theme):
    t = THEMES[theme]
    assert ratio(_rgb(t["BTN_TEXT"]), _rgb(t["BTN_BG"])) >= AA


@pytest.mark.parametrize("is_dark", [True, False])
def test_nav_text_tiers_meet_aa(is_dark):
    p = nav_palette(is_dark)
    bg = _rgb(p["bg"])
    for tier in ("group", "item"):
        assert ratio(_rgb(p[tier], over=bg), bg) >= AA, f"nav {tier} (dark={is_dark})"
    active_bg = _rgb(p["active_bg"], over=bg)
    assert ratio(_rgb(p["active_text"]), active_bg) >= AA
    assert ratio(_rgb(p["accent"]), active_bg) >= GRAPHIC     # active icon: non-text, 3:1 per WCAG 1.4.11
    assert ratio((255, 255, 255), _rgb(p["badge_bg"])) >= AA  # ticket count badge


@pytest.mark.parametrize("is_dark", [True, False])
def test_nav_hierarchy_items_brighter_than_group_labels(is_dark):
    p = nav_palette(is_dark)
    bg = _rgb(p["bg"])
    assert ratio(_rgb(p["item"], over=bg), bg) > ratio(_rgb(p["group"], over=bg), bg)


def test_solid_status_pills_have_readable_white_text():
    """Settings pills: white text on these backgrounds (bg colours are set inline in _settings.py)."""
    for bg in ("#407E3C", "#B42318", "#5F6673"):
        assert ratio((255, 255, 255), _rgb(bg)) >= AA, bg


def test_hero_and_search_text_on_page_background():
    for theme in ("dark", "light"):
        t = THEMES[theme]
        assert ratio(_rgb(t["TEXT_MUTED"]), _rgb(t["SURFACE"])) >= AA     # search box placeholder
        assert ratio(_rgb(t["TEXT_MUTED"]), _rgb(t["BG"])) >= AA          # hero subtitle / meta chip
