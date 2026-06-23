"""Live CLI progress for CRISP-DM pipeline runs.

Uses Rich (already pulled in by CrewAI) for a stderr progress bar and status
line. Hooks are called from the observability patches around orchestrator,
CrewAI kickoffs, and Python sandbox runs.

Disable with ``--quiet`` or ``MAADS_PROGRESS=0``.
"""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from maads.prompts import AGENT_PROMPTS
from maads.run_status import record_substep_done, set_activity
from maads.state import SUBSTEP_NAMES, SUBSTEPS, Phase

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID

TOTAL_SUBSTEPS = sum(len(v) for v in SUBSTEPS.values())

PHASE_NAMES: dict[int, str] = {
    int(Phase.BUSINESS_UNDERSTANDING): "Business Understanding",
    int(Phase.DATA_UNDERSTANDING): "Data Understanding",
    int(Phase.DATA_PREPARATION): "Data Preparation",
    int(Phase.MODELING): "Modeling",
    int(Phase.EVALUATION): "Evaluation",
    int(Phase.DEPLOYMENT): "Deployment",
}

AGENT_LABELS: dict[str, str] = {
    agent_id: meta["role"] for agent_id, meta in AGENT_PROMPTS.items()
}

_active: RunProgress | None = None


def is_progress_enabled(*, quiet: bool = False) -> bool:
    if quiet:
        return False
    env = os.getenv("MAADS_PROGRESS")
    if env is not None:
        return env.lower() not in {"0", "false", "no", "off"}
    return sys.stderr.isatty()


def start_run(case_id: str, *, quiet: bool = False) -> None:
    """Begin the live progress display for a pipeline run."""
    global _active
    if not is_progress_enabled(quiet=quiet):
        return
    _active = RunProgress(case_id)
    _active.start()


def stop_run(halt_reason: str | None = None) -> None:
    global _active
    if halt_reason:
        prefix = "Interrupted" if "interrupt" in halt_reason.lower() else "Complete"
        set_activity(f"{prefix} · {halt_reason}")
    elif _active is None:
        set_activity("Complete")
    if _active is None:
        return
    _active.stop(halt_reason)
    _active = None


def on_substep_start(substep: str, phase: int, owner: str) -> None:
    agent = AGENT_LABELS.get(owner, owner)
    name = SUBSTEP_NAMES.get(substep, substep)
    phase_name = PHASE_NAMES.get(phase, f"Phase {phase}")
    set_activity(f"{substep} {name} · {phase_name} · {agent}")
    if _active is None:
        return
    _active.substep_start(substep, phase, owner)


def on_substep_done(substep: str) -> None:
    record_substep_done(substep)
    if _active is None:
        return
    _active.substep_done(substep)


def on_crew_start(agent_name: str, substep: str) -> None:
    agent = AGENT_LABELS.get(agent_name, agent_name)
    set_activity(f"CrewAI · {agent} · substep {substep} · LLM running…")
    if _active is None:
        return
    _active.crew_start(agent_name, substep)


def on_crew_end(agent_name: str, *, parsed: bool | None = None) -> None:
    agent = AGENT_LABELS.get(agent_name, agent_name)
    if parsed is True:
        detail = "JSON parsed"
    elif parsed is False:
        detail = "JSON parse failed"
    else:
        detail = "done"
    set_activity(f"CrewAI · {agent} · {detail}")
    if _active is None:
        return
    _active.crew_end(agent_name, parsed=parsed)


def on_code_start(label: str = "Python sandbox") -> None:
    set_activity(f"{label} · executing…")
    if _active is None:
        return
    _active.code_start(label)


def on_code_end(*, ok: bool = True) -> None:
    set_activity(f"Python sandbox · {'ok' if ok else 'failed'}")
    if _active is None:
        return
    _active.code_end(ok=ok)


def on_loop(label: str, target_phase: int, reason: str) -> None:
    phase_name = PHASE_NAMES.get(target_phase, f"phase {target_phase}")
    short = reason[:60] + ("…" if len(reason) > 60 else "")
    set_activity(f"Loop {label} → {phase_name} · {short}")
    if _active is None:
        return
    _active.loop_back(label, target_phase, reason)


def format_substep_header(substep: str, phase: int) -> str:
    name = SUBSTEP_NAMES.get(substep, substep)
    phase_name = PHASE_NAMES.get(phase, f"Phase {phase}")
    return f"[bold]{substep}[/] {name} · {phase_name}"


class RunProgress:
    """Rich progress bar + activity line for one orchestrator run."""

    def __init__(self, case_id: str) -> None:
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        self._case_id = case_id
        self._console = Console(stderr=True, highlight=False)
        self._progress: Progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=32),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self._console,
            transient=False,
        )
        self._pipeline_task: TaskID | None = None
        self._activity_task: TaskID | None = None
        self._completed = 0
        self._current_substep: str | None = None

    def start(self) -> None:
        self._progress.start()
        self._pipeline_task = self._progress.add_task(
            f"[cyan]{self._case_id}[/] · CRISP-DM pipeline",
            total=TOTAL_SUBSTEPS,
            completed=0,
        )
        self._activity_task = self._progress.add_task(
            "[dim]Starting…[/]",
            total=None,
        )

    def substep_start(self, substep: str, phase: int, owner: str) -> None:
        self._current_substep = substep
        agent = AGENT_LABELS.get(owner, owner)
        header = format_substep_header(substep, phase)
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=f"{header} · [green]{agent}[/]",
            )

    def substep_done(self, substep: str) -> None:
        self._completed += 1
        if self._pipeline_task is not None:
            self._progress.update(
                self._pipeline_task,
                completed=min(self._completed, TOTAL_SUBSTEPS),
            )
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=f"[dim]Finished {substep}[/]",
            )

    def crew_start(self, agent_name: str, substep: str) -> None:
        agent = AGENT_LABELS.get(agent_name, agent_name)
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=(
                    f"[yellow]CrewAI[/] · {agent} · "
                    f"substep {substep} · [bold]LLM running…[/]"
                ),
            )

    def crew_end(self, agent_name: str, *, parsed: bool | None = None) -> None:
        agent = AGENT_LABELS.get(agent_name, agent_name)
        if parsed is True:
            status = "[green]JSON parsed[/]"
        elif parsed is False:
            status = "[red]JSON parse failed[/]"
        else:
            status = "[dim]done[/]"
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=f"[yellow]CrewAI[/] · {agent} · {status}",
            )

    def code_start(self, label: str) -> None:
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=f"[blue]{label}[/] · [bold]executing…[/]",
            )

    def code_end(self, *, ok: bool = True) -> None:
        status = "[green]ok[/]" if ok else "[red]failed[/]"
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=f"[blue]Python sandbox[/] · {status}",
            )

    def loop_back(self, label: str, target_phase: int, reason: str) -> None:
        phase_name = PHASE_NAMES.get(target_phase, f"phase {target_phase}")
        short = reason[:60] + ("…" if len(reason) > 60 else "")
        if self._activity_task is not None:
            self._progress.update(
                self._activity_task,
                description=(
                    f"[magenta]Loop {label}[/] → {phase_name} · [dim]{short}[/]"
                ),
            )

    def stop(self, halt_reason: str | None) -> None:
        if self._pipeline_task is not None:
            self._progress.update(
                self._pipeline_task,
                completed=min(self._completed, TOTAL_SUBSTEPS),
            )
        if self._activity_task is not None:
            reason = halt_reason or "finished"
            label = (
                "[bold yellow]Interrupted[/]"
                if halt_reason and "interrupt" in halt_reason.lower()
                else "[bold green]Complete[/]"
            )
            self._progress.update(
                self._activity_task,
                description=f"{label} · {reason}",
            )
        self._progress.stop()
        self._console.print()
