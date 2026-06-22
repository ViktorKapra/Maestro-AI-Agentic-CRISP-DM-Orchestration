"""CLI entry point: `python -m maads ...`

Subcommands:
    data download --case <name>         Download a bundled demonstration dataset.
    data download --competition <slug>  Download any Kaggle competition.
    run --case <name>                   Run the CrewAI-backed CRISP-DM pipeline.
    run --config <path>                 Run from an explicit case config YAML.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from maads.config import load_case_config
from maads.data_utils import download_case_data, download_kaggle_competition
from maads.run import run


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

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
    parser.error("unreachable")
    return 2  # pragma: no cover


def cmd_run(args: argparse.Namespace) -> int:
    """Resolve the case config and delegate to ``maads.run.run``."""
    config_path = args.config if args.config else Path(args.config_dir) / f"{args.case}.yaml"

    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1

    config = load_case_config(config_path)
    state = run(config=config, artifact_dir=Path(args.artifact_dir))
    return 1 if state.halted else 0


def cmd_data_download(args: argparse.Namespace) -> int:
    if args.case:
        download_case_data(args.case,
                           data_dir=Path(args.out_dir) if args.out_dir else None)
    else:
        out = Path(args.out_dir) if args.out_dir else Path("data") / args.competition
        download_kaggle_competition(args.competition, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
