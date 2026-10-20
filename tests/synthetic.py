"""Small synthetic study tables for offline model tests."""

import numpy as np
import pandas as pd

PHASE_OPTIONS = [["PHASE2"], ["PHASE3"], ["PHASE2", "PHASE3"]]


def synthetic_studies(n: int = 60, seed: int = 0) -> pd.DataFrame:
    """Rows shaped like the `studies` table, with random but valid values."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2000-01-01") + pd.to_timedelta(rng.integers(0, 8000, n), unit="D")
    status = rng.choice(["TERMINATED", "COMPLETED"], n, p=[0.3, 0.7])
    words = np.array(["insulin", "glucose", "weight", "placebo", "dose", "obesity", "diet"])
    return pd.DataFrame(
        {
            "nct_id": [f"NCT{i:08d}" for i in range(n)],
            "brief_title": [" ".join(rng.choice(words, 4)) for _ in range(n)],
            "brief_summary": [" ".join(rng.choice(words, 12)) for _ in range(n)],
            "overall_status": status,
            "why_stopped": np.where(status == "TERMINATED", "low enrollment", None),
            "has_results": rng.choice([True, False], n),
            "phases": [PHASE_OPTIONS[k] for k in rng.integers(0, len(PHASE_OPTIONS), n)],
            "conditions": [["Diabetes"] * int(k) for k in rng.integers(1, 4, n)],
            "intervention_types": [
                ["DRUG"] if k else ["DRUG", "OTHER"] for k in rng.integers(0, 2, n)
            ],
            "sponsor_class": rng.choice(["INDUSTRY", "OTHER", None], n),
            "allocation": rng.choice(["RANDOMIZED", "NA", None], n),
            "masking": rng.choice(["NONE", "DOUBLE", "QUADRUPLE"], n),
            "start_date": start.date,
            "start_date_type": rng.choice(["ACTUAL", None], n),
            "primary_completion_date": (start + pd.Timedelta(days=400)).date,
            "primary_completion_date_type": "ACTUAL",
            "completion_date": (start + pd.Timedelta(days=500)).date,
            "completion_date_type": "ACTUAL",
            "last_update_post_date": (start + pd.Timedelta(days=900)).date,
            "enrollment": rng.integers(0, 500, n),
            "enrollment_type": rng.choice(["ACTUAL", "ESTIMATED"], n),
        }
    )
