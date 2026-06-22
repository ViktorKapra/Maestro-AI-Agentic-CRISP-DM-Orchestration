"""Entry point for the CRISP-DM pipeline.

Mirrors the CrewAI project layout (`crew_starter/main.py`):
    1. Build a flat `inputs` dict for agent/task YAML interpolation.
    2. Kick off the controller (`Orchestrator.run()` — our equivalent of
       `SomeCrew().crew().kickoff(inputs=inputs)`).
    3. Persist run artefacts and print a summary.

Run via the CLI:
    python -m maads run --case titanic
"""
from __future__ import annotations

import json
from pathlib import Path

from maads.config import CaseConfig
from maads.orchestrator import Orchestrator
from maads.state import CrispDMState


def kickoff_inputs(config: CaseConfig) -> dict[str, str]:
    """Flat inputs dict for CrewAI `{placeholder}` substitution in YAML."""
    return {
        "case_id": config.case_id,
        "kaggle_competition": config.kaggle_competition,
        "problem_statement": config.problem_statement,
        "problem_type": config.problem_type,
        "target_column": config.target_column,
        "id_column": config.id_column,
        "evaluation_metric": config.evaluation_metric,
        "success_metric": config.success_criterion.metric,
        "success_threshold": str(config.success_criterion.threshold),
    }


def run(*, config: CaseConfig, artifact_dir: Path) -> CrispDMState:
    """Run the agentic CRISP-DM pipeline on a case."""
    run_dir = artifact_dir / config.case_id
    run_dir.mkdir(parents=True, exist_ok=True)

    inputs = kickoff_inputs(config)
    (run_dir / "kickoff_inputs.json").write_text(
        json.dumps(inputs, indent=2), encoding="utf-8"
    )

    state = CrispDMState.from_config(config)
    final_state = Orchestrator(state, run_dir, inputs=inputs).run()

    state_path = run_dir / "final_state.json"
    state_path.write_text(final_state.model_dump_json(indent=2), encoding="utf-8")
    _print_summary(final_state, state_path)
    return final_state


def _print_summary(state: CrispDMState, state_path: Path) -> None:
    print("\n" + "=" * 60)
    print("RUN COMPLETE")
    print("=" * 60)
    print(f"Case:   {state.case_id}")
    print(f"Phase:  {state.phase.name} (substep {state.substep})")
    if state.halted:
        print(f"Status: halted — {state.halt_reason}")
    else:
        print("Status: finished")
    if state.dep.submission_path:
        print(f"Submission: {state.dep.submission_path}")
    if state.token_spend:
        total = sum(state.token_spend.values())
        print(f"Tokens: {total} total ({state.token_spend})")
    print(f"State:  {state_path}")
