# maads — Multi-Agent Automated Data Science

A five-agent system that walks Kaggle-style problems through the **CRISP-DM 1.0**
process model. The **Project Manager** orchestrates each turn; specialist agents
(domain, data engineer, data scientist, developer) own their substeps. CrewAI
powers LLM calls; a typed shared state (`CrispDMState`) and trace tooling make
runs observable.

See [`docs/plan.md`](docs/plan.md) for the canonical roadmap and audit notes.

## Project layout

```
configs/                  Case YAML files (titanic, house_prices, disaster_tweets)
data/                     Downloaded competition CSVs
artifacts/<case>/         Per-run outputs (submission, trace, final_state.json)
src/maads/                Installable Python package
  orchestrator.py         CRISP-DM state machine
  agents.py               Five agent wrappers
  crew.py                 CrewAI LLM seam
  observability/          Trace export (timeline, narrative, diagrams)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"

cp .env.example .env
# Set OPENAI_API_KEY and/or MODEL (see .env.example for Ollama vs cloud)
```

Python **3.10–3.13** required (`requires-python` in `pyproject.toml`).

## Download data

```bash
python -m maads data download --case titanic
```

## Run the pipeline

```bash
python -m maads run --case titanic
```

While running, watch `artifacts/titanic/status.json` or the stderr progress bar.
After completion, inspect `artifacts/titanic/trace/` for timelines and diagrams.

Use `--quiet` or `MAADS_PROGRESS=0` to disable the live progress bar.

## Tests

```bash
# Fast path-coverage run (mocked LLM, ~1 min)
MAADS_TRACE=0 coverage run -m pytest src/maads/test_path_coverage.py -q
coverage report --show-missing

# Full test suite
pytest src/maads/
```

## CLI reference

| Command | Description |
|---------|-------------|
| `maads run --case <name>` | Run from `configs/<name>.yaml` |
| `maads run --config <path>` | Run from an explicit config file |
| `maads data download --case <name>` | Download bundled case data |
| `maads data download --competition <slug>` | Download any Kaggle competition |

## Environment variables

See [`.env.example`](.env.example) for `MODEL`, `MAX_TOKENS_PER_RUN`, `MAADS_TRACE`,
`MAADS_PROGRESS`, and Ollama settings.
