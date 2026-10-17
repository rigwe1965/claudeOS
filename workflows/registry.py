"""Workflow Registry — load YAML definitions, CRUD into SQLite."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from core.database import get_db
from core.utils import new_id, utcnow_str
from workflows.schemas import WorkflowDefinition, WorkflowStep

logger = logging.getLogger("claudeos.workflows.registry")

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def _parse_steps(raw: list[dict]) -> list[WorkflowStep]:
    return [WorkflowStep(**s) for s in raw]


def _row_to_definition(row) -> WorkflowDefinition:
    d = dict(row)
    d["trigger_spec"] = json.loads(d.get("trigger_spec") or "{}")
    raw_steps = json.loads(d.get("steps") or "[]")
    d["steps"] = _parse_steps(raw_steps)
    d["enabled"] = bool(d.get("enabled", 1))
    return WorkflowDefinition(**d)


def load_from_yaml(yaml_path: Path) -> WorkflowDefinition:
    if yaml is None:
        raise ImportError("pyyaml required: pip install pyyaml")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not data.get("id"):
        data["id"] = new_id()
    steps_raw = data.get("steps", [])
    data["steps"] = _parse_steps(steps_raw)
    return WorkflowDefinition(**data)


def upsert(wf: WorkflowDefinition) -> WorkflowDefinition:
    now = utcnow_str()
    steps_json = json.dumps([s.model_dump() for s in wf.steps])
    trigger_json = json.dumps(wf.trigger_spec)
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM workflows WHERE name = ?", (wf.name,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE workflows SET
                   display_name=?, description=?, trigger_type=?, trigger_spec=?,
                   steps=?, namespace=?, enabled=?, updated_at=?
                   WHERE name=?""",
                (
                    wf.display_name, wf.description, wf.trigger_type,
                    trigger_json, steps_json, wf.namespace, int(wf.enabled), now, wf.name,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO workflows
                   (id, name, display_name, description, trigger_type, trigger_spec,
                    steps, namespace, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    wf.id, wf.name, wf.display_name, wf.description,
                    wf.trigger_type, trigger_json, steps_json,
                    wf.namespace, int(wf.enabled), now, now,
                ),
            )
    return get_by_name(wf.name)


def get_by_id(workflow_id: str) -> Optional[WorkflowDefinition]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    return _row_to_definition(row) if row else None


def get_by_name(name: str) -> Optional[WorkflowDefinition]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM workflows WHERE name = ?", (name,)).fetchone()
    return _row_to_definition(row) if row else None


def list_workflows(
    trigger_type: Optional[str] = None,
    namespace: Optional[str] = None,
    enabled_only: bool = True,
) -> list[WorkflowDefinition]:
    conditions = []
    params: list = []
    if enabled_only:
        conditions.append("enabled = 1")
    if trigger_type:
        conditions.append("trigger_type = ?")
        params.append(trigger_type)
    if namespace:
        conditions.append("namespace = ?")
        params.append(namespace)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM workflows {where} ORDER BY display_name", params
        ).fetchall()
    return [_row_to_definition(r) for r in rows]


def seed_from_directory(definitions_dir: Path = DEFINITIONS_DIR) -> int:
    if yaml is None:
        raise ImportError("pyyaml required: pip install pyyaml")
    yaml_files = list(definitions_dir.glob("*.yaml")) + list(definitions_dir.glob("*.yml"))
    if not yaml_files:
        logger.warning("No workflow YAML files in %s", definitions_dir)
        return 0
    count = 0
    for yf in sorted(yaml_files):
        try:
            wf = load_from_yaml(yf)
            upsert(wf)
            logger.info("Seeded workflow: %s", wf.name)
            count += 1
        except Exception as e:
            logger.error("Failed to seed %s: %s", yf.name, e)
    return count
