"""Train and evaluate the baseline termination models.

Usage: python -m ctcopilot.train

Reads the `studies` table, labels TERMINATED vs COMPLETED, splits by start
date, picks hyperparameters on the validation period, refits on train +
validation and scores the test period once. Writes docs/results.md and
docs/calibration_test.png.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ctcopilot.config import Settings
from ctcopilot.evaluate import bootstrap_ci, compute_metrics, plot_calibration
from ctcopilot.features import make_preprocessor, prepare_features
from ctcopilot.labels import add_labels
from ctcopilot.split import TimeSplit, drop_missing_start, time_split

DOCS_DIR = Path("docs")
BLOCK_SETS = {
    "structured": ("structured",),
    "text": ("text",),
    "both": ("structured", "text"),
}
# Small hyperparameter grids, chosen on validation PR AUC.
LOGREG_GRID = [{"C": c} for c in (0.01, 0.1, 1.0)]
HGB_GRID = [{"learning_rate": lr, "max_depth": depth} for lr in (0.03, 0.1) for depth in (3, None)]
MIN_CLASS_COUNT_FOR_SUBGROUP = 5
MISSING_GROUP = "(missing)"


@dataclass
class Result:
    name: str
    params: dict[str, Any]
    val_metrics: dict[str, float] | None
    test_metrics: dict[str, float]
    test_ci: dict[str, tuple[float, float]]
    test_prob: np.ndarray
    model: Pipeline | None = None


def load_studies(db_path: Path) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute("SELECT * FROM studies").df()
    finally:
        con.close()


def make_model(kind: str, blocks: tuple[str, ...], params: dict[str, Any]) -> Pipeline:
    classifier: ClassifierMixin
    if kind == "logreg":
        classifier = LogisticRegression(max_iter=5000, **params)
    elif kind == "hgb":
        classifier = HistGradientBoostingClassifier(
            max_iter=200, min_samples_leaf=20, random_state=0, **params
        )
    else:
        raise ValueError(kind)
    return Pipeline(
        [
            ("features", make_preprocessor(blocks, dense=kind == "hgb")),
            ("classifier", classifier),
        ]
    )


def fit_and_score(
    name: str,
    kind: str,
    blocks: tuple[str, ...],
    grid: list[dict[str, Any]],
    data: dict[str, tuple[pd.DataFrame, np.ndarray]],
) -> Result:
    """Pick params on validation PR AUC, refit on train + val, score test."""
    x_train, y_train = data["train"]
    x_val, y_val = data["val"]
    x_test, y_test = data["test"]

    best_params, best_val = None, None
    for params in grid:
        model = make_model(kind, blocks, params).fit(x_train, y_train)
        val_metrics = compute_metrics(y_val, model.predict_proba(x_val)[:, 1])
        if best_val is None or val_metrics["pr_auc"] > best_val["pr_auc"]:
            best_params, best_val = params, val_metrics

    final = make_model(kind, blocks, best_params).fit(
        pd.concat([x_train, x_val]), np.concatenate([y_train, y_val])
    )
    test_prob = final.predict_proba(x_test)[:, 1]
    return Result(
        name,
        best_params,
        best_val,
        compute_metrics(y_test, test_prob),
        bootstrap_ci(y_test, test_prob),
        test_prob,
        final,
    )


def top_text_terms(model: Pipeline, n: int = 20) -> tuple[list[str], list[str]]:
    """Text terms with the largest positive and negative logistic coefficients."""
    vocabulary = model.named_steps["features"].named_transformers_["text"].get_feature_names_out()
    order = np.argsort(model.named_steps["classifier"].coef_[0])
    return [vocabulary[i] for i in order[::-1][:n]], [vocabulary[i] for i in order[:n]]


def dummy_result(name: str, strategy: str, y_fit: np.ndarray, y_test: np.ndarray) -> Result:
    dummy = DummyClassifier(strategy=strategy).fit(np.zeros((len(y_fit), 1)), y_fit)
    test_prob = dummy.predict_proba(np.zeros((len(y_test), 1)))[:, 1]
    return Result(
        name,
        {"strategy": strategy},
        None,
        compute_metrics(y_test, test_prob),
        bootstrap_ci(y_test, test_prob),
        test_prob,
    )


# ---------------------------------------------------------------------------
# Reporting


def _fmt(value: float, ci: tuple[float, float] | None = None) -> str:
    if ci is None:
        return f"{value:.3f}"
    return f"{value:.3f} ({ci[0]:.3f}-{ci[1]:.3f})"


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines + [""]


def split_rows(split: TimeSplit) -> list[list[Any]]:
    rows = []
    for name, part in (("train", split.train), ("val", split.val), ("test", split.test)):
        dates = pd.to_datetime(part["start_date"])
        rows.append(
            [
                name,
                f"{dates.min().date()} to {dates.max().date()}",
                len(part),
                int(part["label"].sum()),
                f"{part['label'].mean():.3f}",
            ]
        )
    return rows


def result_rows(results: list[Result]) -> list[list[Any]]:
    rows = []
    for r in results:
        m, ci = r.test_metrics, r.test_ci
        rows.append(
            [
                r.name,
                _fmt(m["roc_auc"], ci["roc_auc"]),
                _fmt(m["pr_auc"], ci["pr_auc"]),
                _fmt(m["brier"], ci["brier"]),
                _fmt(r.val_metrics["pr_auc"]) if r.val_metrics else "-",
                r.params,
            ]
        )
    return rows


def subgroup_rows(test: pd.DataFrame, results: list[Result], column: str) -> list[list[Any]]:
    groups = test[column].fillna(MISSING_GROUP)
    rows = []
    for group in sorted(groups.unique()):
        mask = (groups == group).to_numpy()
        y = test["label"].to_numpy()[mask]
        positives, negatives = int(y.sum()), int(len(y) - y.sum())
        row: list[Any] = [group, len(y), positives]
        for r in results:
            if min(positives, negatives) >= MIN_CLASS_COUNT_FOR_SUBGROUP:
                m = compute_metrics(y, r.test_prob[mask])
                row += [_fmt(m["roc_auc"]), _fmt(m["pr_auc"])]
            else:
                row += ["-", "-"]
        rows.append(row)
    return rows


def main() -> None:
    settings = Settings()
    studies = load_studies(settings.db_path)
    labelled = add_labels(studies)
    n_labelled = len(labelled)
    labelled, n_no_start = drop_missing_start(labelled)
    labelled["phase_group"] = labelled["phases"].map(lambda p: "/".join(p) if len(p) else None)
    split = time_split(labelled)

    data = {
        name: (prepare_features(part), part["label"].to_numpy())
        for name, part in (("train", split.train), ("val", split.val), ("test", split.test))
    }
    y_fit = np.concatenate([data["train"][1], data["val"][1]])
    y_test = data["test"][1]

    baselines = [
        dummy_result("Dummy: majority class", "most_frequent", y_fit, y_test),
        dummy_result("Dummy: prior rate", "prior", y_fit, y_test),
    ]
    models: dict[str, Result] = {}
    for block_name, blocks in BLOCK_SETS.items():
        for kind, label, grid in (
            ("logreg", "Logistic regression", LOGREG_GRID),
            ("hgb", "HistGradientBoosting", HGB_GRID),
        ):
            name = f"{label} [{block_name}]"
            print(f"fitting {name} ...")
            models[name] = fit_and_score(name, kind, blocks, grid, data)

    towards, away = top_text_terms(models["Logistic regression [text]"].model)
    main_models = [models["Logistic regression [both]"], models["HistGradientBoosting [both]"]]
    calibration_path = DOCS_DIR / "calibration_test.png"
    plot_calibration(
        y_test,
        {r.name: r.test_prob for r in [baselines[1], *main_models]},
        calibration_path,
        title="Calibration on test period",
    )

    metric_header = [
        "Model",
        "ROC AUC (95% CI)",
        "PR AUC (95% CI)",
        "Brier (95% CI)",
        "Val PR AUC",
        "Params",
    ]
    subgroup_header = ["Group", "n", "terminated"]
    for r in main_models:
        subgroup_header += [f"{r.name} ROC AUC", f"{r.name} PR AUC"]

    lines = [
        "# Termination model results",
        "",
        f"Generated by `python -m ctcopilot.train` on {date.today().isoformat()} from "
        f"`{settings.db_path.as_posix()}`. All numbers below come from that run.",
        "",
        "## Data",
        "",
        f"- Studies in table: {len(studies)}",
        f"- Labelled (TERMINATED or COMPLETED): {n_labelled}",
        f"- Dropped for missing start_date: {n_no_start}",
        f"- Used: {len(labelled)}",
        f"- Validation starts at start_date >= {split.val_start.date()}; "
        f"test starts at start_date >= {split.test_start.date()}",
        "",
        *_table(
            ["Split", "start_date range", "n", "terminated", "terminated rate"],
            split_rows(split),
        ),
        "## Test-period results",
        "",
        "Models refit on train + validation with the hyperparameters that had the best "
        "validation PR AUC. Intervals are 95% percentile bootstrap over test studies "
        "(1000 resamples).",
        "",
        *_table(metric_header, result_rows([*baselines, *main_models])),
        "## Ablation: feature blocks (test period)",
        "",
        *_table(metric_header, result_rows(list(models.values()))),
        "## Test-period results by phase",
        "",
        f"Metrics shown only where a group has at least {MIN_CLASS_COUNT_FOR_SUBGROUP} "
        "studies of each class; small groups have wide uncertainty.",
        "",
        *_table(subgroup_header, subgroup_rows(split.test, main_models, "phase_group")),
        "## Test-period results by sponsor class",
        "",
        *_table(subgroup_header, subgroup_rows(split.test, main_models, "sponsor_class")),
        "## Text terms in Logistic regression [text]",
        "",
        "Terms with the largest coefficients in the final (train + validation) model.",
        "",
        f"- Towards termination: {', '.join(towards)}",
        f"- Towards completion: {', '.join(away)}",
        "",
        "## Calibration",
        "",
        f"![Calibration on test period]({calibration_path.name})",
        "",
    ]
    report = "\n".join(lines)
    (DOCS_DIR / "results.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
