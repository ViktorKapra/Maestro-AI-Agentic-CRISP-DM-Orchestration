"""Human-readable agent–LLM communication transcript."""
from __future__ import annotations

import json
from typing import Any

from maads.observability.llm_communications import LLMCommunicationRecord


def _format_messages(messages: Any) -> str:
    if messages is None:
        return "_No provider messages captured._\n"
    if isinstance(messages, str):
        return messages + "\n"
    if isinstance(messages, dict) and messages.get("_truncated"):
        return f"_(truncated, len={messages.get('len')})_\n\n{messages.get('text', '')}\n"
    if isinstance(messages, list):
        lines: list[str] = []
        for i, msg in enumerate(messages, 1):
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if msg.get("content_len"):
                    lines.append(f"**{i}. {role}** _(len={msg['content_len']})_\n")
                else:
                    lines.append(f"**{i}. {role}**\n")
                lines.append(f"{content}\n")
            else:
                lines.append(f"**{i}.** {msg}\n")
        return "\n".join(lines)
    return str(messages) + "\n"


def _format_response(response: Any) -> str:
    if response is None:
        return "_No raw response captured._\n"
    if isinstance(response, dict):
        if response.get("_truncated"):
            return f"_(truncated, len={response.get('len')})_\n\n{response.get('text', '')}\n"
        if response.get("_omitted"):
            return f"_Omitted (keys: {response.get('keys')})_\n"
        return json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    return str(response) + "\n"


def _format_record(rec: LLMCommunicationRecord) -> str:
    duration = f"{rec.duration_ms / 1000:.1f}s" if rec.duration_ms else "?"
    tokens = rec.tokens.get("total")
    token_str = str(tokens) if tokens is not None else "?"
    header = (
        f"## {rec.id} — {rec.agent_name} @ {rec.substep} "
        f"({rec.model or 'unknown model'}, {duration}, tokens: {token_str})"
    )
    if rec.call_id:
        header += f" · call_id=`{rec.call_id}`"
    sections = [header, ""]

    task_desc = rec.maads.get("task_description")
    if task_desc:
        sections.extend(["### MAADS task (sent to CrewAI Task.description)", "", str(task_desc), ""])
    elif rec.maads.get("task_description_len"):
        sections.extend([
            "### MAADS task (sent to CrewAI Task.description)",
            "",
            f"_Omitted (len={rec.maads['task_description_len']})_",
            "",
        ])

    sections.extend([
        "### Provider messages (CrewAI → model)",
        "",
        _format_messages(rec.provider.get("messages")),
    ])

    raw = rec.outcome.get("raw_response") or rec.provider.get("raw_response")
    sections.extend(["### Response (raw)", "", _format_response(raw)])

    parsed = rec.outcome.get("parsed_json")
    sections.append("### Parsed JSON")
    sections.append("")
    if parsed is not None:
        sections.append(json.dumps(parsed, indent=2, ensure_ascii=False, default=str))
    elif rec.outcome.get("parse_ok") is False:
        sections.append("_JSON parsing failed._")
    else:
        sections.append("_No parsed JSON._")
    sections.append("")
    return "\n".join(sections)


def render_communications(records: list[LLMCommunicationRecord]) -> str:
    lines = [
        "# Agent–LLM Communications",
        "",
        "Full prompt/response transcript for each LLM turn in this run.",
        "",
    ]
    if not records:
        lines.append("_No LLM communications were recorded._")
        return "\n".join(lines) + "\n"

    for rec in records:
        lines.append(_format_record(rec))
    return "\n".join(lines)
