# Decision log

Design decisions, newest last. Each entry says what was chosen and why.

## 2026-10-20: Packaging with setuptools and a `[dev]` extra

- **Decision:** Build with setuptools (`pyproject.toml`, src layout). Dev tools
  (pytest, ruff) go in an optional `[dev]` extra, installed with
  `pip install -e ".[dev]"`.
- **Why:** setuptools is the default, widely understood backend and needs no
  extra tooling. The extra keeps runtime dependencies separate from dev tools
  without a second requirements file, and CI and local setup use the same
  command (`make setup`).

## 2026-10-20: Therapeutic area is configuration

- **Decision:** The search conditions (default: diabetes, obesity), phases
  (PHASE2, PHASE3) and study type (INTERVENTIONAL) are fields of
  `ctcopilot.config.Settings`, not hard-coded in the client.
- **Why:** The pipeline should work for other disease areas without code
  changes, and the query that defines the dataset is visible in one place.

## 2026-10-20: API query parameters

- **Decision:** Use `/studies` with `query.cond` for conditions, joined with
  `OR`. Phase and study type go in `filter.advanced` as
  `AREA[Phase](PHASE2 OR PHASE3) AND AREA[StudyType]INTERVENTIONAL`. Request
  only `fields=protocolSection|hasResults`.
- **Why:** The OpenAPI spec (v2.0.5) has no dedicated phase or study-type
  filter parameter, so they go through Essie `AREA[]` expressions. `query.cond`
  searches the "Conditions or disease" area: conditions, titles, condition MeSH
  terms and keywords. The results section is large and not needed yet.
- **Consequence:** A study matches if *any* of its phases is listed, so
  PHASE1/PHASE2 studies are included. Later analysis may need to filter on the
  `phases` column.

## 2026-10-20: Raw page cache

- **Decision:** Cache every raw API page as JSON under
  `data/raw/<hash of query params>/page_NNNN.json`. Re-runs read from the cache.
  `--refresh` forces new API calls.
- **Why:** Re-runs and debugging don't re-hit the API, and the exact raw input
  behind the database is kept on disk.
- **Limitation:** A cached run is a snapshot of when it was fetched. If only
  some pages are cached, the next page is requested with a stored
  `nextPageToken`, which may have expired. Use `--refresh` for a clean pull.

## 2026-10-20: Rate limiting and retries

- **Decision:** Wait at least 1 second between requests. Retry on HTTP 429,
  500, 502, 503, 504 and transport errors up to 5 times, with exponential
  backoff starting at 2 s (capped at 60 s), honouring a numeric `Retry-After`.
- **Why:** The docs pages I could fetch did not state a rate limit, so a
  conservative fixed interval is the polite default.

## 2026-10-20: Partial dates

- **Decision:** Parse `yyyy`, `yyyy-MM` and `yyyy-MM-dd` into a `date`,
  defaulting missing parts to the first month/day. Keep the original string in
  `*_raw` and the API date type (ACTUAL/ESTIMATED) in `*_type`. Malformed dates
  raise an error rather than becoming None.
- **Why:** DuckDB date arithmetic needs a real date, and keeping the raw string
  keeps the precision loss visible. The date type matters for termination
  modelling, because ongoing trials have estimated completion dates. Raising on
  malformed input surfaces data problems instead of hiding them as missing values.

## 2026-10-20: Storage

- **Decision:** One DuckDB table, `studies`, with `nct_id` as primary key, loaded
  with `INSERT OR REPLACE`. Lists (phases, conditions, interventions) are stored
  as `VARCHAR[]`.
- **Why:** Loading is idempotent: re-running never duplicates a study, and a
  study's latest version replaces the old one.

## 2026-10-20: Termination label

- **Decision:** `TERMINATED` = 1, `COMPLETED` = 0. All other statuses are
  excluded from training and evaluation.
- **Why:**
  - `WITHDRAWN` studies stopped before enrolling anyone. That is a different
    event (a trial that never ran) from stopping a running trial early, so it
    is neither a clean positive nor a negative.
  - `UNKNOWN` means the record's status has not been verified for over two
    years, so the real outcome is unknown.
  - `RECRUITING`, `ACTIVE_NOT_RECRUITING`, `NOT_YET_RECRUITING`,
    `ENROLLING_BY_INVITATION` and `SUSPENDED` have no outcome yet. Treating
    them as 0 would label trials that may still terminate as "completed".
- **Consequence:** Recent start years are right-censored. Among recently
  started studies, the ones that already have an outcome lean towards those
  that finished or stopped quickly. The class balance of the latest period
  should be read with that in mind.

## 2026-10-20: Registration-time features only

- **Decision:** The feature builder reads an explicit allow-list of columns:
  phases, intervention types, sponsor class, allocation, masking, conditions
  (count), start date (year), brief title and brief summary. Excluded:
  `why_stopped`, `has_results`, `last_update_post_date`, all completion dates
  and their types, `start_date_type`, `enrollment` and `enrollment_type`. A
  test scrambles every excluded column and checks that the feature matrix does
  not change.
- **Enrollment:** Of the 4,548 labelled studies, `enrollment_type` was ACTUAL
  for 4,133, ESTIMATED for 130 and missing for 285 (checked on the 2026-10-20
  pull). The registry overwrites the planned enrollment with the actual one, so
  planned enrollment is effectively not available. Keeping enrollment only when
  it is ESTIMATED would leak through missingness: a finished study still marked
  ESTIMATED is a record that was not updated, which is itself related to the
  outcome. So enrollment is excluded entirely. Getting true planned enrollment
  would need the ClinicalTrials.gov record version history.
- **Start year:** `start_date_type` was ACTUAL for 1,775 labelled studies and
  missing for 2,773, so many start dates are actual rather than planned. The
  year is coarse and close to registration time, so it is kept. The type column
  is excluded because its missingness tracks record age and updates.
- **Text:** TF-IDF (1–2 grams, min_df 5, max 2,000 terms, English stop words)
  on brief title + brief summary, as a separate block so it can be ablated.
- **Known limitation:** The API returns the *latest* version of each record,
  and sponsors can edit the text after a trial stops. For example,
  NCT04291703's summary says it "was terminated approximately 13 months after
  the first participant enrolled". Phrases like this are rare (the title or
  summary contains "terminat" in 29 of the 4,548 labelled studies, 11 of them
  terminated), but
  some leakage through edited text cannot be ruled out without version history.

## 2026-10-20: Time-based split

- **Decision:** After dropping studies with no start date, split on start_date
  quantiles: earliest 70% train, next 15% validation, latest 15% test. Studies
  that share a start date always go to the same split.
- **Why:** A random split would let the model learn from trials that started
  after the ones it is scored on. A time split mimics using the model on new
  registrations.

## 2026-10-20: Model selection and evaluation

- **Decision:** Baselines are DummyClassifier `most_frequent` and `prior`. The
  models are logistic regression (C in {0.01, 0.1, 1}) and
  HistGradientBoosting (learning rate in {0.03, 0.1}, max depth in {3, None},
  200 iterations). For each model and feature block, pick the hyperparameters
  with the best validation PR AUC, refit on train + validation, and score the
  test period once.
- **Metrics:** ROC AUC, PR AUC (average precision; the main metric because the
  positive class is rare), Brier score, and a quantile-binned reliability
  diagram. 95% CIs come from a 1,000-resample percentile bootstrap over test
  studies. Subgroup metrics are shown only where a group has at least 5 studies
  of each class.
- **No class weighting:** Reweighting classes would distort the predicted
  probabilities, and calibration is one of the things being evaluated.
