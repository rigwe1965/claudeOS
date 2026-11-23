"""Every skill in skills/ must follow the Agent Skills specification (https://agentskills.io/specification).

The same SKILL.md files are read by Claude Code and by other tools (Codex CLI, Gemini CLI, GitHub Copilot and more), so a name that
does not match its folder, an over-long description or an unknown front-matter field is a release bug in every one of them.
This is our own check written from the specification page; it is not the official `skills-ref` validator.
"""
import re
from pathlib import Path

import pytest
import yaml

SKILLS = Path(__file__).resolve().parent.parent / "skills"
DIRS = sorted(p for p in SKILLS.iterdir() if p.is_dir())
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def _parse(folder):
    # Read as text with universal newlines, so a Windows checkout with CRLF does not fail here (line endings are tested elsewhere).
    text = (folder / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, f"{folder.name}: SKILL.md must start with --- front matter ---"
    # A real YAML parse, as other tools do. Reading the lines by hand missed an unquoted ": " inside a description (2026-11-23).
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        pytest.fail(f"{folder.name}: the front matter is not valid YAML (quote values that contain ': '): {str(e).splitlines()[0]}")
    assert isinstance(fm, dict), f"{folder.name}: the front matter must be name: value lines"
    return text, fm, m.group(2)


def test_there_are_skills_to_check():
    assert DIRS, "skills/ has no skill folders"


@pytest.mark.parametrize("folder", DIRS, ids=lambda p: p.name)
def test_name_follows_the_specification(folder):
    name = _parse(folder)[1].get("name")
    assert isinstance(name, str), "name must be text"
    assert 1 <= len(name) <= 64, "name must be 1 to 64 characters"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), "name: lowercase letters, digits and single hyphens; no leading or trailing hyphen"
    assert name == folder.name, f"name '{name}' must match its folder '{folder.name}'"


@pytest.mark.parametrize("folder", DIRS, ids=lambda p: p.name)
def test_description_and_optional_fields_follow_the_specification(folder):
    _, fm, _ = _parse(folder)
    assert isinstance(fm.get("description"), str), "description must be text"
    assert 1 <= len(fm["description"]) <= 1024, "description must be 1 to 1024 characters"
    assert len(str(fm.get("compatibility", "x"))) <= 500, "compatibility is at most 500 characters"
    extra = set(fm) - SPEC_FIELDS
    assert not extra, f"front-matter fields the specification does not define: {sorted(extra)} (put extras under metadata)"


@pytest.mark.parametrize("folder", DIRS, ids=lambda p: p.name)
def test_body_stays_small_and_links_resolve(folder):
    text, _, body = _parse(folder)
    assert len(text.splitlines()) < 500, "keep SKILL.md under 500 lines; move detail into references/"
    assert len(body) // 4 < 5000, "instructions should stay under about 5000 tokens"
    for link in re.findall(r"\]\(((?!https?:|#|mailto:)[^)]+)\)", body):
        assert (folder / link).exists(), f"broken relative link: {link}"
