"""DuckDB storage for study records, upserted on nct_id."""

from collections.abc import Iterable
from pathlib import Path

import duckdb

from ctcopilot.schema import StudyRecord

CREATE_STUDIES_TABLE = """
CREATE TABLE IF NOT EXISTS studies (
    nct_id VARCHAR PRIMARY KEY,
    brief_title VARCHAR,
    official_title VARCHAR,
    overall_status VARCHAR,
    why_stopped VARCHAR,
    has_results BOOLEAN,
    study_type VARCHAR,
    phases VARCHAR[],
    conditions VARCHAR[],
    interventions VARCHAR[],
    intervention_types VARCHAR[],
    sponsor_name VARCHAR,
    sponsor_class VARCHAR,
    start_date DATE,
    start_date_raw VARCHAR,
    start_date_type VARCHAR,
    primary_completion_date DATE,
    primary_completion_date_raw VARCHAR,
    primary_completion_date_type VARCHAR,
    completion_date DATE,
    completion_date_raw VARCHAR,
    completion_date_type VARCHAR,
    last_update_post_date DATE,
    enrollment INTEGER,
    enrollment_type VARCHAR,
    allocation VARCHAR,
    masking VARCHAR,
    brief_summary VARCHAR,
    detailed_description VARCHAR,
    eligibility_criteria VARCHAR
)
"""

COLUMNS = list(StudyRecord.model_fields)


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(CREATE_STUDIES_TABLE)
    return con


def upsert_studies(con: duckdb.DuckDBPyConnection, records: Iterable[StudyRecord]) -> int:
    """Insert records, replacing any existing row with the same nct_id.

    Returns the number of distinct studies written. If the same nct_id appears
    twice in `records`, the last one wins.
    """
    by_id = {record.nct_id: record for record in records}
    if not by_id:
        return 0
    rows = [[getattr(record, column) for column in COLUMNS] for record in by_id.values()]
    placeholders = ", ".join("?" for _ in COLUMNS)
    con.executemany(
        f"INSERT OR REPLACE INTO studies ({', '.join(COLUMNS)}) VALUES ({placeholders})",
        rows,
    )
    return len(by_id)


def count_studies(con: duckdb.DuckDBPyConnection) -> int:
    return con.execute("SELECT count(*) FROM studies").fetchone()[0]
