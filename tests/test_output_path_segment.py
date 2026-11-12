"""_safe_path_segment turns untrusted text (a namespace or output type) into ONE folder name that is valid on every platform.

Before this, control and line-break characters passed through: Linux created a folder with a newline in its name, and Windows
(the supported platform) failed with WinError 123, so the request returned an error.
"""
import pytest

from outputs.manager import _safe_path_segment


@pytest.mark.parametrize("raw", [
    "a\nb", "a\rb", "a\x00b", "a\x1bb", "a\x1cb", "a\x85b", "a\u2028b", "a\u2029b", "a\x7fb",
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


# --- no invisible characters in source files ---------------------------------------------------------------------------
# A literal U+2028 or U+2029 typed into a Python file is invisible to a reviewer and makes str.splitlines() count an extra line.
# Write them as escapes (backslash, u, 2028) instead. The characters are built with chr() so this file contains none itself.
HIDDEN = {chr(c) for c in (0x2028, 0x2029, 0x200B, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069)}


def test_no_hidden_unicode_characters_in_python_sources():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    skip = {".venv", "venv", "node_modules", "dist", "data", ".git"}
    offenders = {}
    for path in root.rglob("*.py"):
        if skip & set(path.relative_to(root).parts):
            continue
        found = sorted({hex(ord(ch)) for ch in path.read_text(encoding="utf-8", errors="ignore") if ch in HIDDEN})
        if found:
            offenders[str(path.relative_to(root))] = found
    assert not offenders, f"invisible characters in source (write them as escapes): {offenders}"
