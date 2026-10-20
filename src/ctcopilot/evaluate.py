"""Metrics, bootstrap confidence intervals and the calibration plot."""

from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only; no display needed
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score  # noqa: E402

METRICS = ("roc_auc", "pr_auc", "brier")


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    """ROC AUC, PR AUC (average precision) and Brier score."""
    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
    }


def bootstrap_ci(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_resamples: int = 1000,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """Percentile bootstrap interval for each metric, resampling studies.

    Resamples that contain only one class are skipped, since ROC AUC is
    undefined for them.
    """
    rng = np.random.default_rng(seed)
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    samples: dict[str, list[float]] = {m: [] for m in METRICS}
    for _ in range(n_resamples):
        idx = rng.integers(0, len(y_true), len(y_true))
        if y_true[idx].min() == y_true[idx].max():
            continue
        for name, value in compute_metrics(y_true[idx], y_prob[idx]).items():
            samples[name].append(value)
    tail = (1 - level) / 2 * 100
    return {
        name: (float(np.percentile(v, tail)), float(np.percentile(v, 100 - tail)))
        for name, v in samples.items()
    }


def plot_calibration(
    y_true: np.ndarray,
    probabilities: Mapping[str, np.ndarray],
    path: Path,
    title: str,
    n_bins: int = 10,
) -> None:
    """Reliability diagram with quantile bins, one line per model."""
    fig, ax = plt.subplots(figsize=(6, 6))
    upper = max(float(np.max(p)) for p in probabilities.values())
    ax.plot([0, upper], [0, upper], linestyle="--", color="grey", label="Perfectly calibrated")
    for name, y_prob in probabilities.items():
        frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")
        ax.plot(mean_pred, frac_pos, marker="o", label=name)
    ax.set_xlabel("Mean predicted probability of termination")
    ax.set_ylabel("Observed fraction terminated")
    ax.set_title(title)
    ax.legend(loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
