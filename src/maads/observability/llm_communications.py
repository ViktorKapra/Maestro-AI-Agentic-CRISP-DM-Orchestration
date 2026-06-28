"""Agent–LLM communication capture for human review and optimizer agents."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

_PREVIEW_MAX = 2000


def llm_io_mode() -> str:
    """Return ``full``, ``preview``, or ``off`` for MAADS_TRACE_LLM_IO."""
    mode = os.getenv("MAADS_TRACE_LLM_IO", "full").lower()
    if mode in {"0", "false", "no", "off"}:
        return "off"
    if mode == "preview":
        return "preview"
    return "full"


def _truncate_text(text: str, mode: str) -> tuple[str, int | None]:
    """Return (stored_text, original_len_if_truncated)."""
    if mode == "off":
        return "", len(text)
    if mode == "preview" and len(text) > _PREVIEW_MAX:
        return text[:_PREVIEW_MAX] + "…", len(text)
    return text, None


def serialize_messages(messages: Any, mode: str | None = None) -> list[dict[str, Any]] | str | None:
    """Normalize CrewAI messages to JSON-safe form with optional truncation."""
    mode = mode or llm_io_mode()
    if messages is None:
        return None
    if isinstance(messages, str):
        text, orig_len = _truncate_text(messages, mode)
        if orig_len is not None:
            return {"_truncated": True, "len": orig_len, "text": text}
        return text
    if isinstance(messages, list):
        out: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, dict):
                item = dict(msg)
                content = item.get("content")
                if isinstance(content, str):
                    text, orig_len = _truncate_text(content, mode)
                    item["content"] = text
                    if orig_len is not None:
                        item["content_len"] = orig_len
                out.append(item)
            else:
                out.append({"role": "unknown", "content": str(msg)})
        return out
    return str(messages)


def serialize_response(response: Any, mode: str | None = None) -> str | dict[str, Any]:
    """Normalize CrewAI response to a string or dict."""
    mode = mode or llm_io_mode()
    if response is None:
        return ""
    if isinstance(response, dict):
        if mode == "off":
            return {"_omitted": True, "keys": list(response.keys())}
        text = json.dumps(response, default=str, ensure_ascii=False)
        stored, orig_len = _truncate_text(text, mode)
        if orig_len is not None:
            return {"_truncated": True, "len": orig_len, "text": stored}
        return response
    text = str(response)
    stored, orig_len = _truncate_text(text, mode)
    if orig_len is not None:
        return {"_truncated": True, "len": orig_len, "text": stored}
    return stored


class LLMCommunicationRecord(BaseModel):
    id: str
    call_id: str | None = None
    trace_event_ids: dict[str, str] = Field(default_factory=dict)
    run_id: str = ""
    case_id: str | None = None
    substep: str = ""
    agent_name: str = ""
    role: str | None = None
    model: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float | None = None
    tokens: dict[str, int | None] = Field(default_factory=dict)
    maads: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    parent_comm_id: str | None = None
    closed: bool = False


class LLMCommunicationRegistry:
    """Thread-safe registry of agent–LLM turns for sidecar export."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0
        self._records: list[LLMCommunicationRecord] = []
        self._open: dict[str, LLMCommunicationRecord] = {}
        self._pending_by_agent: dict[tuple[str, str], str] = {}
        self._by_call_id: dict[str, str] = {}
        self._exported_ids: set[str] = set()

    def reset(self) -> None:
        with self._lock:
            self._counter = 0
            self._records = []
            self._open = {}
            self._pending_by_agent = {}
            self._by_call_id = {}
            self._exported_ids = set()

    def _next_id(self) -> str:
        self._counter += 1
        return f"comm_{self._counter:04d}"

    def open_record_ids(self) -> list[str]:
        with self._lock:
            return [cid for cid, rec in self._open.items() if not rec.closed]

    def open_record(
        self,
        *,
        run_id: str,
        case_id: str | None,
        substep: str,
        agent_name: str,
        role: str | None = None,
        model: str | None = None,
        maads: dict[str, Any] | None = None,
        trace_event_id: str | None = None,
        parent_comm_id: str | None = None,
    ) -> str:
        mode = llm_io_mode()
        maads_data = dict(maads or {})
        if mode == "off":
            for key in ("task_description", "instruction", "state_view", "schema_hint"):
                if key in maads_data and isinstance(maads_data[key], str):
                    maads_data[f"{key}_len"] = len(maads_data[key])
                    del maads_data[key]
        elif mode == "preview":
            for key in ("task_description", "instruction", "state_view", "schema_hint"):
                if key in maads_data and isinstance(maads_data[key], str):
                    text, orig_len = _truncate_text(maads_data[key], mode)
                    maads_data[key] = text
                    if orig_len is not None:
                        maads_data[f"{key}_len"] = orig_len

        comm_id = self._next_id()
        record = LLMCommunicationRecord(
            id=comm_id,
            run_id=run_id,
            case_id=case_id,
            substep=substep,
            agent_name=agent_name,
            role=role,
            model=model,
            maads=maads_data,
            parent_comm_id=parent_comm_id,
        )
        if trace_event_id:
            record.trace_event_ids["crew.start"] = trace_event_id

        with self._lock:
            self._open[comm_id] = record
            self._pending_by_agent[(substep, agent_name)] = comm_id
            self._records.append(record)
        return comm_id

    def _resolve_comm_id(
        self,
        *,
        call_id: str | None = None,
        agent_role: str | None = None,
        task_id: str | None = None,
    ) -> str | None:
        with self._lock:
            if call_id and call_id in self._by_call_id:
                return self._by_call_id[call_id]
            if agent_role:
                from maads.observability.agent_labels import maads_id_for_role

                agent_name = maads_id_for_role(agent_role)
                if agent_name:
                    for key, comm_id in reversed(list(self._pending_by_agent.items())):
                        if key[1] == agent_name and comm_id in self._open:
                            if call_id:
                                self._by_call_id[call_id] = comm_id
                            return comm_id
            if task_id:
                for comm_id, rec in reversed(self._records):
                    if not rec.closed and rec.trace_event_ids.get("task_id") == task_id:
                        if call_id:
                            self._by_call_id[call_id] = comm_id
                        return comm_id
            open_ids = [cid for cid, rec in self._open.items() if not rec.closed]
            if len(open_ids) == 1:
                comm_id = open_ids[0]
                if call_id:
                    self._by_call_id[call_id] = comm_id
                return comm_id
        return None

    def enrich_start(
        self,
        *,
        call_id: str | None = None,
        agent_role: str | None = None,
        task_id: str | None = None,
        model: str | None = None,
        messages: Any = None,
        trace_event_id: str | None = None,
    ) -> str | None:
        comm_id = self._resolve_comm_id(
            call_id=call_id, agent_role=agent_role, task_id=task_id
        )
        if comm_id is None:
            return None

        mode = llm_io_mode()
        with self._lock:
            record = self._open.get(comm_id)
            if record is None:
                return None
            if call_id:
                record.call_id = call_id
                self._by_call_id[call_id] = comm_id
            if model:
                record.model = model
            if agent_role and not record.role:
                record.role = agent_role
            if task_id:
                record.trace_event_ids["task_id"] = task_id
            if trace_event_id:
                record.trace_event_ids["llm.start"] = trace_event_id
            if messages is not None and mode != "off":
                record.provider["messages"] = serialize_messages(messages, mode)
        return comm_id

    def enrich_end(
        self,
        *,
        call_id: str | None = None,
        agent_role: str | None = None,
        response: Any = None,
        usage: dict[str, Any] | None = None,
        finish_reason: str | None = None,
        trace_event_id: str | None = None,
        duration_ms: float | None = None,
    ) -> str | None:
        comm_id = None
        if call_id:
            with self._lock:
                comm_id = self._by_call_id.get(call_id)
        if comm_id is None:
            comm_id = self._resolve_comm_id(call_id=call_id, agent_role=agent_role)

        if comm_id is None:
            return None

        mode = llm_io_mode()
        with self._lock:
            record = self._open.get(comm_id) or next(
                (r for r in self._records if r.id == comm_id), None
            )
            if record is None:
                return None
            if trace_event_id:
                record.trace_event_ids["llm.end"] = trace_event_id
            if duration_ms is not None:
                record.duration_ms = duration_ms
            if finish_reason:
                record.provider["finish_reason"] = finish_reason
            if response is not None and mode != "off":
                record.provider["raw_response"] = serialize_response(response, mode)
            if usage:
                record.tokens = {
                    "prompt": usage.get("prompt_tokens"),
                    "completion": usage.get("completion_tokens"),
                    "total": usage.get("total_tokens"),
                }
        return comm_id

    def close_record(
        self,
        comm_id: str,
        *,
        raw_response: str | None = None,
        parsed_json: dict[str, Any] | None = None,
        parse_ok: bool = False,
        json_valid: bool | None = None,
        schema_ok: bool | None = None,
        schema_errors: list[str] | None = None,
        repair: dict[str, Any] | None = None,
        response_shape: str | None = None,
        tokens: dict[str, int | None] | None = None,
        error: str | None = None,
        trace_event_id: str | None = None,
        duration_ms: float | None = None,
    ) -> LLMCommunicationRecord | None:
        mode = llm_io_mode()
        with self._lock:
            record = self._open.pop(comm_id, None)
            if record is None:
                record = next((r for r in self._records if r.id == comm_id), None)
            if record is None:
                return None

            record.closed = True
            if trace_event_id:
                record.trace_event_ids["crew.end"] = trace_event_id
            if duration_ms is not None:
                record.duration_ms = duration_ms
            if tokens:
                for k, v in tokens.items():
                    if v is not None:
                        record.tokens[k] = v

            outcome: dict[str, Any] = {"parse_ok": parse_ok}
            if json_valid is not None:
                outcome["json_valid"] = json_valid
            if schema_ok is not None:
                outcome["schema_ok"] = schema_ok
            if schema_errors:
                outcome["schema_errors"] = schema_errors
            if repair:
                outcome["repair"] = repair
            if response_shape:
                outcome["response_shape"] = response_shape
            if error:
                outcome["error"] = error
            if mode != "off":
                if raw_response is not None:
                    stored, orig_len = _truncate_text(raw_response, mode)
                    outcome["raw_response"] = stored
                    if orig_len is not None:
                        outcome["raw_response_len"] = orig_len
                if parsed_json is not None:
                    outcome["parsed_json"] = parsed_json
            else:
                if raw_response is not None:
                    outcome["raw_response_len"] = len(raw_response)
            record.outcome = outcome

            key = (record.substep, record.agent_name)
            if self._pending_by_agent.get(key) == comm_id:
                del self._pending_by_agent[key]
            if record.call_id and record.call_id in self._by_call_id:
                if self._by_call_id[record.call_id] == comm_id:
                    del self._by_call_id[record.call_id]
        self._try_incremental_export(record)
        return record

    def _try_incremental_export(self, record: LLMCommunicationRecord) -> None:
        from maads.artifact_config import trace_incremental
        from maads.observability import context as ctx

        if not trace_incremental():
            return
        out = ctx.export_dir.get()
        if out is None or record.id in self._exported_ids:
            return
        from maads.observability.communication_exporter import append_communication_record

        append_communication_record(self, record, out)

    def mark_exported(self, comm_id: str) -> None:
        with self._lock:
            self._exported_ids.add(comm_id)

    def get_record(self, comm_id: str) -> LLMCommunicationRecord | None:
        with self._lock:
            for rec in self._records:
                if rec.id == comm_id:
                    return rec.model_copy(deep=True)
        return None

    def all_records(self) -> list[LLMCommunicationRecord]:
        with self._lock:
            return [r.model_copy(deep=True) for r in self._records]

    def preview_sizes(self, comm_id: str) -> dict[str, int]:
        """Char counts for trace annotations."""
        rec = self.get_record(comm_id)
        if rec is None:
            return {}
        sizes: dict[str, int] = {}
        desc = rec.maads.get("task_description") or rec.maads.get("task_description_len")
        if isinstance(desc, str):
            sizes["prompt_chars"] = len(desc)
        elif isinstance(desc, int):
            sizes["prompt_chars"] = desc
        resp = rec.outcome.get("raw_response") or rec.provider.get("raw_response")
        if isinstance(resp, str):
            sizes["response_chars"] = len(resp)
        elif isinstance(resp, dict) and "len" in resp:
            sizes["response_chars"] = int(resp["len"])
        elif rec.outcome.get("raw_response_len"):
            sizes["response_chars"] = int(rec.outcome["raw_response_len"])
        return sizes


def build_communications_summary(records: list[LLMCommunicationRecord]) -> dict[str, Any]:
    by_agent: dict[str, dict[str, Any]] = {}
    by_model: dict[str, int] = {}
    total_tokens = 0
    parse_failures = 0
    durations: list[float] = []

    for rec in records:
        agent = rec.agent_name or "unknown"
        entry = by_agent.setdefault(
            agent,
            {
                "turns": 0,
                "total_tokens": 0,
                "parse_failures": 0,
                "avg_duration_ms": 0.0,
                "prompt_chars": 0,
                "response_chars": 0,
            },
        )
        entry["turns"] += 1
        tok = rec.tokens.get("total")
        if tok:
            entry["total_tokens"] += tok
            total_tokens += tok
        if not rec.outcome.get("parse_ok", True) and rec.outcome:
            entry["parse_failures"] += 1
            parse_failures += 1
        if rec.duration_ms is not None:
            durations.append(rec.duration_ms)
            entry["avg_duration_ms"] = (
                entry["avg_duration_ms"] * (entry["turns"] - 1) + rec.duration_ms
            ) / entry["turns"]
        desc = rec.maads.get("task_description") or ""
        if isinstance(desc, str):
            entry["prompt_chars"] += len(desc)
        elif rec.maads.get("task_description_len"):
            entry["prompt_chars"] += int(rec.maads["task_description_len"])
        raw = rec.outcome.get("raw_response") or rec.provider.get("raw_response")
        if isinstance(raw, str):
            entry["response_chars"] += len(raw)
        elif isinstance(raw, dict) and raw.get("len"):
            entry["response_chars"] += int(raw["len"])
        elif rec.outcome.get("raw_response_len"):
            entry["response_chars"] += int(rec.outcome["raw_response_len"])

        model = rec.model or "unknown"
        by_model[model] = by_model.get(model, 0) + 1

    return {
        "turn_count": len(records),
        "total_tokens": total_tokens,
        "parse_failures": parse_failures,
        "avg_duration_ms": sum(durations) / len(durations) if durations else None,
        "by_agent": by_agent,
        "by_model": by_model,
    }


def record_for_export(rec: LLMCommunicationRecord) -> dict[str, Any]:
    """Serialize a comm record without duplicating raw_response in provider/outcome."""
    data = rec.model_dump(mode="json")
    provider = dict(data.get("provider") or {})
    outcome = dict(data.get("outcome") or {})
    prov_resp = provider.get("raw_response")
    out_resp = outcome.get("raw_response")
    if prov_resp is not None and out_resp is not None:
        if str(prov_resp) == str(out_resp):
            del provider["raw_response"]
            outcome["response_ref"] = "provider.raw_response"
    data["provider"] = provider
    data["outcome"] = outcome
    return data


_registry: LLMCommunicationRegistry | None = None


def get_communication_registry() -> LLMCommunicationRegistry:
    global _registry
    if _registry is None:
        _registry = LLMCommunicationRegistry()
    return _registry


def reset_communication_registry() -> LLMCommunicationRegistry:
    global _registry
    _registry = LLMCommunicationRegistry()
    return _registry
