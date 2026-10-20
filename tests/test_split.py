import pandas as pd
import pytest
from synthetic import synthetic_studies

from ctcopilot.split import drop_missing_start, time_split


def test_drop_missing_start_counts_rows() -> None:
    studies = synthetic_studies(n=10)
    studies.loc[[2, 5], "start_date"] = None
    kept, dropped = drop_missing_start(studies)
    assert dropped == 2
    assert len(kept) == 8
    assert kept["start_date"].notna().all()


def test_split_is_ordered_by_start_date() -> None:
    split = time_split(synthetic_studies(n=200))
    train = pd.to_datetime(split.train["start_date"])
    val = pd.to_datetime(split.val["start_date"])
    test = pd.to_datetime(split.test["start_date"])

    assert train.max() < val.min()
    assert val.max() < test.min()
    assert train.max() < test.min()
    assert (train < split.val_start).all()
    assert (test >= split.test_start).all()


def test_split_covers_every_study_once() -> None:
    studies = synthetic_studies(n=200)
    split = time_split(studies)
    ids = pd.concat([split.train, split.val, split.test])["nct_id"]
    assert sorted(ids) == sorted(studies["nct_id"])
    assert len(split.train) > len(split.val) > 0
    assert len(split.test) > 0


def test_split_keeps_tied_dates_together() -> None:
    studies = synthetic_studies(n=20)
    studies["start_date"] = pd.Timestamp("2015-01-01").date()
    studies.loc[:9, "start_date"] = pd.Timestamp("2010-01-01").date()
    split = time_split(studies, train_frac=0.5, val_frac=0.25)
    for part in (split.train, split.val, split.test):
        assert pd.to_datetime(part["start_date"]).nunique() <= 1


def test_split_rejects_missing_start_dates() -> None:
    studies = synthetic_studies(n=10)
    studies.loc[0, "start_date"] = None
    with pytest.raises(ValueError):
        time_split(studies)
