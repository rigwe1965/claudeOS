"""Agent Registry — load YAML definitions, CRUD into SQLite."""
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
from agents.schemas import AgentDefinition

logger = logging.getLogger("claudeos.agents.registry")

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def _row_to_agent(row) -> AgentDefinition:
    return AgentDefinition(**dict(row))


def load_from_yaml(yaml_path: Path) -> Optional[AgentDefinition]:
    """Parse a YAML agent definition file."""
    if yaml is None:
        raise ImportError("pyyaml required: pip install pyyaml")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not data.get("id"):
        data["id"] = new_id()
    return AgentDefinition(**data)


def upsert(agent: AgentDefinition) -> AgentDefinition:
    """Insert or update an agent definition in the DB."""
    now = utcnow_str()
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM agents WHERE name = ?", (agent.name,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE agents SET
                   display_name=?, description=?, category=?, system_prompt=?,
                   model=?, max_tokens=?, temperature=?, tools=?, namespace_lock=?,
                   tags=?, enabled=?, version=?, updated_at=?
                   WHERE name=?""",
                (
                    agent.display_name, agent.description, agent.category,
                    agent.system_prompt, agent.model, agent.max_tokens,
                    agent.temperature, json.dumps(agent.tools),
                    agent.namespace_lock, json.dumps(agent.tags),
                    int(agent.enabled), agent.version, now, agent.name,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO agents
                   (id, name, display_name, description, category, system_prompt,
                    model, max_tokens, temperature, tools, namespace_lock, tags,
                    enabled, version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent.id, agent.name, agent.display_name, agent.description,
                    agent.category, agent.system_prompt, agent.model,
                    agent.max_tokens, agent.temperature, json.dumps(agent.tools),
                    agent.namespace_lock, json.dumps(agent.tags),
                    int(agent.enabled), agent.version, now, now,
                ),
            )
    return get_by_name(agent.name)


def get_by_id(agent_id: str) -> Optional[AgentDefinition]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return _row_to_agent(row) if row else None


def get_by_name(name: str) -> Optional[AgentDefinition]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    return _row_to_agent(row) if row else None


def list_agents(category: Optional[str] = None, enabled_only: bool = True) -> list[AgentDefinition]:
    conditions = []
    params: list = []
    if enabled_only:
        conditions.append("enabled = 1")
    if category:
        conditions.append("category = ?")
        params.append(category)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        rows = conn.execute(f"SELECT * FROM agents {where} ORDER BY category, name", params).fetchall()
    return [_row_to_agent(r) for r in rows]


def delete(agent_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    return cursor.rowcount > 0


def seed_from_directory(definitions_dir: Path = DEFINITIONS_DIR) -> int:
    """Load all YAML definitions and upsert into DB. Returns count loaded."""
    if yaml is None:
        raise ImportError("pyyaml required: pip install pyyaml")

    yaml_files = list(definitions_dir.glob("*.yaml")) + list(definitions_dir.glob("*.yml"))
    if not yaml_files:
        logger.warning("No agent YAML files found in %s", definitions_dir)
        return 0

    count = 0
    for yf in sorted(yaml_files):
        try:
            agent = load_from_yaml(yf)
            upsert(agent)
            logger.info("Seeded agent: %s", agent.name)
            count += 1
        except Exception as e:
            logger.error("Failed to seed %s: %s", yf.name, e)

    return count
