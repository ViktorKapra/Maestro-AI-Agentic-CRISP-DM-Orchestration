# Disaster Tweets — domain notes

Binary classification: tweet describes a real disaster or not. Primary feature is `text`; `keyword` and `location` are weak and often missing.

NLP representation: TF-IDF + logistic regression is appropriate. Test set has no target column.

Metric: F1. Class imbalance possible — use stratified CV.
