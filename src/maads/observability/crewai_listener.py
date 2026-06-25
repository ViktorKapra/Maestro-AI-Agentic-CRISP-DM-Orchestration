"""CrewAI event bus listener → TraceCollector."""
from __future__ import annotations

from typing import Any

from crewai.events import BaseEventListener
from crewai.events.types.agent_events import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    LiteAgentExecutionCompletedEvent,
    LiteAgentExecutionErrorEvent,
    LiteAgentExecutionStartedEvent,
)
from crewai.events.types.crew_events import (
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
)
from crewai.events.types.flow_events import (
    FlowFinishedEvent,
    FlowStartedEvent,
    MethodExecutionFailedEvent,
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
)
from crewai.events.types.llm_events import (
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
)
from crewai.events.types.memory_events import (
    MemoryQueryCompletedEvent,
    MemoryQueryFailedEvent,
    MemoryQueryStartedEvent,
    MemoryRetrievalCompletedEvent,
    MemoryRetrievalStartedEvent,
)
from crewai.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

from maads.observability import context as ctx
from maads.observability.agent_labels import agent_role_from_crew, maads_id_for_role
from maads.observability.collector import get_collector
from maads.observability.llm_communications import get_communication_registry


def _agent_role(agent: Any) -> str:
    return getattr(agent, "role", None) or str(agent)


def _safe_attrs(event: Any, **extra: Any) -> dict[str, Any]:
    attrs = dict(extra)
    ctx_maads = ctx.current_maads_agent.get()
    crew_role = extra.get("role") or agent_role_from_crew(event) or getattr(event, "agent_role", None)
    crew_maads = maads_id_for_role(str(crew_role)) if crew_role else None
    # Executing CrewAI agent wins over orchestrator substep owner (e.g. Developer DEBUG).
    agent_id = crew_maads or ctx_maads
    attrs["substep"] = ctx.current_substep.get()
    attrs["maads_agent"] = agent_id
    if agent_id:
        attrs["agent_name"] = agent_id
    if crew_role:
        attrs["role"] = crew_role
    if hasattr(event, "type"):
        attrs["crewai_type"] = event.type
    call_id = getattr(event, "call_id", None)
    if call_id:
        attrs["call_id"] = call_id
    return attrs


def _span_key(prefix: str, event: Any) -> str:
    call_id = getattr(event, "call_id", None)
    if call_id:
        return f"{prefix}.{call_id}"
    fp = getattr(event, "source_fingerprint", None)
    if fp:
        return f"{prefix}.{fp}"
    task_id = getattr(event, "task_id", None)
    if task_id:
        return f"{prefix}.task.{task_id}"
    return f"{prefix}.{id(event)}"


_active_spans: dict[str, str] = {}


class MaadsCrewAIListener(BaseEventListener):
    """Bridge CrewAI events into the MAADS trace collector."""

    def setup_listeners(self, crewai_event_bus: Any) -> None:
        bus = crewai_event_bus

        @bus.on(CrewKickoffStartedEvent)
        def on_crew_start(_src: Any, event: CrewKickoffStartedEvent) -> None:
            key = _span_key("crewai.kickoff", event)
            get_collector().emit_start(
                "crew.start",
                span_key=key,
                name="CrewKickoffStarted",
                source="crewai",
                attributes=_safe_attrs(event),
            )
            _active_spans[key] = key

        @bus.on(CrewKickoffCompletedEvent)
        def on_crew_end(_src: Any, event: CrewKickoffCompletedEvent) -> None:
            key = _span_key("crewai.kickoff", event)
            get_collector().emit_end(
                "crew.end",
                span_key=key,
                attributes=_safe_attrs(event, total_tokens=getattr(event, "total_tokens", None)),
            )
            _active_spans.pop(key, None)

        @bus.on(CrewKickoffFailedEvent)
        def on_crew_fail(_src: Any, event: CrewKickoffFailedEvent) -> None:
            get_collector().emit(
                "exception",
                name="CrewKickoffFailed",
                source="crewai",
                attributes=_safe_attrs(event, error=str(getattr(event, "error", ""))),
            )

        @bus.on(TaskStartedEvent)
        def on_task_start(_src: Any, event: TaskStartedEvent) -> None:
            desc = str(getattr(getattr(event, "task", None), "description", ""))[:200]
            key = _span_key("crewai.task", event)
            get_collector().emit_start(
                "task.start",
                span_key=key,
                name="TaskStarted",
                source="crewai",
                attributes=_safe_attrs(event, description_preview=desc),
            )

        @bus.on(TaskCompletedEvent)
        def on_task_end(_src: Any, event: TaskCompletedEvent) -> None:
            key = _span_key("crewai.task", event)
            get_collector().emit_end(
                "task.end",
                span_key=key,
                attributes=_safe_attrs(
                    event,
                    output_preview=str(getattr(event, "output", ""))[:200],
                ),
            )

        @bus.on(TaskFailedEvent)
        def on_task_fail(_src: Any, event: TaskFailedEvent) -> None:
            get_collector().emit(
                "exception",
                name="TaskFailed",
                source="crewai",
                attributes=_safe_attrs(event, error=str(getattr(event, "error", ""))),
            )

        @bus.on(AgentExecutionStartedEvent)
        def on_agent_start(_src: Any, event: AgentExecutionStartedEvent) -> None:
            role = _agent_role(event.agent)
            key = _span_key("crewai.agent", event)
            get_collector().emit_start(
                "agent.activate",
                span_key=key,
                name=role,
                source="crewai",
                attributes=_safe_attrs(event, role=role),
            )

        @bus.on(AgentExecutionCompletedEvent)
        def on_agent_end(_src: Any, event: AgentExecutionCompletedEvent) -> None:
            role = _agent_role(event.agent)
            key = _span_key("crewai.agent", event)
            get_collector().emit_end(
                "agent.complete",
                span_key=key,
                attributes=_safe_attrs(
                    event,
                    role=role,
                    output_preview=str(getattr(event, "output", ""))[:200],
                ),
            )

        @bus.on(AgentExecutionErrorEvent)
        def on_agent_err(_src: Any, event: AgentExecutionErrorEvent) -> None:
            get_collector().emit(
                "exception",
                name="AgentExecutionError",
                source="crewai",
                attributes=_safe_attrs(event, error=str(getattr(event, "error", ""))),
            )

        @bus.on(LiteAgentExecutionStartedEvent)
        def on_lite_start(_src: Any, event: LiteAgentExecutionStartedEvent) -> None:
            get_collector().emit_start(
                "agent.activate",
                span_key=f"crewai.lite.{id(event)}",
                name="LiteAgent",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(LiteAgentExecutionCompletedEvent)
        def on_lite_end(_src: Any, event: LiteAgentExecutionCompletedEvent) -> None:
            get_collector().emit_end(
                "agent.complete",
                span_key=f"crewai.lite.{id(event)}",
                attributes=_safe_attrs(event),
            )

        @bus.on(LiteAgentExecutionErrorEvent)
        def on_lite_err(_src: Any, event: LiteAgentExecutionErrorEvent) -> None:
            get_collector().emit(
                "exception",
                name="LiteAgentExecutionError",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(ToolUsageStartedEvent)
        def on_tool_start(_src: Any, event: ToolUsageStartedEvent) -> None:
            tool = getattr(event, "tool_name", None) or str(getattr(event, "tool", "?"))
            get_collector().emit_start(
                "tool.start",
                span_key=f"crewai.tool.{id(event)}",
                name=str(tool),
                source="crewai",
                attributes=_safe_attrs(event, tool=str(tool)),
            )

        @bus.on(ToolUsageFinishedEvent)
        def on_tool_end(_src: Any, event: ToolUsageFinishedEvent) -> None:
            get_collector().emit_end(
                "tool.end",
                span_key=f"crewai.tool.{id(event)}",
                attributes=_safe_attrs(event),
            )

        @bus.on(ToolUsageErrorEvent)
        def on_tool_err(_src: Any, event: ToolUsageErrorEvent) -> None:
            get_collector().emit(
                "exception",
                name="ToolUsageError",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(LLMCallStartedEvent)
        def on_llm_start(_src: Any, event: LLMCallStartedEvent) -> None:
            key = _span_key("crewai.llm", event)
            attrs = _safe_attrs(
                event,
                model=str(getattr(event, "model", "")),
            )
            evt_id = get_collector().emit_start(
                "llm.start",
                span_key=key,
                name="LLMCall",
                source="crewai",
                attributes=attrs,
            )
            comm_id = get_communication_registry().enrich_start(
                call_id=getattr(event, "call_id", None),
                agent_role=getattr(event, "agent_role", None),
                task_id=getattr(event, "task_id", None),
                model=str(getattr(event, "model", "")) or None,
                messages=getattr(event, "messages", None),
                trace_event_id=evt_id,
            )
            if comm_id:
                attrs["communication_id"] = comm_id
                with get_collector()._lock:
                    run = get_collector().run
                    if run is not None:
                        for e in reversed(run.events):
                            if e.id == evt_id:
                                e.attributes["communication_id"] = comm_id
                                break

        @bus.on(LLMCallCompletedEvent)
        def on_llm_end(_src: Any, event: LLMCallCompletedEvent) -> None:
            usage = getattr(event, "usage", None) or getattr(event, "token_usage", None)
            tokens = None
            usage_dict: dict[str, Any] = {}
            if usage is not None:
                if isinstance(usage, dict):
                    usage_dict = usage
                    tokens = usage.get("total_tokens")
                else:
                    tokens = getattr(usage, "total_tokens", None)
                    usage_dict = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", None),
                        "completion_tokens": getattr(usage, "completion_tokens", None),
                        "total_tokens": tokens,
                    }
            key = _span_key("crewai.llm", event)
            attrs = _safe_attrs(event, total_tokens=tokens)
            comm_id = get_communication_registry().enrich_end(
                call_id=getattr(event, "call_id", None),
                agent_role=getattr(event, "agent_role", None),
                response=getattr(event, "response", None),
                usage=usage_dict or None,
                finish_reason=getattr(event, "finish_reason", None),
            )
            if comm_id:
                attrs["communication_id"] = comm_id
                sizes = get_communication_registry().preview_sizes(comm_id)
                attrs.update(sizes)
            evt_id = get_collector().emit_end(
                "llm.end",
                span_key=key,
                attributes=attrs,
            )
            if comm_id and evt_id:
                get_communication_registry().enrich_end(
                    call_id=getattr(event, "call_id", None),
                    trace_event_id=evt_id,
                )

        @bus.on(LLMCallFailedEvent)
        def on_llm_fail(_src: Any, event: LLMCallFailedEvent) -> None:
            get_collector().emit(
                "exception",
                name="LLMCallFailed",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(FlowStartedEvent)
        def on_flow_start(_src: Any, event: FlowStartedEvent) -> None:
            get_collector().emit_start(
                "flow.start",
                span_key=f"crewai.flow.{id(event)}",
                name="FlowStarted",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(FlowFinishedEvent)
        def on_flow_end(_src: Any, event: FlowFinishedEvent) -> None:
            get_collector().emit_end(
                "flow.end",
                span_key=f"crewai.flow.{id(event)}",
                attributes=_safe_attrs(event),
            )

        @bus.on(MethodExecutionStartedEvent)
        def on_method_start(_src: Any, event: MethodExecutionStartedEvent) -> None:
            get_collector().emit_start(
                "flow.start",
                span_key=f"crewai.method.{id(event)}",
                name=str(getattr(event, "method_name", "method")),
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MethodExecutionFinishedEvent)
        def on_method_end(_src: Any, event: MethodExecutionFinishedEvent) -> None:
            get_collector().emit_end(
                "flow.end",
                span_key=f"crewai.method.{id(event)}",
                attributes=_safe_attrs(event),
            )

        @bus.on(MethodExecutionFailedEvent)
        def on_method_fail(_src: Any, event: MethodExecutionFailedEvent) -> None:
            get_collector().emit(
                "exception",
                name="MethodExecutionFailed",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MemoryQueryStartedEvent)
        def on_mem_q_start(_src: Any, event: MemoryQueryStartedEvent) -> None:
            get_collector().emit(
                "tool.start",
                name="MemoryQuery",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MemoryQueryCompletedEvent)
        def on_mem_q_end(_src: Any, event: MemoryQueryCompletedEvent) -> None:
            get_collector().emit(
                "tool.end",
                name="MemoryQuery",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MemoryQueryFailedEvent)
        def on_mem_q_fail(_src: Any, event: MemoryQueryFailedEvent) -> None:
            get_collector().emit(
                "exception",
                name="MemoryQueryFailed",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MemoryRetrievalStartedEvent)
        def on_mem_r_start(_src: Any, event: MemoryRetrievalStartedEvent) -> None:
            get_collector().emit(
                "tool.start",
                name="MemoryRetrieval",
                source="crewai",
                attributes=_safe_attrs(event),
            )

        @bus.on(MemoryRetrievalCompletedEvent)
        def on_mem_r_end(_src: Any, event: MemoryRetrievalCompletedEvent) -> None:
            get_collector().emit(
                "tool.end",
                name="MemoryRetrieval",
                source="crewai",
                attributes=_safe_attrs(event),
            )


_listener_instance: MaadsCrewAIListener | None = None


def register_crewai_listener() -> MaadsCrewAIListener:
    global _listener_instance
    if _listener_instance is None:
        _listener_instance = MaadsCrewAIListener()
    return _listener_instance
