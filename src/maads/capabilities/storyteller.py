"""Storyteller capabilities — report evidence and final report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.deltas import StateDelta
from maads.reports.final_report import (
    build_story_spec_from_bundle,
    write_final_report,
)
from maads.state import CrispDMState


def _bundle_present(state: CrispDMState) -> bool:
    cm = state.md.chosen_model
    return bool(cm and cm.evaluation_bundle)


def _extract_story_spec(data: dict[str, Any], state: CrispDMState) -> dict[str, Any]:
    spec = data.get("story_spec")
    if isinstance(spec, dict) and spec.get("storytelling_summary"):
        return spec
    su = (data or {}).get("state_updates") or {}
    dep = su.get("dep") or {}
    if isinstance(dep.get("story_spec"), dict):
        return dep["story_spec"]
    return build_story_spec_from_bundle(state)


def apply_response(
    data: dict,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path,
) -> StateDelta:
    """Map storyteller JSON into shared state and artifacts."""
    from maads.output_contracts import validate_agent_output

    if substep == "6.2":
        if not _bundle_present(state):
            return StateDelta(
                notes="Storyteller 6.2: chosen_model.evaluation_bundle missing",
                failed=True,
            )
        schema_errors = validate_agent_output("storyteller", data, substep=substep)
        if schema_errors and not (data or {}).get("story_spec"):
            state.append_log(
                "storyteller",
                f"6.2 schema warnings: {schema_errors[0]}; using bundle fallback",
                level="warn",
            )
        spec = _extract_story_spec(data or {}, state)
        spec_path = artifact_dir / "story_spec.json"
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        state.dep.story_spec_path = str(spec_path.resolve())
        bundle = state.md.chosen_model.evaluation_bundle  # type: ignore[union-attr]
        if bundle and bundle.figures:
            state.dep.figures_dir = str((artifact_dir / "figures").resolve())
        return StateDelta(
            ["dep.story_spec_path", "dep.figures_dir"],
            notes=(data or {}).get("summary", "Story spec written"),
        )

    if substep == "6.3":
        if not state.dep.story_spec_path:
            return StateDelta(notes="Storyteller 6.3: story_spec_path missing", failed=True)
        spec = json.loads(Path(state.dep.story_spec_path).read_text(encoding="utf-8"))
        report_path = write_final_report(state, spec, artifact_dir)
        state.dep.final_report_path = str(report_path.resolve())
        return StateDelta(["dep.final_report_path"], notes="Final report rendered")

    return StateDelta(notes=f"Storyteller no-op for {substep}")


def generate_report_evidence(
    state: CrispDMState,
    artifact_dir: Path,
    data: dict | None = None,
) -> StateDelta:
    """6.2 entry: write story spec from LLM response or bundle fallback."""
    return apply_response(data or {}, state, "6.2", artifact_dir)


def render_final_report_step(
    state: CrispDMState,
    artifact_dir: Path,
) -> StateDelta:
    """6.3 entry: deterministic markdown render."""
    return apply_response({}, state, "6.3", artifact_dir)
