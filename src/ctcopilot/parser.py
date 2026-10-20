"""Turn nested API study JSON into flat `StudyRecord`s.

Field paths follow the API's study data structure (see /studies/metadata).
"""

from typing import Any

from ctcopilot.schema import StudyRecord


def _get(data: dict[str, Any], *keys: str) -> Any:
    """Follow nested keys, returning None as soon as one is missing."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_study(study: dict[str, Any]) -> StudyRecord:
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    sponsor = _get(protocol, "sponsorCollaboratorsModule", "leadSponsor") or {}
    interventions = _get(protocol, "armsInterventionsModule", "interventions") or []

    def date_fields(prefix: str, struct_key: str) -> dict[str, Any]:
        raw = _get(status, struct_key, "date")
        return {
            prefix: raw,
            f"{prefix}_raw": raw,
            f"{prefix}_type": _get(status, struct_key, "type"),
        }

    return StudyRecord(
        nct_id=ident["nctId"],
        brief_title=ident.get("briefTitle"),
        official_title=ident.get("officialTitle"),
        overall_status=status.get("overallStatus"),
        why_stopped=status.get("whyStopped"),
        has_results=study.get("hasResults"),
        study_type=design.get("studyType"),
        phases=design.get("phases", []),
        conditions=_get(protocol, "conditionsModule", "conditions") or [],
        interventions=[i["name"] for i in interventions if i.get("name")],
        intervention_types=sorted({i["type"] for i in interventions if i.get("type")}),
        sponsor_name=sponsor.get("name"),
        sponsor_class=sponsor.get("class"),
        **date_fields("start_date", "startDateStruct"),
        **date_fields("primary_completion_date", "primaryCompletionDateStruct"),
        **date_fields("completion_date", "completionDateStruct"),
        last_update_post_date=_get(status, "lastUpdatePostDateStruct", "date"),
        enrollment=_get(design, "enrollmentInfo", "count"),
        enrollment_type=_get(design, "enrollmentInfo", "type"),
        allocation=_get(design, "designInfo", "allocation"),
        masking=_get(design, "designInfo", "maskingInfo", "masking"),
        brief_summary=_get(protocol, "descriptionModule", "briefSummary"),
        detailed_description=_get(protocol, "descriptionModule", "detailedDescription"),
        eligibility_criteria=_get(protocol, "eligibilityModule", "eligibilityCriteria"),
    )


def parse_page(page: dict[str, Any]) -> list[StudyRecord]:
    return [parse_study(study) for study in page.get("studies", [])]
