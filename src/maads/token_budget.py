"""Central token budget guards for run-wide and per-agent LLM spend."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from maads.state import CrispDMState

HALT_REASON = "token budget exceeded"


class TokenBudgetExceeded(RuntimeError):
    """Raised when a run-wide or per-agent token cap is reached."""


def _parse_int(name: str, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def _agent_caps_map() -> dict[str, int]:
    raw = os.getenv("MAX_TOKENS_PER_AGENT", "").strip()
    if not raw:
        return {}
    caps: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        agent, _, limit = part.partition(":")
        agent = agent.strip()
        try:
            caps[agent] = int(limit.strip())
        except ValueError:
            continue
    return caps


def run_cap() -> int | None:
    return _parse_int("MAX_TOKENS_PER_RUN")


def clear_caches() -> None:
    """Reset cached env parsing (for tests)."""
    _agent_caps_map.cache_clear()


def agent_cap(agent: str) -> int | None:
    return _agent_caps_map().get(agent)


def soft_limit_pct() -> float:
    return _parse_float("TOKEN_BUDGET_SOFT_PCT", 90.0)


def code_retries(*, soft: bool = False) -> int:
    if soft:
        return 1
    return _parse_int("MAX_CODE_RETRIES", 3) or 3


def debug_retries() -> int:
    return _parse_int("MAX_DEBUG_RETRIES", 3) or 3


def total_spent(state: CrispDMState) -> int:
    return sum(state.token_spend.values())


def agent_spent(state: CrispDMState, agent: str) -> int:
    return state.token_spend.get(agent, 0)


def soft_limit_reached(state: CrispDMState) -> bool:
    cap = run_cap()
    if cap is None or cap <= 0:
        return False
    threshold = cap * soft_limit_pct() / 100.0
    return total_spent(state) >= threshold


def over_budget(state: CrispDMState) -> bool:
    cap = run_cap()
    if cap is None:
        return False
    return total_spent(state) >= cap


def agent_over_budget(state: CrispDMState, agent: str) -> bool:
    cap = agent_cap(agent)
    if cap is None:
        return False
    return agent_spent(state, agent) >= cap


def repairs_allowed(state: CrispDMState) -> bool:
    if over_budget(state):
        return False
    return not soft_limit_reached(state)


def budget_status(state: CrispDMState) -> dict[str, Any]:
    cap = run_cap()
    spent = total_spent(state)
    remaining = max(cap - spent, 0) if cap is not None else None
    pct = round(100.0 * spent / cap, 1) if cap else None
    soft = soft_limit_reached(state)
    agent_caps = _agent_caps_map()
    per_agent: dict[str, dict[str, Any]] = {}
    for agent, tokens in sorted(state.token_spend.items()):
        acap = agent_caps.get(agent)
        per_agent[agent] = {
            "spent": tokens,
            "cap": acap,
            "remaining": max(acap - tokens, 0) if acap is not None else None,
            "over": agent_over_budget(state, agent),
        }
    return {
        "cap": cap,
        "spent": spent,
        "remaining": remaining,
        "pct": pct,
        "soft_limit": soft,
        "soft_limit_pct": soft_limit_pct(),
        "halted_by_budget": state.halt_reason == HALT_REASON,
        "per_agent": per_agent,
    }


def _budget_message(*, agent: str | None = None, run: bool = False) -> str:
    cap = run_cap()
    if run and cap is not None:
        return f"Run-wide token cap of {cap} reached. Halting to avoid runaway cost."
    if agent:
        acap = agent_cap(agent)
        if acap is not None:
            return (
                f"Per-agent token cap of {acap} reached for {agent}. "
                "Halting to avoid runaway cost."
            )
    return "Token budget exceeded."


def assert_can_spend(state: CrispDMState, agent: str) -> None:
    """Pre-call guard: raise if run-wide or per-agent cap is already reached."""
    if over_budget(state):
        raise TokenBudgetExceeded(_budget_message(run=True))
    if agent_over_budget(state, agent):
        raise TokenBudgetExceeded(_budget_message(agent=agent))


def check_after_spend(state: CrispDMState, agent: str) -> None:
    """Post-call guard: same checks after token accounting."""
    assert_can_spend(state, agent)


def build_spending_summary(state: CrispDMState) -> dict[str, Any]:
    """Structured spending summary for reports and dashboards."""
    status = budget_status(state)
    spend = dict(state.token_spend)
    total = status["spent"] or 0
    by_agent: list[dict[str, Any]] = []
    top_agent: str | None = None
    top_tokens = 0
    for agent, tokens in sorted(spend.items(), key=lambda kv: kv[1], reverse=True):
        pct_of_total = round(100.0 * tokens / total, 1) if total else 0.0
        acap = agent_cap(agent)
        pct_of_cap = round(100.0 * tokens / acap, 1) if acap else None
        if tokens > top_tokens:
            top_agent = agent
            top_tokens = tokens
        by_agent.append({
            "agent": agent,
            "tokens": tokens,
            "pct_of_total": pct_of_total,
            "cap": acap,
            "pct_of_cap": pct_of_cap,
        })
    cap = status["cap"]
    pct_of_run_cap = status["pct"]
    return {
        "total": total,
        "by_agent": by_agent,
        "by_provider": dict(state.token_spend_by_provider),
        "top_agent": top_agent,
        "top_agent_tokens": top_tokens,
        "top_agent_pct_of_total": round(100.0 * top_tokens / total, 1) if total else 0.0,
        "run_cap": cap,
        "pct_of_run_cap": pct_of_run_cap,
        "budget": status,
    }


def format_spending_lines(summary: dict[str, Any]) -> list[str]:
    """Markdown bullet lines for token spending in run reports."""
    lines: list[str] = []
    total = summary.get("total", 0)
    cap = summary.get("run_cap")
    pct_cap = summary.get("pct_of_run_cap")
    if cap is not None:
        lines.append(
            f"- **Total tokens:** {total:,} / {cap:,} "
            f"({pct_cap}% of run cap)"
        )
    else:
        lines.append(f"- **Total tokens:** {total:,}")
    top = summary.get("top_agent")
    if top:
        lines.append(
            f"- **Top agent:** {top} "
            f"({summary.get('top_agent_tokens', 0):,} tokens, "
            f"{summary.get('top_agent_pct_of_total', 0)}% of total)"
        )
    by_agent = summary.get("by_agent") or []
    if by_agent:
        lines.append("- **By agent:**")
        for row in by_agent:
            cap_note = ""
            if row.get("cap") is not None:
                cap_note = f", cap {row['cap']:,}"
                if row.get("pct_of_cap") is not None:
                    cap_note += f" ({row['pct_of_cap']}% of agent cap)"
            lines.append(
                f"  - {row['agent']}: {row['tokens']:,} "
                f"({row.get('pct_of_total', 0)}% of total{cap_note})"
            )
    budget = summary.get("budget") or {}
    if budget.get("soft_limit"):
        lines.append(
            f"- **Soft limit:** active at {budget.get('soft_limit_pct')}% of run cap"
        )
    if budget.get("halted_by_budget"):
        lines.append("- **Halted by token budget:** yes")
    return lines
