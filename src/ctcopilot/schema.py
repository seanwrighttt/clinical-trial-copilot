"""Flattened study record: one row per trial."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

_PARTIAL_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def parse_partial_date(value: object) -> date | None:
    """Parse the API's `yyyy`, `yyyy-MM` or `yyyy-MM-dd` dates.

    Missing parts default to the first month or day, so "2019-03" becomes
    2019-03-01. The original string is kept separately in the `*_raw` fields
    so the loss of precision stays visible.
    """
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"expected a date string, got {value!r}")
    match = _PARTIAL_DATE.match(value.strip())
    if match is None:
        raise ValueError(f"unrecognised date format: {value!r}")
    year, month, day = match.groups()
    return date(int(year), int(month or 1), int(day or 1))


PartialDate = Annotated[date | None, BeforeValidator(parse_partial_date)]


class StudyRecord(BaseModel):
    nct_id: str
    brief_title: str | None = None
    official_title: str | None = None

    overall_status: str | None = None
    why_stopped: str | None = None
    has_results: bool | None = None

    study_type: str | None = None
    phases: list[str] = []
    conditions: list[str] = []
    interventions: list[str] = []
    intervention_types: list[str] = []

    sponsor_name: str | None = None
    sponsor_class: str | None = None

    # Each date has its parsed value, the original string and the API's date
    # type (ACTUAL or ESTIMATED; missing on some older records).
    start_date: PartialDate = None
    start_date_raw: str | None = None
    start_date_type: str | None = None
    primary_completion_date: PartialDate = None
    primary_completion_date_raw: str | None = None
    primary_completion_date_type: str | None = None
    completion_date: PartialDate = None
    completion_date_raw: str | None = None
    completion_date_type: str | None = None
    last_update_post_date: PartialDate = None

    enrollment: int | None = None
    enrollment_type: str | None = None
    allocation: str | None = None
    masking: str | None = None

    brief_summary: str | None = None
    detailed_description: str | None = None
    eligibility_criteria: str | None = None
