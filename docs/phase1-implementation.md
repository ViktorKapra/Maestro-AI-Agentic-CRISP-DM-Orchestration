# Phase 1 — Titanic vertical slice (implementation plan)

Companion to [`plan-v2-crewai-over-scaffold.md`](plan-v2-crewai-over-scaffold.md). This is the
detailed build sheet for the **first end-to-end run**.

## Goal (exit criterion)

`python -m maads run --case titanic` runs **end-to-end with no human intervention**, walks
1.1 → 6.x once, and:
- writes a **schema-valid** `artifacts/titanic/submission.csv` (columns/dtypes/row-count match
  `data/titanic/gender_submission.csv`),
- stays under `MAX_TOKENS_PER_RUN`,
- `final_state.json` reaches phase 6 and the per-agent log shows **which agent ran which substep**,
- the smoke tests stay green.

> "Vertical slice" = the thinnest complete thread through **all** phases that really produces a
> submission — every step minimal, depth added later. Not building one agent to perfection first.

## Decisions (locked with the user)

- **Fixed baseline code** for data-prep + modeling: a known-good `pandas`+`sklearn` snippet that
  agents **execute** via `PythonExec`. Agent-*generated* code is deferred to Phase 2. This
  guarantees a valid submission on the first try and proves the pipeline.
- **Models:** develop on **local Ollama** (`ollama/gemma3:4b` / `gemma2:9b`), verify the final
  run on **OpenAI** (tiering via `llm_for`). Hub-and-spoke; deterministic orchestrator.

## Prerequisites from Phase 0 (currently MISSING in the repo — blockers)

Confirmed absent after merging `master` (colleague pushed only `src/maads/` core):
- ❌ `configs/*.yaml` — **even `titanic.yaml` is not in the repo.** Hard requirement: `cmd_run`
  loads `configs/<case>.yaml`. Copy the three from `D:\SummerSchool\starter\configs\`.
- ❌ `data/titanic/` — download via `python -m maads data download --case titanic` (needs Kaggle creds).
- ❌ ML stack in `requirements.txt` — needs `pandas`, `scikit-learn`, `pyarrow` (parquet I/O) for
  the baseline snippet. Add with `uv add`.
- ❌ env: numpy/pandas import must work (the Application-Control DLL block — **assumed fixed**).
- ❌ `tests/` at repo root (only `src/maads/test_smoke.py` exists).

## Run-layout note

Package lives at `src/maads`; `cmd_run` resolves `configs/` and the data paths **relative to the
current working directory**. Pick one and document it:
- **Recommended:** add a minimal `pyproject.toml` (uv), make `maads` importable from repo root,
  keep `configs/` + `data/` at repo root, run `uv run python -m maads run --case titanic`.
- Alternative: run from `src/` with `configs/`+`data/` under `src/`.

## Work breakdown

### A. New: `src/maads/crew.py` (CrewAI plumbing)
- `build_llm(agent_name)` — return a CrewAI `LLM`. Dev: honor `MODEL=ollama/...`; final:
  OpenAI per `llm_for` tiers (PM/Data Scientist → TOP, others → MID). **Reuse the switching
  pattern already written in [`src/crew_starter/crew.py`](../src/crew_starter/crew.py) `_build_llm`.**
- `make_agent(name)` — build a `crewai.Agent` from the role/goal/backstory in `prompts.py`,
  with `llm=build_llm(name)`.
- `run_json_task(agent, instruction, context_view, schema_hint)` — build a `crewai.Task`, run a
  single-agent `Crew(...).kickoff()`, parse JSON (one repair pass), return `dict`. Also fold the
  reported token usage into `state.token_spend`.
- (BaseTool wrap of `PythonExec` is **not needed in Phase 1** — fixed snippets run via
  `self.pyexec.run(...)` directly. Defer the tool adapter to Phase 2 when agents generate code.)

### B. New: `src/maads/prompts.py`
Stable per-agent **system** prompts (cache-friendly) + per-substep **task** templates: the PM
decision prompt (returns `{action,target_substep,loop_to_phase,reason}`), Domain Expert BU prompt,
and short instructions for the agents whose Phase-1 work is mostly executing fixed code.

### C. Fill the seam in `src/maads/agents.py` (replace `NotImplementedError`)
Keep the ABC and the `plan`/`act` names — the orchestrator calls them. **Each `act()` switches on
`state.substep`** and does only that substep's work (the orchestrator dispatches per substep).
- `ProjectManagerAgent.plan()` — Phase 1 is linear: largely **deterministic** (advance through
  substeps; return `act` when prereqs satisfied, else `skip`). Keep one LLM call for realism with a
  deterministic fallback so a weak Ollama model can't stall the run. Loops return `request_loop_back`
  only from Phase 3 onward.
- `ProjectManagerAgent.act()` — write 1.4 (`bu.project_plan`,
  `bu.initial_assessment_of_tools_and_techniques`), 5.2 (`ev.review_of_process`),
  5.3 (`ev.list_of_possible_actions`, `ev.decision`).
- `DomainExpertAgent.act()` — 1.1–1.3 via LLM text → `bu.business_objectives`,
  `business_success_criteria`, `data_mining_goals`, `data_mining_success_criteria`.
- `DataEngineerAgent.act()` — 2.1/2.2/2.4 + 3.x via **fixed snippet** through `PythonExec`:
  load `data/titanic/{train,test}.csv`; write `du.data_description_report` (shapes/dtypes/missing/
  cardinality), `du.data_quality_report` (`{"blockers": [], "tolerable": [...]}`); impute Age/Fare,
  encode Sex/Embarked/Pclass via an sklearn `Pipeline`; write `train.parquet`/`test.parquet` and set
  `dp.dataset = {"train": ..., "test": ...}`.
- `DataScientistAgent.act()` — 2.3 + 4.1–4.4 via **fixed snippet**: choose technique
  (`md.modeling_technique`), stratified 5-fold CV, append `ModelRun(cv_score=...)` to `md.models`,
  set `md.chosen_model`.
- `DeveloperAgent.act()` — 6.1–6.3 via **fixed snippet**: refit chosen model on full train, predict
  test, build `[PassengerId, Survived]`, **validate columns/row-count against
  `gender_submission.csv` before writing**, write `artifacts/titanic/submission.csv`, set
  `dep.submission_path`; write a short `final_report.md` → `dep.final_report_path`. Debug-toolkit
  methods stay stubbed in Phase 1 (no agent-generated code yet).

### D. Fill `src/maads/orchestrator.py`
- `run()` — loop: caps check → `pm.plan(state)` → on `act` call `_dispatch(state.substep)` then
  `_advance_substep()`; on `skip` just `_advance_substep()`; on `request_loop_back` call
  `_fire_loop(...)` (implemented but not exercised until Phase 3). Halt after phase 6's last substep.
- `_dispatch(substep)` — if `not state.substep_prereqs_satisfied(substep)`: log warn + return;
  else `agents[SUBSTEP_OWNER[substep]].act(state)` and log the `StateDelta`.
- `_advance_substep()` — walk `SUBSTEPS[phase]`; roll to next phase at the end; update
  `_n_transitions` / `_phase_visits`; set `halted` past phase 6.
- Token cap: accumulate CrewAI usage into `state.token_spend`; `_force_halt` if over cap.

### E. Wire `src/maads/__main__.py` `cmd_run`
Replace the placeholder body: load config, `CrispDMState.from_config`, build
`Orchestrator(state, artifact_dir)`, call `.run()`, dump `final_state.json` (+ the submission is
already written by the Developer). Leave `cmd_data_download` untouched.

### F. Dependencies
`uv add pandas scikit-learn pyarrow` (xgboost/lightgbm later if needed).

## Files

- **New:** `src/maads/crew.py`, `src/maads/prompts.py`, `configs/{titanic,house_prices,disaster_tweets}.yaml`
  (copy from `D:\SummerSchool\starter\configs\`), optional `pyproject.toml`.
- **Modify:** `src/maads/agents.py` (seam bodies), `src/maads/orchestrator.py` (fill),
  `src/maads/__main__.py` (`cmd_run`), `requirements.txt` (ML stack).
- **Reuse (do not rebuild):** `state.view_for` / `substep_prereqs_satisfied` / `SUBSTEP_OWNER` /
  `SUBSTEPS` in `src/maads/state.py`; `PythonExec` / `FileIO` in `src/maads/tools.py`; `llm_for` in
  `src/maads/llm.py`; the Ollama/OpenAI switch in `src/crew_starter/crew.py`.

## Verification

1. `uv run pytest` (smoke tests) green.
2. Dev run: `MODEL=ollama/gemma3:4b uv run python -m maads run --case titanic` → produces
   `artifacts/titanic/submission.csv`, schema-valid vs `gender_submission.csv`; `final_state.json`
   shows phase 6 reached and per-agent substep log present.
3. Final run on OpenAI (unset `MODEL`, set `OPENAI_API_KEY`) → same valid submission;
   `state.token_spend` recorded per agent and under `MAX_TOKENS_PER_RUN`.
4. Idempotent: a second run overwrites artifacts cleanly and still passes.

## Risks / watch-outs

- **Missing Phase-0 inputs** (configs, data, ML deps) — must land first; listed above.
- **Weak Ollama JSON** for the PM — mitigated by the deterministic PM fallback in Phase 1.
- **Submission schema drift** — the Developer validates against `gender_submission.csv` and fails
  loudly; do not skip this check.
- Keep the fixed snippets small and leakage-safe (fit the sklearn `Pipeline` on train only).
