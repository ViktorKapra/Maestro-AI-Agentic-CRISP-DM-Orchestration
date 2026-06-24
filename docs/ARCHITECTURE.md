# maads architecture

## Overview

maads runs a CRISP-DM pipeline using **CrewAI Flow** as the workflow engine and **phase-scoped crews** for agent collaboration. Shared run state lives in `CrispDMState`; deterministic Python execution stays in `capabilities/`.

## Control flow

```mermaid
flowchart TD
    CLI[python -m maads run] --> Flow[CrispDMFlow.kickoff]
    Flow --> P1[phase_1 Business Understanding]
    P1 --> P2[phase_2 Data Understanding]
    P2 --> C31[checkpoint_3_1 PM router]
    C31 -->|loop A| P1
    C31 -->|advance| P3[phase_3 Data Preparation]
    P3 --> P4[phase_4 Modeling]
    P4 --> C51[checkpoint_5_1 PM router]
    C51 -->|loop B| P3
    C51 -->|advance| P5[phase_5 Evaluation]
    P5 --> C52[checkpoint_5_2 PM router]
    C52 -->|loop C| P1
    C52 -->|advance| P5T[phase_5_tail]
    P5T --> P6[phase_6 Deployment]
    P6 --> Done[complete]
```

## Module layout

| Path | Role |
|------|------|
| `flow/crisp_dm_flow.py` | `@start` / `@listen` / `@router` flow graph |
| `flow/phase_runner.py` | Shared substep dispatch, advance, loops, caps |
| `flow/routers.py` | PM checkpoint routing helpers |
| `flow/tracing.py` | Trace + status flush hooks for flow steps |
| `crews/*_crew/` | Phase-scoped `@CrewBase` crews with YAML config |
| `capabilities/` | Sandbox execution + JSON apply |
| `state.py` | `CrispDMState` — single source of truth |

## Substep dispatch

Each substep:

1. `capabilities.execution_evidence` (when applicable)
2. Phase crew `kickoff_substep` → one-agent Crew kickoff
3. `capabilities.apply_response`

## Artifacts

Unchanged: `status.json`, `process.json`, `state.json`, `trace/` under `artifacts/<case>/runs/<run_id>/`.

## CLI

- `python -m maads run --case titanic` — runs via `CrispDMFlow`
- `python -m maads flow plot` — HTML graph of `CrispDMFlow`
