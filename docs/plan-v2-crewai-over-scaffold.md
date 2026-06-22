# Plan v2: Multi-Agent CRISP-DM System — CrewAI over the kept `maads` scaffold

> This is a **new** plan that supersedes `D:\New folder\plan.md` (left unchanged).
> It folds in what we learned by reading the real scaffold and case docs under `D:\SummerSchool`.
> Companion diagram: [`architecture-v2.svg`](architecture-v2.svg).

## Context

The original plan (`plan.md`) was written **before** the actual scaffold and case docs were read. Reading them changes two assumptions:

1. **The scaffold is a complete framework-agnostic skeleton, not just utilities.**
   `D:\SummerSchool\starter\maads` ships working `state.py`, `config.py`, `tools.py`
   (`PythonExec`/`FileIO`), `llm.py` (token caps + tiering), `data_utils.py` — **plus**
   `agents.py` (an `Agent` ABC + 5 concrete stubs) and `orchestrator.py` (a control-loop
   skeleton with caps + `_dispatch`/`_fire_loop`/`_advance_substep`).
2. **The case explicitly wants a mature framework, and the ABC class hierarchy is the
   *deprecated* prescription.** `docs\ARCHITECTURE.md:5`: the doc "used to prescribe a
   specific Python class hierarchy … the prescription moved up a level." The README
   (`D:\SummerSchool\README.md:3,19,228`) calls `starter/` "drop-in **utilities** you can
   use with any framework."

**Decision (confirmed with the user):** keep the scaffold's **spine** (state/config/tools/
llm/data), **replace the `Agent` ABC with CrewAI** agents, and **fill in** the scaffold's
`orchestrator.py` for deterministic caps + the four loops (the docs require caps in code,
not in prompts — `ARCHITECTURE.md:67,118,173`).

**Intended outcome (unchanged from the case):** one command per dataset; three Kaggle-valid
`submission.csv` beating baselines; ≥1 loop fires correctly on ≥1 run; architecture doc +
4–8 page paper; token spend logged per agent and under budget.

## What changed vs `plan.md`

- `plan.md` said "repurpose `agents.py` for CrewAI" loosely. **Now precise:** the `Agent`
  ABC is the deprecated layer — drop its hand-rolled `self.llm.chat` bodies and run each
  agent through CrewAI, **keeping the `plan(state)->Plan` / `act(state)->StateDelta` method
  names** because the orchestrator calls them (the seam).
- Confirmed exact seam signatures (in `starter/maads/agents.py`): `plan(self, state) -> Plan`,
  `act(self, state) -> StateDelta`, where `Plan(action, target_substep, loop_to_phase, reason)`.
- Confirmed loop firing is **config-driven**: `configs/titanic.yaml` has
  `success_criterion.threshold: 0.77` ("below this, the 5→1 loop should fire") — so loop C
  is **deterministically testable**, not luck-dependent (fixes a risk flagged on `plan.md`).
- New risk surfaced: **CrewAI bypasses `llm.py`'s `MAX_TOKENS_PER_RUN` cap** → caps must be
  re-asserted in the orchestrator (see Integration decisions).

## Architecture: keep vs replace vs fill

| Scaffold file | Action | Why |
|---|---|---|
| `maads/state.py` (`CrispDMState`) | **Keep as-is** | The 24 CRISP-DM named outputs; the shared object CrewAI agents read/write. `ARCHITECTURE.md:49`. |
| `maads/config.py` + `configs/*.yaml` | **Keep** | Required input schema; generality (only config differs per dataset). |
| `maads/tools.py` → `PythonExec`, `FileIO` | **Keep** + wrap `PythonExec` as a CrewAI `BaseTool` | Sandbox is "non-negotiable" (`ARCHITECTURE.md:80`). |
| `maads/tools.py` → `RAGRetriever` | **Implement** (stub today) | Domain Expert grounding. Keep < ~100 lines. |
| `maads/llm.py` | **Keep** for token caps/tiering | `llm_for` tiering + run cap; reused by orchestrator-side accounting. |
| `maads/data_utils.py` | **Keep** | Kaggle download. |
| `maads/agents.py` (`Agent` ABC + stubs) | **Replace bodies with CrewAI**, keep `plan`/`act` names | Deprecated prescription; framework does the agent work. |
| `maads/orchestrator.py` | **Fill the stubs** (`run`, `_dispatch`, `_fire_loop`, `_advance_substep`) | Deterministic, bounded, observable control of caps + loops. |
| `maads/__main__.py` → `cmd_run` | **Wire** to `Orchestrator(...).run()` | Currently a placeholder. |

See the companion diagram [`architecture-v2.svg`](architecture-v2.svg) for the full picture
and the keep/replace color coding.

## Build order (vertical slice first; C1/C2 parallel)

**Day 0 — lock the contracts (whole code team, ~½ day).** The seam between C1 (orchestrator)
and C2 (agents) is already half-fixed by the scaffold. Confirm: the `plan`/`act` signatures,
the `Plan` decision schema, the named state fields the prereqs gate on, and the
`PythonExec`→CrewAI `BaseTool` interface. This lets C1 and C2 work in **parallel** against
mocks (C1 builds the loop against mock agents that write canned outputs; C2 builds CrewAI
agents tested against a fixed input state).

### Phase 0 — Setup (whole team)
- Work **inside `D:\SummerSchool\starter`** (not `D:\New folder`). New venv;
  `pip install -r requirements.txt` + `pip install crewai crewai-tools`.
- `.env` with real `OPENAI_API_KEY`, `OPENAI_MODEL_TOP`, `OPENAI_MODEL_MID`,
  `MAX_TOKENS_PER_RUN`, `TRAIN_SUBSET` (dev). Kaggle creds.
- `python -m maads data download --case titanic`; `pytest tests/` green.

### Phase 1 — Titanic vertical slice (me + C1 + C2)
- C1: fill `orchestrator.run()` + `_dispatch`/`_fire_loop`/`_advance_substep` using existing
  caps (`MAX_PHASE_TRANSITIONS=12`, `MAX_VISITS_PER_PHASE=3`, `MAX_INNER_LOOP_ITERATIONS=3`)
  and `state.substep_prereqs_satisfied`. Wire `cmd_run`.
- C2: define the 5 CrewAI agents in new `crew.py`/`prompts.py`; reimplement each agent's
  `act`/`plan` to run a CrewAI Agent+Task, parse, and write named outputs to `CrispDMState`.
  Minimal bodies — just enough to fill the prereq-gated fields
  (`business_objectives`, `data_description_report`, `data_quality_report`, `dp.dataset`,
  `md.models`, `md.chosen_model`, `dep.submission_path`).
- Developer 6.1 validates `submission.csv` against `sample_submission_csv` before writing —
  **fail loudly on mismatch**.
- **Exit:** `python -m maads run --case titanic` finishes under the token cap, writes a
  schema-valid `submission.csv`, and the per-agent log shows who ran each substep.

### Phase 2 — Flesh out agents + RAG (me + C2, N1 on prompts/corpus)
- Full per-substep behaviour writing the canonical outputs; JSON-mode + tight `max_tokens`;
  send `df.describe().to_dict()`/schema summaries, **never raw CSVs**. Use `state.view_for(agent)`.
- Developer debug toolkit (`classify_error`, `propose_fix`, `re_execute`, `schema_check`,
  `repair_json`), diagnose-first, retry budget 3.
- `RAGRetriever`: ~200-token chunks, `text-embedding-3-small`, cosine/FAISS, top-3–5.

### Phase 3 — Loops + caps (me + C1)
- Loop A (2→1 on non-empty `du.data_quality_report["blockers"]`), B (4→3 on prep deficit, ≤3),
  C (5→1 when `success_criterion` unmet & A not fired twice), D (6→1 optional).
- Caps abort cleanly. **Deterministic loop proof:** lower a YAML `success_criterion.threshold`
  to force loop C on a dev run; confirm `state.loop_history` records it for the right reason.

### Phase 4 — Generalize (me + C2 + N2)
- House Prices (regression, RMSE on log target) + Disaster Tweets (TF-IDF or OpenAI
  embeddings; **no transformer fine-tuning**). **Zero dataset-specific agent code** — only
  config differs. Targets: Titanic ≥0.77 acc, House Prices ≤0.15 RMSE, Disaster Tweets ≥0.78 F1.

### Phase 5 — Reporting (N2 + N3, me reviewing)
- Token worksheet per dataset; one full backup run (state JSON + logs + submissions).
  Architecture doc (all 8 sections of `ARCHITECTURE.md:181`, incl. failure-modes log) + paper.
  Optional Validator agent if time allows. **Start N3's arch doc in Phase 1** (diagram/agent
  table don't need results) so reporting isn't back-loaded.

## Integration decisions

- **The seam:** the orchestrator stays the controller. Each agent's `act()`/`plan()` builds a
  CrewAI `Agent` + `Task`, runs `kickoff`, parses the result, and writes named outputs to
  `CrispDMState`. The `Agent` ABC can remain as a thin contract or be dropped — keep the
  method names since `orchestrator.py` calls them.
- **PM decision = `Plan` dataclass** (`action`/`target_substep`/`loop_to_phase`/`reason`),
  produced by the PM's CrewAI task in JSON-mode. Hub-and-spoke (`ARCHITECTURE.md:150`).
- **Token caps with CrewAI:** CrewAI does **not** go through `llm.py`, so `MAX_TOKENS_PER_RUN`
  won't auto-fire. Re-assert caps in the orchestrator: count PM calls (~30) and total calls
  (~150) per `ARCHITECTURE.md:160`, and sum CrewAI's reported usage into `state.token_spend`
  via `state.add_tokens`. Optionally point CrewAI's per-agent `llm=` at a thin wrapper.
- **Model strategy:** dev cheaply on **local Ollama** (`ollama/gemma3:4b` / `gemma2:9b`, as
  already wired in `D:\New folder`), real runs on **OpenAI tiering** via `llm_for`
  (PM/Data Scientist → top, others → mid). Optional DeepSeek for Developer/Data Engineer to
  cut cost (`README.md:177`).

## Files to create / modify

- **Modify:** `starter/maads/agents.py` (CrewAI-backed `act`/`plan`),
  `starter/maads/orchestrator.py` (fill `run` + helpers), `starter/maads/__main__.py`
  (`cmd_run`), `starter/maads/tools.py` (`RAGRetriever` + `PythonExec`→`BaseTool` adapter),
  `configs/*.yaml` (`feature_hints` tuning).
- **Create:** `starter/maads/crew.py` (CrewAI agent/LLM construction),
  `starter/maads/prompts.py` (stable per-agent system prompts), `starter/rag_corpus/`
  (curated passages), `docs/` write-ups (arch doc + paper drafts).
- **Keep untouched:** `starter/maads/state.py`, `config.py`, `data_utils.py`, `llm.py`.

## Verification

1. `pytest tests/` passes after setup.
2. `python -m maads run --case titanic` completes with no human intervention, under
   `MAX_TOKENS_PER_RUN`, emitting per-agent substep logs and a schema-valid `submission.csv`
   (validated against `gender_submission.csv`).
3. All three `python -m maads run --case <name>` runs succeed with **identical agent code**.
4. `state.loop_history` shows ≥1 loop event on ≥1 run, fired for the right reason (force loop C
   via a lowered `success_criterion.threshold` for a deterministic demo).
5. Each submission beats its baseline on the public leaderboard (targets above).
6. `state.token_spend` logged per agent (and provider); a Titanic run sits well under budget.
