"""_safe_path_segment turns untrusted text (a namespace or output type) into ONE folder name that is valid on every platform.

Before this, control and line-break characters passed through: Linux created a folder with a newline in its name, and Windows
(the supported platform) failed with WinError 123, so the request returned an error.
"""
import pytest

from outputs.manager import _safe_path_segment


@pytest.mark.parametrize("raw", [
    "a\nb", "a\rb", "a\x00b", "a\x1bb", "a\x1cb", "a\x85b", "a b", "a b", "a\x7fb",
])
def test_control_and_line_break_characters_are_replaced(raw):
    out = _safe_path_segment(raw)
    assert out == "a_b"
    assert len(out.splitlines()) == 1


def test_each_character_of_a_crlf_pair_is_replaced():
    assert _safe_path_segment("a\r\nb") == "a__b"


@pytest.mark.parametrize("ch", list('<>:"|?*'))
def test_windows_forbidden_characters_are_replaced(ch):
    assert _safe_path_segment(f"a{ch}b") == "a_b"


@pytest.mark.parametrize("raw, expected", [
    ("../etc/passwd", "_etc_passwd"),
    ("..\\windows", "_windows"),
    ("a/b\\c", "a_b_c"),
    ("global", "global"),
    ("ns-a", "ns-a"),
    ("report.v2", "report.v2"),
])
def test_separators_and_dotdot_still_neutralised_and_normal_names_unchanged(raw, expected):
    assert _safe_path_segment(raw) == expected


@pytest.mark.parametrize("raw", ["", "...", "  ", ". .", "/", ".."])
def test_names_that_end_up_empty_become_unknown(raw):
    # "/" becomes "_" (not empty); the others reduce to nothing
    out = _safe_path_segment(raw)
    assert out in ("unknown", "_")


def test_trailing_dot_and_space_are_removed_because_windows_drops_them():
    assert _safe_path_segment("name. ") == "name"


def test_length_is_bounded():
    assert len(_safe_path_segment("x" * 500)) == 64
