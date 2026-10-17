"""Pydantic models for Agent Registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from core.models import default_model, resolve_model


class AgentDefinition(BaseModel):
    id: str
    name: str
    display_name: str
    description: str = ""
    category: str = "general"
    system_prompt: str
    model: str = Field(default_factory=default_model)
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list[str] = Field(default_factory=list)
    namespace_lock: Optional[str] = None  # restrict to one namespace
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    version: str = "1.0.0"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("model", mode="before")
    @classmethod
    def upgrade_legacy_model(cls, v) -> str:
        return resolve_model(v)

    @field_validator("tools", "tags", mode="before")
    @classmethod
    def parse_json_list(cls, v) -> list:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    @field_validator("enabled", mode="before")
    @classmethod
    def parse_bool(cls, v) -> bool:
        if isinstance(v, int):
            return bool(v)
        return v


class AgentRun(BaseModel):
    id: str
    agent_id: str
    session_id: Optional[str] = None
    namespace: str = "global"
    input: dict = Field(default_factory=dict)
    output: Optional[dict] = None
    status: str = "pending"  # pending | running | done | failed | cancelled
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    triggered_by: str = "user"
    workflow_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("input", "output", mode="before")
    @classmethod
    def parse_json_dict(cls, v) -> Optional[dict]:
        if v is None:
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {"raw": v}
        return v


class AgentRunCreate(BaseModel):
    agent_id: str
    namespace: str = "global"
    prompt: str
    context: dict = Field(default_factory=dict)
    session_id: Optional[str] = None
    triggered_by: str = "user"
    workflow_run_id: Optional[str] = None
    save_output: bool = True


class AgentDispatchRequest(BaseModel):
    prompt: str
    namespace: str = "global"
    context: dict = Field(default_factory=dict)
    session_id: Optional[str] = None
    save_output: bool = True
    triggered_by: str = "user"
    workflow_run_id: Optional[str] = None
