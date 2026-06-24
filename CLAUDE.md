# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**maads** — a five-agent system that walks Kaggle-style problems through the **CRISP-DM 1.0**
process model. A deterministic orchestrator (`orchestrator.py`) drives a hub-and-spoke loop:
the **Project Manager** plans each turn; specialist agents (**domain expert, data engineer,
data scientist, developer**) own their substeps. CrewAI powers the LLM calls; a typed shared
state (`CrispDMState`) is the only thing agents read/write, and a trace/observability stack
makes every run inspectable.

`docs/plan.md` is the canonical roadmap and an honest audit of where the system falls short of
the case requirements (loops wired but not exercised, fixed baselines vs. agent-authored code,
inverted token economy). Read it before extending behavior — it states intent the code doesn't.

> Package management here is **uv-only** — never `pip`. Use `uv sync`, `uv run`, `uv add`.

## Commands

Run from the repo root (`src` layout; the importable package is `src/maads`).

```bash
# Setup
uv sync                          # installs from pyproject.toml + uv.lock
uv sync --extra dev --extra dashboard   # include pytest/coverage and the dashboard API
cp .env.example .env             # then set MODEL and OPENAI_API_KEY (or use ollama/<name>)

# Download case data (Kaggle CLI must be configured)
uv run python -m maads data download --case titanic

# Run the pipeline
uv run python -m maads run --case titanic
uv run python -m maads run --config configs/house_prices.yaml
uv run python -m maads run --case titanic --quiet     # or MAADS_PROGRESS=0

# Trace dashboard (needs the dashboard extra)
uv run python -m maads dashboard --case titanic        # serves dashboard/dist if built
cd dashboard && npm install && npm run dev             # dev UI, proxies /api to :8765
```

### Tests

There is a real test suite (pytest), despite the bare repo appearance. Tests mock the LLM
(`src/maads/testing/fake_llm.py`) so they need no API key.

```bash
uv run pytest src/maads/                       # full suite
uv run pytest src/maads/test_orchestrator_advance.py -q        # one file
uv run pytest src/maads/test_orchestrator_advance.py::test_name # one test

# Fast path-coverage run (mocked LLM, ~1 min) — disable trace to keep it quick
MAADS_TRACE=0 uv run coverage run -m pytest src/maads/test_path_coverage.py -q
uv run coverage report --show-missing
```

Test files live next to the code they cover (`test_*.py` inside `src/maads/`,
`src/maads/observability/`, `src/maads/dashboard/`). Shared fakes are in `src/maads/testing/`.

There are no linters or formatters configured. Python **3.10–3.13** only (`requires-python` in
`pyproject.toml`); newer interpreters may fail to resolve CrewAI's deps.

## Architecture

The system is a **deterministic state machine over LLM agents**, not an agent free-for-all.
Understanding three seams unlocks the codebase:

### 1. The state machine (`orchestrator.py` + `state.py`)

- `CrispDMState` (in `state.py`) is the single source of truth: one nested model per CRISP-DM
  phase (`bu`, `du`, `dp`, `md`, `ev`, `dep`), each field named after a canonical CRISP-DM 1.0
  output. The 24 substeps and their owners are the `SUBSTEPS` and `SUBSTEP_OWNER` tables.
- `Orchestrator.run()` is the hub-and-spoke loop: each turn it calls `pm.plan(state)`, then
  dispatches the **current** substep to its owning agent, then `_advance_substep()` moves
  forward mechanically. Hard caps (`MAX_PHASE_TRANSITIONS`, `MAX_VISITS_PER_PHASE`,
  `MAX_INNER_LOOP_ITERATIONS`, `MAX_TOKENS_PER_RUN`) guarantee termination.
- **Loops** (CRISP-DM back-edges A–D) are fully wired (`_fire_loop`, `_can_fire_loop`,
  `record_loop`) but, per `docs/plan.md`, are not yet exercised on a normal run. The PM returns
  `loop_back` plans; `validate_phase_*` in `validators.py` seed `state.validator_findings` on
  phase transitions, which the PM reads as Loop B signals. Keep this machinery — it's the P0 work.

Two invariants from `state.py` to preserve when editing:
1. **Append-only logs** — `log`, `loop_history`, `md.models` only grow.
2. **No agent reads another agent's prompts** — agents communicate only through state. Each agent
   is given only `state.view_for(agent_name)`, a minimal slice (token discipline). Adding a field
   an agent needs means extending `view_for`, not dumping the whole state.

### 2. The agents (`agents.py`)

Five plain classes (no inheritance), each exposing `act(state) -> StateDelta`; only the PM also
has `plan(state) -> Plan`. The owner of the current substep is looked up in `SUBSTEP_OWNER`.

The key tension (documented in `docs/plan.md`): some substeps are **agent-authored** (the LLM
writes Python, run via `codegen.run_authored_code`, validated against a contract, self-debugged,
and falling back to a fixed snippet only on repeated failure — `res.degraded` marks this and is a
Loop-B signal), while others still run **fixed baseline snippets** (`_PIPE_HELPER`, `_TRAIN_SRC`,
`_SUBMIT_SRC`, etc.). When making an agent "do real work," the pattern to follow is
`run_authored_code` with a `contract` + `fallback`, and the rule **measured execution wins over
LLM prose** when writing back to state.

### 3. The CrewAI seam (`crew.py`)

`crew.py` is the only file that touches CrewAI. `run_json_task` / `run_text_task` build a
one-agent, one-task `Crew`, kick it off, parse the result (`_extract_json` does a lenient repair
pass), and fold reported token usage into `state.token_spend`. `build_llm` selects the backend:
`MODEL=ollama/<name>` → local Ollama; otherwise OpenAI with per-agent tiering (PM and data
scientist get `OPENAI_MODEL_TOP`, others `OPENAI_MODEL_MID`). Agent personas live in
`prompts/` (`identities/` for the specialist backstories).

### Supporting subsystems

- **`observability/`** — Runtime Execution Intelligence. `auto_enable`/`begin_run`/`end_run`
  (called from `__main__.py`) install OpenTelemetry + CrewAI listeners that capture every
  agent–LLM exchange. `render/` turns the trace into `artifacts/<case>/trace/` outputs
  (timeline, narrative, mermaid flowchart/sequence, `communications.md` with full prompts).
  Gated by `MAADS_TRACE` / `MAADS_TRACE_LLM_IO` env vars.
- **`dashboard/`** (Python, `src/maads/dashboard/`) — FastAPI + uvicorn server aggregating
  artifact files into a live JSON API (`api.py`, `aggregators.py`, `store.py`). Optional extra.
- **`dashboard/`** (repo root) — separate Vite + React + Tailwind frontend that polls that API.
- **`run_status.py` / `progress.py` / `shutdown.py`** — file-based live status
  (`artifacts/<case>/status.json`), the stderr progress bar, and graceful SIGINT handling.
- **`config.py`** — loads `configs/<case>.yaml` into `CaseConfig`; `kickoff_inputs` builds the
  templating dict. **`paths.py`** resolves repo-relative paths consistently.

### Flow of a run (`__main__.py:cmd_run`)

`load_dotenv` → `auto_enable` (trace) → load config → `CrispDMState.from_config` → create
`artifacts/<case>/` → install SIGINT handler, bind status/progress/trace → `Orchestrator(...).run()`
→ write `final_state.json`. Outputs land in `artifacts/<case>/` (`submission.csv`, `trace/`,
`status.json`, `final_state.json`).

## Adding a case

Drop a `configs/<name>.yaml` (see `configs/titanic.yaml` for the schema: `problem_type`,
`target_column`, `id_column`, `evaluation_metric`, `data.*_csv` paths, `feature_hints`,
`success_criterion.threshold`). The goal (`docs/plan.md`) is that the **same agent code** handles
all three bundled cases (`titanic`, `house_prices`, `disaster_tweets`) from config alone — NLP
cases will need a model/prep path the fixed snippets don't yet cover.

## Configuration

Read from `.env` (git-ignored; see `.env.example`):
`OPENAI_API_KEY`, `MODEL`, `OPENAI_MODEL_TOP`/`OPENAI_MODEL_MID`, `OLLAMA_BASE_URL`,
`MAX_TOKENS_PER_RUN`, `MAADS_TRACE`, `MAADS_TRACE_LLM_IO`, `MAADS_PROGRESS`. CrewAI's LLM plumbing
is LiteLLM under the hood, so any LiteLLM-supported backend works through `MODEL`.

## Debugging

VS Code launch configs are in `.vscode/launch.json` (`.vscode/settings.json` points at `.venv`,
`src/`, and `.env`). See `DEBUGGING.md` (in Bulgarian) for the breakpoint/step workflow; note its
references to `crew_starter` are stale — the package is `maads` and the relevant configs are
"maads run --case titanic" and "Current file".
