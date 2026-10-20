# Clinical Trial Intelligence Copilot

A Python project that ingests clinical trial records from the
ClinicalTrials.gov API v2 into DuckDB. It will later train a calibrated
baseline model to predict early termination of trials, and answer analyst
questions over trial text with retrieval-augmented generation that cites NCT
IDs. Right now only the ingestion layer is built.

## Quickstart

Requires Python 3.11+ and `make`. Inside a virtual environment:

```bash
make setup && make test
```

`make lint` runs ruff (lint and format check).

## Ingestion

```bash
python -m ctcopilot.ingest            # uses cached pages in data/raw/ if present
python -m ctcopilot.ingest --refresh  # call the API again
```

This fetches Phase 2/3 interventional studies matching the configured
conditions (default: diabetes, obesity; see `src/ctcopilot/config.py`). Each
raw page is cached to `data/raw/`, and the flattened records are loaded into
the `studies` table in `data/trials.duckdb`, keyed on `nct_id`. Design choices
are recorded in [docs/decision-log.md](docs/decision-log.md).

## Roadmap (not yet built)

- Feature engineering and a calibrated early-termination baseline with honest evaluation
- Retrieval-augmented Q&A over trial text, citing NCT IDs
- FastAPI service and a vector index (FAISS or Chroma)
