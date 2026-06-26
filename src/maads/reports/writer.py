"""Write all post-run reports and seal the manifest."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from maads.artifact_config import reports_enabled
from maads.artifact_paths import RunPaths, seal_manifest, update_runs_index
from maads.observability.llm_communications import (
    LLMCommunicationRecord,
    build_communications_summary,
)
from maads.observability.schema import TraceRun
from maads.outcome import ml_run_succeeded, workflow_complete
from maads.reports.case_report import build_case_report, render_case_report_md
from maads.reports.execution_analysis import (
    build_execution_analysis,
    render_execution_analysis_md,
)
from maads.reports.improvement_bundle import build_improvement_bundle
from maads.reports.postmortem import build_postmortem
from maads.state import CrispDMState


def write_run_reports(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    trace: TraceRun | None = None,
    communications: list[LLMCommunicationRecord] | None = None,
    case_root: Path | None = None,
    force: bool = False,
) -> None:
    if not reports_enabled():
        return
    paths = RunPaths(artifact_dir)
    paths.reports.mkdir(parents=True, exist_ok=True)
    stamp_path = paths.reports / ".generated"
    if stamp_path.is_file() and not force:
        return

    comm_summary = build_communications_summary(communications or [])
    postmortem = build_postmortem(state, paths, trace=trace, comm_summary=comm_summary)
    (paths.reports / "postmortem.json").write_text(
        json.dumps(postmortem, indent=2, default=str), encoding="utf-8",
    )

    case_report = build_case_report(state)
    (paths.reports / "case_report.json").write_text(
        json.dumps(case_report, indent=2, default=str), encoding="utf-8",
    )
    (paths.reports / "case_report.md").write_text(
        render_case_report_md(case_report), encoding="utf-8",
    )

    analysis = build_execution_analysis(
        state, paths, trace=trace, comm_summary=comm_summary,
    )
    (paths.reports / "execution_analysis.json").write_text(
        json.dumps(analysis, indent=2, default=str), encoding="utf-8",
    )
    (paths.reports / "execution_analysis.md").write_text(
        render_execution_analysis_md(analysis), encoding="utf-8",
    )

    bundle = build_improvement_bundle(
        state, paths, communications or [], case_root=case_root,
    )
    (paths.reports / "improvement_bundle.json").write_text(
        json.dumps(bundle, indent=2, default=str), encoding="utf-8",
    )

    ended_at = datetime.now(timezone.utc).isoformat()
    seal_manifest(
        paths,
        ended_at=ended_at,
        workflow_complete=workflow_complete(state),
        ml_success=ml_run_succeeded(state),
        halt_reason=state.halt_reason,
    )
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    manifest["reports_generated_at"] = ended_at
    paths.manifest.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    stamp_path.write_text(ended_at, encoding="utf-8")

    if case_root is not None:
        update_runs_index(case_root, run_id=paths.run_dir.name, manifest=manifest)
