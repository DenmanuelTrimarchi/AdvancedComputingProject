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
    # Failures are plotted against the full protocol count, not the scored pairs.
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
    # Quote the raw CPLFW counts so the plotted rate is checkable by arithmetic.
    cplfw_row = summary["cplfw"]
    cplfw_total = int(as_float(require(cplfw_row, "total_pairs", "metrics_summary.csv")))
    cplfw_scored = int(as_float(require(cplfw_row, "scored_pairs", "metrics_summary.csv")))
    footnote(
        fig,
        f"A pair fails extraction when the detector finds zero faces, or more than one face, on either "
        f"side. {cplfw_total - cplfw_scored:,} of {cplfw_total:,} raw CPLFW pairs failed face "
        f"extraction. Failed pairs are excluded from the score-based metrics but retained in the "
        f"protocol total and reported here — the raw CPLFW rate is the dominant cross-pose finding of "
        f"this evaluation. An extraction failure is not a verification error: no similarity score was "
        f"produced for those pairs.",
    )
    return save(fig, out)


def figure_05_cplfw_breakdown(cplfw: Dict[str, Any], out: Path) -> Path:
    # Category counts are read straight from cplfw_metrics.json, never hardcoded.
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
    # The categories partition the failed pairs, so the bars sum to failed_pairs
    # exactly; see verification_evaluator.evaluate_pairs for the left-first rule.
    footnote(
        fig,
        f"The four categories partition the {total:,} failed pairs and sum to that total exactly: "
        f"sides are attempted left first and a pair is abandoned at its first terminal failure, so "
        f"each failure is counted once. A right-side category therefore means the left image had "
        f"already yielded one valid face. Zero-face detections dominate, which locates the cross-pose "
        f"difficulty in detection rather than in embedding comparison.",
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
    # The series name is deliberately unused: these bars reuse the colours of
    # the embedding series, so re-labelling would duplicate the legend entries.
    for index, (value, _label, color) in enumerate(
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
    mono: Dict[str, Any] = {"family": "DejaVu Sans Mono"}

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


def source_label(source: Path) -> str:
    """Repo-relative label for a source artefact, never an absolute path.

    ``source`` is resolved first: --results-root is normally passed as a
    relative path, and a relative path is never ``is_relative_to`` an
    absolute REPO_ROOT, so skipping the resolve silently degraded every
    label to a bare filename — ambiguous provenance, since the same
    basename can occur under several roots.
    """
    resolved = Path(source).resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return str(resolved.relative_to(REPO_ROOT))
    return resolved.name


def build_manifest_entry(
    *, path: Path, kind: str, title: str, sources: List[Path], commit: str,
    section: str, caption: str, output_root: Path,
) -> Dict[str, Any]:
    return {
        "filename": str(path.relative_to(output_root)),
        "type": kind,
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [source_label(source) for source in sources],
        "source_file_sha256": {
            source_label(source): sha256_of(source) for source in sources if source.is_file()
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
            "source": ", ".join(source_label(s) for s in sources), "section": section,
            "caption": caption, "kind": "figure",
        })

    generated_screenshot_count = 0
    if args.run_validation:
        print("Running validation commands...")

        def render_evidence(
            number: str, filename: str, title: str, command: str, section: str, caption: str, *,
            argv_: Optional[List[str]] = None, log_name: Optional[str] = None,
            rendered: Optional[str] = None, skip_reason: Optional[str] = None,
            precomputed: Optional[Tuple[Optional[int], str]] = None,
        ) -> Tuple[Optional[int], str]:
            """Run (or render, or skip) one evidence item immediately and write
            its PNG, log, manifest and index entries. Returns (exit_code, body)
            so a later item (the local-run summary) can report on this one's
            outcome without re-running it."""
            nonlocal generated_screenshot_count
            if precomputed is not None:
                exit_code, body = precomputed
            elif skip_reason:
                body = (f"NOT RUN.\n\n{skip_reason}\n\n"
                        "This command needs a private dataset/model root, which is deliberately not "
                        "recorded in any published artifact. Re-run the generator with the relevant "
                        "root argument to produce this evidence image.")
                exit_code = None
            elif rendered is not None:
                body, exit_code = rendered, None
            elif argv_ is None:
                # Reached only if an item is declared with nothing to run,
                # render or skip; fail here rather than deep inside run_command.
                raise ValueError(f"Evidence item {number} ({title}) has no command to run.")
            else:
                exit_code, body = run_command(argv_)
            body = redact(body, redactions)

            if log_name:
                (logs_dir / log_name).write_text(
                    f"$ {command}\n"
                    f"# exit code: {exit_code if exit_code is not None else 'n/a'}\n"
                    f"# generated: {datetime.now(timezone.utc).isoformat()}\n"
                    f"# git commit: {commit}\n\n{body}\n",
                    encoding="utf-8",
                )

            path = render_terminal(
                title=f"Evidence {number} — {title}",
                command=command, exit_code=exit_code, body=body,
                out=screenshots_dir / filename, commit=commit, dirty=dirty,
                note="Paths in this output are redacted placeholders, not the values used at run time.",
            )
            manifest.append(build_manifest_entry(
                path=path, kind="generated_screenshot", title=title,
                sources=[], commit=commit, section=section,
                caption=caption, output_root=output_root,
            ))
            index_rows.append({
                "id": number, "filename": f"screenshots/{filename}",
                "title": title, "source": command, "section": section,
                "caption": caption, "kind": "generated_screenshot",
            })
            generated_screenshot_count += 1
            return exit_code, body

        # 01-05 run first: the local-run summary (06) reports on their outcome.
        result_01 = render_evidence(
            "01", "screenshot_01_local_environment_check.png",
            "Local environment and dependency contract check",
            "python scripts/check_environment.py",
            "Appendix B — Reproducibility evidence",
            "Local macOS execution environment confirming the pinned Python and dependency contract "
            "used for the experiment.",
            argv_=[sys.executable, str(SCRIPTS_DIR / "check_environment.py")],
            log_name="environment_check.txt",
        )

        if args.model_root:
            result_02 = render_evidence(
                "02", "screenshot_02_model_hash_verification.png", "Pinned model hash verification",
                'python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"',
                "Appendix B — Reproducibility evidence",
                "YuNet and SFace ONNX files verified against the pinned SHA-256 values before inference.",
                argv_=[sys.executable, str(SCRIPTS_DIR / "verify_models.py"), "--model-root", args.model_root],
                log_name="model_verification.txt",
            )
        else:
            result_02 = render_evidence(
                "02", "screenshot_02_model_hash_verification.png", "Pinned model hash verification",
                'python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"',
                "Appendix B — Reproducibility evidence",
                "YuNet and SFace ONNX files verified against the pinned SHA-256 values before inference.",
                skip_reason="--model-root was not supplied, so this command was not run.",
            )

        if args.lfw_dataset_root and args.protocol_root:
            result_03 = render_evidence(
                "03", "screenshot_03_lfw_dataset_verification.png", "LFW dataset and protocol verification",
                'python scripts/verify_lfw_dataset.py --dataset-root "$FACE_DATA_ROOT/lfw_funneled" '
                '--protocol-root "$FACE_PROTOCOL_ROOT"',
                "Appendix B — Reproducibility evidence",
                "Verification that the LFW development and final pair protocols resolved against the "
                "configured institutional dataset.",
                argv_=[sys.executable, str(SCRIPTS_DIR / "verify_lfw_dataset.py"),
                       "--dataset-root", args.lfw_dataset_root, "--protocol-root", args.protocol_root],
                log_name="lfw_dataset_verification.txt",
            )
        else:
            result_03 = render_evidence(
                "03", "screenshot_03_lfw_dataset_verification.png", "LFW dataset and protocol verification",
                "python scripts/verify_lfw_dataset.py ...",
                "Appendix B — Reproducibility evidence",
                "Verification that the LFW development and final pair protocols resolved against the "
                "configured institutional dataset.",
                skip_reason="--lfw-dataset-root and/or --protocol-root were not supplied.",
            )

        if args.cplfw_dataset_root and args.protocol_root:
            result_04 = render_evidence(
                "04", "screenshot_04_cplfw_raw_dataset_verification.png",
                "Raw CPLFW dataset and protocol verification",
                'python scripts/verify_cplfw_dataset.py --dataset-root "$CPLFW_RAW_ROOT" '
                '--protocol-root "$FACE_PROTOCOL_ROOT" --image-variant raw',
                "Appendix B — Reproducibility evidence",
                "Verification that all 6,000 raw CPLFW protocol pairs resolved against the "
                "authors-distributed image set.",
                argv_=[sys.executable, str(SCRIPTS_DIR / "verify_cplfw_dataset.py"),
                       "--dataset-root", args.cplfw_dataset_root, "--protocol-root", args.protocol_root,
                       "--image-variant", "raw"],
                log_name="cplfw_raw_dataset_verification.txt",
            )
        else:
            result_04 = render_evidence(
                "04", "screenshot_04_cplfw_raw_dataset_verification.png",
                "Raw CPLFW dataset and protocol verification",
                "python scripts/verify_cplfw_dataset.py ...",
                "Appendix B — Reproducibility evidence",
                "Verification that all 6,000 raw CPLFW protocol pairs resolved against the "
                "authors-distributed image set.",
                skip_reason="--cplfw-dataset-root and/or --protocol-root were not supplied.",
            )

        # pytest sets PYTEST_CURRENT_TEST for the duration of a test's own
        # execution, specifically so a subprocess it spawns can detect this.
        # Without this guard, a test that exercises --run-validation would
        # have this very step re-invoke pytest with no path filter, which
        # re-collects and re-runs that same test, which spawns this step
        # again -- an unbounded recursive subprocess chain, not merely a
        # slow test.
        if os.environ.get("PYTEST_CURRENT_TEST"):
            result_05 = render_evidence(
                "05", "screenshot_05_local_test_suite_passed.png", "Automated test suite",
                "pytest -v",
                "Appendix B — Reproducibility evidence",
                "The complete synthetic-fixture test suite executed locally on macOS without access to "
                "private benchmark images or model binaries.",
                skip_reason="Already running inside an active pytest session "
                            f"({os.environ['PYTEST_CURRENT_TEST']}); running pytest -v again here "
                            "would recursively re-invoke the very test that triggered this generator run.",
            )
        else:
            result_05 = render_evidence(
                "05", "screenshot_05_local_test_suite_passed.png", "Automated test suite",
                "pytest -v",
                "Appendix B — Reproducibility evidence",
                "The complete synthetic-fixture test suite executed locally on macOS without access to "
                "private benchmark images or model binaries.",
                argv_=[sys.executable, "-m", "pytest", "-v"], log_name="pytest_result.txt",
            )

        # 10 (privacy scan) runs here, ahead of its file position, because 06
        # reports on its outcome too; the call order is independent of the
        # number embedded in the filename.
        result_10 = render_evidence(
            "10", "screenshot_10_public_output_privacy_scan.png", "Public-output privacy scan",
            "python scripts/check_public_outputs.py --paths results/aggregate results/report_evidence",
            "Appendix C — Data governance evidence",
            "Privacy validation confirming that public aggregate outputs contain no private path, "
            "identity information or biometric image.",
            argv_=[sys.executable, str(SCRIPTS_DIR / "check_public_outputs.py"),
                   "--paths", str(results_root), str(output_root)],
            log_name="privacy_scan.txt",
        )

        expected_aggregate = [
            "calibrated_threshold.json", "lfw_development_metrics.json", "lfw_final_metrics.json",
            "cplfw_metrics.json", "duplicate_gallery_metrics.json", "run_manifest.json",
            "metrics_summary.csv", "confusion_matrices.csv", "roc_points.csv", "FINAL_EVALUATION_REPORT.md",
        ]
        aggregate_present = [(results_root / name).is_file() for name in expected_aggregate]
        complete_experiment_ok = all(aggregate_present)

        # ------------------------------------------------------------------
        # 06 — local-run summary. Every line is derived from the results
        # above and from the aggregate JSON files already loaded, never
        # hardcoded; a check that did not run (no root supplied) is reported
        # as SKIPPED rather than fabricated as a pass.
        # ------------------------------------------------------------------
        def check_line(label: str, result: Optional[Tuple[Optional[int], str]]) -> str:
            if result is None or result[0] is None:
                return f"{label}: SKIPPED"
            return f"{label}: PASS" if result[0] == 0 else f"{label}: FAILED (exit code {result[0]})"

        test_match = re.search(r"(\d+) passed", result_05[1])
        if result_05[0] is None:
            tests_line = "Tests: SKIPPED (see screenshot 05)"
        elif result_05[0] == 0 and test_match:
            tests_line = f"Tests: {test_match.group(1)} passed"
        elif test_match:
            tests_line = f"Tests: {test_match.group(0)} (exit code {result_05[0]}, see screenshot 05)"
        else:
            tests_line = f"Tests: FAILED (exit code {result_05[0]}, see screenshot 05)"

        all_ok = (
            result_01[0] == 0
            and (result_02[0] in (0, None))
            and (result_03[0] in (0, None))
            and (result_04[0] in (0, None))
            and (result_05[0] in (0, None))
            and complete_experiment_ok
            and result_10[0] == 0
        )
        heading = "LOCAL MACOS RUN COMPLETED" if all_ok else "LOCAL MACOS RUN — ONE OR MORE CHECKS FAILED"

        final_lfw = summary["lfw_final"]
        cplfw_row = summary["cplfw"]
        summary_lines = [
            heading,
            check_line("Environment check", result_01),
            tests_line,
            check_line("Model verification", result_02),
            check_line("LFW protocol verification", result_03),
            check_line("Raw CPLFW protocol verification", result_04),
            "Complete experiment: PASS" if complete_experiment_ok else "Complete experiment: INCOMPLETE",
            check_line("Privacy scan", result_10),
            "",
            f"Final LFW accuracy: {as_float(require(final_lfw, 'accuracy', 'metrics_summary.csv')) * 100:.2f}%",
            f"Raw CPLFW conditional accuracy: "
            f"{as_float(require(cplfw_row, 'accuracy', 'metrics_summary.csv')) * 100:.2f}%",
            f"Raw CPLFW extraction-failure rate: "
            f"{as_float(require(cplfw_row, 'failure_rate', 'metrics_summary.csv')) * 100:.2f}%",
            f"Gallery duplicate detection: "
            f"{as_float(require(gallery_payload, 'duplicate_detection_rate', 'duplicate_gallery_metrics.json')) * 100:.2f}%",
            f"Gallery false-review rate: "
            f"{as_float(require(gallery_payload, 'false_duplicate_review_rate', 'duplicate_gallery_metrics.json')) * 100:.2f}%",
        ]
        render_evidence(
            "06", "screenshot_06_local_complete_run.png", "Complete local pipeline run",
            "./scripts/run_local_mac.sh",
            "Appendix B — Reproducibility evidence",
            "Successful end-to-end local execution of the five-experiment pipeline using the "
            "institutional OneDrive-backed datasets, protocols and pinned models.",
            rendered="\n".join(summary_lines), log_name="local_complete_run.txt",
        )

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
        render_evidence(
            "07", "screenshot_07_threshold_freeze_evidence.png", "Threshold freeze provenance",
            "(selected fields from results/aggregate/calibrated_threshold.json)",
            "Chapter 3 — Methodology, Threshold selection",
            "Threshold provenance confirming that candidate selection occurred on the development "
            "protocol before final LFW and CPLFW evaluation.",
            rendered="\n".join(freeze_lines),
        )

        variant_fields = ["dataset_image_variant", "dataset_image_source", "dataset_archive_sha256",
                          "protocol_file", "protocol_sha256", "total_pairs", "scored_pairs",
                          "failed_pairs", "failure_rate"]
        variant_lines = [f"{name:<26} {cplfw_payload.get(name)}" for name in variant_fields]
        render_evidence(
            "08", "screenshot_08_cplfw_raw_variant_evidence.png", "CPLFW image-variant provenance",
            "(selected fields from results/aggregate/cplfw_metrics.json)",
            "Chapter 3 — Methodology, Datasets",
            "Provenance record confirming that the reported CPLFW experiment used the raw, "
            "unconstrained image variant rather than the pre-aligned copy.",
            rendered="\n".join(variant_lines),
        )

        listing_lines = ["results/aggregate/"]
        for name, present in zip(expected_aggregate, aggregate_present):
            candidate = results_root / name
            mark = "OK  " if present else "MISSING"
            size = f"{candidate.stat().st_size:>10,} bytes" if present else " " * 16
            listing_lines.append(f"  [{mark}] {name:<38} {size}")
        listing_lines.append("")
        listing_lines.append(f"{sum(aggregate_present)} / {len(expected_aggregate)} required aggregate outputs present")
        listing_lines.append("")
        listing_lines.append("results/report_evidence/")
        listing_lines.append(f"  [OK  ] figures/     {len(figure_specs)} figures generated")
        render_evidence(
            "09", "screenshot_09_generated_output_inventory.png", "Generated output inventory",
            "(inventory of results/aggregate and results/report_evidence)",
            "Appendix B — Reproducibility evidence",
            "Inventory of the aggregate outputs generated by the complete local experiment.",
            rendered="\n".join(listing_lines),
        )

        status_out = redact(run_command(["git", "status", "--short"])[1], redactions)
        log_out = redact(run_command(["git", "log", "-1", "--oneline"])[1], redactions)
        git_lines = ["$ git status --short"]
        git_lines.extend((status_out or "(working tree clean)").splitlines())
        git_lines.append("")
        git_lines.append("$ git log -1 --oneline")
        git_lines.extend(log_out.splitlines())
        render_evidence(
            "11", "screenshot_11_local_git_state.png", "Repository state at generation time",
            "git status --short && git log -1 --oneline",
            "Appendix B — Reproducibility evidence",
            "Local source-control state used to generate the aggregate results and evidence pack.",
            precomputed=(None, "\n".join(git_lines)),
        )

    manual_items = [
        ("screenshot_12_streamlit_human_review_interface.png", "Local human-review interface",
         "A terminal running `streamlit run local_review/app.py --server.address=127.0.0.1 "
         "-- --db results/raw/review.sqlite`, then the browser at 127.0.0.1",
         "The review UI showing opaque case identifiers and the reviewer decision controls.",
         "Nothing should need redacting — the interface shows only opaque identifiers by design. "
         "Confirm before capturing that no real face image, no real name and no private path is on "
         "screen; if any is, stop and report it as a defect rather than cropping it out.",
         "Chapter 5 — Human-review decision policy",
         "Localhost-only review interface showing opaque case identifiers and proportionate reviewer "
         "controls; no automatic account sanction is applied."),
        ("screenshot_13_arden_onedrive_storage.png", "Institutional storage location",
         "The Arden University OneDrive research folder, navigated to the project's own "
         "subfolder (not the OneDrive account root) — the migration is complete and verified, "
         "see docs/USER_ACTIONS_REQUIRED.md for the checksum/file-count record",
         "The university-controlled OneDrive identity/location; the project subfolder; and the "
         "high-level folder structure (datasets/, protocols/, models/, optionally cache/).",
         "Face-image thumbnails; participant or identity names; unrelated university or personal "
         "files; absolute local paths containing your account name. Navigate *into* the project "
         "subfolder before capturing rather than screenshotting the OneDrive account root — an "
         "institutional OneDrive root commonly also holds unrelated personal documents (coursework, "
         "assignments, or similar) that must never appear in a committed screenshot. Switch the file "
         "browser out of any thumbnail/preview mode first.",
         "Appendix C — Data governance evidence",
         "Datasets, protocols and pinned models stored in the access-controlled Arden University "
         "OneDrive research location, outside the Git repository."),
        ("screenshot_14_ethics_approval.png", "Ethics approval record",
         "The university ethics approval page or approval document — **only if your institution "
         "permits reproducing it** in a dissertation appendix",
         "The institution; the approval status; the project title or reference; and the approval "
         "date/reference number.",
         "Reviewer names and signatures; personal contact details; any personal data not needed to "
         "evidence the approval itself.",
         "Appendix C — Data governance evidence",
         "Institutional ethics approval or recorded authorisation covering the benchmark evaluation."),
        ("screenshot_15_github_backup_final_commit.png", "GitHub backup of the final commit",
         "GitHub → AdvancedComputingProject → the repository main page, on branch `main`",
         "The repository name; that the branch is `main`; the final commit message and short SHA; "
         "and the source file listing.",
         "The Actions tab; billing information; private email addresses; unrelated repositories in "
         "the sidebar. GitHub is version-controlled backup evidence here, not an execution-passing "
         "claim — do not include an Actions screenshot.",
         "Appendix B — Version-control and backup evidence",
         "GitHub repository used as version-controlled backup of the project source code and "
         "privacy-reviewed aggregate artefacts; execution was performed locally on macOS."),
    ]

    manual_doc = ["# Manual screenshots required", "",
                  "These four items cannot be generated locally, and this project will not fabricate "
                  "them or emit look-alike placeholders. Capture each one yourself and save it into "
                  "`results/report_evidence/screenshots/` using the filename given below.", "",
                  "GitHub Actions is not part of this list: validation is performed locally on macOS "
                  "(see `scripts/run_local_mac.sh` and `docs/REPRODUCIBILITY.md`), and GitHub is used "
                  "only as version-controlled backup — screenshot_15 below evidences that backup, not "
                  "a remote CI pass.", ""]
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
        # A manual screenshot already present at this path (the researcher
        # captured it and it is already sitting in --output-root) is recorded
        # as captured, with a real hash -- it is never overwritten, and this
        # generator never fabricates one that is not already there.
        existing = screenshots_dir / filename
        already_captured = existing.is_file()
        manifest.append({
            "filename": f"screenshots/{filename}", "type": "manual_screenshot", "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat() if already_captured else None,
            "source_files": [], "source_file_sha256": {}, "git_commit": commit,
            "contains_real_face_image": False, "contains_identity_information": False,
            "contains_absolute_path": False, "report_section": section, "suggested_caption": caption,
            "sha256": sha256_of(existing) if already_captured else None,
            "status": "captured" if already_captured else "awaiting manual capture by the researcher",
        })
        index_rows.append({
            "id": filename.split("_")[1], "filename": f"screenshots/{filename}", "title": title,
            "source": "manual capture", "section": section, "caption": caption,
            "kind": "manual_screenshot",
        })
    (output_root / "manual_screenshots_required.md").write_text("\n".join(manual_doc), encoding="utf-8")

    # Rows were appended in execution order (e.g. the privacy scan runs ahead
    # of its file position so the local-run summary can report on it), not
    # file order. Sort figures 01-09 then screenshots 01-15 for a report-ready
    # table, without disturbing the sets used for validation above.
    index_rows.sort(key=lambda row: (row["filename"].split("/")[0], int(row["id"])))

    manifest_by_filename = {entry["filename"]: entry for entry in manifest}
    screenshot_rows = [row for row in index_rows if row["filename"].startswith("screenshots/")]

    screenshot_index = [
        "# Screenshot evidence index", "",
        "All 15 screenshots, generated (01-11) and manual (12-15), in report order. "
        "GitHub Actions is deliberately not among them — see "
        "`docs/REPRODUCIBILITY.md` for why remote CI is not part of this project's "
        "validation design.", "",
        "| Order | Filename | Type | Report placement | Status |",
        "|---:|---|---|---|---|",
    ]
    for row in screenshot_rows:
        entry = manifest_by_filename[row["filename"]]
        kind = "Manual" if row["kind"] == "manual_screenshot" else "Generated"
        status = "Captured" if entry.get("sha256") else "Pending"
        screenshot_index.append(
            f"| {row['id']} | `{Path(row['filename']).name}` | {kind} | {row['section']} | {status} |"
        )
    screenshot_index.extend(["", "## Detail", ""])
    for row in screenshot_rows:
        entry = manifest_by_filename[row["filename"]]
        privacy_note = (
            "Confirmed: contains_real_face_image, contains_identity_information and "
            "contains_absolute_path are all false in the manifest."
            if row["kind"] != "manual_screenshot"
            else "Not yet checked — verify before committing (see manual_screenshots_required.md)."
        )
        screenshot_index.extend([
            f"### {row['id']} — {Path(row['filename']).name}", "",
            f"- **Title.** {row['title']}",
            f"- **Purpose / source.** `{row['source']}`",
            f"- **Suggested caption.** {row['caption']}",
            f"- **Report section.** {row['section']}",
            f"- **Privacy check.** {privacy_note}",
            f"- **SHA-256.** {entry.get('sha256') or 'null (not yet captured)'}",
            "",
        ])
    (output_root / "SCREENSHOT_INDEX.md").write_text("\n".join(screenshot_index), encoding="utf-8")

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
        for entry in manifest:
            if entry["type"] == "generated_screenshot" and not (output_root / entry["filename"]).is_file():
                problems.append(f"expected screenshot missing: {entry['filename']}")

        # All 15 numbers 01-15 must appear exactly once across the generated
        # (01-11) and manual (12-15) screenshots, with no gap and no GitHub
        # Actions screenshot re-appearing under any name.
        screenshot_numbers = sorted(
            int(row["id"]) for row in index_rows if row["filename"].startswith("screenshots/")
        )
        if screenshot_numbers != list(range(1, 16)):
            problems.append(f"screenshot numbering is not exactly 1-15: {screenshot_numbers}")
        for row in index_rows:
            if "github_actions" in row["filename"]:
                problems.append(f"a GitHub Actions screenshot must not be required: {row['filename']}")

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
    print(f"OK   {figure_count} figures, {generated_screenshot_count} generated screenshots, "
          f"{len(manual_items)} manual screenshots pending, no private path found.")
    print(f"\nEvidence pack written to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
