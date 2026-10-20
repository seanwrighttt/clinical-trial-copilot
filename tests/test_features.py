import numpy as np
import pandas as pd
import pytest
from synthetic import synthetic_studies

from ctcopilot.features import (
    EXCLUDED_COLUMNS,
    SOURCE_COLUMNS,
    make_preprocessor,
    prepare_features,
)

REQUIRED_EXCLUSIONS = {
    "why_stopped",
    "has_results",
    "last_update_post_date",
    "primary_completion_date",
    "completion_date",
    "enrollment",
    "overall_status",
}


def test_required_columns_are_excluded() -> None:
    assert REQUIRED_EXCLUSIONS <= EXCLUDED_COLUMNS
    assert not EXCLUDED_COLUMNS & set(SOURCE_COLUMNS)


def test_feature_frame_has_no_excluded_columns() -> None:
    features = prepare_features(synthetic_studies())
    assert not EXCLUDED_COLUMNS & set(features.columns)
    for column in features.columns:
        for excluded in EXCLUDED_COLUMNS:
            assert excluded not in column, f"{column} looks derived from {excluded}"


def scramble_excluded(studies: pd.DataFrame) -> pd.DataFrame:
    """Overwrite every excluded column with values unrelated to the originals."""
    scrambled = studies.copy()
    rng = np.random.default_rng(42)
    for column in EXCLUDED_COLUMNS & set(studies.columns):
        scrambled[column] = rng.permutation(scrambled[column].to_numpy())
    scrambled["why_stopped"] = "something else"
    scrambled["enrollment"] = 999_999
    return scrambled


@pytest.mark.parametrize("blocks", [("structured",), ("text",), ("structured", "text")])
def test_excluded_columns_cannot_change_feature_matrix(blocks: tuple[str, ...]) -> None:
    """Leakage test: scrambling every excluded column leaves the matrix unchanged."""
    studies = synthetic_studies()
    preprocessor = make_preprocessor(blocks, dense=True).fit(prepare_features(studies))
    original = preprocessor.transform(prepare_features(studies))
    scrambled = preprocessor.transform(prepare_features(scramble_excluded(studies)))
    np.testing.assert_array_equal(original, scrambled)


def test_label_does_not_reach_features() -> None:
    studies = synthetic_studies()
    studies["label"] = 1
    assert "label" not in prepare_features(studies).columns


def test_structured_features() -> None:
    studies = synthetic_studies(n=3)
    studies["phases"] = [["PHASE2"], ["PHASE2", "PHASE3"], []]
    studies["intervention_types"] = [["DRUG"], ["DRUG", "BEHAVIORAL"], None]
    studies["conditions"] = [["a"], ["a", "b"], None]
    studies["sponsor_class"] = ["INDUSTRY", None, "OTHER"]
    studies["start_date"] = pd.to_datetime(["2010-05-01", "2015-01-01", "2020-12-31"]).date

    features = prepare_features(studies)
    assert features["phase_PHASE2"].tolist() == [1, 1, 0]
    assert features["phase_PHASE3"].tolist() == [0, 1, 0]
    assert features["intervention_BEHAVIORAL"].tolist() == [0, 1, 0]
    assert features["n_conditions"].tolist() == [1, 2, 0]
    assert features["sponsor_class"].tolist() == ["INDUSTRY", "MISSING", "OTHER"]
    assert features["start_year"].tolist() == [2010, 2015, 2020]


def test_feature_blocks_are_separate() -> None:
    features = prepare_features(synthetic_studies())
    n_structured = make_preprocessor(("structured",), dense=True).fit_transform(features).shape[1]
    n_text = make_preprocessor(("text",), dense=True).fit_transform(features).shape[1]
    n_both = make_preprocessor(("structured", "text"), dense=True).fit_transform(features).shape[1]
    assert n_both == n_structured + n_text


def test_rejects_unknown_block() -> None:
    with pytest.raises(ValueError):
        make_preprocessor(("enrollment",))
