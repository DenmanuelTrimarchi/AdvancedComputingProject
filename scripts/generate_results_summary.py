#!/usr/bin/env python3
"""Generate a single, plain-English results summary: every figure shown
inline with a short, jargon-light description of what it means. This is
deliberately a quick-look companion, not a replacement for
``results/report_evidence/REPORT_EVIDENCE_INDEX.md`` (the dissertation-grade
evidence index with chapter placements, hashes and privacy flags).

Every number in the write-up is read from ``results/aggregate/*`` at
generation time -- nothing here is hardcoded. If the nine figures do not
already exist under --figures-root, this script generates them first by
calling scripts/generate_report_evidence.py in its default (figures-only)
mode, so a first-time reader only has to run one command.

Usage:
    python scripts/generate_results_summary.py
    # or, explicitly:
    python scripts/generate_results_summary.py \
        --results-root results/aggregate \
        --figures-root results/report_evidence/figures \
        --output results/RESULTS_SUMMARY.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIGURES = [
    "figure_01_roc_comparison.png",
    "figure_02_lfw_final_confusion_matrix.png",
    "figure_03_cplfw_confusion_matrix.png",
    "figure_04_extraction_failure_rates.png",
    "figure_05_cplfw_failure_breakdown.png",
    "figure_06_gallery_outcomes.png",
    "figure_07_threshold_candidate_comparison.png",
    "figure_08_latency_comparison.png",
    "figure_09_experiment_flow.png",
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Required aggregate output is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv_rows(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Required aggregate output is missing: {path}")
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["experiment"]: row for row in csv.DictReader(handle)}


def pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def one_in(value: Any) -> str:
    """'about 1 in N' phrasing for an error rate, easier to picture than a
    bare percentage."""
    rate = float(value)
    if rate <= 0:
        return "effectively none"
    return f"about 1 in {round(1 / rate)}"


def ensure_figures(results_root: Path, figures_root: Path) -> None:
    missing = [name for name in REQUIRED_FIGURES if not (figures_root / name).is_file()]
    if not missing:
        return
    print(f"{len(missing)} figure(s) missing under {figures_root} — generating them now...")
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_report_evidence.py"),
         "--results-root", str(results_root), "--output-root", str(figures_root.parent)],
        cwd=REPO_ROOT,
    )
    if completed.returncode != 0:
        raise SystemExit("Figure generation failed; see the output above.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", type=Path, default=Path("results/aggregate"))
    parser.add_argument("--figures-root", type=Path, default=Path("results/report_evidence/figures"))
    parser.add_argument("--output", type=Path, default=Path("results/RESULTS_SUMMARY.md"))
    args = parser.parse_args(argv)

    ensure_figures(args.results_root, args.figures_root)

    final = load_json(args.results_root / "lfw_final_metrics.json")
    cplfw = load_json(args.results_root / "cplfw_metrics.json")
    gallery = load_json(args.results_root / "duplicate_gallery_metrics.json")
    threshold = load_json(args.results_root / "calibrated_threshold.json")
    summary = load_csv_rows(args.results_root / "metrics_summary.csv")

    fig_dir = os.path.relpath(args.figures_root, start=args.output.parent)

    breakdown = cplfw["failure_breakdown"]
    selected = threshold["operating_strategy"]

    lines: List[str] = []

    def h(text: str) -> None:
        lines.append(text)
        lines.append("")

    def p(text: str) -> None:
        lines.append(text)
        lines.append("")

    def fig(number: str, filename: str, alt: str) -> None:
        lines.append(f"![{alt}]({fig_dir}/{filename})")
        lines.append("")

    h("# Results at a glance")
    p(
        "A plain-English walkthrough of every figure this project generates. For the "
        "full dissertation-grade evidence index (chapter placements, source hashes, "
        "privacy flags), see `results/report_evidence/REPORT_EVIDENCE_INDEX.md` instead — "
        "this page exists just to make the outcome easy to read at a glance."
    )
    p(
        "**What this project tests.** How well a pretrained face-matching AI can tell "
        "whether two photos show the same person, and whether it can spot duplicate "
        "profiles in a group of photos — while making sure a match is only ever a "
        "prompt for a human to review, never an automatic decision."
    )

    h("## Headline numbers")
    lines.append(
        f"- **Ordinary photos (LFW):** {pct(final['accuracy'])} accuracy — a mistake "
        f"{one_in(1 - float(final['accuracy']))} of the time."
    )
    lines.append(
        f"- **Awkward-angle photos (raw CPLFW):** accuracy drops to {pct(cplfw['accuracy'])}, "
        f"and a face couldn't even be detected in {pct(cplfw['failure_rate'])} of attempts "
        f"— pose is a far bigger obstacle than anything else tested here."
    )
    lines.append(
        f"- **Spotting duplicate profiles** in a gallery of {gallery['gallery_size']:,} people: "
        f"caught {pct(gallery['duplicate_detection_rate'])} of genuine repeats, but also "
        f"flagged {pct(gallery['false_duplicate_review_rate'])} of genuinely new people as "
        f"'maybe a duplicate' — too many to act on without a human checking."
    )
    lines.append("")

    h("## Figure 1 — How reliable is the matching, overall?")
    fig("01", "figure_01_roc_comparison.png", "ROC curves for LFW development, LFW final and raw CPLFW")
    p(
        "This is an ROC curve: it shows the trade-off between catching real matches and "
        "raising false alarms as the matching rule is made stricter or looser. A line "
        "that hugs the top-left corner means the system rarely has to choose between "
        "the two. All three lines sit close to that corner — the system is generally "
        "reliable — but the raw CPLFW line (awkward-angle photos) sits a little lower, "
        f"confirming cross-pose photos are the harder case (AUC "
        f"{float(summary['cplfw']['roc_auc']):.4f} vs "
        f"{float(summary['lfw_final']['roc_auc']):.4f} on ordinary photos; 1.0 would be perfect)."
    )

    h("## Figure 2 — Final LFW result, in detail")
    fig("02", "figure_02_lfw_final_confusion_matrix.png", "Final LFW confusion matrix")
    p(
        "Every pair of photos the system successfully processed lands in one of four "
        "boxes: correctly said 'same person', correctly said 'different people', wrongly "
        f"said 'same' when they weren't (a false match, {pct(final['false_match_rate'])} of the "
        f"time), or wrongly said 'different' when they were the same (a missed match, "
        f"{pct(final['false_non_match_rate'])} of the time). Almost every pair here lands in one "
        "of the two 'correct' boxes."
    )

    h("## Figure 3 — The harder test, in detail")
    fig("03", "figure_03_cplfw_confusion_matrix.png", "Raw CPLFW confusion matrix")
    p(
        "The same kind of chart as Figure 2, but for the awkward-angle photos. There are "
        f"visibly more mistakes here, and specifically more missed matches "
        f"({pct(cplfw['false_non_match_rate'])}) than false alarms "
        f"({pct(cplfw['false_match_rate'])}) — when the system gets confused by pose, it "
        "tends to err on the side of saying two photos of the same person look different, "
        "not the other way round."
    )

    h("## Figure 4 — Before comparing faces, can it even find one?")
    fig("04", "figure_04_extraction_failure_rates.png", "Face-extraction failure rates across protocols")
    p(
        "Before two photos can be compared, the system first has to locate a face in "
        "each one — that step alone can fail. On ordinary photos it fails about "
        f"{pct(final['failure_rate'])} of the time; on the awkward-angle photos it fails "
        f"{pct(cplfw['failure_rate'])} of the time — nearly half of those pairs never even "
        "reach the comparison stage. This is reported openly rather than quietly dropped, "
        "because ignoring it would make the accuracy numbers look better than they really are."
    )

    h("## Figure 5 — Why detection fails on awkward-angle photos")
    fig("05", "figure_05_cplfw_failure_breakdown.png", "Raw CPLFW face-extraction failure categories")
    p(
        "Zooming into *why* detection failed: overwhelmingly, no face at all could be "
        f"found ({breakdown.get('zero_faces_left', 0):,} + {breakdown.get('zero_faces_right', 0):,} "
        f"cases), rather than the detector finding too many faces "
        f"({breakdown.get('multiple_faces_left', 0):,} + {breakdown.get('multiple_faces_right', 0):,} "
        "cases). That points squarely at the sharp camera angles being the obstacle, not "
        "photo quality or crowding."
    )

    h("## Figure 6 — Finding duplicate profiles in a crowd")
    fig("06", "figure_06_gallery_outcomes.png", "1:N duplicate-profile gallery outcomes")
    p(
        f"Simulates a real gallery of {gallery['gallery_size']:,} people and asks, for each "
        "new photo, 'has this exact face appeared before?'. The system correctly caught "
        f"{pct(gallery['duplicate_detection_rate'])} of genuine repeat appearances, but also "
        f"raised a false alarm on {pct(gallery['false_duplicate_review_rate'])} of genuinely "
        "new people. That's why this project's rule is: a flagged result opens a case for "
        "a **human** to review — it never bans, blocks or accuses anyone automatically."
    )

    h("## Figure 7 — How the matching threshold was chosen")
    fig("07", "figure_07_threshold_candidate_comparison.png", "Candidate threshold comparison")
    p(
        "There's no single 'correct' setting for how similar two faces must look before "
        "counting them as a match — it's a dial. This chart compares several candidate "
        "settings, each tried out on a held-back set of practice photos never used for the "
        f"real results above, with the one actually chosen ('{selected}') marked with a "
        "star. Choosing it this way, before ever looking at the final test photos, is what "
        "makes the headline numbers a fair test rather than a tuned-up one."
    )

    h("## Figure 8 — How fast is it?")
    fig("08", "figure_08_latency_comparison.png", "Embedding and gallery search latency")
    mean_ms = float(summary["lfw_final"]["embedding_time_mean_ms"])
    gallery_ms = float(gallery["gallery_search_time_mean_ms"])
    p(
        f"On average, processing one photo takes about {mean_ms:.0f} milliseconds "
        f"(roughly {1000 / mean_ms:.0f} photos a second); searching the whole "
        f"{gallery['gallery_size']:,}-person gallery for a match takes about "
        f"{gallery_ms:.1f} milliseconds per search. These numbers depend on the machine "
        "they were measured on, so they're a feasibility indicator, not a formal benchmark."
    )

    h("## Figure 9 — How the whole experiment was run")
    fig("09", "figure_09_experiment_flow.png", "Experimental workflow and held-out evaluation boundary")
    p(
        "A step-by-step map of the whole pipeline, showing that the matching threshold "
        "was locked in using only practice data, *before* it was ever applied to the real "
        "final photos or the awkward-angle photos — so nothing downstream of that line was "
        "tuned to get a good score."
    )

    h("## Bottom line")
    lines.append(
        f"- On ordinary photos, the matching is very reliable ({pct(final['accuracy'])})."
    )
    lines.append(
        "- On awkward-angle photos, detecting a face at all is the main bottleneck, not "
        "the matching itself — worth fixing first in any follow-on work."
    )
    lines.append(
        "- For duplicate-profile search, this pipeline is good at catching real repeats but "
        "flags too many innocent people to act on automatically — hence the human-review-only "
        "policy running throughout this project."
    )
    lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
