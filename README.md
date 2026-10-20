# Clinical Trial Intelligence Copilot

A Python project that will ingest clinical trial records from the
ClinicalTrials.gov API v2 into DuckDB, train a calibrated baseline model to
predict early termination of trials, and later answer analyst questions over
trial text with retrieval-augmented generation that cites NCT IDs. Right now
the repository holds only the package skeleton, tests and CI.

## Quickstart

Requires Python 3.11+ and `make`. Inside a virtual environment:

```bash
make setup && make test
```

`make lint` runs ruff (lint and format check).

## Roadmap (not yet built)

- Ingestion from the ClinicalTrials.gov API v2 into DuckDB
- Feature engineering and a calibrated early-termination baseline with honest evaluation
- Retrieval-augmented Q&A over trial text, citing NCT IDs
- FastAPI service and a vector index (FAISS or Chroma)
