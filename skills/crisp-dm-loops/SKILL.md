# CRISP-DM Loop Contours

Fire back-edges only when triggers are present in state:

- **Loop A (2→1):** `data_quality_report.blockers` non-empty → return to 1.3
- **Loop B (4→3):** `validator_findings`, `degraded_flags`, or CV below threshold → return to Phase 3 (max 3×)
- **Loop C (5→1):** business success criteria not met → return to 1.3; halt if Loop A fired twice
- **Loop D (6→1):** optional after 6.4; experience feeds next run knowledge

Output directive JSON: `action` (advance|loop_back|halt), `loop_label`, `loop_to_phase`, `target_substep`, `reason`.
