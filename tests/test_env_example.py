"""Every setting the code reads is documented in .env.example, and nothing is listed there that the code no longer reads.

Settings are read three ways: os.environ / os.getenv, the _env() / _checked() helpers in core/models.py, and the fields
of the Settings class in core/config.py (pydantic reads each field from .env by its name). Add a setting: read it one
of these ways, then add it to .env.example (commented out with its default if it is optional)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"tests", "venv", ".venv", "node_modules", ".git", "__pycache__"}
READ = re.compile(r"""(?:os\.environ\.get|os\.getenv|os\.environ\[|\b_env|\b_checked)\(?\s*["']([A-Z][A-Z0-9_]*)["']""")
# Listed in .env.example but read by a library, not by this code.
READ_BY_LIBRARIES = {"HF_HUB_OFFLINE"}  # huggingface_hub


def _code_reads():
    names = {}
    for path in ROOT.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        for name in READ.findall(path.read_text(encoding="utf-8")):
            names.setdefault(name, str(path.relative_to(ROOT)))
    config = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
    fields = config.split("class Settings(BaseSettings):", 1)[1].split("model_config", 1)[0]
    for name in re.findall(r"^    ([A-Z][A-Z0-9_]*)\s*:", fields, flags=re.M):
        names.setdefault(name, "core/config.py Settings")
    return names


def _example_names():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", text, flags=re.M))


def test_the_scan_finds_all_three_kinds_of_read():
    reads = _code_reads()
    assert reads.get("SMTP_FROM") == str(Path("core/notifications.py"))      # os.environ
    assert "CLAUDE_PRICE_IN_PER_MTOK" in reads                               # _env() helper
    assert reads.get("SQLITE_PATH") == "core/config.py Settings"              # Settings field


def test_every_setting_the_code_reads_is_in_env_example():
    missing = {n: f for n, f in _code_reads().items() if n not in _example_names()}
    assert not missing, f"add these to .env.example: {missing}"


def test_nothing_listed_that_the_code_no_longer_reads():
    stale = _example_names() - set(_code_reads()) - READ_BY_LIBRARIES
    assert not stale, f"not read anywhere (remove from .env.example, or declare it in Settings): {stale}"


def test_sync_interval_can_be_set():
    """SYNC_INTERVAL_MIN was read with getattr(settings, ...) but never declared, so .env could not change it."""
    from core.config import Settings
    assert "SYNC_INTERVAL_MIN" in Settings.model_fields
    assert Settings.model_fields["SYNC_INTERVAL_MIN"].default == 15
