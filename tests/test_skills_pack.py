"""The standalone skills in skills/ must stay self-contained and honest about what they need.

They are published to skill marketplaces and installed into other people's agents, so a skill that names a ClaudeOS-only tool
(it would do nothing there), asks for more permission than its README says, or carries a secret, is a release bug.
"""
import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "skills"
NAMES = ["claudeos-qa-review", "claudeos-deep-research", "claudeos-research-digest"]
# Tools that exist only inside the ClaudeOS runtime.
CLAUDEOS_ONLY = ["get_recent_outputs", "search_outputs", "get_output", "multi_search", "search_wikipedia", "get_news", "fetch_page", "namespace"]


def _read(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    assert m, "missing --- frontmatter ---"
    return dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line and not line.startswith(" "))


def test_exactly_the_documented_skills_exist():
    found = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    assert found == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_frontmatter(name):
    fm = {k.strip(): v.strip() for k, v in _frontmatter(_read(name)).items()}
    assert fm["name"] == name, "the name must equal the folder name"
    assert 40 < len(fm["description"]) <= 1024
    # An agent only picks a skill without being told when its description says plainly when to use it. Measured: the passive
    # wording used before triggered the reviewer 0 of 4 times on "Review app.py for problems"; this wording, 4 of 4.
    assert fm["description"].startswith("Use this skill whenever"), "keep the description assertive so the skill is chosen"
    assert fm["license"] == "MIT"
    assert fm["allowed-tools"], "every skill must declare the tools it needs"


@pytest.mark.parametrize("name", NAMES)
def test_no_claudeos_only_tools_or_terms(name):
    body = _read(name).lower()
    for term in CLAUDEOS_ONLY:
        assert term not in body, f"{name} mentions {term!r}, which does not exist outside ClaudeOS"


@pytest.mark.parametrize("name", NAMES)
def test_no_secrets_no_emojis(name):
    text = _read(name)
    assert not re.search(r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY", text)
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", text), "skills promise plain text, no emojis"


def test_qa_review_cannot_change_anything():
    tools = _frontmatter(_read("claudeos-qa-review"))["allowed-tools"]
    for forbidden in ("Write", "Edit", "WebFetch", "WebSearch"):
        assert forbidden not in tools, f"the read-only reviewer must not be given {forbidden}"
    assert "Bash(" in tools and "Bash(git diff" in tools, "shell access must be limited to named read-only git commands"
    assert not re.search(r"\bBash\b(?!\()", tools), "no unrestricted Bash"


def test_readme_lists_the_same_tools_as_each_skill():
    readme = (SKILLS / "README.md").read_text(encoding="utf-8")
    for name in NAMES:
        row = next(line for line in readme.splitlines() if line.startswith(f"| `{name}`"))
        for tool in re.split(r",\s*", _frontmatter(_read(name))["allowed-tools"].strip()):
            base = re.sub(r"Bash\((git \w+).*", r"\1", tool).strip()
            assert base in row, f"README row for {name} does not mention {base}"
