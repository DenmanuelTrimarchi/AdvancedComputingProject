#!/usr/bin/env python3
"""Generate report-ready figures from the committed ``results/aggregate/*``
outputs only. Never touches a raw image, embedding, or identity, and never
hardcodes a metric value — every number plotted is read from disk at
generation time.

Usage:
    python scripts/generate_report_figures.py \
        --results-root results/aggregate \
        --output-root results/figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIGURE_DPI = 150
FIGURE_SIZE = (7.0, 4.5)

# Fixed categorical order (never cycled/reassigned) drawn from this project's
# validated data-viz palette.
COLOR_BLUE = "#2a78d6"
COLOR_ORANGE = "#eb6834"
COLOR_AQUA = "#1baf7a"
COLOR_YELLOW = "#eda100"
CATEGORICAL = [COLOR_BLUE, COLOR_ORANGE, COLOR_AQUA, COLOR_YELLOW]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)


def _legend(ax) -> None:
    legend = ax.legend(frameon=False, loc="best", labelcolor=INK_SECONDARY)
    if legend is not None:
        legend.get_frame().set_alpha(0)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Required aggregate output missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=FIGURE_DPI, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")


VERIFICATION_EXPERIMENTS = [
    ("lfw_development", "LFW development\n(pairsDevTest.txt)"),
    ("lfw_final", "LFW final\n(pairs.txt)"),
    ("cplfw", "CPLFW\n(pairs_CPLFW.txt)"),
]


def fig_roc_comparison(metrics: Dict[str, Dict[str, Any]], output_root: Path) -> None:
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    for (key, label), color in zip(VERIFICATION_EXPERIMENTS, CATEGORICAL):
        points = metrics[key].get("roc_points") or []
        if not points:
            continue
        ordered = sorted(points, key=lambda p: p["false_match_rate"])
        ax.plot(
            [p["false_match_rate"] for p in ordered],
            [p["true_match_rate"] for p in ordered],
            color=color, linewidth=2, label=label.replace("\n", " "),
        )
    ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1, linestyle="--", label="Chance")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False match rate")
    ax.set_ylabel("True match rate")
    ax.set_title("ROC curve: LFW development vs. LFW final vs. CPLFW")
    _style_axes(ax)
    _legend(ax)
    _save(fig, output_root / "roc_comparison.png")


def _confusion_matrix_figure(payload: Dict[str, Any], title: str, output_path: Path) -> None:
    matrix = payload.get("confusion_matrix") or {}
    tp, fp = matrix.get("true_positive", 0), matrix.get("false_positive", 0)
    fn, tn = matrix.get("false_negative", 0), matrix.get("true_negative", 0)
    grid = [[tp, fn], [fp, tn]]
    max_count = max(max(row) for row in grid) or 1

    fig, ax = plt.subplots(figsize=(5.0, 4.5))
    ax.imshow(grid, cmap="Blues", vmin=0, vmax=max_count)
    for i, row in enumerate(grid):
        for j, value in enumerate(row):
            text_color = "white" if value / max_count > 0.6 else INK_PRIMARY
            ax.text(j, i, f"{value:,}", ha="center", va="center", color=text_color, fontsize=13)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Predicted: same", "Predicted: different"], color=INK_SECONDARY)
    ax.set_yticklabels(["Actual: same", "Actual: different"], color=INK_SECONDARY)
    ax.set_title(title, color=INK_PRIMARY)
    ax.spines[:].set_visible(False)

    failure_rate = payload.get("failure_rate")
    scored, total = payload.get("scored_pairs"), payload.get("total_pairs")
    if failure_rate is not None:
        fig.text(
            0.5, -0.02,
            f"Computed over the {scored:,}/{total:,} pairs with a successfully detected face on both "
            f"sides ({failure_rate * 100:.1f}% face-extraction failure rate, excluded here and reported "
            "separately — never silently dropped).",
            ha="center", va="top", color=INK_MUTED, fontsize=8, wrap=True,
        )
    _save(fig, output_path)


def fig_lfw_final_confusion_matrix(metrics: Dict[str, Dict[str, Any]], output_root: Path) -> None:
    _confusion_matrix_figure(
        metrics["lfw_final"], "LFW final evaluation — confusion matrix", output_root / "lfw_final_confusion_matrix.png"
    )


def fig_cplfw_confusion_matrix(metrics: Dict[str, Dict[str, Any]], output_root: Path) -> None:
    _confusion_matrix_figure(
        metrics["cplfw"], "CPLFW cross-pose generalisation — confusion matrix", output_root / "cplfw_confusion_matrix.png"
    )


def fig_extraction_failure_rates(metrics: Dict[str, Dict[str, Any]], output_root: Path) -> None:
    labels = [label for _, label in VERIFICATION_EXPERIMENTS]
    rates = [metrics[key].get("failure_rate", 0.0) * 100 for key, _ in VERIFICATION_EXPERIMENTS]

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    bars = ax.bar(labels, rates, color=CATEGORICAL[: len(labels)], width=0.5, zorder=2)
    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{rate:.1f}%",
            ha="center", va="bottom", color=INK_PRIMARY, fontsize=10,
        )
    ax.set_ylabel("Face-extraction failure rate (%)")
    ax.set_title("Face-extraction failure rate by protocol")
    ax.set_ylim(0, max(rates + [10]) * 1.2)
    _style_axes(ax)
    _save(fig, output_root / "extraction_failure_rates.png")


def fig_cplfw_failure_breakdown(metrics: Dict[str, Dict[str, Any]], output_root: Path) -> None:
    breakdown = metrics["cplfw"].get("failure_breakdown") or {}
    order = ["zero_faces_left", "zero_faces_right", "multiple_faces_left", "multiple_faces_right"]
    labels = [name.replace("_", " ") for name in order]
    values = [breakdown.get(name, 0) for name in order]

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    bars = ax.bar(labels, values, color=CATEGORICAL, width=0.5, zorder=2)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:,}",
            ha="center", va="bottom", color=INK_PRIMARY, fontsize=10,
        )
    ax.set_ylabel("Pairs affected (count)")
    ax.set_title("CPLFW face-extraction failure breakdown")
    _style_axes(ax)
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    _save(fig, output_root / "cplfw_failure_breakdown.png")


def fig_gallery_outcomes(gallery: Dict[str, Any], output_root: Path) -> None:
    metric_labels = [
        ("duplicate_detection_rate", "Duplicate\ndetection rate"),
        ("rank1_identification_rate", "Rank-1\nidentification rate"),
        ("true_duplicate_miss_rate", "True duplicate\nmiss rate"),
        ("false_duplicate_review_rate", "False duplicate-\nreview rate"),
    ]
    labels = [label for _, label in metric_labels]
    values = [(gallery.get(key) or 0.0) * 100 for key, _ in metric_labels]

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    bars = ax.bar(labels, values, color=CATEGORICAL, width=0.5, zorder=2)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{value:.1f}%",
            ha="center", va="bottom", color=INK_PRIMARY, fontsize=10,
        )
    ax.set_ylabel("Rate (%)")
    ax.set_title(f"Real 1:N duplicate-profile gallery outcomes (gallery size {gallery.get('gallery_size', 'n/a')})")
    ax.set_ylim(0, 110)
    _style_axes(ax)
    fig.text(
        0.5, -0.02,
        gallery.get("policy_note", "A result above threshold opens a case for human review only."),
        ha="center", va="top", color=INK_MUTED, fontsize=8, wrap=True,
    )
    _save(fig, output_root / "gallery_outcomes.png")


def fig_threshold_candidate_comparison(threshold_payload: Dict[str, Any], output_root: Path) -> None:
    evidence: Dict[str, Dict[str, Any]] = threshold_payload.get("selection_evidence") or {}
    if not evidence:
        raise SystemExit(
            "calibrated_threshold.json has no 'selection_evidence' — it must be the frozen artifact "
            "written by scripts/evaluate_lfw.py --split dev, not the raw Stage-1 candidates artifact."
        )
    selected = threshold_payload.get("operating_strategy")
    names = sorted(evidence)
    balanced_accuracy = [evidence[name].get("balanced_accuracy", 0.0) * 100 for name in names]
    colors = [COLOR_ORANGE if name == selected else COLOR_BLUE for name in names]

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    bars = ax.bar(names, balanced_accuracy, color=colors, width=0.5, zorder=2)
    for bar, value in zip(bars, balanced_accuracy):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5, f"{value:.2f}%",
            ha="center", va="bottom", color=INK_PRIMARY, fontsize=9,
        )
    ax.set_ylabel("Development-split (pairsDevTest.txt) balanced accuracy (%)")
    ax.set_title("Threshold-candidate comparison (Stage 2 selection)")
    ax.set_ylim(0, 110)
    _style_axes(ax)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOR_ORANGE, label=f"Selected: {selected}"),
        plt.Rectangle((0, 0), 1, 1, color=COLOR_BLUE, label="Not selected"),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower right", labelcolor=INK_SECONDARY)
    _save(fig, output_root / "threshold_candidate_comparison.png")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)

    metrics = {key: _load_json(args.results_root / f"{key}_metrics.json") for key, _ in VERIFICATION_EXPERIMENTS}
    gallery = _load_json(args.results_root / "duplicate_gallery_metrics.json")
    threshold_payload = _load_json(args.results_root / "calibrated_threshold.json")

    args.output_root.mkdir(parents=True, exist_ok=True)

    fig_roc_comparison(metrics, args.output_root)
    fig_lfw_final_confusion_matrix(metrics, args.output_root)
    fig_cplfw_confusion_matrix(metrics, args.output_root)
    fig_extraction_failure_rates(metrics, args.output_root)
    fig_cplfw_failure_breakdown(metrics, args.output_root)
    fig_gallery_outcomes(gallery, args.output_root)
    fig_threshold_candidate_comparison(threshold_payload, args.output_root)

    print(f"\nGenerated 7 figures in {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
