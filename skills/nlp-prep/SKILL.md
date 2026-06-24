# NLP Data Preparation

- Primary signal is often free text; keyword/location may be sparse or missing.
- Test set typically has no target column.
- TF-IDF + linear model is a strong baseline; avoid fine-tuning transformers unless required.
- Use the same vocabulary fit on train when transforming test.
- Handle empty strings; lowercase/normalize consistently.
