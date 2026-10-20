from pathlib import Path
from typing import Any

from ctcopilot.parser import parse_page
from ctcopilot.schema import StudyRecord
from ctcopilot.store import connect, count_studies, upsert_studies


def test_loading_twice_does_not_duplicate(tmp_path: Path, studies_page: dict[str, Any]) -> None:
    records = parse_page(studies_page)
    con = connect(tmp_path / "trials.duckdb")
    upsert_studies(con, records)
    upsert_studies(con, records)

    assert count_studies(con) == len(records)
    distinct = con.execute("SELECT count(DISTINCT nct_id) FROM studies").fetchone()[0]
    assert distinct == len(records)


def test_upsert_replaces_existing_row(tmp_path: Path) -> None:
    con = connect(tmp_path / "trials.duckdb")
    upsert_studies(con, [StudyRecord(nct_id="NCT00000001", overall_status="RECRUITING")])
    upsert_studies(con, [StudyRecord(nct_id="NCT00000001", overall_status="TERMINATED")])

    rows = con.execute("SELECT nct_id, overall_status FROM studies").fetchall()
    assert rows == [("NCT00000001", "TERMINATED")]


def test_round_trip_keeps_lists_and_dates(tmp_path: Path, studies_page: dict[str, Any]) -> None:
    con = connect(tmp_path / "trials.duckdb")
    upsert_studies(con, parse_page(studies_page))

    phases, start = con.execute(
        "SELECT phases, start_date FROM studies WHERE nct_id = 'NCT03919929'"
    ).fetchone()
    assert phases == ["PHASE2", "PHASE3"]
    assert str(start) == "2019-05-03"
