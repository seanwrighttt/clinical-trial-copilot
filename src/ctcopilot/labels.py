"""Target label for early termination.

TERMINATED = 1, COMPLETED = 0. Every other status is excluded: see
docs/decision-log.md for the reasoning.
"""

import pandas as pd

LABELS: dict[str, int] = {"TERMINATED": 1, "COMPLETED": 0}


def label_for_status(status: str | None) -> int | None:
    """1 for TERMINATED, 0 for COMPLETED, None for anything else."""
    if status is None:
        return None
    return LABELS.get(status)


def add_labels(studies: pd.DataFrame) -> pd.DataFrame:
    """Keep only labelled studies and add an integer `label` column."""
    labels = studies["overall_status"].map(label_for_status)
    labelled = studies[labels.notna()].copy()
    labelled["label"] = labels[labels.notna()].astype(int)
    return labelled
