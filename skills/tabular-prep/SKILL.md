# Tabular Data Preparation

- Profile dtypes and missingness before transforming.
- Impute numeric with median/mean; categorical with mode or "Unknown".
- Encode categoricals consistently across train and test.
- Align train/test columns; test may lack target column.
- Drop high-cardinality IDs from features; keep ID in test for submission only.
