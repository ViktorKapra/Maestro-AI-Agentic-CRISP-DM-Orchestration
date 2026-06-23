"""CLI entry point: `python -m maads ...`

Subcommands:
    data download --case <name>         Download a bundled demonstration dataset.
    data download --competition <slug>  Download any Kaggle competition.
    run --case <name>                   Run the CrewAI-backed CRISP-DM pipeline.
    run --config <path>                 Run from an explicit case config YAML.
    dashboard                           Web UI for live trace monitoring.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from maads.config import load_case_config, kickoff_inputs
from maads.data_utils import download_case_data, download_kaggle_competition
from maads.observability import auto_enable, begin_run, end_run
from maads.orchestrator import Orchestrator
from maads.paths import resolve_path
from maads.progress import start_run as start_progress, stop_run as stop_progress
from maads.run_status import bind_run, flush_status
from maads.shutdown import apply_interrupt_to_state, install_sigint_handler, shutdown_requested
from maads.state import CrispDMState


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    auto_enable()

    parser = argparse.ArgumentParser(prog="maads")
    sub = parser.add_subparsers(dest="cmd")

    # ── run ────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run the agentic pipeline on a dataset.")
    g_run = p_run.add_mutually_exclusive_group(required=True)
    g_run.add_argument("--case", help="Shorthand: load configs/<case>.yaml.")
    g_run.add_argument("--config", type=Path,
                       help="Path to a case config YAML.")
    p_run.add_argument("--config-dir", default="configs",
                       help="Directory holding bundled <case>.yaml files. "
                            "Used only when --case is given.")
    p_run.add_argument("--artifact-dir", default="artifacts",
                       help="Where to write per-run artefacts. A subdirectory "
                            "named after case_id is created.")
    p_run.add_argument("--quiet", "-q", action="store_true",
                       help="Disable live progress output (also MAADS_PROGRESS=0).")

    # ── data ───────────────────────────────────────────────────────────
    p_data = sub.add_parser("data", help="Data utilities.")
    sub_data = p_data.add_subparsers(dest="data_cmd")

    p_dl = sub_data.add_parser("download",
                               help="Download a Kaggle competition's data.")
    g_dl = p_dl.add_mutually_exclusive_group(required=True)
    g_dl.add_argument("--case", help="Shorthand for bundled configs.")
    g_dl.add_argument("--competition",
                      help="Any Kaggle competition slug.")
    p_dl.add_argument("--out-dir", default=None,
                      help="Where to put the data (default: data/<name>/).")

    # ── dashboard ──────────────────────────────────────────────────────
    p_dash = sub.add_parser("dashboard", help="Launch the trace monitoring web UI.")
    p_dash.add_argument("--case", default=None,
                        help="Open a specific case (e.g. titanic).")
    p_dash.add_argument("--artifact-dir", default="artifacts",
                        help="Root directory containing per-case artifact folders.")
    p_dash.add_argument("--port", type=int, default=8765,
                        help="HTTP port (default: 8765).")
    p_dash.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default: 127.0.0.1).")
    p_dash.add_argument("--no-open", action="store_true",
                        help="Do not open a browser tab automatically.")
    p_dash.add_argument("--static-dir", type=Path, default=None,
                        help="Serve built frontend from this directory "
                             "(default: dashboard/dist if it exists).")

    args = parser.parse_args(argv)

    if args.cmd is None:
        parser.print_help()
        return 0
    if args.cmd == "data" and args.data_cmd is None:
        p_data.print_help()
        return 0

    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "data" and args.data_cmd == "download":
        return cmd_data_download(args)
    if args.cmd == "dashboard":
        return cmd_dashboard(args)
    parser.error("unreachable")
    return 2  # pragma: no cover


def cmd_run(args: argparse.Namespace) -> int:
    """Resolve the case config and run the orchestrator."""
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = resolve_path(config_path)
    else:
        config_path = resolve_path(args.config_dir) / f"{args.case}.yaml"

    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    config = load_case_config(config_path)
    state = CrispDMState.from_config(config)

    artifact_dir = resolve_path(args.artifact_dir) / config.case_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    inputs = kickoff_inputs(config)
    (artifact_dir / "kickoff_inputs.json").write_text(
        json.dumps(inputs, indent=2), encoding="utf-8",
    )

    resolved = artifact_dir.resolve()
    print(f"Artifacts: {resolved}")
    print(f"Live status: {resolved / 'status.json'}  (refresh while running)")
    print(f"Trace:       {resolved / 'trace'}/")

    install_sigint_handler()
    bind_run(artifact_dir, state)
    start_progress(config.case_id, quiet=args.quiet)
    begin_run(config.case_id, artifact_dir)
    halt_reason: str | None = None
    interrupted = False
    try:
        state = Orchestrator(state, artifact_dir).run()
        if shutdown_requested() and not state.halted:
            halt_reason = apply_interrupt_to_state(state)
            interrupted = True
        else:
            halt_reason = state.halt_reason
    except KeyboardInterrupt:
        halt_reason = apply_interrupt_to_state(state)
        interrupted = True
        print("\nForced quit.", file=sys.stderr)
    finally:
        flush_status()
        end_run(artifact_dir)
        stop_progress(halt_reason)

    state_path = artifact_dir / "final_state.json"
    state_path.write_text(state.model_dump_json(indent=2))

    print(f"Halted: {state.halt_reason}")
    print(f"Submission: {state.dep.submission_path}")
    print(f"Token spend: {state.token_spend}")
    print(f"Final state written to {state_path}")
    if interrupted:
        return 130
    return 0 if state.dep.submission_path else 1


def cmd_data_download(args: argparse.Namespace) -> int:
    if args.case:
        download_case_data(args.case,
                           data_dir=Path(args.out_dir) if args.out_dir else None)
    else:
        out = Path(args.out_dir) if args.out_dir else Path("data") / args.competition
        download_kaggle_competition(args.competition, out)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start the trace monitoring dashboard."""
    try:
        from maads.dashboard import run_dashboard
    except ImportError:
        print(
            "ERROR: dashboard dependencies not installed. "
            'Run: pip install -e ".[dashboard]"',
            file=sys.stderr,
        )
        return 1

    artifact_root = resolve_path(args.artifact_dir)
    static_dir = args.static_dir
    if static_dir is None:
        default_static = resolve_path("dashboard") / "dist"
        if default_static.is_dir():
            static_dir = default_static
    elif not static_dir.is_absolute():
        static_dir = resolve_path(static_dir)

    print(f"Artifact root: {artifact_root.resolve()}")
    print(f"Dashboard:     http://{args.host}:{args.port}/")
    if static_dir:
        print(f"Frontend:      {static_dir}")
    else:
        print("Frontend:      not built — use `cd dashboard && npm run dev` for dev UI")

    run_dashboard(
        artifact_dir=artifact_root,
        host=args.host,
        port=args.port,
        static_dir=static_dir,
        open_browser=not args.no_open,
        case_id=args.case,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
