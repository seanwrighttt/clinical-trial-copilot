# Clinical Trial Intelligence Copilot

A Python project that ingests clinical trial records from the
ClinicalTrials.gov API v2 into DuckDB and trains baseline models to predict
whether a trial terminates early, evaluated on a time-based split with
calibration checks. Later it will answer analyst questions over trial text
with retrieval-augmented generation that cites NCT IDs. Right now the
ingestion layer and the baseline termination model are built.

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

## Termination model

```bash
python -m ctcopilot.train
```

- **Label:** TERMINATED = 1, COMPLETED = 0. Other statuses are excluded.
- **Features:** only information available at registration time. Structured:
  phase, intervention types, sponsor class, allocation, masking, number of
  conditions, start year. Text: TF-IDF on brief title + brief summary.
  Enrollment is excluded because the registry keeps the actual enrollment, not
  the planned figure.
- **Split:** by start date: earliest 70% train, next 15% validation, latest 15%
  test.
- **Models:** two dummy baselines, logistic regression and
  HistGradientBoosting. Hyperparameters are picked on validation PR AUC; models
  are then refit on train + validation and scored once on test.

The run writes [docs/results.md](docs/results.md) (all tables) and
[docs/calibration_test.png](docs/calibration_test.png).

## Results

From one run on 2026-10-20 against the ClinicalTrials.gov data pulled the same
day; full tables, including per-phase and per-sponsor-class results, are in
[docs/results.md](docs/results.md).

**Data:** 4,548 labelled studies; 30 dropped for missing start date; 4,518 used.

| Split | start_date range | n | terminated rate |
|---|---|---|---|
| train | 1972-01-01 to 2015-09-30 | 3153 | 0.112 |
| val | 2015-10-01 to 2019-09-24 | 687 | 0.122 |
| test | 2019-09-30 to 2026-06-12 | 678 | 0.100 |

**Test period, 95% bootstrap CIs:**

| Model | Features | ROC AUC | PR AUC | Brier |
|---|---|---|---|---|
| Dummy: majority class | - | 0.500 | 0.100 (0.078-0.124) | 0.100 (0.078-0.124) |
| Dummy: prior rate | - | 0.500 | 0.100 (0.078-0.124) | 0.090 (0.073-0.109) |
| Logistic regression | structured | 0.499 (0.431-0.572) | 0.111 (0.084-0.168) | 0.092 (0.076-0.110) |
| Logistic regression | text | 0.653 (0.585-0.718) | 0.214 (0.146-0.311) | 0.090 (0.073-0.109) |
| Logistic regression | both | 0.634 (0.564-0.703) | 0.202 (0.136-0.299) | 0.091 (0.076-0.106) |
| HistGradientBoosting | structured | 0.465 (0.400-0.534) | 0.092 (0.071-0.123) | 0.105 (0.088-0.123) |
| HistGradientBoosting | text | 0.589 (0.521-0.658) | 0.132 (0.100-0.196) | 0.102 (0.082-0.123) |
| HistGradientBoosting | both | 0.598 (0.528-0.673) | 0.154 (0.110-0.230) | 0.094 (0.077-0.112) |

**How to read this:**

- The signal is weak. Logistic regression with text roughly doubles PR AUC
  over the 0.100 base rate, but the confidence intervals are wide: the test set
  has only 68 terminated trials.
- No model has a better Brier score than the prior-rate baseline (0.090).
- The structured features alone do no better than chance on the test period.
  Nearly all the signal comes from the text block.
- The text terms most associated with termination (listed in
  docs/results.md) are mostly names of drug programs that were discontinued
  during the training period (for example rimonabant, tesaglitazar, inhaled
  insulin). The text model largely learns which programs failed before, not
  general features of trial design.
- Registry text can be edited after a trial stops, so some leakage through the
  text cannot be ruled out; see the decision log.
- Recent start years are right-censored: only trials that have already ended
  can be labelled.

## Roadmap (not yet built)

- Retrieval-augmented Q&A over trial text, citing NCT IDs
- FastAPI service and a vector index (FAISS or Chroma)
