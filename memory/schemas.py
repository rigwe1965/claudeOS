"""Pydantic models for the Memory Engine."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


VALID_CATEGORIES = {"fact", "decision", "context", "preference", "reminder", "insight"}

# TTL defaults (days). None = permanent.
CATEGORY_TTL: dict[str, Optional[int]] = {
    "fact": None,
    "decision": None,
    "context": 7,
    "preference": None,
    "reminder": None,   # reminder uses explicit expires_at
    "insight": 30,
}


class MemoryEntry(BaseModel):
    id: str
    namespace: str = "global"
    category: str = "fact"
    key: str
    value: str
    source: str = "user"
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []

    def tags_json(self) -> str:
        return json.dumps(self.tags)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else datetime.now(timezone.utc) > self.expires_at


class MemoryEntryCreate(BaseModel):
    namespace: str = "global"
    category: str = "fact"
    key: str
    value: str
    source: str = "user"
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    expires_at: Optional[datetime] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}")
        return v


class MemoryEntryUpdate(BaseModel):
    value: Optional[str] = None
    tags: Optional[list[str]] = None
    confidence: Optional[float] = None
    expires_at: Optional[datetime] = None


class VectorMeta(BaseModel):
    id: str
    memory_id: str
    chroma_id: str
    model: str = "all-MiniLM-L6-v2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemorySearchRequest(BaseModel):
    query: str
    namespace: Optional[str] = None
    category: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    mode: str = "semantic"  # "semantic" | "text" | "both"
    min_confidence: float = 0.0
