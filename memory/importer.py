"""Import existing .claude/memory/*.md files into the memory engine.

Parses YAML frontmatter + markdown body.
Maps Claude Code memory types → ClaudeOS memory categories:
    user     → preference
    feedback → preference
    project  → fact
    reference → fact
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from memory import engine
from memory.schemas import VALID_CATEGORIES

logger = logging.getLogger("claudeos.memory.importer")

# YAML frontmatter pattern
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

TYPE_TO_CATEGORY = {
    "user": "preference",
    "feedback": "preference",
    "project": "fact",
    "reference": "fact",
    "fact": "fact",
    "decision": "decision",
    "context": "context",
    "insight": "insight",
    "reminder": "reminder",
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (frontmatter_dict, body_text)."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text.strip()

    fm_raw = m.group(1)
    body = text[m.end():].strip()
    fm: dict = {}

    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip().lower()] = v.strip().strip('"').strip("'")

    return fm, body


def _truncate(s: str, max_len: int = 4000) -> str:
    return s[:max_len] if len(s) > max_len else s


def import_file(md_path: Path, namespace: str = "global", dry_run: bool = False) -> int:
    """Import a single .md memory file. Returns number of entries written."""
    if not md_path.exists():
        logger.warning("Memory file not found: %s", md_path)
        return 0

    text = md_path.read_text(encoding="utf-8")

    # Skip MEMORY.md index file
    if md_path.name.upper() == "MEMORY.md":
        return 0

    fm, body = _parse_frontmatter(text)

    # Derive key from filename (strip extension)
    key = md_path.stem.replace("_", ".").replace("-", ".")
    name = fm.get("name", key)
    mem_type = fm.get("type", "fact").lower()
    category = TYPE_TO_CATEGORY.get(mem_type, "fact")
    description = fm.get("description", "")

    # Value = description (if present) + body
    value_parts = []
    if description:
        value_parts.append(description)
    if body:
        value_parts.append(body)
    value = _truncate("\n\n".join(value_parts)) if value_parts else _truncate(name)

    if not value.strip():
        logger.debug("Skipping empty entry: %s", md_path.name)
        return 0

    tags = ["imported", f"source:{md_path.stem}", f"type:{mem_type}"]

    if not dry_run:
        try:
            engine.write(
                namespace=namespace,
                category=category,
                key=f"import.{key}",
                value=value,
                source="import",
                tags=tags,
                confidence=0.9,
            )
        except Exception as e:
            logger.error("Failed to import %s: %s", md_path.name, e)
            return 0

    logger.info("Imported %s → [%s] import.%s", md_path.name, category, key)
    return 1


def import_directory(
    memory_dir: Path,
    namespace: str = "global",
    dry_run: bool = False,
) -> dict[str, int]:
    """Import all *.md files from a directory. Returns {filename: 0|1}."""
    if not memory_dir.exists():
        logger.warning("Memory directory not found: %s", memory_dir)
        return {}

    results: dict[str, int] = {}
    md_files = [f for f in memory_dir.glob("*.md") if f.name.upper() != "MEMORY.MD"]

    logger.info("Found %d memory files in %s", len(md_files), memory_dir)

    for md_path in sorted(md_files):
        count = import_file(md_path, namespace=namespace, dry_run=dry_run)
        results[md_path.name] = count

    total = sum(results.values())
    logger.info("Import complete: %d/%d files written", total, len(md_files))
    return results
