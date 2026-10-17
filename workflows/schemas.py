"""Workflow Engine schemas."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkflowStep(BaseModel):
    step_id: str
    agent_name: str
    prompt_template: str
    save_output: bool = True
    context: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    on_failure: str = "stop"   # "stop" (default) | "continue" — continue skips step and proceeds


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    display_name: str
    description: str = ""
    trigger_type: str = "manual"       # manual | schedule | event
    trigger_spec: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStep] = Field(default_factory=list)
    namespace: str = "global"
    enabled: bool = True


class WorkflowRunCreate(BaseModel):
    workflow_name: str
    namespace: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = "user"


class WorkflowStepLog(BaseModel):
    step_id: str
    agent_name: str
    status: str        # pending | running | done | failed | skipped
    run_id: Optional[str] = None
    output_preview: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
