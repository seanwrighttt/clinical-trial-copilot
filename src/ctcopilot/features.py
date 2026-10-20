"""Features knowable at registration time.

`prepare_features` builds model inputs from an explicit allow-list of study
columns, so a column cannot reach the model unless it is named here. Columns
in EXCLUDED_COLUMNS are known to leak the outcome; a test checks that none of
them can affect the feature matrix.
"""

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Recorded after the outcome, or only final ("ACTUAL") values are available.
EXCLUDED_COLUMNS = frozenset(
    {
        "overall_status",
        "why_stopped",
        "has_results",
        "last_update_post_date",
        "primary_completion_date",
        "primary_completion_date_raw",
        "primary_completion_date_type",
        "completion_date",
        "completion_date_raw",
        "completion_date_type",
        "start_date_type",
        # Almost always the ACTUAL enrollment for finished studies; see decision log.
        "enrollment",
        "enrollment_type",
    }
)

# Study columns that prepare_features reads. Nothing else is used.
SOURCE_COLUMNS = (
    "phases",
    "intervention_types",
    "sponsor_class",
    "allocation",
    "masking",
    "conditions",
    "start_date",
    "brief_title",
    "brief_summary",
)

# Values from the API's Phase and InterventionType enums (OpenAPI spec v2.0.5).
PHASES = ("EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA")
INTERVENTION_TYPES = (
    "BEHAVIORAL",
    "BIOLOGICAL",
    "COMBINATION_PRODUCT",
    "DEVICE",
    "DIAGNOSTIC_TEST",
    "DIETARY_SUPPLEMENT",
    "DRUG",
    "GENETIC",
    "PROCEDURE",
    "RADIATION",
    "OTHER",
)

CATEGORICAL_FEATURES = ["sponsor_class", "allocation", "masking"]
INDICATOR_FEATURES = [f"phase_{p}" for p in PHASES] + [
    f"intervention_{t}" for t in INTERVENTION_TYPES
]
NUMERIC_FEATURES = ["n_conditions", "start_year"]
TEXT_FEATURE = "text"

BLOCKS = ("structured", "text")
MISSING = "MISSING"


def _as_list(value: Any) -> list[str]:
    """DuckDB list columns arrive as lists, arrays or None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    return list(value)


def _indicators(values: pd.Series, vocabulary: Iterable[str], prefix: str) -> pd.DataFrame:
    sets = values.map(lambda v: set(_as_list(v)))
    return pd.DataFrame(
        {f"{prefix}_{term}": sets.map(lambda s, t=term: int(t in s)) for term in vocabulary},
        index=values.index,
    )


def prepare_features(studies: pd.DataFrame) -> pd.DataFrame:
    """Turn study rows into a flat frame of model inputs."""
    source = studies[list(SOURCE_COLUMNS)]
    categorical = source[CATEGORICAL_FEATURES].fillna(MISSING).astype(str)
    numeric = pd.DataFrame(
        {
            "n_conditions": source["conditions"].map(lambda v: len(_as_list(v))),
            "start_year": pd.to_datetime(source["start_date"]).dt.year.astype(float),
        },
        index=source.index,
    )
    text = (source["brief_title"].fillna("") + ". " + source["brief_summary"].fillna("")).rename(
        TEXT_FEATURE
    )
    return pd.concat(
        [
            categorical,
            _indicators(source["phases"], PHASES, "phase"),
            _indicators(source["intervention_types"], INTERVENTION_TYPES, "intervention"),
            numeric,
            text,
        ],
        axis=1,
    )


def make_preprocessor(blocks: Sequence[str], dense: bool = False) -> ColumnTransformer:
    """Column transformer for the chosen feature blocks ("structured", "text").

    `dense=True` returns a dense array, which HistGradientBoosting needs.
    """
    unknown = set(blocks) - set(BLOCKS)
    if unknown or not blocks:
        raise ValueError(f"blocks must be a non-empty subset of {BLOCKS}, got {blocks}")
    transformers = []
    if "structured" in blocks:
        transformers += [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("indicators", "passthrough", INDICATOR_FEATURES),
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ]
    if "text" in blocks:
        tfidf = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=5,
            max_features=2000,
            sublinear_tf=True,
        )
        transformers.append(("text", tfidf, TEXT_FEATURE))
    return ColumnTransformer(transformers, sparse_threshold=0.0 if dense else 0.3)
