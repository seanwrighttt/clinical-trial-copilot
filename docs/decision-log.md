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
