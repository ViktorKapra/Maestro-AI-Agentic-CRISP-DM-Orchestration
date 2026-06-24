# Developer Debug Rubric

1. Classify error: syntax, schema, shape, type, timeout, leakage.
2. Read stderr and column list from state; do not invent column names.
3. Propose minimal fix; re-run under retry budget (max 3).
4. If STUCK, return clear diagnosis for PM Loop B signal.
5. Authored code must print one JSON line on stdout when contract requires it.
