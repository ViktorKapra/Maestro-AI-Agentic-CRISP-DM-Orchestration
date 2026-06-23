"""Trace event schema for Runtime Execution Intelligence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    id: str
    parent_id: str | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ts_mono_ms: float = 0.0
    duration_ms: float | None = None
    type: str
    source: str = "maads"
    name: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    thread_id: int | None = None


class TraceRun(BaseModel):
    run_id: str
    case_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    events: list[TraceEvent] = Field(default_factory=list)
