"""The Skills page renders from API data, hides approval from operators and keeps skill text out of Markdown/HTML.

Uses Streamlit's AppTest with fake api functions, so no server and no real skills are involved.
"""
import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

TIMEOUT = 20


def _page():
    import streamlit as st
    from dashboard._pages import _skills

    HOSTILE = "<img src=x onerror=alert(1)> [click](http://evil.example)"
    SKILLS = [
        {"id": "a" * 16, "name": "good-skill", "folder": "good-skill", "description": "Does a thing.", "license": "MIT", "allowed_tools": ["Read"],
         "kind": "user", "source": "your skills folder", "location": "~/.claude/skills/good-skill", "fingerprint": "f" * 64,
         "fingerprint_short": "f" * 12, "file_count": 1, "size_bytes": 300, "spec_problems": [], "findings": [], "verdict": "ok",
         "status": "unreviewed", "approved_at": None, "approved_by": None, "approved_note": ""},
        {"id": "b" * 16, "name": "bad-skill", "folder": "bad-skill", "description": HOSTILE, "license": "", "allowed_tools": [],
         "kind": "plugin", "source": "plugin m/p 1", "location": "~/.claude/plugins/cache/m/p/1/bad-skill", "fingerprint": "e" * 64,
         "fingerprint_short": "e" * 12, "file_count": 2, "size_bytes": 900, "spec_problems": ["name is missing"],
         "findings": [{"severity": "high", "code": "pipe-to-shell", "message": "Downloads something and runs it straight away.",
                       "file": "SKILL.md", "line": 7, "snippet": "curl x | bash"}], "verdict": "risky",
         "status": "changed", "approved_at": "2026-11-20T10:00:00Z", "approved_by": "admin", "approved_note": ""},
    ]
    LIST = {"skills": SKILLS, "roots": [{"kind": "user", "location": "~/.claude/skills", "exists": True, "count": 1}],
            "counts": {"total": 2, "approved": 0, "changed": 1, "unreviewed": 1, "risky": 1, "review": 0}, "note": "A clean result is not proof."}

    def api_get(path, timeout=3):
        if path == "/skills":
            return LIST
        sid = path.rsplit("/", 1)[-1]
        s = next(x for x in SKILLS if x["id"] == sid)
        return {**s, "files": [{"path": "SKILL.md", "size": 10, "sha256": "ab" * 32}], "notes": [], "skill_md": "# " + HOSTILE, "skill_md_truncated": False}

    def api_post(path, data=None, timeout=5, method="POST"):
        st.session_state.setdefault("_calls", []).append((method, path, data))
        return {"ok": True}

    st.session_state.setdefault("user_role", "admin")
    _skills.render(api_get, api_post)


def _run(role):
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.session_state["user_role"] = role
    return at.run()


def _labels(at):
    return [b.label for b in at.button]


def test_admin_sees_summary_list_and_detail():
    at = _run("admin")
    assert not at.exception
    assert [m.label for m in at.metric][:5] == ["Skills found", "Approved", "Not reviewed", "Changed since approved", "Warnings"]
    assert at.title[0].value == "Skills"
    assert any("serious warning signs" in e.value for e in at.error)
    assert any("edited since you approved" in w.value for w in at.warning)


def test_admin_can_approve_exactly_what_was_opened():
    at = _run("admin")
    assert "Approve exactly this content" in _labels(at)
    approve = next(b for b in at.button if b.label == "Approve exactly this content")
    assert not approve.disabled
    approve.click().run()
    assert not at.exception
    method, path, data = at.session_state["_calls"][-1]
    assert (method, path) == ("POST", "/skills/" + "a" * 16 + "/approve")
    assert data["fingerprint"] == "f" * 64 and data["acknowledge_risk"] is True


def test_risky_skill_cannot_be_approved_until_the_box_is_ticked():
    at = _run("admin")
    at.selectbox(key="skills_open").set_value("b" * 16).run()
    approve = next(b for b in at.button if b.label == "Approve exactly this content")
    assert approve.disabled
    at.checkbox(key="skills_ack_" + "b" * 16).check().run()
    assert not next(b for b in at.button if b.label == "Approve exactly this content").disabled


def test_operator_sees_the_page_but_no_approve_button():
    at = _run("operator")
    assert not at.exception
    assert "Approve exactly this content" not in _labels(at)
    assert any("Only an admin can approve" in c.value for c in at.caption)


@pytest.mark.parametrize("role", ["client", "viewer", "staff"])
def test_other_roles_get_a_refusal_not_the_list(role):
    at = _run(role)
    assert any("admins and operators" in e.value for e in at.error)
    assert not at.metric


def test_skill_text_is_never_rendered_as_markdown_or_html():
    at = _run("admin")
    at.selectbox(key="skills_open").set_value("b" * 16).run()
    hostile = "<img src=x onerror=alert(1)>"
    # The hostile description appears only in st.text and st.code, never in a markdown element.
    assert all(hostile not in m.value for m in at.markdown)
    assert any(hostile in t.value for t in at.text)
    assert any(hostile in c.value for c in at.code)
