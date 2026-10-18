"""Local project scans require the same roles as project attachment."""
from unittest.mock import Mock

import pytest

from dashboard._pages import _projects


DENIED_ROLES = ["client", "viewer", "staff", "unknown", "", None]


@pytest.mark.parametrize("role", DENIED_ROLES)
def test_scan_denied_before_any_path_access(monkeypatch, role):
    state = {"user_role": role} if role is not None else {}
    monkeypatch.setattr(_projects.st, "session_state", state)
    path = Mock(side_effect=AssertionError("Unauthorized filesystem access"))
    monkeypatch.setattr(_projects, "Path", path)

    result = _projects._scan_directory("/private/project")

    path.assert_not_called()
    assert result["ok"] is False
    assert result["description"] == ""
    assert result["tech_stack"] == []
    assert "admin" in result["error"] and "operator" in result["error"]


@pytest.mark.parametrize("role", DENIED_ROLES)
def test_attachment_denied_before_widgets_or_scan(monkeypatch, role):
    state = {"user_role": role} if role is not None else {}
    # Simulate an old widget value remaining in the session.
    state["attach_path"] = "/private/project"
    monkeypatch.setattr(_projects.st, "session_state", state)
    monkeypatch.setattr(_projects.st, "info", Mock())
    widget = Mock(side_effect=AssertionError("Unauthorized attachment widget"))
    scan = Mock(side_effect=AssertionError("Unauthorized scan"))
    post = Mock()
    monkeypatch.setattr(_projects.st, "text_input", widget)
    monkeypatch.setattr(_projects, "_scan_directory", scan)

    _projects._attach_project_form(post, [{"display_name": "Own", "id": "own"}])

    widget.assert_not_called()
    scan.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("role", ["client", "viewer"])
@pytest.mark.parametrize("access", ["direct", "traversal", "directory_symlink", "document_symlink"])
def test_scan_cannot_disclose_server_documentation(monkeypatch, tmp_path, role, access):
    private = tmp_path / "private"
    private.mkdir()
    (private / "README.md").write_text("Confidential server documentation", encoding="utf-8")
    own = tmp_path / "own"
    own.mkdir()
    if access == "direct":
        target = private
    elif access == "traversal":
        target = own / ".." / "private"
    elif access == "directory_symlink":
        target = own / "linked"
        try:
            target.symlink_to(private, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Directory symlinks are unavailable in this environment")
    else:
        try:
            (own / "README.md").symlink_to(private / "README.md")
        except (OSError, NotImplementedError):
            pytest.skip("File symlinks are unavailable in this environment")
        target = own
    monkeypatch.setattr(_projects.st, "session_state", {"user_role": role, "user_namespace": "own"})

    result = _projects._scan_directory(str(target))

    assert result["ok"] is False
    assert "Confidential" not in str(result)


@pytest.mark.parametrize("role", ["admin", "operator"])
def test_authorized_attachment_scans_and_submits_metadata(monkeypatch, tmp_path, role):
    project = tmp_path / "Example Project"
    project.mkdir()
    (project / "README.md").write_text("# Example\n\nProject description.\n", encoding="utf-8")
    (project / "requirements.txt").write_text("flask==3.1.3\n", encoding="utf-8")
    state = {"user_role": role}
    monkeypatch.setattr(_projects.st, "session_state", state)
    monkeypatch.setattr(_projects.st, "text_input", lambda label, key, **kw:
                        str(project) if key == "attach_path" else state.get(key, ""))
    monkeypatch.setattr(_projects.st, "button", lambda *a, **kw: True)
    monkeypatch.setattr(_projects.st, "selectbox", lambda label, options, **kw: options[0])
    for method in ("markdown", "success", "error"):
        monkeypatch.setattr(_projects.st, method, Mock())
    post = Mock(return_value=None)

    _projects._attach_project_form(post, [{"display_name": "Own", "id": "own"}])

    assert state["attach_scan_result"]["ok"] is True
    post.assert_called_once_with("/projects", {
        "namespace_id": "own", "name": "Example Project", "slug": "example-project",
        "description": "Project description.", "tech_stack": ["Flask", "Python"],
        "priority": 1, "path": str(project),
    })
