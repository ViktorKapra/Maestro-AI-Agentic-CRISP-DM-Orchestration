# Leakage and Cross-Validation Discipline

- Fit preprocessors and encoders on training data only; apply the same transform to test.
- Never use the target or post-outcome columns as features.
- Use stratified K-fold for classification when classes are imbalanced.
- Report CV mean and std; do not claim leaderboard scores from CV.
- Flag any feature unavailable at prediction time.
