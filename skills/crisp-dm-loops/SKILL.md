# CRISP-DM Loop Contours

Fire back-edges only when triggers are present in state:

- **Loop A (2→1):** Fire only when **actionable** quality issues remain after considering `quality_gate` (`na_means_absent`, `domain_data_quality_flags`, `loop_a_recommendation`) — not when blockers are only structural absence already documented. Return to 1.3.
- **Loop B (4→3):** `validator_findings`, `degraded_flags`, or CV below threshold → return to Phase 3 (max 3×)
- **Loop C (5→1):** business success criteria not met → return to 1.3; halt if Loop A fired twice
- **Loop D (6→1):** optional after 6.4; experience feeds next run knowledge

Output directive JSON: `action` (advance|loop_back|halt), `loop_label`, `loop_to_phase`, `target_substep`, `reason`.
