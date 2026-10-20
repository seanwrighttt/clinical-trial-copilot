import pandas as pd
import pytest

from ctcopilot.labels import add_labels, label_for_status


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("TERMINATED", 1),
        ("COMPLETED", 0),
        ("WITHDRAWN", None),
        ("UNKNOWN", None),
        ("SUSPENDED", None),
        ("RECRUITING", None),
        ("ACTIVE_NOT_RECRUITING", None),
        (None, None),
    ],
)
def test_label_for_status(status: str | None, expected: int | None) -> None:
    assert label_for_status(status) == expected


def test_add_labels_keeps_only_terminated_and_completed() -> None:
    studies = pd.DataFrame(
        {
            "nct_id": ["A", "B", "C", "D", "E"],
            "overall_status": ["TERMINATED", "COMPLETED", "WITHDRAWN", "UNKNOWN", None],
        }
    )
    labelled = add_labels(studies)
    assert labelled["nct_id"].tolist() == ["A", "B"]
    assert labelled["label"].tolist() == [1, 0]
    assert labelled["label"].dtype == int
