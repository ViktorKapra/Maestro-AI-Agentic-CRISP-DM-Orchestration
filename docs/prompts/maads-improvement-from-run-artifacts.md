# Prompt: Improve maads from a completed run

Use this prompt with Cursor Agent after a `maads run --case <id>` finishes. The goal is to improve **maads** (orchestration, prompts, capabilities, validators) so the **next run makes better decisions and achieves better results** — not only fewer crashes.

Copy everything below the line into the chat. Attach the files listed in **Attachments** for the run you are reviewing.

---

## Your task

Analyze one (or two contrasting) maads runs and produce a **prioritized improvement plan** for the codebase. Focus on:

1. **Decision quality** — PM checkpoints, loops, prep/model/eval choices
2. **Degraded vs agent-authored paths** — where baselines won or agent code failed repeatedly
3. **Outcome gaps** — `workflow_complete` vs `ml_success`, deficits, validator findings
4. **Orchestration** — caps, loop wiring, progress/trace accuracy (if relevant)

Do **not** implement unless asked. Default deliverable: analysis + ranked proposals with evidence citations.

If asked to implement, prefer **minimal diffs** in `src/maads/` (prompts, `flow/`, `capabilities/`, `validators/`) and add tests only when they cover real behavior.

---

## Context: what maads is

maads is a multi-agent CRISP-DM pipeline (`src/maads/`). Each run writes under:

```text
artifacts/<case_id>/
  current -> runs/<run_id>/
  runs/<run_id>/
    manifest.json
    collected/          # primary evidence (comms, events, sandbox manifest)
    derived/            # live_summary, trace.json, summaries
    reports/            # post-run: postmortem, case_report, improvement_bundle
    final_state.json    # sealed end-of-run state
    sandbox/exec/       # agent Python attempts
  archive/<run_id>/     # prior runs
  runs_index.json       # cross-run index
```

**Workflow complete ≠ ML success.** A run can finish phase 6 without a valid submission or chosen model. The improvement session must address both.

**Not sufficient for maads improvement:** `knowledge/<case>_experience.md` (thin RAG doc for the next *case* run, not engineering maads).

---

## Attachments

### Required (start here)

| Attach | Why |
|--------|-----|
| `@artifacts/<case>/current/reports/improvement_bundle.json` | Bounded decision/outcome/sandbox summary (~500 KB) |
| `@artifacts/<case>/current/reports/postmortem.json` | Loops, tokens, sandbox stats, drill-down pointers |
| `@docs/ARCHITECTURE.md` | Control flow and module layout |

If `current` is missing or has no `reports/`, use `@artifacts/<case>/runs/<run_id>/` or `@artifacts/<case>/archive/<run_id>/` from a completed run.

### Recommended (code areas implicated by the bundle)

Attach only modules the bundle points at — e.g.:

- `@src/maads/flow/phase_runner.py`, `@src/maads/flow/routers.py` — loops, caps, substep dispatch
- `@src/maads/agents.py`, `@src/maads/crew/` — agent kickoffs
- `@src/maads/prompts/` — instructions and schema hints
- `@src/maads/capabilities/` — sandbox, apply_response, baselines
- `@src/maads/validators.py` — phase exit checks
- `@src/maads/conclusions.py` — how outcomes are projected (not source of truth)

### Optional drill-down (when bundle cites a specific failure or decision)

| Attach when… | File |
|--------------|------|
| A `comm_id` in `decision_chain` or `comm_excerpts` needs full context | Filter `collected/communications.jsonl` to that id (or attach whole file if &lt;1 MB) |
| Sandbox retries matter | `collected/sandbox/manifest.jsonl` + `sandbox/exec/<seq>_*.py` + `*.stderr.txt` |
| Checkpoint / loop rationale | `final_state.json` (`loop_history`, `bu`/`ev`/`degraded_flags`) |
| Compare to prior run | `@artifacts/<case>/runs_index.json` + `@artifacts/<case>/archive/<prior>/reports/postmortem.json` |
| One substep debug slice | API: `GET /api/cases/<case>/debug/substep/<id>` or equivalent files |

### Do not attach by default

- `prep/*.parquet`, `train.parquet`, `test.parquet` — case data, not maads logic
- Full `trace/communications.md`, `timeline.md`, `*.mmd` — regenerable; use JSONL + bundle
- Entire `crewai_storage/` — framework internal

---

## Evidence rules

Every claim about **why** maads behaved a certain way must cite evidence:

- `improvement_bundle.json` field (e.g. `sandbox_highlights[2].near_miss_seqs`)
- `comm_id` + field in `collected/communications.jsonl`
- `state` path in `final_state.json` (e.g. `state.loop_history[0].reason`)
- `postmortem.json` counter or loop entry

Do **not** invent agent intent or stakeholder psychology. If evidence is missing, say what artifact would be needed.

---

## What to analyze

### 1. Outcome

From `improvement_bundle.outcome` and `postmortem`:

- `workflow_complete` vs `ml_success` vs `ml_deficits`
- CV, chosen model, submission existence
- Token spend by agent (orchestration cost vs value)

### 2. Decision chain

From `improvement_bundle.decision_chain`:

- For each substep (`1.1`, `1.3`, `3.1`, `4.4`, `5.3`, …): what was decided, which `comm_ids` support it?
- PM checkpoints (`3.1`, `5.1`, `5.2`): loop labels A/B/C — were they correct given state?

### 3. Degradations

From `degraded_paths` and `final_state.degraded_flags`:

- Which substeps used baseline/fallback code?
- Did degradation help or hurt ML outcome?

### 4. Sandbox / codegen

From `sandbox_highlights` and manifest:

- Winners vs near-misses per label (`data_engineer_attempt*`, `developer_debug_*`)
- Repeated stderr patterns → prompt, schema, or capability bug?

### 5. Communication quality

From `comm_excerpts` (+ full comm lines if needed):

- Parse failures (`parse_ok: false`)
- Substantive **successful** turns (prep rationale, model choice, eval decision) — not only errors
- Prompt/schema mismatches (`parsed_json_keys` vs what validators expect)

### 6. Cross-run (if second run attached)

- Same case, different outcome: what changed in decisions, not just crashes?
- Use `runs_index.json` and prior `postmortem.json`

---

## Deliverables for your response

Structure your answer as follows:

### A. Run summary (5–10 lines)

Case, run id, workflow vs ML outcome, key loops, top 1–3 issues.

### B. Decision audit

Table: substep → what maads decided → evidence → assessment (good / weak / wrong).

### C. Root causes (ranked)

For each: symptom → evidence → likely code/prompt area → suggested fix type (prompt / validator / capability / flow).

### D. Prioritized improvements

| Priority | Change | Files / modules | Expected effect on next run | Effort |
|----------|--------|-----------------|-----------------------------|--------|
| P0 | … | … | Better decision X / fewer retries Y | S/M/L |

Prefer changes that improve **decision logic and results**, not only error handling.

### E. Optional implementation sketch

If a P0 is obvious: function names, prompt diff outline, or test case description. No code unless requested.

### F. Gaps

Artifacts or instrumentation still missing to answer open questions.

---

## Constraints

- Python 3.10+, existing `src/maads/` patterns; no greenfield observability stack.
- Do not tune hyperparameters for the case dataset unless the bug is clearly in maads feature/model **selection** logic.
- Distinguish **case-specific** luck from **systematic** maads bugs (repeated across substeps or runs).
- Preserve local-first artifacts; no cloud-only workflows.

---

## Success criteria

The session is successful if you can answer:

1. Why did maads make the most important decision (loop, model, prep path)?
2. What single change would most improve **ML outcome** on the next run of this case?
3. What single change would most improve **decision quality** across cases?
4. Which evidence would you use to verify the fix after the next run?

---

## Quick copy block (minimal session)

```text
Improve maads from this run. Attach:
@artifacts/<case>/current/reports/improvement_bundle.json
@artifacts/<case>/current/reports/postmortem.json
@docs/ARCHITECTURE.md

Analyze decision chain, degradations, sandbox highlights, and outcome gaps.
Produce sections A–F. Cite evidence for every claim. Do not implement unless I ask.
```

## Quick copy block (failed substep deep-dive)

```text
Substep <X.Y> failed or degraded. Attach:
@artifacts/<case>/current/reports/improvement_bundle.json
@artifacts/<case>/current/collected/sandbox/manifest.jsonl
@artifacts/<case>/current/sandbox/exec/   (or specific seq files)
@artifacts/<case>/current/collected/communications.jsonl   (or comm lines for cited comm_ids)
@src/maads/capabilities/<relevant>.py

Explain root cause with evidence; propose minimal fix. Do not implement unless I ask.
```

## Quick copy block (compare two runs)

```text
Compare these maads runs on case <case> and propose improvements:
@artifacts/<case>/runs_index.json
@artifacts/<case>/archive/<failed_run_id>/reports/improvement_bundle.json
@artifacts/<case>/runs/<better_run_id>/reports/improvement_bundle.json
@docs/ARCHITECTURE.md

What decision differences explain the outcome gap? Ranked improvements for maads codebase.
```
