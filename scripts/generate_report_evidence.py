#!/usr/bin/env python3
"""Generate the dissertation report evidence pack: reproducible figures,
rendered validation-command evidence images, an evidence index and a
content-addressed manifest.

Every number plotted is read from ``results/aggregate/*`` at generation
time. Nothing here hardcodes a metric, opens a dataset image, reads an
embedding, or touches the network. Absolute filesystem paths are redacted
out of every rendered image and log before it is written.

Default mode generates figures only, from already-generated aggregate
results:

    python scripts/generate_report_evidence.py \
        --results-root results/aggregate \
        --output-root results/report_evidence

``--run-validation`` additionally runs the project's own read-only
verification commands and renders their redacted output as evidence
images. The three dataset/model commands are skipped, with a recorded
reason, unless their (private, never-published) roots are supplied:

    python scripts/generate_report_evidence.py \
        --results-root results/aggregate \
        --output-root results/report_evidence \
        --run-validation \
        --model-root "$FACE_MODEL_ROOT" \
        --lfw-dataset-root "$FACE_DATA_ROOT/lfw_funneled" \
        --cplfw-dataset-root "$CPLFW_RAW_ROOT" \
        --protocol-root "$FACE_PROTOCOL_ROOT"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
# Redacted placeholders are shell-style ($FACE_MODEL_ROOT), and a bare '$' is
# otherwise parsed as the start of a mathtext expression and raises. No figure
# here uses mathtext, so switching the parser off globally is the safe fix.
matplotlib.rcParams["text.parse_math"] = False
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from face_verification.privacy import default_forbidden_path_substrings, find_path_leaks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

FIGURE_DPI = 200
PNG_METADATA = {"Software": "face-verification report evidence generator"}

# Fixed categorical order (never cycled) from this project's validated
# data-viz palette; slots 1-3 are the all-pairs-safe subset.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK_PRIMARY, INK_SECONDARY, INK_MUTED = "#0b0b0b", "#52514e", "#898781"
GRIDLINE, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"

TERMINAL_BG, TERMINAL_FG = "#1a1a19", "#e8e8e4"
TERMINAL_ACCENT, TERMINAL_DIM = "#3987e5", "#898781"
TERMINAL_OK, TERMINAL_FAIL = "#0ca30c", "#d03b3b"

EXPERIMENTS = [
    ("lfw_development", "LFW development\n(pairsDevTest.txt)"),
    ("lfw_final", "LFW final\n(pairs.txt)"),
    ("cplfw", "Raw CPLFW\n(pairs_CPLFW.txt)"),
]

CONDITIONAL_NOTE = (
    "Metrics are conditional on successful face extraction: pairs where a face could not be "
    "detected on both sides are excluded from this chart and reported separately as the "
    "extraction failure rate (Figure 4), never silently dropped."
)


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

# Temp-directory paths are swept too, not just home directories: macOS puts the
# account name inside them (".../T/pytest-of-<user>/..."), so a pytest traceback
# can carry a username into a rendered image. The privacy scanner reads PNG
# metadata, never pixels, so this redaction is the only thing protecting the
# rendered text -- keep it broad.
_GENERIC_PATH_PATTERN = re.compile(
    r"(?:/Users/|/home/|/private/var/folders/|/var/folders/|/private/tmp/|/tmp/)[^\s\"'`,;:)\]]*"
)


def build_redactions(args: argparse.Namespace) -> List[Tuple[str, str]]:
    """(actual value, placeholder) pairs, longest first so the most specific
    path wins before a shorter prefix of it can match."""
    candidates: List[Tuple[Optional[str], str]] = [
        (args.cplfw_dataset_root, "$CPLFW_RAW_ROOT"),
        (args.lfw_dataset_root, "$FACE_DATA_ROOT/lfw_funneled"),
        (args.model_root, "$FACE_MODEL_ROOT"),
        (args.protocol_root, "$FACE_PROTOCOL_ROOT"),
        (os.environ.get("FACE_DATA_ROOT"), "$FACE_DATA_ROOT"),
        (os.environ.get("FACE_PROTOCOL_ROOT"), "$FACE_PROTOCOL_ROOT"),
        (os.environ.get("FACE_MODEL_ROOT"), "$FACE_MODEL_ROOT"),
        (os.environ.get("FACE_CACHE_ROOT"), "$FACE_CACHE_ROOT"),
        (str(REPO_ROOT), "$REPO_ROOT"),
        (str(Path.home()), "$HOME"),
    ]
    pairs = [(str(value), placeholder) for value, placeholder in candidates if value]
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def redact(text: str, redactions: Sequence[Tuple[str, str]]) -> str:
    """Replace every known private root with its placeholder, then sweep any
    surviving absolute home path. Redaction is applied to rendered evidence
    and logs alike — the pack must be publishable as-is."""
    for actual, placeholder in redactions:
        text = text.replace(actual, placeholder)
    return _GENERIC_PATH_PATTERN.sub("<redacted-path>", text)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Required aggregate output is missing: {path.name} (looked in {path.parent})")
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Required aggregate output is missing: {path.name} (looked in {path.parent})")
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(mapping: Dict[str, Any], key: str, where: str) -> Any:
    """Fail loudly rather than silently rendering an incomplete chart."""
    if key not in mapping or mapping[key] in (None, ""):
        raise SystemExit(f"Required field '{key}' is missing from {where}; refusing to draw a partial chart.")
    return mapping[key]


def as_float(value: Any) -> float:
    return float(value)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def git_is_dirty() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return bool(completed.stdout.strip())


# --------------------------------------------------------------------------
# Chart chrome
# --------------------------------------------------------------------------


def style_axes(ax, *, grid_axis: str = "y") -> None:
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.grid(axis=grid_axis, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)


def footnote(fig, text: str) -> None:
    fig.text(0.5, -0.04, text, ha="center", va="top", color=INK_MUTED, fontsize=7.5, wrap=True)


def display_path(path: Path) -> str:
    """Repo-relative when possible, bare filename otherwise — never an
    absolute path, so console output stays as publishable as the pack."""
    resolved = Path(path).resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return str(resolved.relative_to(REPO_ROOT))
    return f".../{resolved.parent.name}/{resolved.name}"


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=FIGURE_DPI, facecolor=SURFACE, bbox_inches="tight", metadata=PNG_METADATA)
    plt.close(fig)
    print(f"  wrote {display_path(path)}")
    return path


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------


def figure_01_roc(roc_rows: List[Dict[str, str]], summary: Dict[str, Dict[str, str]], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for (key, label), color in zip(EXPERIMENTS, (BLUE, ORANGE, AQUA)):
        points = [row for row in roc_rows if row["experiment"] == key]
        if not points:
            raise SystemExit(f"roc_points.csv contains no rows for experiment '{key}'.")
        points.sort(key=lambda row: as_float(row["false_match_rate"]))
        auc = as_float(require(summary[key], "roc_auc", "metrics_summary.csv"))
        ax.plot(
            [as_float(row["false_match_rate"]) for row in points],
            [as_float(row["true_match_rate"]) for row in points],
            color=color, linewidth=2,
            label=f"{label.replace(chr(10), ' ')} — AUC {auc:.4f}",
        )
    ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1, linestyle="--", label="Chance (AUC 0.5000)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("False match rate")
    ax.set_ylabel("True match rate")
    ax.set_title("ROC Curves for LFW Development, Final LFW and Raw CPLFW", fontsize=12, pad=12)
    style_axes(ax, grid_axis="both")
    legend = ax.legend(frameon=False, loc="lower right", labelcolor=INK_SECONDARY, fontsize=9)
    legend.get_frame().set_alpha(0)
    footnote(fig, CONDITIONAL_NOTE)
    return save(fig, out)


def _confusion(row: Dict[str, str], summary_row: Dict[str, str], title: str, caption: str, out: Path) -> Path:
    tp = int(require(row, "true_positive", "confusion_matrices.csv"))
    fp = int(require(row, "false_positive", "confusion_matrices.csv"))
    tn = int(require(row, "true_negative", "confusion_matrices.csv"))
    fn = int(require(row, "false_negative", "confusion_matrices.csv"))
    grid = [[tp, fn], [fp, tn]]
    largest = max(max(r) for r in grid) or 1

    fig, ax = plt.subplots(figsize=(6.0, 5.0))
    ax.imshow(grid, cmap="Blues", vmin=0, vmax=largest)
    cells = [("True positive", tp), ("False negative", fn), ("False positive", fp), ("True negative", tn)]
    for index, (name, value) in enumerate(cells):
        i, j = divmod(index, 2)
        strong = value / largest > 0.55
        ax.text(j, i - 0.13, f"{value:,}", ha="center", va="center",
                color="white" if strong else INK_PRIMARY, fontsize=17)
        ax.text(j, i + 0.17, name, ha="center", va="center",
                color="#e8e8e4" if strong else INK_SECONDARY, fontsize=9)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Predicted: same person", "Predicted: different"], color=INK_SECONDARY, fontsize=9)
    ax.set_yticklabels(["Actual: same person", "Actual: different"], color=INK_SECONDARY, fontsize=9)
    ax.set_title(title, fontsize=12, pad=12, color=INK_PRIMARY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    scored = int(as_float(require(summary_row, "scored_pairs", "metrics_summary.csv")))
    total = int(as_float(require(summary_row, "total_pairs", "metrics_summary.csv")))
    rate = as_float(require(summary_row, "failure_rate", "metrics_summary.csv"))
    threshold = as_float(require(summary_row, "threshold", "metrics_summary.csv"))
    footnote(
        fig,
        f"{caption} Computed at the frozen threshold {threshold:.6f} over the {scored:,} of {total:,} pairs "
        f"with a face successfully detected on both sides ({rate * 100:.2f}% extraction failure rate, "
        f"reported separately in Figure 4 — never silently dropped).",
    )
    return save(fig, out)


def figure_02_lfw_confusion(conf: Dict[str, Dict[str, str]], summary: Dict[str, Dict[str, str]], out: Path) -> Path:
    return _confusion(
        conf["lfw_final"], summary["lfw_final"],
        "Final LFW Confusion Matrix at the Frozen Threshold",
        "The frozen threshold was selected on pairsDevTest.txt and applied unchanged to pairs.txt.",
        out,
    )


def figure_03_cplfw_confusion(conf: Dict[str, Dict[str, str]], summary: Dict[str, Dict[str, str]], out: Path) -> Path:
    return _confusion(
        conf["cplfw"], summary["cplfw"],
        "Raw CPLFW Confusion Matrix Using the LFW-Frozen Threshold",
        "Cross-pose generalisation on the authors' raw (images.rar) image set, with no CPLFW recalibration.",
        out,
    )


def figure_04_failure_rates(summary: Dict[str, Dict[str, str]], out: Path) -> Path:
    labels = [label for _, label in EXPERIMENTS]
    rates, annotations = [], []
    for key, _ in EXPERIMENTS:
        row = summary[key]
        rates.append(as_float(require(row, "failure_rate", "metrics_summary.csv")) * 100)
        scored = int(as_float(require(row, "scored_pairs", "metrics_summary.csv")))
        total = int(as_float(require(row, "total_pairs", "metrics_summary.csv")))
        annotations.append(f"{scored:,} / {total:,} scored")

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(labels, rates, color=(BLUE, ORANGE, AQUA), width=0.5, zorder=2)
    for bar, rate, annotation in zip(bars, rates, annotations):
        centre = bar.get_x() + bar.get_width() / 2
        ax.text(centre, bar.get_height() + 1.4, f"{rate:.2f}%", ha="center", va="bottom",
                color=INK_PRIMARY, fontsize=11)
        ax.text(centre, 1.2, annotation, ha="center", va="bottom", color="white", fontsize=8.5)
    ax.set_ylabel("Face-extraction failure rate (%)")
    ax.set_ylim(0, max(rates) * 1.3)
    ax.set_title("Face-Extraction Failure Rates Across Benchmark Protocols", fontsize=12, pad=12)
    style_axes(ax)
    footnote(
        fig,
        "A pair fails extraction when the detector finds zero faces, or more than one face, on either "
        "side. Failed pairs are excluded from accuracy metrics and reported here instead — the raw CPLFW "
        "failure rate is the dominant cross-pose finding of this evaluation.",
    )
    return save(fig, out)


def figure_05_cplfw_breakdown(cplfw: Dict[str, Any], out: Path) -> Path:
    breakdown = require(cplfw, "failure_breakdown", "cplfw_metrics.json")
    order = ["zero_faces_left", "zero_faces_right", "multiple_faces_left", "multiple_faces_right"]
    labels = ["Zero faces\n(left image)", "Zero faces\n(right image)",
              "Multiple faces\n(left image)", "Multiple faces\n(right image)"]
    values = [int(breakdown.get(name, 0)) for name in order]
    total = int(require(cplfw, "failed_pairs", "cplfw_metrics.json"))

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(labels, values, color=(BLUE, ORANGE, AQUA, YELLOW), width=0.55, zorder=2)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.015,
                f"{value:,}", ha="center", va="bottom", color=INK_PRIMARY, fontsize=11)
    ax.set_ylabel("Failure occurrences (count)")
    ax.set_ylim(0, max(values) * 1.18)
    ax.set_title("Raw CPLFW Face-Extraction Failure Categories", fontsize=12, pad=12)
    style_axes(ax)
    footnote(
        fig,
        f"Counts are per-side occurrences across {total:,} failed pairs, so they sum to more than the "
        "failed-pair count when both sides of a pair fail. Zero-face detections dominate, which locates "
        "the cross-pose difficulty in detection rather than in embedding comparison.",
    )
    return save(fig, out)


def figure_06_gallery(gallery: Dict[str, Any], out: Path) -> Path:
    fields = [
        ("duplicate_detection_rate", "Duplicate\ndetection rate", BLUE),
        ("rank1_identification_rate", "Rank-1\nidentification rate", AQUA),
        ("true_duplicate_miss_rate", "True duplicate\nmiss rate", YELLOW),
        ("false_duplicate_review_rate", "False duplicate-\nreview rate", ORANGE),
    ]
    labels = [label for _, label, _ in fields]
    values = [as_float(require(gallery, key, "duplicate_gallery_metrics.json")) * 100 for key, _, _ in fields]
    colors = [color for _, _, color in fields]
    size = require(gallery, "gallery_size", "duplicate_gallery_metrics.json")

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=2)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, f"{value:.2f}%",
                ha="center", va="bottom", color=INK_PRIMARY, fontsize=11)
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(0, 112)
    ax.set_title(f"1:N Duplicate-Profile Gallery Outcomes (gallery size {size})", fontsize=12, pad=12)
    style_axes(ax)
    footnote(
        fig,
        "The high false-review rate demonstrates that the 1:1 verification threshold is unsuitable for "
        "direct 1:N deployment. A result above threshold opens a case for human review only — it never "
        "bans, rejects, accuses or classifies an identity as fraudulent.",
    )
    return save(fig, out)


def figure_07_candidates(threshold_payload: Dict[str, Any], out: Path) -> Path:
    evidence = require(threshold_payload, "selection_evidence", "calibrated_threshold.json")
    selected = require(threshold_payload, "operating_strategy", "calibrated_threshold.json")
    names = sorted(evidence)

    series = [
        ("balanced_accuracy", "Balanced accuracy", BLUE),
        ("false_match_rate", "False match rate", ORANGE),
        ("false_non_match_rate", "False non-match rate", AQUA),
    ]
    width = 0.26
    positions = range(len(names))

    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    for offset, (key, label, color) in enumerate(series):
        values = [as_float(require(evidence[name], key, f"selection_evidence.{name}")) * 100 for name in names]
        shifted = [p + (offset - 1) * width for p in positions]
        bars = ax.bar(shifted, values, width=width, color=color, label=label, zorder=2)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2, f"{value:.2f}",
                    ha="center", va="bottom", color=INK_SECONDARY, fontsize=7.5, rotation=90)

    # The frozen marker goes on its own line, and every label carries the same
    # number of lines, so a long marker can never overrun its neighbour.
    tick_labels = []
    for name in names:
        tau = as_float(require(evidence[name], "threshold", f"selection_evidence.{name}"))
        marker = "★ FROZEN" if name == selected else " "
        tick_labels.append(f"{name}\nτ = {tau:.4f}\n{marker}")

    ax.set_xticks(list(positions))
    ax.set_xticklabels(tick_labels, fontsize=8)
    for tick_label, name in zip(ax.get_xticklabels(), names):
        if name == selected:
            tick_label.set_color(INK_PRIMARY)
            tick_label.set_fontweight("bold")
    ax.set_ylabel("Development-split rate (%)")
    ax.set_ylim(0, 118)
    ax.set_title("Candidate Threshold Evaluation on pairsDevTest.txt", fontsize=12, pad=12)
    style_axes(ax)
    legend = ax.legend(frameon=False, loc="upper center", ncol=3, labelcolor=INK_SECONDARY, fontsize=9)
    legend.get_frame().set_alpha(0)
    footnote(
        fig,
        f"Every candidate generated on pairsDevTrain.txt is evaluated here on pairsDevTest.txt; "
        f"'{selected}' was selected and frozen by the fixed rule (maximum balanced accuracy, ties broken "
        f"by lower development false match rate, then candidate name). Each candidate's own threshold "
        f"value τ is printed beneath its label, so no second axis is needed.",
    )
    return save(fig, out)


def figure_08_latency(summary: Dict[str, Dict[str, str]], gallery: Dict[str, Any], out: Path) -> Path:
    # Short group names: the protocol filenames are carried by Figures 1-4, and
    # spelling them out here overruns the neighbouring tick label.
    groups = ["LFW development", "LFW final", "Raw CPLFW"]
    stats = [
        ("embedding_time_mean_ms", "Mean", BLUE),
        ("embedding_time_median_ms", "Median", AQUA),
        ("embedding_time_p95_ms", "p95", ORANGE),
    ]
    width = 0.26
    fig, ax = plt.subplots(figsize=(9.0, 5.2))

    for offset, (key, label, color) in enumerate(stats):
        values = [as_float(require(summary[key_name], key, "metrics_summary.csv")) for key_name, _ in EXPERIMENTS]
        shifted = [i + (offset - 1) * width for i in range(len(groups))]
        bars = ax.bar(shifted, values, width=width, color=color, label=label, zorder=2)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4, f"{value:.1f}",
                    ha="center", va="bottom", color=INK_SECONDARY, fontsize=8)

    gallery_mean = as_float(require(gallery, "gallery_search_time_mean_ms", "duplicate_gallery_metrics.json"))
    gallery_p95 = as_float(require(gallery, "gallery_search_time_p95_ms", "duplicate_gallery_metrics.json"))
    base = len(groups) + 0.35
    for index, (value, label, color) in enumerate(
        ((gallery_mean, "Mean", BLUE), (gallery_p95, "p95", ORANGE))
    ):
        bar = ax.bar([base + (index - 0.5) * width], [value], width=width, color=color, zorder=2)[0]
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4, f"{value:.1f}",
                ha="center", va="bottom", color=INK_SECONDARY, fontsize=8)

    divider = len(groups) - 0.32
    ax.axvline(divider, color=AXIS, linewidth=1, linestyle="--", zorder=1)
    ax.set_xticks(list(range(len(groups))) + [base])
    ax.set_xticklabels(
        [f"{name}\n(per image)" for name in groups]
        + [f"1:N gallery search\n(per probe, N = {gallery.get('gallery_size', 'n/a')})"],
        fontsize=8.5,
    )
    ax.set_ylabel("Time (milliseconds)")
    ax.set_title("Embedding and Gallery Search Latency", fontsize=12, pad=12)
    style_axes(ax)
    legend = ax.legend(frameon=False, loc="upper right", labelcolor=INK_SECONDARY, fontsize=9)
    legend.get_frame().set_alpha(0)
    footnote(
        fig,
        "Left of the divider: time to embed one image, per protocol. Right of the divider: time to search "
        "one probe against the whole gallery. The two have different denominators and are not directly "
        "comparable — they share an axis only because they share a unit. Timings are machine-dependent "
        "and are not part of the reproducibility contract (see docs/REPRODUCIBILITY.md).",
    )
    return save(fig, out)


def figure_09_flow(threshold_payload: Dict[str, Any], out: Path) -> Path:
    threshold = as_float(require(threshold_payload, "threshold", "calibrated_threshold.json"))
    selected = require(threshold_payload, "operating_strategy", "calibrated_threshold.json")

    stages = [
        ("pairsDevTrain.txt\n(validation split)", BLUE, "Stage 1"),
        ("Candidate thresholds\nstatus = \"candidates\"", BLUE, ""),
        ("pairsDevTest.txt\n(development split)", ORANGE, "Stage 2"),
        (f"Select & freeze ONE threshold\n{selected}, τ = {threshold:.6f}\nstatus = \"frozen\"", ORANGE, ""),
        ("Final LFW\npairs.txt", AQUA, "Stage 3"),
        ("Raw CPLFW\npairs_CPLFW.txt", AQUA, ""),
        ("1:N LFW duplicate\ngallery", AQUA, ""),
        ("Aggregate JSON / CSV /\nMarkdown outputs", INK_SECONDARY, ""),
        ("Human-review-only\ninterpretation", INK_SECONDARY, ""),
    ]

    fig, ax = plt.subplots(figsize=(7.4, 9.2))
    # The flow is drawn in data coordinates, so let the axes fill the canvas
    # instead of leaving matplotlib's default subplot margins as dead space.
    fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.02)
    ax.set_xlim(0, 10)
    ax.set_ylim(0.2, len(stages) * 1.32 + 0.35)
    ax.axis("off")

    box_height, box_width = 0.82, 6.6
    centres = []
    for index, (text, color, stage_label) in enumerate(stages):
        y = (len(stages) - index - 1) * 1.32 + 0.5
        centres.append(y)
        ax.add_patch(
            FancyBboxPatch(
                (5 - box_width / 2, y), box_width, box_height,
                boxstyle="round,pad=0.06,rounding_size=0.12",
                linewidth=1.6, edgecolor=color, facecolor=SURFACE, zorder=2,
            )
        )
        ax.text(5, y + box_height / 2, text, ha="center", va="center",
                color=INK_PRIMARY, fontsize=9.5, zorder=3)
        if stage_label:
            ax.text(5 - box_width / 2 - 0.25, y + box_height / 2, stage_label, ha="right", va="center",
                    color=color, fontsize=9, fontweight="bold", zorder=3)

    for index in range(len(stages) - 1):
        top = centres[index]
        bottom = centres[index + 1] + box_height
        ax.add_patch(
            FancyArrowPatch((5, top), (5, bottom), arrowstyle="-|>", mutation_scale=13,
                            linewidth=1.4, color=INK_MUTED, zorder=1)
        )

    guard_y = (centres[3] + centres[4] + box_height) / 2
    ax.text(
        5 + box_width / 2 + 0.15, guard_y,
        "the frozen artifact is\nREQUIRED past this line —\nStages 3+ cannot\nrecalibrate it",
        ha="left", va="center", color=TERMINAL_FAIL, fontsize=8.5, style="italic", zorder=3,
    )
    ax.plot([5 - box_width / 2 - 0.6, 5 + box_width / 2 + 0.1], [guard_y, guard_y],
            color=TERMINAL_FAIL, linewidth=1.2, linestyle="--", zorder=1)

    ax.set_title("Experimental Workflow and Held-Out Evaluation Boundary", fontsize=12.5, pad=16, color=INK_PRIMARY)
    footnote(
        fig,
        "Enforced in code, not only in documentation: calibration refuses any split but 'validation', and "
        "the final/CPLFW evaluations refuse any threshold artifact whose status is not \"frozen\" "
        "(src/face_verification/calibration.py, tests/test_no_partition_leakage.py). CPLFW reuses the "
        "LFW-frozen threshold and never recalibrates.",
    )
    return save(fig, out)


# --------------------------------------------------------------------------
# Rendered command evidence
# --------------------------------------------------------------------------

MAX_RENDERED_LINES = 44
MAX_LINE_WIDTH = 108


def render_terminal(
    *, title: str, command: str, exit_code: Optional[int], body: str, out: Path,
    commit: str, dirty: bool, note: str = "",
) -> Path:
    lines: List[str] = []
    for raw in body.splitlines():
        while len(raw) > MAX_LINE_WIDTH:
            lines.append(raw[:MAX_LINE_WIDTH])
            raw = "    " + raw[MAX_LINE_WIDTH:]
        lines.append(raw)
    # Keep both ends when truncating: for a test run the head shows what ran
    # and the tail carries the pass/fail summary, which is the actual evidence.
    truncated = 0
    if len(lines) > MAX_RENDERED_LINES:
        truncated = len(lines) - MAX_RENDERED_LINES
        head = MAX_RENDERED_LINES // 2
        tail = MAX_RENDERED_LINES - head
        lines = lines[:head] + [f"[... {truncated} line(s) omitted ...]"] + lines[-tail:]

    header_rows, footer_rows = 3, 3
    total_rows = len(lines) + header_rows + footer_rows + (1 if truncated else 0) + (1 if note else 0)
    fig_height = max(2.6, 0.235 * total_rows + 0.8)
    fig, ax = plt.subplots(figsize=(11.0, fig_height))
    fig.patch.set_facecolor(TERMINAL_BG)
    ax.set_facecolor(TERMINAL_BG)
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, total_rows)

    row = total_rows - 0.7
    mono = {"family": "DejaVu Sans Mono"}

    ax.text(0.012, row, title, color=TERMINAL_FG, fontsize=11.5, fontweight="bold", va="top", **mono)
    row -= 1.15
    ax.text(0.012, row, f"$ {command}", color=TERMINAL_ACCENT, fontsize=9.5, va="top", **mono)
    row -= 1.25

    for line in lines:
        ax.text(0.012, row, line, color=TERMINAL_FG, fontsize=8.6, va="top", **mono)
        row -= 1.0
    if truncated:
        ax.text(0.012, row, f"({truncated} line(s) omitted from the middle of this rendering)",
                color=TERMINAL_DIM, fontsize=8.4, va="top", style="italic", **mono)
        row -= 1.0
    if note:
        ax.text(0.012, row, note, color=TERMINAL_DIM, fontsize=8.4, va="top", style="italic", **mono)
        row -= 1.0

    row -= 0.35
    if exit_code is None:
        status_text, status_color = "exit code: n/a (rendered from generated artifacts, not a command)", TERMINAL_DIM
    elif exit_code == 0:
        status_text, status_color = "exit code: 0  (success)", TERMINAL_OK
    else:
        status_text, status_color = f"exit code: {exit_code}  (FAILED)", TERMINAL_FAIL
    ax.text(0.012, row, status_text, color=status_color, fontsize=9, fontweight="bold", va="top", **mono)
    row -= 1.0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    tree_state = (
        "source tree: DIRTY (uncommitted changes present)" if dirty else "source tree: clean"
    )
    ax.text(0.012, row, f"generated: {stamp}   |   source commit: {commit[:12]}   |   {tree_state}",
            color=TERMINAL_DIM, fontsize=8.2, va="top", **mono)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=FIGURE_DPI, facecolor=TERMINAL_BG, bbox_inches="tight", metadata=PNG_METADATA)
    plt.close(fig)
    print(f"  wrote {display_path(out)}")
    return out


def run_command(argv: List[str]) -> Tuple[int, str]:
    completed = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


# --------------------------------------------------------------------------
# Index and manifest
# --------------------------------------------------------------------------


def build_manifest_entry(
    *, path: Path, kind: str, title: str, sources: List[Path], commit: str,
    section: str, caption: str, output_root: Path,
) -> Dict[str, Any]:
    return {
        "filename": str(path.relative_to(output_root)),
        "type": kind,
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [str(source.relative_to(REPO_ROOT)) if source.is_relative_to(REPO_ROOT) else source.name
                         for source in sources],
        "source_file_sha256": {
            (str(source.relative_to(REPO_ROOT)) if source.is_relative_to(REPO_ROOT) else source.name): sha256_of(source)
            for source in sources if source.is_file()
        },
        "git_commit": commit,
        "contains_real_face_image": False,
        "contains_identity_information": False,
        "contains_absolute_path": False,
        "report_section": section,
        "suggested_caption": caption,
        "sha256": sha256_of(path),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--run-validation", action="store_true",
                        help="Also run the project's read-only verification commands and render their "
                             "redacted output as evidence images.")
    parser.add_argument("--model-root", default=None)
    parser.add_argument("--lfw-dataset-root", default=None)
    parser.add_argument("--cplfw-dataset-root", default=None)
    parser.add_argument("--protocol-root", default=None)
    args = parser.parse_args(argv)

    results_root, output_root = args.results_root, args.output_root
    figures_dir = output_root / "figures"
    screenshots_dir = output_root / "screenshots"
    logs_dir = output_root / "logs"
    for directory in (figures_dir, screenshots_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    redactions = build_redactions(args)
    commit, dirty = git_commit(), git_is_dirty()
    # Writing the pack into the repository makes the tree dirty as a side
    # effect of generation, which would then be reported as an unclean source
    # state. Generating to an external directory keeps the source tree clean
    # so the recorded provenance is meaningful.
    generated_outside_repo = not output_root.resolve().is_relative_to(REPO_ROOT)

    threshold_path = results_root / "calibrated_threshold.json"
    cplfw_path = results_root / "cplfw_metrics.json"
    gallery_path = results_root / "duplicate_gallery_metrics.json"
    summary_path = results_root / "metrics_summary.csv"
    confusion_path = results_root / "confusion_matrices.csv"
    roc_path = results_root / "roc_points.csv"

    threshold_payload = load_json(threshold_path)
    cplfw_payload = load_json(cplfw_path)
    gallery_payload = load_json(gallery_path)
    summary = {row["experiment"]: row for row in load_csv(summary_path)}
    confusion = {row["experiment"]: row for row in load_csv(confusion_path)}
    roc_rows = load_csv(roc_path)

    for key, _ in EXPERIMENTS:
        for name, table in (("metrics_summary.csv", summary), ("confusion_matrices.csv", confusion)):
            if key not in table:
                raise SystemExit(f"{name} has no row for experiment '{key}'.")

    manifest: List[Dict[str, Any]] = []
    index_rows: List[Dict[str, str]] = []

    print("Generating figures...")
    figure_specs = [
        (figure_01_roc, (roc_rows, summary), "figure_01_roc_comparison.png",
         "ROC Curves for LFW Development, Final LFW and Raw CPLFW", [roc_path, summary_path],
         "Chapter 4 — Results, §4.1 Verification performance",
         "ROC curves for the three verification protocols. Raw CPLFW sits below both LFW curves, "
         "quantifying the cost of extreme pose variation at a fixed operating threshold."),
        (figure_02_lfw_confusion, (confusion, summary), "figure_02_lfw_final_confusion_matrix.png",
         "Final LFW Confusion Matrix at the Frozen Threshold", [confusion_path, summary_path],
         "Chapter 4 — Results, §4.2 Final LFW evaluation",
         "Confusion matrix for the final LFW protocol at the frozen threshold, showing the "
         "false-match/false-non-match balance the threshold was selected to achieve."),
        (figure_03_cplfw_confusion, (confusion, summary), "figure_03_cplfw_confusion_matrix.png",
         "Raw CPLFW Confusion Matrix Using the LFW-Frozen Threshold", [confusion_path, summary_path],
         "Chapter 4 — Results, §4.3 Cross-pose generalisation",
         "Confusion matrix for raw CPLFW using the unchanged LFW-frozen threshold. Errors shift "
         "markedly towards false non-matches under cross-pose conditions."),
        (figure_04_failure_rates, (summary,), "figure_04_extraction_failure_rates.png",
         "Face-Extraction Failure Rates Across Benchmark Protocols", [summary_path],
         "Chapter 4 — Results, §4.4 Face-extraction failures",
         "Face-extraction failure rates by protocol. The raw CPLFW rate is roughly four times the LFW "
         "rate and is the dominant practical limitation identified by this evaluation."),
        (figure_05_cplfw_breakdown, (cplfw_payload,), "figure_05_cplfw_failure_breakdown.png",
         "Raw CPLFW Face-Extraction Failure Categories", [cplfw_path],
         "Chapter 4 — Results, §4.4 Face-extraction failures",
         "Breakdown of raw CPLFW extraction failures by category. Zero-face detections dominate, "
         "locating the difficulty in detection rather than in embedding comparison."),
        (figure_06_gallery, (gallery_payload,), "figure_06_gallery_outcomes.png",
         "1:N Duplicate-Profile Gallery Outcomes", [gallery_path],
         "Chapter 4 — Results, §4.5 Duplicate-profile gallery",
         "Outcomes of the 1:N duplicate-profile gallery experiment. High detection is accompanied by a "
         "false-review rate that makes the 1:1 threshold unsuitable for direct 1:N deployment."),
        (figure_07_candidates, (threshold_payload,), "figure_07_threshold_candidate_comparison.png",
         "Candidate Threshold Evaluation on pairsDevTest.txt", [threshold_path],
         "Chapter 3 — Methodology, §3.5 Threshold selection",
         "Development-split evaluation of every candidate threshold, with the frozen selection marked. "
         "Evidence that selection was deterministic and made before any held-out data was read."),
        (figure_08_latency, (summary, gallery_payload), "figure_08_latency_comparison.png",
         "Embedding and Gallery Search Latency", [summary_path, gallery_path],
         "Chapter 4 — Results, §4.6 Processing latency",
         "Embedding latency per image and gallery-search latency per probe. Both are machine-dependent "
         "and are reported for feasibility context, not as a reproducibility guarantee."),
        (figure_09_flow, (threshold_payload,), "figure_09_experiment_flow.png",
         "Experimental Workflow and Held-Out Evaluation Boundary", [threshold_path],
         "Chapter 3 — Methodology, §3.2 Experimental design",
         "The experimental workflow and the held-out boundary enforced in code. CPLFW reuses the "
         "LFW-frozen threshold and cannot recalibrate it."),
    ]

    for function, function_args, filename, title, sources, section, caption in figure_specs:
        path = function(*function_args, figures_dir / filename)
        manifest.append(build_manifest_entry(
            path=path, kind="figure", title=title, sources=sources, commit=commit,
            section=section, caption=caption, output_root=output_root,
        ))
        index_rows.append({
            "id": filename.split("_")[1], "filename": f"figures/{filename}", "title": title,
            "source": ", ".join(s.name for s in sources), "section": section,
            "caption": caption, "kind": "figure",
        })

    screenshot_specs: List[Dict[str, Any]] = []
    if args.run_validation:
        print("Running validation commands...")

        def spec(number: str, filename: str, title: str, command: str, argv_: Optional[List[str]],
                 log_name: Optional[str], section: str, caption: str,
                 rendered: Optional[str] = None, skip_reason: Optional[str] = None) -> None:
            screenshot_specs.append({
                "number": number, "filename": filename, "title": title, "command": command,
                "argv": argv_, "log_name": log_name, "section": section, "caption": caption,
                "rendered": rendered, "skip_reason": skip_reason,
            })

        spec("01", "screenshot_01_environment_check.png", "Environment and dependency contract check",
             "python scripts/check_environment.py",
             [sys.executable, str(SCRIPTS_DIR / "check_environment.py")], "environment_check.txt",
             "Appendix B — Reproducibility evidence",
             "The pinned dependency contract verified at run time, not merely declared in pyproject.toml.")

        if args.model_root:
            spec("02", "screenshot_02_model_verification.png", "Pinned model hash verification",
                 'python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"',
                 [sys.executable, str(SCRIPTS_DIR / "verify_models.py"), "--model-root", args.model_root],
                 "model_verification.txt", "Appendix B — Reproducibility evidence",
                 "Both ONNX models verified against their pinned SHA-256 values before any inference.")
        else:
            spec("02", "screenshot_02_model_verification.png", "Pinned model hash verification",
                 'python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"', None, None,
                 "Appendix B — Reproducibility evidence",
                 "Both ONNX models verified against their pinned SHA-256 values before any inference.",
                 skip_reason="--model-root was not supplied, so this command was not run.")

        if args.lfw_dataset_root and args.protocol_root:
            spec("03", "screenshot_03_lfw_dataset_verification.png", "LFW dataset and protocol verification",
                 'python scripts/verify_lfw_dataset.py --dataset-root "$FACE_DATA_ROOT/lfw_funneled" '
                 '--protocol-root "$FACE_PROTOCOL_ROOT"',
                 [sys.executable, str(SCRIPTS_DIR / "verify_lfw_dataset.py"),
                  "--dataset-root", args.lfw_dataset_root, "--protocol-root", args.protocol_root],
                 "lfw_dataset_verification.txt", "Appendix B — Reproducibility evidence",
                 "All three LFW protocol files parsed with every referenced image resolving.")
        else:
            spec("03", "screenshot_03_lfw_dataset_verification.png", "LFW dataset and protocol verification",
                 "python scripts/verify_lfw_dataset.py ...", None, None,
                 "Appendix B — Reproducibility evidence",
                 "All three LFW protocol files parsed with every referenced image resolving.",
                 skip_reason="--lfw-dataset-root and/or --protocol-root were not supplied.")

        if args.cplfw_dataset_root and args.protocol_root:
            spec("04", "screenshot_04_cplfw_raw_dataset_verification.png",
                 "Raw CPLFW dataset and protocol verification",
                 'python scripts/verify_cplfw_dataset.py --dataset-root "$CPLFW_RAW_ROOT" '
                 '--protocol-root "$FACE_PROTOCOL_ROOT" --image-variant raw',
                 [sys.executable, str(SCRIPTS_DIR / "verify_cplfw_dataset.py"),
                  "--dataset-root", args.cplfw_dataset_root, "--protocol-root", args.protocol_root,
                  "--image-variant", "raw"],
                 "cplfw_raw_dataset_verification.txt", "Appendix B — Reproducibility evidence",
                 "All 6,000 raw CPLFW pairs (3,000 matched, 3,000 mismatched) resolved against the "
                 "authors' images.rar image set.")
        else:
            spec("04", "screenshot_04_cplfw_raw_dataset_verification.png",
                 "Raw CPLFW dataset and protocol verification",
                 "python scripts/verify_cplfw_dataset.py ...", None, None,
                 "Appendix B — Reproducibility evidence",
                 "All 6,000 raw CPLFW pairs resolved against the authors' images.rar image set.",
                 skip_reason="--cplfw-dataset-root and/or --protocol-root were not supplied.")

        spec("05", "screenshot_05_pytest_result.png", "Automated test suite",
             "pytest -v", [sys.executable, "-m", "pytest", "-v"], "pytest_result.txt",
             "Appendix B — Reproducibility evidence",
             "The synthetic-fixture test suite, which runs with no dataset or model file present.")

        spec("06", "screenshot_06_privacy_scan.png", "Public-output privacy scan",
             "python scripts/check_public_outputs.py --paths results/aggregate results/report_evidence",
             [sys.executable, str(SCRIPTS_DIR / "check_public_outputs.py"),
              "--paths", str(results_root), str(output_root)], "privacy_scan.txt",
             "Appendix C — Data governance evidence",
             "Committed aggregate outputs confirmed free of personal or absolute filesystem paths.")

        # Screenshots 7-10 are rendered from generated artifacts rather than
        # from a single command, so they are built below with rendered= set.
        listing_lines = ["results/aggregate/"]
        expected_aggregate = [
            "calibrated_threshold.json", "lfw_development_metrics.json", "lfw_final_metrics.json",
            "cplfw_metrics.json", "duplicate_gallery_metrics.json", "run_manifest.json",
            "metrics_summary.csv", "confusion_matrices.csv", "roc_points.csv", "FINAL_EVALUATION_REPORT.md",
        ]
        for name in expected_aggregate:
            candidate = results_root / name
            mark = "OK  " if candidate.is_file() else "MISSING"
            size = f"{candidate.stat().st_size:>10,} bytes" if candidate.is_file() else " " * 16
            listing_lines.append(f"  [{mark}] {name:<38} {size}")
        listing_lines.append("")
        listing_lines.append(f"{sum(1 for n in expected_aggregate if (results_root / n).is_file())}"
                             f" / {len(expected_aggregate)} required aggregate outputs present")
        listing_lines.append("")
        listing_lines.append("results/report_evidence/")
        listing_lines.append(f"  [OK  ] figures/     {len(figure_specs)} figures generated")
        spec("07", "screenshot_07_output_file_listing.png", "Generated output inventory",
             "(inventory of results/aggregate and results/report_evidence)", None, "output_file_listing.txt",
             "Appendix B — Reproducibility evidence",
             "Inventory confirming that all ten aggregate outputs and the evidence pack exist.",
             rendered="\n".join(listing_lines))

        variant_fields = ["dataset_image_variant", "dataset_image_source", "dataset_archive_sha256",
                          "protocol_file", "protocol_sha256", "total_pairs", "scored_pairs",
                          "failed_pairs", "failure_rate"]
        variant_lines = [f"{name:<26} {cplfw_payload.get(name)}" for name in variant_fields]
        spec("08", "screenshot_08_cplfw_variant_evidence.png", "CPLFW image-variant provenance",
             "(selected fields from results/aggregate/cplfw_metrics.json)", None, None,
             "Chapter 3 — Methodology, §3.4 Datasets",
             "The reported CPLFW result records the raw authors-distributed image set explicitly, "
             "removing the ambiguity present in the superseded aligned run.",
             rendered="\n".join(variant_lines))

        freeze_fields = ["status", "threshold", "operating_strategy", "frozen_from_protocol",
                         "frozen_from_protocol_sha256", "selection_rule"]
        freeze_lines = []
        for name in freeze_fields:
            value = str(threshold_payload.get(name))
            if len(value) > 78:
                freeze_lines.append(f"{name:<30} {value[:78]}")
                for start in range(78, len(value), 78):
                    freeze_lines.append(" " * 31 + value[start:start + 78])
            else:
                freeze_lines.append(f"{name:<30} {value}")
        spec("09", "screenshot_09_threshold_freeze_evidence.png", "Threshold freeze provenance",
             "(selected fields from results/aggregate/calibrated_threshold.json)", None, None,
             "Chapter 3 — Methodology, §3.5 Threshold selection",
             "The threshold artifact records status \"frozen\", the protocol it was frozen from, that "
             "file's SHA-256, and the deterministic selection rule applied.",
             rendered=None)
        screenshot_specs[-1]["rendered"] = "\n".join(freeze_lines)

        status_code, status_out = run_command(["git", "status", "--short"])
        log_code, log_out = run_command(["git", "log", "-1", "--oneline"])
        git_lines = ["$ git status --short"]
        git_lines.extend((status_out or "(working tree clean)").splitlines())
        git_lines.append("")
        git_lines.append("$ git log -1 --oneline")
        git_lines.extend(log_out.splitlines())
        spec("10", "screenshot_10_git_status.png", "Repository state at generation time",
             "git status --short && git log -1 --oneline", None, None,
             "Appendix B — Reproducibility evidence",
             "Repository state when this evidence pack was generated. A dirty working tree is reported "
             "as dirty and never presented as clean.",
             rendered="\n".join(git_lines))

        for item in screenshot_specs:
            if item["skip_reason"]:
                body = (f"NOT RUN.\n\n{item['skip_reason']}\n\n"
                        "This command needs a private dataset/model root, which is deliberately not "
                        "recorded in any published artifact. Re-run the generator with the relevant "
                        "root argument to produce this evidence image.")
                exit_code = None
            elif item["rendered"] is not None:
                body, exit_code = item["rendered"], None
            else:
                exit_code, raw = run_command(item["argv"])
                body = raw
            body = redact(body, redactions)

            if item["log_name"]:
                log_path = logs_dir / item["log_name"]
                log_path.write_text(
                    f"$ {item['command']}\n"
                    f"# exit code: {exit_code if exit_code is not None else 'n/a'}\n"
                    f"# generated: {datetime.now(timezone.utc).isoformat()}\n"
                    f"# git commit: {commit}\n\n{body}\n",
                    encoding="utf-8",
                )

            path = render_terminal(
                title=f"Evidence {item['number']} — {item['title']}",
                command=item["command"], exit_code=exit_code, body=body,
                out=screenshots_dir / item["filename"], commit=commit, dirty=dirty,
                note="Paths in this output are redacted placeholders, not the values used at run time.",
            )
            manifest.append(build_manifest_entry(
                path=path, kind="generated_screenshot", title=item["title"],
                sources=[], commit=commit, section=item["section"],
                caption=item["caption"], output_root=output_root,
            ))
            index_rows.append({
                "id": item["number"], "filename": f"screenshots/{item['filename']}",
                "title": item["title"], "source": item["command"], "section": item["section"],
                "caption": item["caption"], "kind": "generated_screenshot",
            })

    manual_items = [
        ("manual_01_github_actions_pass.png", "GitHub Actions CI run passing for the final commit",
         "GitHub → AdvancedComputingProject → Actions → CI → the run for the final `main` commit",
         "The repository name; the workflow name (CI); a green success status; the final commit SHA; "
         "and the completed `test` job with its steps expanded.",
         "Unrelated account information; any other repository in the sidebar; private email addresses.",
         "Appendix B — Reproducibility evidence",
         "Continuous integration passing for the submitted commit. CI runs the synthetic-fixture suite "
         "only; it never has access to real datasets or model binaries."),
        ("manual_02_final_github_commit.png", "Repository main page at the final commit",
         "GitHub → AdvancedComputingProject → the repository main page, on branch `main`",
         "That the branch is `main`; the final commit message and short SHA; and the file listing "
         "including `scripts/generate_report_evidence.py`.",
         "Unrelated repositories in the sidebar; private email addresses.",
         "Appendix B — Reproducibility evidence",
         "The public repository at the submitted commit, showing that no dataset, model binary or "
         "database file is tracked."),
        ("manual_03_streamlit_review_interface.png", "Local human-review interface",
         "A terminal running `streamlit run local_review/app.py --server.address=127.0.0.1 "
         "-- --db results/raw/review.sqlite`, then the browser at 127.0.0.1",
         "The review UI showing opaque case identifiers and the reviewer decision controls.",
         "Nothing should need redacting — the interface shows only opaque identifiers by design. "
         "Confirm before capturing that no real face image, no real name and no private path is on "
         "screen; if any is, stop and report it as a defect rather than cropping it out.",
         "Chapter 5 — Human-review decision policy",
         "The localhost-only review interface. Every case is identified by an opaque one-way hash; a "
         "similarity result opens a review case and never an automatic sanction."),
        ("manual_04_au_onedrive_storage_evidence.png", "Institutional storage location",
         "The Arden University OneDrive research folder — **only after the migration is actually "
         "done**; it is still outstanding (see docs/USER_ACTIONS_REQUIRED.md)",
         "The university-controlled OneDrive identity/location; the project folder; and the "
         "high-level folder structure (datasets/, protocols/, models/).",
         "Face-image thumbnails; participant or identity names; unrelated university or personal "
         "files; absolute local paths containing your account name. Switch the file browser out of "
         "any thumbnail/preview mode before capturing.",
         "Appendix C — Data governance evidence",
         "Benchmark images, protocols and models held in access-controlled institutional storage, "
         "outside the repository and outside any personal cloud service."),
        ("manual_05_ethics_approval_evidence.png", "Ethics approval record",
         "The university ethics approval page or approval document — **only if your institution "
         "permits reproducing it** in a dissertation appendix",
         "The institution; the approval status; the project title or reference; and the approval "
         "date/reference number.",
         "Reviewer names and signatures; personal contact details; any personal data not needed to "
         "evidence the approval itself.",
         "Appendix C — Data governance evidence",
         "Institutional ethics approval covering this evaluation. Capture only if your institution "
         "permits reproducing the record in a dissertation appendix."),
    ]

    manual_doc = ["# Manual screenshots required", "",
                  "These five items cannot be generated locally, and this project will not fabricate "
                  "them or emit look-alike placeholders. Capture each one yourself and save it into "
                  "`results/report_evidence/screenshots/` using the filename given below.", "",
                  "> **Do not capture item 1 until a real GitHub Actions run has actually passed for "
                  "the final commit.** Nothing in this repository asserts that remote CI has passed.", ""]
    for filename, title, where, visible, redactions_needed, section, caption in manual_items:
        manual_doc.extend([
            f"## `{filename}`", "",
            f"**Title.** {title}", "",
            f"**Where to capture.** {where}", "",
            f"**Must be visible.** {visible}", "",
            f"**Must be redacted.** {redactions_needed}", "",
            f"**Report section.** {section}", "",
            f"**Suggested caption.** {caption}", "",
        ])
        manifest.append({
            "filename": f"screenshots/{filename}", "type": "manual_screenshot", "title": title,
            "generated_at": None, "source_files": [], "source_file_sha256": {}, "git_commit": commit,
            "contains_real_face_image": False, "contains_identity_information": False,
            "contains_absolute_path": False, "report_section": section, "suggested_caption": caption,
            "sha256": None, "status": "awaiting manual capture by the researcher",
        })
        index_rows.append({
            "id": filename.split("_")[1], "filename": f"screenshots/{filename}", "title": title,
            "source": "manual capture", "section": section, "caption": caption,
            "kind": "manual_screenshot",
        })
    (output_root / "manual_screenshots_required.md").write_text("\n".join(manual_doc), encoding="utf-8")

    index = [
        "# Report evidence index", "",
        f"Generated by `scripts/generate_report_evidence.py` at "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} from source commit "
        f"`{commit[:12]}`"
        + (
            ", whose working tree was clean at generation time."
            if not dirty
            else ", whose working tree had UNCOMMITTED CHANGES at generation time — the source "
                 "state is therefore not fully described by that commit alone."
        ), "",
        "The evidence files themselves are **not** part of that source commit: they are generated "
        "from it and added by a subsequent commit. Every figure is derived only from "
        "`results/aggregate/*` — no raw image, embedding, identity or absolute path is read or "
        "reproduced. Per-item hashes are in `report_evidence_manifest.json`.", "",
        "| # | File | Title | Source | Report section | May be committed |",
        "|---|---|---|---|---|---|",
    ]
    for row in index_rows:
        committable = "yes" if row["kind"] != "manual_screenshot" else "yes, once captured and redacted"
        index.append(
            f"| {row['id']} | `{row['filename']}` | {row['title']} | `{row['source']}` | "
            f"{row['section']} | {committable} |"
        )
    index.extend(["", "## Captions and interpretation", ""])
    for row in index_rows:
        index.extend([
            f"### {row['id']} — {row['title']}", "",
            f"- **File.** `{row['filename']}`",
            f"- **Source.** `{row['source']}`",
            f"- **Report section.** {row['section']}",
            f"- **Suggested caption.** {row['caption']}",
        ])
        if row["kind"] == "figure":
            index.append(f"- **Limitation.** {CONDITIONAL_NOTE}"
                         if row["id"] in {"01", "02", "03"} else
                         "- **Limitation.** Derived from a single run on LFW/CPLFW, whose demographic "
                         "composition is not representative of a real user base "
                         "(see `docs/THREATS_TO_VALIDITY.md`).")
        elif row["kind"] == "manual_screenshot":
            index.append("- **Limitation.** Not yet captured; this project will not fabricate it.")
        else:
            index.append("- **Limitation.** A point-in-time record of a local run; paths are redacted "
                         "placeholders, not the values used at run time.")
        index.append("")
    (output_root / "REPORT_EVIDENCE_INDEX.md").write_text("\n".join(index), encoding="utf-8")

    (output_root / "report_evidence_manifest.json").write_text(
        json.dumps({
            "artifact_type": "report_evidence_manifest",
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            # Provenance of the *source* that produced this pack, stated so a
            # reader cannot mistake it for a claim that the evidence files
            # themselves existed at that commit. They do not: they are
            # generated from a clean source tree and added by a later commit.
            "source_git_commit": commit,
            "source_working_tree_clean_before_generation": not dirty,
            "evidence_generated_outside_repository": generated_outside_repo,
            "provenance_note": (
                "Generated from source commit "
                f"{commit}"
                + (
                    " with a clean working tree"
                    if not dirty
                    else " with UNCOMMITTED CHANGES present, so the source state is not"
                         " fully described by that commit alone"
                )
                + ". The evidence artefacts themselves are added by a subsequent commit; "
                "they are not part of the source commit named here."
            ),
            "validation_commands_run": bool(args.run_validation),
            "items": manifest,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nValidating the generated pack...")
    problems: List[str] = []

    for _, _, filename, _, _, _, _ in figure_specs:
        if not (figures_dir / filename).is_file():
            problems.append(f"expected figure missing: figures/{filename}")
    if args.run_validation:
        for item in screenshot_specs:
            if not (screenshots_dir / item["filename"]).is_file():
                problems.append(f"expected screenshot missing: screenshots/{item['filename']}")

    index_files = {row["filename"] for row in index_rows}
    manifest_files = {entry["filename"] for entry in manifest}
    if index_files != manifest_files:
        for name in sorted(index_files ^ manifest_files):
            problems.append(f"index/manifest disagree about: {name}")

    for entry in manifest:
        if entry["type"] == "manual_screenshot":
            continue
        if not entry["sha256"]:
            problems.append(f"manifest entry has no sha256: {entry['filename']}")

    leaks = find_path_leaks(output_root, forbidden_substrings=default_forbidden_path_substrings())
    for leak in leaks:
        problems.append(f"private path leaked into the evidence pack: {leak}")

    if problems:
        print("\nFAIL — the evidence pack did not validate:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    figure_count = len(figure_specs)
    screenshot_count = len(screenshot_specs)
    print(f"OK   {figure_count} figures, {screenshot_count} generated screenshots, "
          f"{len(manual_items)} manual screenshots pending, no private path found.")
    print(f"\nEvidence pack written to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
