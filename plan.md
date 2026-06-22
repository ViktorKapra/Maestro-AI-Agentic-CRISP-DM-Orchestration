# Plan: Multi-Agent CRISP-DM Data-Science System (CrewAI)

## Context

The case (`case-multi-agent-system-for-automated-data-science-main`) asks a team of five
to build a multi-agent LLM system that walks the full **CRISP-DM** process — 6 phases,
24 substeps, 4 feedback loops — to automatically produce trained models and Kaggle-ready
submissions for **three competitions** (Titanic, House Prices, Disaster Tweets). The *same*
agent code must run all three; only a per-dataset YAML config differs. Five agents
(Project Manager, Domain Expert, Data Engineer, Data Scientist, Developer; optional
Validator) own different parts of the cycle and cooperate through a shared typed state.

Deliverables: a working repo (one command per dataset), three `submission.csv` + leaderboard
scores, an architecture document, and a 4–8 page paper. Token economy is a graded concern
(<$0.50/Titanic run), hard caps must be enforced **in code**, and at least one loop must fire
correctly on at least one run.

**Decisions locked in (from the user):**
- Framework: **CrewAI** (the docs' recommended default; lowest learning curve).
- My role: design the system, all agent prompts, and the loop logic, **and write the core code**.
- Team: 5 people but **only 2 can write code** → the split below gives the other three
  substantial non-code ownership (prompts/RAG, experiments/eval, architecture+paper).
- Setup: OpenAI key ready, Kaggle access ready, **env not yet set up**, **deadline tight** →
  front-load a single working Titanic run before breadth.

**What the scaffold already gives us (reuse, don't rebuild):**
- `starter/maads/state.py` — typed `CrispDMState`, `SUBSTEP_OWNER`, `view_for(agent)`,
  `substep_prereqs_satisfied()`, append-only log, `token_spend`. **Keep as-is; it's the spine.**
- `starter/maads/config.py` — `CaseConfig` loader. `configs/{titanic,house_prices,disaster_tweets}.yaml`.
- `starter/maads/tools.py` — `PythonExec` (subprocess sandbox + timeout) and `FileIO` **work**;
  `RAGRetriever` is a stub we implement.
- `starter/maads/llm.py` — token-accounting wrapper + `llm_for(agent)` model tiering (top/mid).
- `starter/maads/data_utils.py` — Kaggle downloader, wired into `python -m maads data download`.

**What we replace/build:**
- `starter/maads/agents.py` — currently a hand-rolled `Agent` base + stubs. We **repurpose it
  for CrewAI**: define the 5 agents as CrewAI `Agent`s (role/goal/backstory, per-agent `llm=`,
  tools), keeping thin `act(state)`/`plan(state)` wrappers the orchestrator calls.
- `starter/maads/orchestrator.py` — keep its skeleton (caps, prereq checks, loop bookkeeping,
  `_dispatch`/`_fire_loop`/`_advance_substep`); fill in `run()`.
- `cmd_run` in `starter/maads/__main__.py` — wire to the orchestrator.

## Architecture decision: CrewAI agents + our own thin orchestrator

We use **CrewAI for the role/prompt/tool/LLM-tiering abstractions** but keep loop control in
our own deterministic orchestrator (the provided `orchestrator.py` shape). Rationale: the four
CRISP-DM loops and the hard caps (phase transitions ≤12, visits/phase ≤3, Loop B ≤3) need
*deterministic, observable, bounded* control — handing that to CrewAI's black-box hierarchical
manager risks non-termination and cost runaway, the two failure modes the case explicitly
penalises. This is exactly the "mix a framework with your own small utilities" the README
endorses. Communication pattern: **hub-and-spoke** through the PM (per ARCHITECTURE.md §5).

Each substep: orchestrator asks the **PM agent** for a structured JSON decision
(`{action, target_substep, loop_to_phase, reason}`), then dispatches the substep to its
`SUBSTEP_OWNER`, which runs a CrewAI agent whose task writes named outputs back into
`CrispDMState`. All data access goes through `PythonExec` wrapped as a CrewAI tool.

## Work split (5 people; 2 coders C1/C2, 3 non-coders N1/N2/N3; I pair with C1/C2)

- **C1 — Orchestration/infra (codes).** `orchestrator.run()` + helpers, hard caps, prereq
  gating, CLI wiring (`cmd_run`), `PythonExec`→CrewAI tool adapter, run/artifact plumbing,
  Developer's deployment + submission-schema validation (6.1).
- **C2 — Agents/ML (codes).** The 5 CrewAI agent definitions and per-substep `act()` bodies,
  modeling menu (4.1–4.4), Developer debug toolkit (`classify_error`, `propose_fix`,
  `re_execute`, `repair_json`, `schema_check`), `RAGRetriever` implementation.
- **N1 — Prompts + domain/RAG (no code).** Iterates the system prompts I draft, curates the
  RAG corpus (CRISP-DM excerpts, per-dataset domain notes, data dictionaries), tunes
  `feature_hints` in each config. Owns prompt-quality feedback loop.
- **N2 — Experiments/eval (no code).** Runs all three datasets, submits to Kaggle, records
  leaderboard scores vs targets, fills the TOKEN_BUDGET worksheet (per-agent/per-provider
  spend), captures logs proving a loop fires, builds results tables, manual submission QA.
- **N3 — Architecture doc + paper (no code).** Architecture write-up (diagram, agent table,
  loop implementation, model tiering, **failure-modes log**) and the 4–8 page paper
  (incl. related-work survey). Consumes N2's results and the Developer's `final_report.md`.
- **Me (Claude):** system design, all agent system prompts, loop logic, and the core code
  (orchestrator + agents + RAG + deployment), pairing with C1/C2.

## Build order (tight-deadline: vertical slice first)

### Phase 0 — Setup (whole team, ~½ day)
- `python -m venv .venv && source .venv/bin/activate`, `pip install -r requirements.txt`,
  `pip install crewai crewai-tools`.
- `cp .env.example .env`, add `OPENAI_API_KEY`; set `MAX_TOKENS_PER_RUN`, `TRAIN_SUBSET=200`
  (dev). Configure Kaggle creds; `python -m maads data download --case titanic` (then the
  other two). `pytest tests/` green.

### Phase 1 — Titanic vertical slice (me + C1 + C2)
Minimal but real path `1.1 → … → 6.3` on Titanic, producing a valid `submission.csv`.
- Wrap `PythonExec` as a CrewAI `BaseTool`; define the 5 CrewAI agents with per-agent `llm=`
  via `llm_for` tiering (PM/DS top, others mid).
- Implement `orchestrator.run()` + `_dispatch`/`_fire_loop`/`_advance_substep` using existing
  caps and `substep_prereqs_satisfied()`. Hub-and-spoke via the PM decision JSON.
- Implement just enough of each agent's `act()` to fill the state fields the prereq checks gate
  on (`business_objectives`, `data_description_report`, `data_quality_report`, `dataset`,
  `models`, `chosen_model`, `submission_path`). Developer 6.1 validates submission schema
  against `sample_submission.csv` before writing — **fail loudly on mismatch**.
- Exit criterion: `python -m maads run --case titanic` finishes under the token cap, writes
  `submission.csv`, and the per-agent log shows which agent ran which substep.

### Phase 2 — Flesh out agents (me + C2, with N1 on prompts/RAG)
- Full per-substep behaviour writing the canonical CRISP-DM named outputs; JSON-mode +
  tight `max_tokens`; `df.describe().to_dict()`/schema summaries in prompts, **never raw CSVs**
  (TOKEN_BUDGET §3). Use `state.view_for(agent)` everywhere.
- Developer debug toolkit (diagnose-first, retry budget 3) + `schema_check` before re-exec.
- `RAGRetriever`: chunk corpus ~200 tokens, embed `text-embedding-3-small`, cosine/FAISS,
  retrieve top-3–5 appended at the **back** of the user message (cache-friendly).

### Phase 3 — Loops + caps (me + C1)
- Implement Loop A (2→1 on non-empty `data_quality_report["blockers"]`), B (4→3 on prep deficit,
  ≤3), C (5→1 if success criterion unmet & A hasn't fired twice), D (6→1 optional/stretch).
- Verify caps abort cleanly; ensure **at least one loop fires when it should** (most likely on
  House Prices or Disaster Tweets) and the system recovers.

### Phase 4 — Generalize (me + C2 + N2)
- Run House Prices (regression, RMSE on log target) and Disaster Tweets (text → TF-IDF or
  OpenAI embeddings; **no transformer fine-tuning** per DATASETS.md). Confirm **zero
  dataset-specific agent code** — only config differs. Beat baselines:
  Titanic ≥0.77 acc, House Prices ≤0.15 RMSE, Disaster Tweets ≥0.78 F1.

### Phase 5 — Reporting (N2 + N3, me reviewing)
- Token worksheet per dataset; record one full backup run (state JSON + logs + submissions)
  per TOKEN_BUDGET §14. Architecture doc (all 8 required sections incl. failure-modes log)
  and the paper. Optional sixth **Validator** agent if time allows (defend either way).

## Files to create / modify (representative)
- Modify: `starter/maads/agents.py` (CrewAI agent defs + `act`/`plan`), `starter/maads/orchestrator.py`
  (`run()` + helpers), `starter/maads/__main__.py` (`cmd_run`), `starter/maads/tools.py`
  (`RAGRetriever` + CrewAI tool adapter), `configs/*.yaml` (`feature_hints` tuning).
- Create: `starter/maads/prompts.py` (stable per-agent system prompts), `starter/maads/crew.py`
  (CrewAI agent/LLM construction), `rag_corpus/` (curated passages), `docs/` write-ups.
- Keep untouched: `state.py`, `config.py`, `data_utils.py`, `llm.py` (token accounting).

## Verification
1. `pytest tests/` passes after setup.
2. `python -m maads run --case titanic` completes with no human intervention, under
   `MAX_TOKENS_PER_RUN`, emitting per-agent substep logs and a schema-valid `submission.csv`
   (validated against `gender_submission.csv`).
3. All three `python -m maads run --case <name>` runs succeed with identical agent code.
4. Assert ≥1 loop event in `state.loop_history` on at least one run, fired for the right reason.
5. Each submission beats its baseline on the public leaderboard (targets above).
6. `state.token_spend` logged per agent (and provider); a Titanic run sits well under budget.
