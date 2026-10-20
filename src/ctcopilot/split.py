"""Time-based train / validation / test split on start_date."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TimeSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    # train: start_date < val_start; val: val_start <= start_date < test_start;
    # test: start_date >= test_start.
    val_start: pd.Timestamp
    test_start: pd.Timestamp


def drop_missing_start(studies: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove studies without a start date; return the rest and how many were dropped."""
    has_start = studies["start_date"].notna()
    return studies[has_start].copy(), int((~has_start).sum())


def time_split(
    studies: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15
) -> TimeSplit:
    """Split by start_date quantiles: earliest studies train, latest test.

    Studies sharing a start date always land in the same split, so the actual
    fractions can differ slightly from the requested ones.
    """
    if studies["start_date"].isna().any():
        raise ValueError("drop studies without start_date before splitting")
    if not 0 < train_frac < train_frac + val_frac < 1:
        raise ValueError("need 0 < train_frac < train_frac + val_frac < 1")

    dates = pd.to_datetime(studies["start_date"])
    val_start = dates.quantile(train_frac, interpolation="higher")
    test_start = dates.quantile(train_frac + val_frac, interpolation="higher")
    return TimeSplit(
        train=studies[dates < val_start],
        val=studies[(dates >= val_start) & (dates < test_start)],
        test=studies[dates >= test_start],
        val_start=val_start,
        test_start=test_start,
    )
