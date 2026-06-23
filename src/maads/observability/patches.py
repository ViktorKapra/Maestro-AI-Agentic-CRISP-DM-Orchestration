"""Import-time monkey-patches for orchestrator, crew, and tools."""
from __future__ import annotations

import functools
import hashlib
import time
from typing import Any

from maads.observability import context as ctx
from maads.observability.collector import get_collector
from maads.observability.python_tracer import PythonTracer
from maads.state import SUBSTEP_NAMES, SUBSTEP_OWNER


def _subprocess_key(code: str) -> str:
    return hashlib.md5(code.encode(), usedforsecurity=False).hexdigest()[:8]


def _flush_trace_snapshot() -> None:
    """Write the current trace to disk without closing the run."""
    out = ctx.export_dir.get()
    if out is None:
        from maads.run_status import flush_status

        flush_status()
        return
    coll = get_collector()
    if coll.run is None:
        from maads.run_status import flush_status

        flush_status()
        return
    from maads.observability.exporter import write_trace_artifacts
    from maads.run_status import flush_status

    write_trace_artifacts(coll, out, finalize=False)
    flush_status()


def apply_patches() -> None:
    _patch_orchestrator()
    _patch_crew()
    _patch_tools()


def _patch_orchestrator() -> None:
    import maads.orchestrator as orch_mod

    Orchestrator = orch_mod.Orchestrator
    if getattr(Orchestrator.run, "_maads_traced", False):
        return

    orig_run = Orchestrator.run
    orig_dispatch = Orchestrator._dispatch
    orig_advance = Orchestrator._advance_substep
    orig_loop = Orchestrator._fire_loop
    orig_halt = Orchestrator._force_halt

    @functools.wraps(orig_run)
    def traced_run(self, *args: Any, **kwargs: Any):
        coll = get_collector()
        tracer = PythonTracer(coll)
        coll.emit_start(
            "run.start",
            span_key="orchestrator.run",
            name="Orchestrator.run",
            source="maads.orchestrator",
            attributes={
                "case_id": self.state.case_id,
                "phase": int(self.state.phase),
                "substep": self.state.substep,
            },
        )
        ctx.trace_active.set(True)
        ctx.python_trace_active.set(True)
        tracer.install()
        try:
            return orig_run(self, *args, **kwargs)
        except Exception as exc:
            coll.emit(
                "exception",
                name=type(exc).__name__,
                source="maads.orchestrator",
                attributes={"message": str(exc)},
            )
            raise
        finally:
            tracer.uninstall()
            ctx.python_trace_active.set(False)
            ctx.trace_active.set(False)
            coll.emit_end(
                "run.end",
                span_key="orchestrator.run",
                attributes={"halt_reason": self.state.halt_reason, "halted": self.state.halted},
            )

    @functools.wraps(orig_dispatch)
    def traced_dispatch(self, substep: str) -> None:
        coll = get_collector()
        owner = SUBSTEP_OWNER.get(substep, "?")
        ctx.current_substep.set(substep)
        ctx.current_maads_agent.set(owner)
        if not self.state.substep_prereqs_satisfied(substep):
            coll.emit(
                "branch",
                name=f"skip {substep}",
                source="maads.orchestrator",
                attributes={
                    "substep": substep,
                    "reason": "prereqs not satisfied",
                    "owner": owner,
                },
            )
        coll.emit_start(
            "substep.dispatch",
            span_key=f"substep.{substep}",
            name=SUBSTEP_NAMES.get(substep, substep),
            source="maads.orchestrator",
            attributes={
                "substep": substep,
                "substep_name": SUBSTEP_NAMES.get(substep, ""),
                "owner": owner,
                "phase": int(self.state.phase),
            },
        )
        from maads.progress import on_substep_start

        on_substep_start(substep, int(self.state.phase), owner)
        coll.emit(
            "agent.activate",
            name=owner,
            source="maads.orchestrator",
            attributes={"substep": substep, "agent": owner},
        )
        try:
            orig_dispatch(self, substep)
        except Exception as exc:
            coll.emit(
                "exception",
                name=type(exc).__name__,
                source="maads.orchestrator",
                attributes={"substep": substep, "message": str(exc)},
            )
            raise
        finally:
            coll.emit(
                "agent.complete",
                name=owner,
                source="maads.orchestrator",
                attributes={"substep": substep, "agent": owner},
            )
            coll.emit_end(
                "substep.end",
                span_key=f"substep.{substep}",
                attributes={"substep": substep},
            )
            from maads.progress import on_substep_done

            on_substep_done(substep)
            _flush_trace_snapshot()

    @functools.wraps(orig_advance)
    def traced_advance(self) -> bool:
        prev_phase = int(self.state.phase)
        prev_substep = self.state.substep
        done = orig_advance(self)
        if int(self.state.phase) != prev_phase or self.state.substep != prev_substep:
            get_collector().emit(
                "phase.transition",
                name=f"phase {prev_phase} -> {int(self.state.phase)}",
                source="maads.orchestrator",
                attributes={
                    "from_phase": prev_phase,
                    "to_phase": int(self.state.phase),
                    "from_substep": prev_substep,
                    "to_substep": self.state.substep,
                },
            )
        return done

    @functools.wraps(orig_loop)
    def traced_loop(self, target_phase: int, reason: str, label: str = "?") -> None:
        from maads.progress import on_loop

        on_loop(label, target_phase, reason)
        get_collector().emit(
            "loop",
            name=f"loop {label}",
            source="maads.orchestrator",
            attributes={
                "label": label,
                "from_phase": int(self.state.phase),
                "to_phase": target_phase,
                "reason": reason,
            },
        )
        orig_loop(self, target_phase, reason, label)

    @functools.wraps(orig_halt)
    def traced_halt(self, reason: str) -> None:
        get_collector().emit(
            "run.end",
            name="force_halt",
            source="maads.orchestrator",
            attributes={"halt_reason": reason, "forced": True},
        )
        orig_halt(self, reason)

    traced_run._maads_traced = True  # type: ignore[attr-defined]
    Orchestrator.run = traced_run  # type: ignore[method-assign]
    Orchestrator._dispatch = traced_dispatch  # type: ignore[method-assign]
    Orchestrator._advance_substep = traced_advance  # type: ignore[method-assign]
    Orchestrator._fire_loop = traced_loop  # type: ignore[method-assign]
    Orchestrator._force_halt = traced_halt  # type: ignore[method-assign]


def _patch_crew() -> None:
    import maads.crew as crew_mod

    if getattr(crew_mod.run_json_task, "_maads_traced", False):
        return

    orig = crew_mod.run_json_task
    from maads.crew import build_task_description, pop_last_kickoff_output
    from maads.observability.llm_communications import get_communication_registry
    from maads.prompts import AGENT_PROMPTS

    @functools.wraps(orig)
    def traced_run_json_task(
        agent_name: str,
        instruction: str,
        state: Any,
        schema_hint: str = "",
    ):
        coll = get_collector()
        registry = get_communication_registry()
        substep = state.substep
        ctx.current_maads_agent.set(agent_name)
        ctx.current_substep.set(substep)

        description, state_view, agent = build_task_description(
            agent_name, instruction, state, schema_hint
        )
        model_name = getattr(getattr(agent, "llm", None), "model", None)
        role = AGENT_PROMPTS.get(agent_name, {}).get("role")

        run = coll.run
        run_id = run.run_id if run else ""
        case_id = run.case_id if run else None

        crew_evt_id = coll.emit_start(
            "crew.start",
            span_key=f"crew.{substep}.{agent_name}",
            name=f"Crew kickoff ({agent_name})",
            source="maads.crew",
            attributes={
                "agent_name": agent_name,
                "substep": substep,
                "instruction_preview": instruction[:200],
            },
        )

        comm_id = registry.open_record(
            run_id=run_id,
            case_id=case_id,
            substep=substep,
            agent_name=agent_name,
            role=role,
            model=str(model_name) if model_name else None,
            maads={
                "task_description": description,
                "instruction": instruction,
                "schema_hint": schema_hint,
                "state_view": state_view,
                "state_view_bytes": len(state_view.encode("utf-8")),
            },
            trace_event_id=crew_evt_id,
        )

        crew_attrs = {
            "agent_name": agent_name,
            "substep": substep,
            "communication_id": comm_id,
            "prompt_preview": description[:200],
        }
        with coll._lock:
            if coll.run is not None:
                for e in reversed(coll.run.events):
                    if e.id == crew_evt_id:
                        e.attributes.update(crew_attrs)
                        break

        from maads.progress import on_crew_end, on_crew_start

        on_crew_start(agent_name, substep)
        _flush_trace_snapshot()
        t0 = time.monotonic()
        try:
            result = orig(agent_name, instruction, state, schema_hint)
            raw_output, total_tokens = pop_last_kickoff_output()
            duration_ms = round((time.monotonic() - t0) * 1000, 2)
            sizes = registry.preview_sizes(comm_id)

            registry.close_record(
                comm_id,
                raw_response=raw_output,
                parsed_json=result,
                parse_ok=result is not None,
                tokens={"total": total_tokens},
                duration_ms=duration_ms,
            )

            end_attrs = {
                "agent_name": agent_name,
                "substep": substep,
                "parsed": result is not None,
                "communication_id": comm_id,
                **sizes,
            }
            coll.emit_end(
                "crew.end",
                span_key=f"crew.{substep}.{agent_name}",
                attributes=end_attrs,
            )
            on_crew_end(agent_name, parsed=result is not None)
            _flush_trace_snapshot()
            return result
        except Exception as exc:
            duration_ms = round((time.monotonic() - t0) * 1000, 2)
            raw_output, total_tokens = pop_last_kickoff_output()
            registry.close_record(
                comm_id,
                raw_response=raw_output,
                parsed_json=None,
                parse_ok=False,
                tokens={"total": total_tokens},
                error=str(exc),
                duration_ms=duration_ms,
            )
            coll.emit(
                "exception",
                name=type(exc).__name__,
                source="maads.crew",
                attributes={"agent_name": agent_name, "message": str(exc), "communication_id": comm_id},
            )
            coll.emit_end(
                "crew.end",
                span_key=f"crew.{substep}.{agent_name}",
                attributes={
                    "agent_name": agent_name,
                    "error": str(exc),
                    "communication_id": comm_id,
                },
            )
            on_crew_end(agent_name, parsed=False)
            _flush_trace_snapshot()
            raise

    traced_run_json_task._maads_traced = True  # type: ignore[attr-defined]
    crew_mod.run_json_task = traced_run_json_task

    # agents.py does `from maads.crew import run_json_task` at import time, so
    # replacing crew_mod.run_json_task alone does not affect agent LLM calls.
    import maads.agents as agents_mod

    if agents_mod.run_json_task is orig:
        agents_mod.run_json_task = traced_run_json_task


def _patch_tools() -> None:
    import maads.tools as tools_mod

    PythonExec = tools_mod.PythonExec
    FileIO = tools_mod.FileIO

    if not getattr(PythonExec.run, "_maads_traced", False):
        orig_pyexec = PythonExec.run

        @functools.wraps(orig_pyexec)
        def traced_pyexec_run(self, code: str, extra_env: dict | None = None):
            coll = get_collector()
            key = f"pyexec.{_subprocess_key(code)}"
            coll.emit_start(
                "python.subprocess",
                span_key=key,
                name="PythonExec.run",
                source="maads.tools",
                attributes={
                    "code_bytes": len(code),
                    "substep": ctx.current_substep.get(),
                    "agent": ctx.current_maads_agent.get(),
                },
            )
            from maads.progress import on_code_end, on_code_start

            on_code_start()
            try:
                result = orig_pyexec(self, code, extra_env)
                coll.emit_end(
                    "python.subprocess",
                    span_key=key,
                    attributes={
                        "ok": result.ok,
                        "return_code": result.return_code,
                        "timed_out": result.timed_out,
                        "stdout_len": len(result.stdout),
                        "stderr_len": len(result.stderr),
                    },
                )
                on_code_end(ok=result.ok)
                return result
            except Exception as exc:
                coll.emit(
                    "exception",
                    name=type(exc).__name__,
                    source="maads.tools",
                    attributes={"message": str(exc)},
                )
                coll.emit_end("python.subprocess", span_key=key, attributes={"error": str(exc)})
                on_code_end(ok=False)
                raise

        traced_pyexec_run._maads_traced = True  # type: ignore[attr-defined]
        PythonExec.run = traced_pyexec_run  # type: ignore[method-assign]

    if not getattr(FileIO.write_text, "_maads_traced", False):
        orig_write_text = FileIO.write_text
        orig_write_json = FileIO.write_json

        @functools.wraps(orig_write_text)
        def traced_write_text(self, name: str, content: str):
            get_collector().emit(
                "tool.end",
                name="FileIO.write_text",
                source="maads.tools",
                attributes={"path": name, "bytes": len(content)},
            )
            return orig_write_text(self, name, content)

        @functools.wraps(orig_write_json)
        def traced_write_json(self, name: str, data: Any):
            get_collector().emit(
                "tool.end",
                name="FileIO.write_json",
                source="maads.tools",
                attributes={"path": name},
            )
            return orig_write_json(self, name, data)

        traced_write_text._maads_traced = True  # type: ignore[attr-defined]
        traced_write_json._maads_traced = True  # type: ignore[attr-defined]
        FileIO.write_text = traced_write_text  # type: ignore[method-assign]
        FileIO.write_json = traced_write_json  # type: ignore[method-assign]
