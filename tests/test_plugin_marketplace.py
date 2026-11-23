"""The Claude Code plugin marketplace file (.claude-plugin/marketplace.json) must stay installable.

People add this repository with `/plugin marketplace add`, so a broken file, a skill that is listed but missing, a name Claude
Code reserves, or a tool pattern the plugin loader silently drops, is a release bug.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
# Claude Code refuses plugin names that start with these, and marketplace names it reserves for itself.
RESERVED_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
RESERVED_EXACT = {"claude", "anthropic", "anthropics", "claude-code", "claude-mods"}


def _data():
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def test_marketplace_has_the_required_fields():
    d = _data()
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", d["name"]) and ".." not in d["name"]
    assert d["owner"]["name"]
    assert isinstance(d["plugins"], list) and d["plugins"]


def test_plugin_names_are_allowed():
    for p in _data()["plugins"]:
        name = p["name"]
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", name), f"{name}: use kebab-case"
        assert name not in RESERVED_EXACT and not name.startswith(RESERVED_PREFIXES), f"{name} is reserved by Claude Code"


def test_every_listed_skill_exists_and_is_the_only_content_installed():
    # The plugin source is the skills folder, so installing copies only skills, not the dashboard, data or vault.
    for p in _data()["plugins"]:
        src = p["source"]
        assert src.startswith("./") and ".." not in src, "source must be a relative path inside the repository"
        base = (ROOT / src).resolve()
        assert base.is_dir() and base != ROOT, "do not point the plugin at the repository root: it would copy everything"
        for s in p["skills"]:
            assert (base / s / "SKILL.md").is_file(), f"{s} is listed but has no SKILL.md"


def test_listed_skills_are_all_the_skills():
    for p in _data()["plugins"]:
        base = (ROOT / p["source"]).resolve()
        listed = sorted(Path(s).name for s in p["skills"])
        on_disk = sorted(d.name for d in base.iterdir() if d.is_dir())
        assert listed == on_disk, "a skill folder is missing from the marketplace list (or the other way round)"


def test_tool_patterns_use_the_form_the_plugin_loader_accepts():
    # `Bash(git diff:*)` made Claude Code skip the whole skill when installed as a plugin (found 2026-11-23); use `Bash(git diff *)`.
    for skill in (ROOT / "skills").glob("*/SKILL.md"):
        head = skill.read_text(encoding="utf-8").split("\n---", 1)[0]
        assert ":*)" not in head, f"{skill.parent.name}: use 'Bash(cmd *)' not 'Bash(cmd:*)' in allowed-tools"


def test_plugin_files_are_checked_out_as_lf():
    # On Windows (core.autocrlf=true) a CRLF checkout makes Claude Code skip claudeos-qa-review. .gitattributes must force LF.
    rules = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^skills/\*\*\s+text\s+eol=lf\s*$", rules, re.M), "skills/** must be forced to LF"
    assert re.search(r"^\.claude-plugin/\*\*\s+text\s+eol=lf\s*$", rules, re.M), ".claude-plugin/** must be forced to LF"
