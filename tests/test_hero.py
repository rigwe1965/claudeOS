"""aurora_hero must never emit a blank line — markdown would turn the rest into a code block."""
import pytest

from dashboard.components import brand


@pytest.mark.parametrize("title", ["ClaudeOS", ""])
def test_hero_html_has_no_blank_lines(monkeypatch, title):
    out = []
    monkeypatch.setattr(brand.st, "markdown", lambda html, **kw: out.append(html))
    monkeypatch.setattr(brand, "get_theme", lambda: "dark")
    monkeypatch.setattr(brand, "get_ns_brand", lambda: {})
    brand.aurora_hero(title, "sub", "pill")
    assert len(out) == 1
    assert all(line.strip() for line in out[0].splitlines())
    assert "aurora-hero-card" in out[0]
