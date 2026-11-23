"""Skill inventory: find the skills installed on this machine, fingerprint them, check them against the Agent Skills specification
and scan them for risky content.

Read-only. Nothing here runs a skill or any script inside one. The scan is a set of simple text patterns: it finds the usual
warning signs (download-and-run, hidden characters, instructions aimed at the model, reaching for credentials), it does not prove
a skill is safe. A clean scan means "nothing obvious", not "trusted"; trusting is the owner's decision (see skill_approvals).

Where skills live:
  user     ~/.claude/skills/<name>/SKILL.md
  bundled  <this repository>/skills/<name>/SKILL.md
  plugin   ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/.../<name>/SKILL.md
  custom   every folder in the SKILL_ROOTS setting (os.pathsep separated), one level deep
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Iterable, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_SKILLS = 500
MAX_FILES = 200                 # files looked at per skill
MAX_HASH_BYTES = 50_000_000     # a file bigger than this is recorded by size only
MAX_SCAN_BYTES = 1_000_000      # a file bigger than this is not text-scanned
MAX_FINDINGS_PER_CODE = 5
MAX_PLUGIN_DEPTH = 7
SKILL_MD_PREVIEW_CHARS = 20_000

TEXT_SUFFIXES = {".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".csv", ".html", ".xml",
                 ".py", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".cjs", ".ts"}
EXEC_SUFFIXES = {".py", ".sh", ".bash", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".cjs", ".ts", ".exe", ".dll", ".so", ".jar"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# ── Patterns ────────────────────────────────────────────────────────────────────
# (code, severity, message, regex, where): where is "any" (prose and code) or "code" (only fenced code blocks and script files:
# a skill that merely talks about `rm -rf` in a sentence is not running it).
_I = re.IGNORECASE
_PATTERNS = [
    ("pipe-to-shell", "high", "Downloads something and runs it straight away.",
     re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(sh|bash|zsh|python3?|perl|ruby|node)\b|"
                r"\b(iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]*\|\s*(iex|Invoke-Expression)\b|"
                r"\biex\s*\(\s*(New-Object|iwr|irm|Invoke-)", _I), "code"),
    ("encoded-exec", "high", "Decodes hidden text and runs it.",
     re.compile(r"base64\s+(-d|--decode)[^\n|]*\|\s*(sh|bash|python3?)\b|"
                r"powershell(\.exe)?\s+[^\n]*-(enc|encodedcommand)\b|"
                r"\b(eval|exec)\s*\(\s*(base64\.b64decode|bytes\.fromhex|codecs\.decode)|"
                r"FromBase64String[^\n]*\b(iex|Invoke-Expression)\b", _I), "code"),
    ("prompt-injection", "high", "Contains wording that tries to override the user's instructions or hide things from the user.",
     re.compile(r"\bignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)\b|"
                r"\bdisregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|system)\s+(instructions|rules|prompt)\b|"
                r"\b(do\s+not|don't|never)\s+(tell|inform|show|reveal\s+(this\s+)?to)\s+the\s+user\b|"
                r"\bwithout\s+(telling|informing|notifying)\s+the\s+user\b", _I), "any"),
    ("secrets-access", "high", "Reaches for credential files or key folders.",
     re.compile(r"(~|\$HOME|%USERPROFILE%|\$env:USERPROFILE)[/\\]\.(ssh|aws|gnupg|kube|docker)\b|"
                r"\bid_(rsa|ed25519|ecdsa)\b|\.aws[/\\]credentials|\.git-credentials|\.netrc\b|\.npmrc\b|"
                r"\bcredentials\.json\b", _I), "any"),
    ("destructive-command", "medium", "Contains a command that deletes or overwrites a lot.",
     re.compile(r"\brm\s+-[a-z]*(rf|fr)[a-z]*\b|Remove-Item\b[^\n]*-Recurse[^\n]*-Force|Remove-Item\b[^\n]*-Force[^\n]*-Recurse|"
                r"\bgit\s+push\s+(-f\b|--force)|\bgit\s+reset\s+--hard\b|\bdrop\s+(table|database)\b|\bmkfs(\.\w+)?\b|"
                r"\bformat\s+[a-z]:|\bdel\s+/[sfq]\b", _I), "code"),
    ("sends-data-out", "medium", "Can send data to an outside address (upload, webhook or paste site).",
     re.compile(r"https?://(discord(app)?\.com/api/webhooks|hooks\.slack\.com|pastebin\.com|transfer\.sh|file\.io|webhook\.site|"
                r"requestbin|[\w-]+\.ngrok(-free)?\.(io|app|dev)|[\w.-]*(interact\.sh|oast\.\w+))|"
                r"\bcurl\b[^\n]*\s(-d|--data(-binary|-raw|-urlencode)?|-F|--form|-T|--upload-file)\b|"
                r"\b(Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b[^\n]*-Method\s+Post", _I), "code"),
    ("reads-env-file", "medium", "Reads a .env file, where API keys are usually kept.",
     re.compile(r"(cat|type|Get-Content|open|read_text|readFile\w*)\b[^\n]*[\"'\s/\\]\.env\b", _I), "code"),
    ("installs-packages", "low", "Installs software when it runs.",
     re.compile(r"\b(pip3?|npm|pnpm|yarn|gem|cargo)\s+(install|add)\b|\bsudo\s+apt(-get)?\s+install\b|\bchmod\s+\+x\b", _I), "code"),
]
# Characters that are invisible or flip the reading direction: a known way to hide instructions in a text file.
_HIDDEN_CODES = (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2028, 0x2029,
                 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x2066, 0x2067, 0x2068, 0x2069)
# Written from code points on purpose: invisible characters must never sit in the source itself (tests/test_output_path_segment.py).
_HIDDEN = re.compile("[" + "".join(map(chr, _HIDDEN_CODES)) + chr(0xE0000) + "-" + chr(0xE007F) + "]")
_BOM = chr(0xFEFF)
_FENCE = re.compile(r"^\s*(```|~~~)")


def _finding(severity, code, message, file="", line=0, snippet=""):
    return {"severity": severity, "code": code, "message": message, "file": file, "line": line, "snippet": snippet}


# ── Roots and discovery ─────────────────────────────────────────────────────────

def home_display(path: Path) -> str:
    """Show a path with the home folder as ~ so a screenshot does not carry the account name."""
    try:
        return "~/" + path.resolve().relative_to(Path.home().resolve()).as_posix()
    except Exception:
        return str(path)


def default_roots(extra: str = "") -> list[dict]:
    home = Path.home()
    roots = [
        {"kind": "user", "path": home / ".claude" / "skills"},
        {"kind": "bundled", "path": REPO_ROOT / "skills"},
        {"kind": "plugin", "path": home / ".claude" / "plugins" / "cache"},
    ]
    for p in (extra or "").split(os.pathsep):
        if p.strip():
            roots.append({"kind": "custom", "path": Path(p.strip()).expanduser()})
    return roots


def skill_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def _within(child: Path, root: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _find_skill_dirs(root: dict) -> Iterable[Path]:
    base: Path = root["path"]
    if not base.is_dir():
        return
    if root["kind"] != "plugin":
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.is_symlink() and (child / "SKILL.md").is_file():
                yield child
        return
    # Plugin cache: skills sit at varying depth (<marketplace>/<plugin>/<version>/[skills/]<name>/SKILL.md).
    base_depth = len(base.parts)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        depth = len(Path(dirpath).parts) - base_depth
        if "SKILL.md" in filenames and depth >= 1:
            dirnames[:] = []                      # everything below belongs to this skill
            yield Path(dirpath)
            continue
        # temp_subdir_* are Claude Code's own half-finished clones, not installed plugins.
        keep = [d for d in dirnames if d not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink() and not (depth == 0 and d.startswith("temp_subdir_"))]
        dirnames[:] = sorted(keep) if depth < MAX_PLUGIN_DEPTH else []


def _source_label(root: dict, skill_dir: Path) -> str:
    kind = root["kind"]
    if kind == "plugin":
        parts = skill_dir.relative_to(root["path"]).parts
        if len(parts) >= 3:
            return f"plugin {parts[0]}/{parts[1]} {parts[2]}"
        return "plugin"
    return {"user": "your skills folder", "bundled": "bundled with ClaudeOS"}.get(kind, f"custom folder {home_display(root['path'])}")


# ── Fingerprint ─────────────────────────────────────────────────────────────────

def _file_digest(path: Path, normalise: bool) -> Optional[str]:
    h = hashlib.sha256()
    try:
        if normalise:
            h.update(path.read_bytes().replace(b"\r\n", b"\n"))   # a Windows (CRLF) and a Linux (LF) copy must hash the same
        else:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def walk_files(skill_dir: Path) -> tuple[list[dict], list[str]]:
    """Every regular file in the skill (symlinks are never followed), as [{path, size, sha256}], plus notes about what was skipped."""
    files, notes = [], []
    for dirpath, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink())
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            rel = full.relative_to(skill_dir).as_posix()
            if full.is_symlink():
                notes.append(f"{rel}: a link, not followed")
                continue
            if len(files) >= MAX_FILES:
                notes.append(f"more than {MAX_FILES} files: the rest are not checked")
                return files, notes
            try:
                size = full.stat().st_size
            except OSError:
                continue
            if size > MAX_HASH_BYTES:
                files.append({"path": rel, "size": size, "sha256": f"too-large:{size}"})
                notes.append(f"{rel}: too large to hash, recorded by size only")
                continue
            digest = _file_digest(full, full.suffix.lower() in TEXT_SUFFIXES)
            if digest is None:
                notes.append(f"{rel}: could not be read")
                continue
            files.append({"path": rel, "size": size, "sha256": digest})
    return files, notes


def fingerprint(files: list[dict]) -> str:
    """One hash for the whole skill: changes if any file is added, removed, renamed or edited."""
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x["path"]):
        h.update(f["path"].encode("utf-8") + b"\0" + f["sha256"].encode("ascii") + b"\n")
    return h.hexdigest()


# ── Parse + spec check ──────────────────────────────────────────────────────────

def _split_frontmatter(text: str) -> tuple[Optional[str], str]:
    text = text.lstrip(_BOM).replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else (None, text)


def parse_skill_md(text: str) -> tuple[dict, str, list[str]]:
    """(front matter as a dict, body, problems with the format)."""
    raw, body = _split_frontmatter(text)
    if raw is None:
        return {}, body, ["SKILL.md does not start with --- front matter ---"]
    try:
        fm = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, body, ["the front matter is not valid YAML"]
    if not isinstance(fm, dict):
        return {}, body, ["the front matter is not a set of name: value lines"]
    return fm, body, []


def spec_problems(folder_name: str, fm: dict, body: str, line_count: int) -> list[str]:
    """Differences from https://agentskills.io/specification (so the skill also works in the other tools that read the format)."""
    out = []
    name, desc = fm.get("name"), fm.get("description")
    if not isinstance(name, str) or not name:
        out.append("name is missing")
    else:
        if not 1 <= len(name) <= 64 or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            out.append("name must be 1 to 64 lowercase letters, digits and single hyphens")
        if name != folder_name:
            out.append(f"name '{name}' does not match its folder '{folder_name}'")
    if not isinstance(desc, str) or not desc.strip():
        out.append("description is missing")
    elif len(desc) > 1024:
        out.append(f"description is {len(desc)} characters (the limit is 1024)")
    extra = sorted(str(k) for k in set(fm) - SPEC_FIELDS)
    if extra:
        out.append("fields the specification does not define: " + ", ".join(extra))
    if line_count >= 500:
        out.append(f"SKILL.md has {line_count} lines (keep it under 500)")
    return out


def _tool_tokens(value) -> list[str]:
    """Split an allowed-tools value on commas and spaces that are not inside parentheses."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    tokens, depth, cur = [], 0, ""
    for ch in str(value or ""):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ", \t\n" and depth == 0:
            if cur.strip():
                tokens.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        tokens.append(cur.strip())
    return tokens


# ── Risk scan ───────────────────────────────────────────────────────────────────

def scan_text(rel: str, text: str, is_script: bool) -> list[dict]:
    findings, in_code = [], False
    is_md = rel.lower().endswith(".md")
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if is_md and _FENCE.match(line):
            in_code = not in_code
            continue
        if n == 1 and line.startswith(_BOM):
            line = line[1:]
        if _HIDDEN.search(line):
            findings.append(_finding("high", "hidden-characters",
                                     "Contains invisible or direction-changing characters, a known way to hide instructions.", rel, n))
        code_context = is_script or in_code or not is_md
        for code, severity, message, rx, where in _PATTERNS:
            if where == "code" and not code_context:
                continue
            if rx.search(line):
                snippet = "" if code == "secrets-access" else line.strip()[:120]
                findings.append(_finding(severity, code, message, rel, n, snippet))
    return findings


def scan_skill(skill_dir: Path, fm: dict, files: list[dict]) -> list[dict]:
    findings = []
    for f in files:
        suffix = Path(f["path"]).suffix.lower()
        if suffix not in TEXT_SUFFIXES or f["size"] > MAX_SCAN_BYTES:
            continue
        try:
            text = (skill_dir / f["path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings += scan_text(f["path"], text, is_script=suffix in EXEC_SUFFIXES)
    scripts = [f["path"] for f in files if Path(f["path"]).suffix.lower() in EXEC_SUFFIXES]
    if scripts:
        findings.append(_finding("medium", "bundles-code", f"Bundles {len(scripts)} program file(s) that can run on this machine: "
                                 + ", ".join(scripts[:5]) + (" ..." if len(scripts) > 5 else "") + ". Read them before trusting the skill."))
    for tok in _tool_tokens(fm.get("allowed-tools")):
        if tok in ("Bash", "Bash(*)", "Bash(:*)", "Bash(* *)", "PowerShell", "PowerShell(*)"):
            findings.append(_finding("medium", "unrestricted-shell", f"Asks for unrestricted shell access ({tok}), not a named list of commands.", "SKILL.md"))
    # Keep the report readable: the same warning at most MAX_FINDINGS_PER_CODE times, worst first.
    seen: dict[str, int] = {}
    kept = []
    for f in sorted(findings, key=lambda x: (SEVERITY_ORDER[x["severity"]], x["file"], x["line"])):
        seen[f["code"]] = seen.get(f["code"], 0) + 1
        if seen[f["code"]] <= MAX_FINDINGS_PER_CODE:
            kept.append(f)
    return kept


def verdict(findings: list[dict]) -> str:
    if any(f["severity"] == "high" for f in findings):
        return "risky"
    if any(f["severity"] == "medium" for f in findings):
        return "review"
    return "ok"


# ── Inventory ───────────────────────────────────────────────────────────────────

def inspect_skill(skill_dir: Path, root: dict) -> dict:
    files, notes = walk_files(skill_dir)
    md_path = skill_dir / "SKILL.md"
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    fm, body, fmt_problems = parse_skill_md(text)
    problems = fmt_problems + (spec_problems(skill_dir.name, fm, body, len(text.splitlines())) if not fmt_problems else [])
    findings = scan_skill(skill_dir, fm, files)
    fp = fingerprint(files)
    desc = fm.get("description")
    return {
        "id": skill_id(skill_dir),
        "name": str(fm.get("name") or skill_dir.name),
        "folder": skill_dir.name,
        "description": desc if isinstance(desc, str) else "",
        "license": str(fm.get("license") or ""),
        "allowed_tools": _tool_tokens(fm.get("allowed-tools")),
        "kind": root["kind"],
        "source": _source_label(root, skill_dir),
        "location": home_display(skill_dir),
        "fingerprint": fp,
        "fingerprint_short": fp[:12],
        "file_count": len(files),
        "size_bytes": sum(f["size"] for f in files if isinstance(f["size"], int)),
        "files": files,
        "notes": notes,
        "spec_problems": problems,
        "findings": findings,
        "verdict": verdict(findings),
    }


def inventory(extra_roots: str = "", roots: Optional[list[dict]] = None) -> tuple[list[dict], list[dict]]:
    """(skills, roots). Never raises for one unreadable skill: it is left out and the rest are returned."""
    roots = roots if roots is not None else default_roots(extra_roots)
    skills, seen, info = [], set(), []
    for root in roots:
        count = 0
        for d in _find_skill_dirs(root):
            if len(skills) >= MAX_SKILLS:
                break
            if not _within(d, root["path"]) or str(d.resolve()) in seen:
                continue
            seen.add(str(d.resolve()))
            try:
                skills.append(inspect_skill(d, root))
                count += 1
            except Exception:
                continue
        info.append({"kind": root["kind"], "location": home_display(root["path"]), "exists": root["path"].is_dir(), "count": count})
    rank = {"risky": 0, "review": 1, "ok": 2}
    skills.sort(key=lambda s: (rank.get(s["verdict"], 2), s["name"].lower(), s["location"]))
    return skills, info


def locate(sid: str, extra_roots: str = "", roots: Optional[list[dict]] = None) -> Optional[tuple[dict, Path]]:
    """Find one skill by its id and inspect it again now. The id comes from the caller but a path never does: it is matched against
    the folders this module discovers itself, so it cannot be used to read anything else."""
    roots = roots if roots is not None else default_roots(extra_roots)
    for root in roots:
        for d in _find_skill_dirs(root):
            if _within(d, root["path"]) and skill_id(d) == sid:
                return inspect_skill(d, root), d
    return None


def read_skill_md(skill_dir: Path) -> tuple[str, bool]:
    """(the SKILL.md text, was it cut short). Shown to the owner so they can read the whole skill before trusting it."""
    try:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return "", False
    return text[:SKILL_MD_PREVIEW_CHARS], len(text) > SKILL_MD_PREVIEW_CHARS


def apply_approvals(skills: list[dict], approvals: dict[str, dict]) -> None:
    """Add status: approved (same content as when approved), changed (edited since approved) or unreviewed."""
    for s in skills:
        a = approvals.get(s["id"])
        if not a:
            s.update(status="unreviewed", approved_at=None, approved_by=None, approved_note="")
        else:
            s.update(status="approved" if a["fingerprint"] == s["fingerprint"] else "changed",
                     approved_at=a["approved_at"], approved_by=a["approved_by"], approved_note=a.get("note") or "")
