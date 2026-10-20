from datetime import date
from typing import Any

from ctcopilot.parser import parse_page, parse_study


def test_parse_page_returns_one_record_per_study(studies_page: dict[str, Any]) -> None:
    records = parse_page(studies_page)
    assert [r.nct_id for r in records] == [
        "NCT01074801",
        "NCT03919929",
        "NCT03554200",
        "NCT07521631",
        "NCT01285934",
    ]


def test_parse_terminated_study(studies_page: dict[str, Any]) -> None:
    record = {r.nct_id: r for r in parse_page(studies_page)}["NCT03554200"]
    assert record.brief_title == "EMPA Acute Heart Failure"
    assert record.overall_status == "TERMINATED"
    assert record.why_stopped == "COVID 19"
    assert record.phases == ["PHASE2"]
    assert record.conditions == ["Diabetes Mellitus, Type 2", "Acute Heart Failure"]
    assert record.interventions == ["Empagliflozin", "Placebo"]
    assert record.intervention_types == ["DRUG"]
    assert record.sponsor_name == "RWTH Aachen University"
    assert record.sponsor_class == "OTHER"
    assert record.start_date == date(2018, 6, 11)
    assert record.completion_date == date(2020, 10, 29)
    assert record.enrollment == 19
    assert record.allocation == "RANDOMIZED"
    assert record.masking == "DOUBLE"
    assert record.eligibility_criteria.startswith("Inclusion Criteria")


def test_parse_partial_dates_from_api(studies_page: dict[str, Any]) -> None:
    record = {r.nct_id: r for r in parse_page(studies_page)}["NCT01074801"]
    assert record.start_date_raw == "2010-03"
    assert record.start_date == date(2010, 3, 1)
    assert record.start_date_type is None
    assert record.completion_date == date(2010, 10, 1)
    assert record.completion_date_type == "ACTUAL"


def test_parse_missing_fields_become_none(studies_page: dict[str, Any]) -> None:
    record = {r.nct_id: r for r in parse_page(studies_page)}["NCT07521631"]
    assert record.detailed_description is None
    assert record.why_stopped is None


def test_parse_minimal_study() -> None:
    record = parse_study({"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}})
    assert record.nct_id == "NCT00000001"
    assert record.overall_status is None
    assert record.start_date is None
    assert record.phases == []
    assert record.interventions == []
    assert record.sponsor_name is None


def test_start_before_completion_where_both_exist(studies_page: dict[str, Any]) -> None:
    checked = 0
    for record in parse_page(studies_page):
        if record.start_date and record.completion_date:
            assert record.start_date <= record.completion_date, record.nct_id
            checked += 1
    assert checked > 0
