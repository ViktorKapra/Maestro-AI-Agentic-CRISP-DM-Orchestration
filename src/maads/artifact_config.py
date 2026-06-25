"""Environment flags for artifact collection and exports."""
from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


def write_renders() -> bool:
    """Write regenerable trace markdown/mermaid on flush (default off)."""
    return _env_bool("MAADS_WRITE_RENDERS", False)


def trace_incremental() -> bool:
    """Append collected JSONL instead of only rewriting derived blobs."""
    return _env_bool("MAADS_TRACE_INCREMENTAL", True)


def trace_otel_enabled() -> bool:
    """Mirror OpenTelemetry spans into the MAADS trace (default on)."""
    return _env_bool("MAADS_TRACE_OTEL", True)


def live_summary_enabled() -> bool:
    return _env_bool("MAADS_LIVE_SUMMARY", True)


def reports_enabled() -> bool:
    return _env_bool("MAADS_REPORTS", True)


def report_excerpt_chars() -> int:
    return int(os.getenv("MAADS_REPORT_EXCERPT_CHARS", "2000"))
