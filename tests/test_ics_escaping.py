from datetime import datetime

from notifications.email import _build_ics


def test_ics_text_cannot_inject_properties():
    out = _build_ics("a\r\nATTENDEE:evil;x", "l1\rATTENDEE:evil\nl3", datetime(2026, 1, 1))
    lines = out.split("\r\n")
    assert not any(l.startswith("ATTENDEE") for l in lines)
    assert "SUMMARY:a\\nATTENDEE:evil\\;x" in lines
    assert "\r" not in "".join(lines) and "\n" not in "".join(lines)
