"""Phase 7 — Sync schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TableSyncResult(BaseModel):
    table_name: str
    rows_pushed: int = 0
    rows_failed: int = 0
    error: Optional[str] = None
    duration_ms: int = 0


class SyncResult(BaseModel):
    success: bool
    tables: list[TableSyncResult] = []
    total_pushed: int = 0
    total_failed: int = 0
    duration_ms: int = 0
    started_at: str
    completed_at: str


class SyncStatus(BaseModel):
    configured: bool          # Supabase creds present
    last_sync_at: Optional[str] = None
    table_states: dict        # table_name -> {last_synced_at, rows_pushed, rows_failed}
    auto_sync_enabled: bool = False
    auto_sync_interval_min: int = 15
