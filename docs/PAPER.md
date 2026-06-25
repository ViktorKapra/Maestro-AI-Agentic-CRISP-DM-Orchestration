# maads: A Multi-Agent System for Automated Data Science over CRISP-DM

*Authors: the maads team. Draft v1 — honest results edition.*
*Artifacts and source: this repository (MIT-licensed, public).*

> **Honesty note (read first).** This paper reports what the system *actually did*, not
> what it was designed to do. At the time of writing, the system has been run
> end-to-end only on **Titanic**; **House Prices** and **Disaster Tweets** are
> architecturally supported (config + code paths exist) but have **not** been run to a
> recorded public-leaderboard score. No number in the Results section is invented: every
> measured value comes from run artifacts (`docs/Optimisation_Research.md`,
> `artifacts/<case>/.../status.json` / `final_state.json`). Where we have no measurement,
> we say so explicitly rather than estimate. The most complete measured run predates
> several fixes now in the codebase; we flag this throughout.

---

## Abstract

We present **maads**, a multi-agent system that drives Kaggle-style supervised-learning
problems through the full CRISP-DM 1.0 process model — its six phases, twenty-four generic
tasks, and four back-edge loop contours — using a small team of role-specialized,
LLM-driven agents. maads is built on **CrewAI Flow** as the workflow engine, with
phase-scoped crews for agent collaboration and a deterministic "capabilities" layer that
executes pandas/scikit-learn code in a sandbox so that committed state reflects code that
actually ran, not text an agent generated. Six agents (Project Manager, Domain Expert,
Data Engineer, Data Scientist, Developer, Storyteller) own disjoint CRISP-DM substeps and
communicate only through a typed shared state. The Project Manager fires CRISP-DM loops at
deterministic checkpoints; the Developer acts as an on-call debugger that classifies
execution failures, re-executes under a retry budget, and repairs malformed structured
output. On Titanic, maads produces a schema-valid submission with 5-fold cross-validated
accuracy of **0.795** (above the 0.766 "all-female-survive" baseline and the project's
0.77 target). It does so, however, at a measured cost of **~2.75M tokens and ~116 minutes**
on a local Ollama backend — roughly an order of magnitude over our own token budget — and
the same run exhibited a spurious Loop C that marked the run's ML outcome as failed despite
the good model. We report these failures in detail, describe the fixes since applied, and
discuss what an agentic, process-faithful approach to automated data science costs in
practice. Our central finding is that **CRISP-DM fidelity and agent observability are
achievable, but token economy and decision-timing correctness are the hard parts** — and
they dominate both cost and outcome.

---

## 1. Introduction

Automated data science promises to compress the repetitive, judgment-laden work of taking a
dataset from raw files to a validated predictive model. Classical AutoML systems automate
*model and hyperparameter search* but treat the surrounding process — framing the problem,
understanding the data, deciding what preparation is warranted, and judging whether results
meet a business need — as out of scope. Large language models change the calculus: an LLM
can read a problem statement, reason about a schema, propose feature engineering, write and
debug the code to execute it, and narrate its own evaluation. The open question is whether a
*team* of specialized LLM agents, coordinated by an explicit process model, does this better
and more auditably than a single monolithic agent — and at what cost.

This work studies that question concretely. We adopt **CRISP-DM 1.0** (Chapman et al., 2000)
as the process spine, not as decoration but as the literal control structure: each of its
24 generic tasks is an owned substep, each named output is a typed state field, and each of
its four loop contours is an implemented back-edge. We assign the six roles the case
prescribes to six agents, give the code-writing agents a real Python sandbox, and instrument
every step.

Our contributions are:

1. A **process-faithful multi-agent architecture** in which CRISP-DM's structure is
   executable: a CrewAI Flow state machine whose routers *are* the CRISP-DM loops, with
   per-substep agent ownership and a typed shared state that mirrors the reference model's
   named outputs.
2. An **execution-authoritative design** that makes agents doers rather than narrators: the
   owning agent authors Python, it runs in a sandbox under a contract, and only execution
   output is committed — with the interpretive LLM call *skipped* when execution already
   satisfies the contract.
3. A **Developer-as-debugger** mechanism — error classification, bounded re-execution, and
   JSON repair — that contains the characteristic failure modes of agentic ML.
4. An **honest empirical account** of a real Titanic run: a good model produced at a cost
   (tokens, wall-clock, and a decision-timing bug) far worse than our design targets, with a
   ranked analysis of where the cost and the error came from.

We deliberately under-claim on generality: the system *can* run House Prices (regression)
and Disaster Tweets (NLP) by config, and the code paths exist, but we have not yet produced
recorded leaderboard scores for them. We treat that gap as a result, not a footnote.

---

## 2. Related Work

**CRISP-DM.** The CRoss-Industry Standard Process for Data Mining (Chapman et al., 2000)
remains the most widely used process model in applied data science. Its value here is its
hierarchy (phases → generic tasks → outputs) and its *iterative* philosophy: the loop
contours encode the expectation that later phases revise earlier ones. Most "CRISP-DM"
implementations in practice are linear walkthroughs; a system that never fires a back-edge
is, in the case's framing, a script with sections rather than a process.

**Classical AutoML.** TPOT (Olson & Moore, 2016), auto-sklearn (Feurer et al., 2015), and
H2O AutoML automate pipeline construction and hyperparameter optimization, typically via
genetic programming, Bayesian optimization, or ensembling over a fixed search space. They
are mature, efficient, and reproducible, but they operate *inside* the modeling phase: they
do not read a problem statement, decide whether a feature is leakage, or judge a result
against a business criterion. An agentic approach is more flexible and more interpretable
(every decision is a logged, natural-language rationale) but, as we show, dramatically more
expensive per run.

**LLM agents for data science.** A recent line of work uses LLMs as data scientists.
Data Interpreter (Hong et al., 2024) plans and executes data-analysis tasks as a dynamic
graph with runtime code execution and verification. DS-Agent (Guo et al., 2024) uses
case-based reasoning over Kaggle-style tasks, retrieving and adapting expert insights.
AutoGen (Wu et al., 2023) provides conversational multi-agent infrastructure on which
data-analysis assistants have been built. maads differs from these in being explicitly
*process-structured*: rather than letting a planner discover an arbitrary task graph, we fix
the CRISP-DM 24-substep skeleton and four loops, and study how well a role-specialized team
fills it. This trades planning flexibility for auditability and a direct mapping to a
methodology practitioners already use.

**Agentic foundations.** ReAct (Yao et al., 2023) established the interleaving of reasoning
and acting that underlies tool-using agents; our code-authoring loop (reason → write code →
observe execution → revise) is a ReAct pattern specialized to a JSON contract. Reflexion
(Shinn et al., 2023) frames verbal self-correction from feedback, which is conceptually the
role of our Developer debugger and of the loop contours: failed execution and unmet criteria
are fed back as signals that change the next action.

**Frameworks.** We use CrewAI (role/goal/tools/tasks) and specifically its Flow engine
(typed shared state, `@start`/`@listen`/`@router` graph). LangGraph would have made the loop
edges even more explicit; CrewAI was chosen for the cleaner role-to-agent mapping and lower
ramp-up, consistent with the case's recommendation. We discuss this trade-off in §6.

---

## 3. Method

### 3.1 Three-layer architecture

maads separates *when*, *what*, and *how* into three layers:

- **`flow/`** — a `CrispDMFlow` (CrewAI `Flow[CrispDMState]`) is the state machine. Phases
  are `@listen` steps; the three Project-Manager checkpoints are `@router`s. This layer
  decides *when* each substep runs and *whether a loop fires*.
- **`crews/`** — six phase-scoped `@CrewBase` crews wrap CrewAI agents (shared `agents.yaml`,
  per-phase `tasks.yaml`). This layer decides *what* via the LLM: each substep is a one-agent
  Crew kickoff returning structured JSON.
- **`capabilities/`** — deterministic Python: it authors-and-runs sandboxed pandas/sklearn,
  measures artifacts, and applies validated results to state. This layer does the *how*; it
  contains no LLM-orchestration logic, which makes it unit-testable.

The single source of truth is `CrispDMState` (`state.py`), a Pydantic model with one nested
sub-model per phase and one field per CRISP-DM named output (`data_quality_report`,
`derived_attributes`, `test_design`, `assessment_of_dm_results`, …). Two invariants hold:
logs and `loop_history` are append-only, and **no agent reads another agent's prompt** — they
read only the state slice returned by `view_for(agent_name)`, which keeps agents swappable
and bounds prompt size.

### 3.2 The six agents and CRISP-DM ownership

| Phase | Substeps | Owner(s) |
|---|---|---|
| 1 Business Understanding | 1.1–1.3 / 1.4 | Domain Expert / **PM** |
| 2 Data Understanding | 2.1, 2.2, 2.4 / 2.3 | Data Engineer / Data Scientist |
| 3 Data Preparation | 3.1–3.5 | Data Engineer |
| 4 Modeling | 4.1–4.4 | Data Scientist |
| 5 Evaluation | 5.1 / 5.2, 5.3 | Data Scientist / **PM** |
| 6 Deployment/Reporting | 6.1, 6.4 / 6.2, 6.3 | Developer / **Storyteller** |

The **Storyteller** is a sixth agent (beyond the case's five) that owns report-evidence
generation (6.2) and the final report (6.3), turning the measured `EvaluationBundle`
(metrics, confusion matrix, figures) into human-facing narrative. We added it because
conflating "produce the submission" (an engineering act) with "explain the result" (a
communication act) weakened both in early versions.

### 3.3 Execution-authoritative substeps (doers, not narrators)

For every substep that touches data, the owning agent's LLM **authors Python**; the sandbox
(`PythonExec`, a subprocess with a wall-clock timeout) runs it; the code must print a single
JSON line satisfying a **contract** (a predicate returning a list of human-readable errors).
On failure the captured stderr is fed back for a revision, up to a retry budget. Crucially,
`capabilities.shared.execution_authoritative()` then checks whether the measured output
already satisfies the substep's required keys; if so, the *second*, interpretive LLM call is
**skipped** and results are applied mechanically. This both guarantees integrity — the
prepared parquet, the CV score, and the submission are the ones the code produced — and
removes a redundant LLM call per substep.

When all authoring attempts fail, control passes to the Developer (below); only if that also
fails do we fall back to a fixed baseline snippet, and a fallback is recorded as a
`degraded_flag` — itself a Loop B signal.

### 3.4 Loops as deterministic checkpoints

The Project Manager's LLM is invoked **only at decision substeps**
(`PM_DECISION_SUBSTEPS = {1.1, 2.1, 3.1, 4.1, 5.1, 5.2, 6.1, 6.4}`); all other advances are
mechanical and incur no LLM call. At the three loop checkpoints the flow computes a
**deterministic suggested action** from state and offers it to the PM as advice:

- **Loop A (2→1)** at checkpoint 3.1 when `data_quality_report.blockers` is non-empty.
- **Loop B (4→3)** at checkpoint 5.1 when `validator_findings` or `degraded_flags` are
  non-empty (a state-vs-artifact validator runs at phase exit).
- **Loop C (5→1)** at checkpoint 5.2 when `assessment_of_dm_results` does not meet the
  success criterion (and halts instead if Loop A already fired twice).
- **Loop D (6→1)** appends the run's experience documentation into the knowledge corpus for
  the next run.

Hard caps (max phase transitions, max visits per phase, Loop B ≤ 3) are enforced in code,
not in prompts.

### 3.5 Developer as on-call debugger

`debug.py` implements the case's most-skipped requirement. `classify_exec_error()` labels a
failure as schema / shape / type / oom / lib_version / leakage / timeout / syntax /
json_parse. `debug_python_exec()` then diagnoses, re-authors, and re-executes against the
original contract under a retry budget of three. `debug_json_parse()` repairs malformed
structured output — deterministically first, then via a Developer LLM call — and validates
the repair against the agent's output schema. The codegen loop routes to the Developer
*before* falling back to a baseline.

### 3.6 Domain RAG, knowledge, and skills

The Domain Expert is grounded by a retrieval-augmented corpus (`rag.py`): markdown is
chunked and embedded (Ollama or OpenAI embeddings, with a keyword-search fallback when no
embedder is available), and top-k passages are retrieved per state. Phase-specific guidance
(leakage/CV discipline, tabular vs NLP prep, the Kaggle submission contract, the
JSON-output contract, the developer debug rubric) is provided to the relevant agents as
CrewAI *skills*.

### 3.7 Observability and artifacts

Every run writes to `artifacts/<case>/runs/<run_id>/` (with a `current` symlink and an
`archive/`): `final_state.json`, a `collected/` evidence tree (communications, events,
sandbox manifest), `derived/` summaries and trace, and post-run `reports/` (postmortem,
case report, improvement bundle). Token spend is logged **per agent and per provider**. A
React dashboard renders progress, token spend, the agent–LLM communications, and the
architecture graph live.

### 3.8 Model backends

The default backend is local **Ollama** (free, offline); OpenAI and OpenAI-compatible
providers (e.g. DeepSeek) are supported, with per-agent model tiering (top-tier for the PM
and Data Scientist). All measurements in this paper are on Ollama.

---

## 4. Experimental Setup

**Datasets.** The demonstration suite is three Kaggle competitions chosen for diversity:
Titanic (binary classification, mixed tabular, accuracy), House Prices (regression, 79
features, RMSE on log price), and Disaster Tweets (binary classification, free text, F1).
The same agent code runs all three; only a per-case YAML differs.

**Targets (a priori).** Titanic ≥ 0.77 accuracy; House Prices ≤ 0.15 RMSE; Disaster Tweets
≥ 0.78 F1. Token budget guidance: a Titanic run under ~200k tokens.

**Metrics.** We report 5-fold cross-validated scores from out-of-fold predictions, total and
per-agent token spend, and wall-clock time. **We do not report public-leaderboard scores
because we did not submit to Kaggle in the measured runs** — a gap we return to in §6.

**What was actually run.** Three Titanic runs exist (`docs/Optimisation_Research.md`): one
completed, one interrupted at substep 2.3, and one in progress. House Prices and Disaster
Tweets were not run to completion. The completed run predates fixes described in §6.1.

---

## 5. Results

### 5.1 Titanic: a good model at a bad price

The completed Titanic run produced a **schema-valid `submission.csv`** and a chosen model
with **5-fold CV accuracy 0.795**, above both the 0.766 "all-female-survive" baseline and the
0.77 target. The pipeline walked all six phases.

It did so in **~116 minutes** (08:00→09:56 UTC) and **~2.75M tokens** — about **14× our
~200k-token budget**. Approximately **88 minutes** were spent inside LLM calls (median
**101 s/call**, max **633 s**); the remainder was sandbox execution and I/O. Because the
backend was local Ollama, wall-clock is dominated by model latency, not orchestration logic.

**Per-agent token spend (measured):**

| Agent | Tokens | Share |
|---|---:|---:|
| Data Engineer | 1,647,459 | 60% |
| Developer | 488,648 | 18% |
| Project Manager | 364,441 | 13% |
| Data Scientist | 201,506 | 7% |
| Domain Expert | 51,282 | 2% |

The distribution is the headline result: **cost is dominated by the code-writing agent's
retry churn and the Developer's repair tax**, not by CRISP-DM breadth. The Data Engineer's
spend is concentrated in Phase-3 preparation substeps (3.2–3.5), where authored-code attempts
retry; the Developer's spend is almost entirely DEBUG and JSON repair. The run logged **17
authored-code attempts**, **3 Developer python-exec debug interventions**, **8 Developer
JSON-repair interventions**, and **1 baseline fallback** (a CSV-encoding error at 3.5).

### 5.2 A spurious loop corrupted the outcome flag

The same run finished with `ml_success: false` *despite* the 0.795 model. Root cause: at the
5.1 checkpoint the PM was consulted **before** the Data Scientist had written
`assessment_of_dm_results`; the state view computed `business_goal_met` as
`bool(None_assessment.get("meets"))`, i.e. `False`, and the PM fired **Loop C** back to 1.3.
The loop re-entered 1.3 as a no-op, `assessment_of_dm_results` was never set, and the outcome
projection reported ML failure. This is a pure **decision-timing bug**: the model was good;
the orchestration mis-read its own state because it asked the question before the answer
existed. It also wasted PM and Developer tokens.

### 5.3 Loop behavior, honestly

The only loop we observed fire on Titanic was this *erroneous* Loop C. We have **not** yet
recorded a run in which a loop fired *for the right reason and the system recovered* — the
behavior the case treats as the signal that the system is thinking rather than executing. The
machinery exists and is unit-tested (`test_loop_signals.py`), and a forcing config
(`titanic_loopdemo.yaml`, success threshold 0.99) exists to demonstrate it, but a clean
demonstrated recovery is unrun.

### 5.4 Generality: unproven

House Prices and Disaster Tweets have configs and dedicated code paths (the NLP path uses
TF-IDF + logistic regression, the case's prescribed sweet spot, avoiding transformer
fine-tuning). Neither was run to a recorded score. We therefore claim only that the
architecture is **not tabular-only by construction**, not that generality is empirically
demonstrated.

---

## 6. Discussion — what didn't work

### 6.1 Fixes already applied (and not yet re-measured)

The measured run predates several corrections now in the codebase, which we list honestly as
"fixed in code, unverified by a fresh end-to-end run":

- **False Loop C.** The state view now returns `business_goal_met = None` when the assessment
  is absent at 5.1, and computes it deterministically from `cv_score` vs threshold otherwise,
  so the PM no longer reads a missing answer as failure.
- **Double LLM call per execution substep.** `execution_authoritative()` now skips the
  interpretive call when execution already satisfies the contract — the single largest
  predicted token saving.
- **Per-provider token logging** (`token_spend_by_provider`) was added, satisfying the
  case's per-provider cost-reporting requirement.

Because these are unverified by a new run, we do **not** claim the 2.75M-token figure has
improved; the next honest step is a re-measured Titanic run.

### 6.2 Open problems

- **Token economy is the central weakness.** Even after the single-call fix, the design
  carries heavy fixed costs: large agent backstories (the Data Engineer persona alone is
  ~16.7 KB, sent on every call), retry stacks that can reach 7–10 LLM calls on one bad
  substep, and full-prior-code retry prompts. The case's ~200k-token budget assumed a
  cloud mini-tier model and aggressive prompt economy; our local-Ollama, full-prompt design
  is far from it. `MAX_TOKENS_PER_RUN` exists but is unset by default — nothing currently
  bounds a runaway run.
- **JSON fragility taxes the Developer.** Small local models frequently return non-JSON or
  schema-invalid JSON, and each repair is another full Developer LLM call (18% of spend).
  This is the cost of insisting on structured output from models that are not reliably
  structured.
- **The RAG corpus is currently empty.** `knowledge_corpus_paths()` still references
  `crisp-dm-excerpt.md` and `ml-problem-approach-notes.md`, which were removed in a repo
  reorganization; only `titanic_experience.md` remains, and it is created only *after* a
  Titanic run. The retriever is sound but, for a fresh case, retrieves nothing. The Domain
  Expert is therefore less grounded than the architecture implies.
- **Baseline fallbacks are Titanic-specific.** The fixed fallback snippets impute
  `Age/Fare/Embarked` and engineer `FamilySize`; on House Prices or Disaster Tweets a
  *degraded* run would produce nonsensical preparation. The agent-authored path is general;
  the safety net is not.
- **No leaderboard submission.** We measure CV, not the public test set. CV ≥ 0.77 does not
  guarantee leaderboard ≥ 0.77, and the case explicitly asks for *observed* scores.

### 6.3 Framework reflection

CrewAI Flow gave us a clean role mapping and an explicit-enough loop graph, but its
`BaseModel` state copying required care (we keep the caller's object authoritative via
`object.__setattr__`), and several token-economy levers (per-call output caps, prompt-prefix
discipline) we had to build ourselves. LangGraph would have made the loop edges and partial
state propagation more first-class; for a team optimizing token cost, that explicitness might
have paid off.

---

## 7. Limitations and Threats to Validity

- **Single-dataset evidence.** All quantitative results are from one completed Titanic run on
  one backend (Ollama). Generality and cross-dataset cost claims are unsupported.
- **Stale measurement.** The measured run predates current code; reported costs may
  overstate the present system.
- **Backend confound.** Wall-clock is dominated by local model latency; a cloud backend would
  change time (and possibly JSON reliability) substantially without changing the architecture.
- **CV vs leaderboard.** Reported scores are cross-validated, not held-out leaderboard
  scores; optimism bias is possible.
- **Construct validity of "loop fired correctly."** Our one observed loop was erroneous, so we
  cannot yet evidence the system's core iterative claim.

---

## 8. Conclusion and Future Work

maads demonstrates that a role-specialized, process-faithful multi-agent system *can* execute
the full CRISP-DM cycle on a real Kaggle problem, produce a valid submission with a
competitive cross-validated score, and remain fully auditable — with agents that execute
rather than narrate and a Developer that genuinely debugs. It also demonstrates, just as
clearly, that the hard parts are **token economy** and **decision-timing correctness**: our
one fully measured run cost ~14× its budget and mis-reported its own success because it asked
a question before the answer existed.

The honest scorecard today: end-to-end run (yes), agent observability (yes), valid
submission beating the trivial baseline on CV (yes), architecture document (yes), per-agent
and per-provider token logging (yes); a correctly-firing-and-recovering loop (not yet
evidenced), three-dataset generality with recorded leaderboard scores (not yet), and a sane
token budget (not yet). The most valuable next experiments are therefore not new features but
*new evidence*: (1) a re-measured Titanic run to verify the single-call and Loop-C fixes; (2)
a forced, correct loop with recorded recovery; (3) House Prices and Disaster Tweets runs with
**submitted** leaderboard scores; (4) restoring the RAG corpus and generalizing the baseline
fallbacks; and (5) bringing a run under budget via shorter personas, tiered retry budgets,
and an enforced token cap. We would rather report these gaps plainly than a five-page success
story, because in an agentic data-science system the failures are where the engineering is.

---

## References

1. Chapman, P., Clinton, J., Kerber, R., Khabaza, T., Reinartz, T., Shearer, C., & Wirth, R.
   (2000). *CRISP-DM 1.0: Step-by-step data mining guide.* The CRISP-DM Consortium.
2. Olson, R. S., & Moore, J. H. (2016). *TPOT: A tree-based pipeline optimization tool for
   automating machine learning.* ICML AutoML Workshop.
3. Feurer, M., Klein, A., Eggensperger, K., Springenberg, J., Blum, M., & Hutter, F. (2015).
   *Efficient and robust automated machine learning (auto-sklearn).* NeurIPS.
4. Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023).
   *ReAct: Synergizing reasoning and acting in language models.* ICLR.
5. Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023).
   *Reflexion: Language agents with verbal reinforcement learning.* NeurIPS.
6. Hong, S., et al. (2024). *Data Interpreter: An LLM agent for data science.* arXiv:2402.18679.
7. Guo, S., et al. (2024). *DS-Agent: Automated data science by empowering large language
   models with case-based reasoning.* ICML.
8. Wu, Q., et al. (2023). *AutoGen: Enabling next-gen LLM applications via multi-agent
   conversation.* arXiv:2308.08155.
9. CrewAI. *CrewAI: Framework for orchestrating role-playing, autonomous AI agents.*
   https://docs.crewai.com
10. H2O.ai. *H2O AutoML: Scalable automatic machine learning.* https://docs.h2o.ai

*Reference details (venues/years) should be verified against the canonical sources before
submission.*
