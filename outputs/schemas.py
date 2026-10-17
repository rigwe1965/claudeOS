"""Output Manager schemas."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

OUTPUT_TYPES = ("report", "draft", "analysis", "code", "note", "archive")
OUTPUT_FORMATS = ("markdown", "text", "json", "html")


class OutputSave(BaseModel):
    namespace: str = "global"
    title: str
    content: str
    output_type: str = "report"
    format: str = "markdown"
    tags: list[str] = Field(default_factory=list)
    agent_run_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    project_id: Optional[str] = None
    summary: str = ""


class Output(OutputSave):
    id: str
    file_path: str = ""
    size_bytes: int = 0
    created_at: str = ""
    updated_at: str = ""


class OutputSearchResult(BaseModel):
    id: str
    namespace: str
    title: str
    summary: str
    output_type: str
    format: str
    tags: list[str]
    size_bytes: int
    created_at: str
    score: float = 0.0
