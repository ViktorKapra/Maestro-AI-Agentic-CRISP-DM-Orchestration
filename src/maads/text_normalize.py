"""Markdown and passage normalization helpers (no prompt/RAG dependencies)."""
from __future__ import annotations

import json
import re
from typing import Any

_HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
_LEADING_HEADING_LINE = re.compile(r"^#{1,6}\s+.+$")
_PASSAGE_SOURCE_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)


def strip_markdown_headers(text: str, *, keep_first: bool = True) -> str:
    """Remove markdown heading lines from chunk text."""
    text = text.strip()
    if not text:
        return ""
    if keep_first:
        lines = text.splitlines()
        if lines and _LEADING_HEADING_LINE.match(lines[0].strip()):
            lines = lines[1:]
        return "\n".join(lines).strip()
    return _HEADING_RE.sub("", text).strip()


def normalize_passage_text(text: str) -> str:
    """Collapse whitespace and strip headings for dedup hashing."""
    cleaned = strip_markdown_headers(text, keep_first=False)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def dedupe_passages(passages: list[str]) -> list[str]:
    """Drop passages whose normalized body already appeared (preserve order)."""
    seen: set[str] = set()
    out: list[str] = []
    for passage in passages:
        m = _PASSAGE_SOURCE_RE.match(passage)
        body = m.group(2) if m else passage
        key = normalize_passage_text(body)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(passage)
    return out


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def dedupe_nested_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return overlay with keys removed when they duplicate equal values in base."""
    result: dict[str, Any] = {}
    for key, value in overlay.items():
        if key in base and _json_key(base[key]) == _json_key(value):
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested = dedupe_nested_dict(base[key], value)
            if nested:
                result[key] = nested
        else:
            result[key] = value
    return result
