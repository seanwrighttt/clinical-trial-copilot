# Clinical Trial Intelligence Copilot

## What this is
A Python project that ingests clinical trial data from the ClinicalTrials.gov
API v2 into DuckDB, predicts early termination of trials with a calibrated ML
baseline, and (later) answers analyst questions over trial text with
retrieval-augmented generation (RAG), citing NCT IDs. It is a portfolio
project for a data science role in an investment bank, so engineering
discipline and honest evaluation matter more than headline accuracy.

## Stack
Python 3.11+, pydantic, httpx, DuckDB, pandas, scikit-learn, pytest, ruff,
GitHub Actions. FastAPI and a vector index (FAISS or Chroma) come later.

## Conventions
- Source in `src/ctcopilot/`, tests in `tests/`, config in `pyproject.toml`.
- Type hints everywhere; keep functions small and testable.
- Tests must run offline: use saved JSON fixtures in `tests/fixtures/`, never
  the live API.
- Never commit raw data or secrets; `data/` and `.env` are git-ignored.
- Small, focused commits with clear messages.
- Verify API parameters against the official docs/OpenAPI spec; do not guess.

## Honesty rules (important)
- No placeholder or invented metrics anywhere. Every number in the README or
  docs must come from a real run in this repo.
- The README describes only what the code actually does today. Planned work
  goes under a "Roadmap" heading, clearly labelled as not built.
- Record design decisions in `docs/decision-log.md` as we make them.

## Working style
- Explain what you are about to do before large changes.
- I need to be able to explain every file in an interview, so keep code
  readable and prefer simple solutions over clever ones.