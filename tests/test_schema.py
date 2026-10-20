from datetime import date

import pytest

from ctcopilot.schema import StudyRecord, parse_partial_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2019-03-15", date(2019, 3, 15)),
        ("2019-03", date(2019, 3, 1)),
        ("2019", date(2019, 1, 1)),
        (None, None),
    ],
)
def test_parse_partial_date(raw: str | None, expected: date | None) -> None:
    assert parse_partial_date(raw) == expected


@pytest.mark.parametrize("raw", ["March 2019", "2019-3", "19-03-01", "2019-13"])
def test_parse_partial_date_rejects_malformed(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_partial_date(raw)


def test_record_requires_only_nct_id() -> None:
    record = StudyRecord(nct_id="NCT00000001")
    assert record.start_date is None
    assert record.phases == []
