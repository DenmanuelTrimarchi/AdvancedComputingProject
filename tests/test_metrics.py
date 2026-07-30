"""Metric definitions verified against hand-checked values.

Every figure reported in the dissertation comes from this module, and it
deliberately carries no scikit-learn dependency, so the implementations are
checked against known-answer cases rather than another library. Tied scores
and single-class input get particular attention: the first is where a
rank-based AUC silently goes wrong, the second is where a rate is undefined
and must not be reported as zero.
"""

from __future__ import annotations


import pytest

from face_verification.metrics import (
    MetricsError,
    confusion_matrix,
    equal_error_rate,
    rates_from_confusion,
    roc_auc,
    select_threshold,
)


def test_known_confusion_and_metrics():
    scores = [0.9, 0.6, 0.55, 0.2]
    labels = [1, 0, 1, 0]
    matrix = confusion_matrix(scores, labels, threshold=0.5)

    assert matrix.as_dict() == {
        "true_positive": 2,
        "false_positive": 1,
        "true_negative": 1,
        "false_negative": 0,
    }

    rates = rates_from_confusion(matrix)
    assert rates["accuracy"] == pytest.approx(0.75)
    assert rates["precision"] == pytest.approx(2 / 3)
    assert rates["recall"] == pytest.approx(1.0)
    assert rates["f1"] == pytest.approx(0.8)
    assert rates["false_match_rate"] == pytest.approx(0.5)
    assert rates["false_non_match_rate"] == pytest.approx(0.0)


def test_perfect_separation_has_auc_one_and_eer_zero():
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [1, 1, 0, 0]

    assert roc_auc(scores, labels) == pytest.approx(1.0)
    eer = equal_error_rate(scores, labels)
    assert eer["equal_error_rate"] == pytest.approx(0.0, abs=1e-9)


def test_tied_scores_use_average_ranks():
    # Two positives tied with one negative at 0.5: manual Mann-Whitney U.
    scores = [0.5, 0.5, 0.5, 0.1]
    labels = [1, 1, 0, 0]
    # Ranks (ascending, 1-indexed, ties averaged): 0.1 -> rank 1;
    # the three 0.5s share ranks {2,3,4} -> average rank 3 each.
    # Positive rank sum = 3 + 3 = 6 (two of the three tied values are positive).
    # AUC = (sum_ranks_pos - n_pos*(n_pos+1)/2) / (n_pos * n_neg) = (6 - 2*3/2) / (2*2) = (6-3)/4 = 0.75
    assert roc_auc(scores, labels) == pytest.approx(0.75)


def test_rejects_non_finite_and_single_class():
    with pytest.raises(MetricsError):
        confusion_matrix([0.1, float("nan")], [1, 0], threshold=0.5)
    with pytest.raises(MetricsError):
        confusion_matrix([0.1, 0.2], [1, 1], threshold=0.5)  # only one class present
    with pytest.raises(MetricsError):
        confusion_matrix([], [], threshold=0.5)


def test_target_fmr_constraint():
    scores = [0.95, 0.9, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
    labels = [1, 1, 1, 0, 1, 0, 0, 0]
    candidate = select_threshold(scores, labels, strategy="target_fmr", target_false_match_rate=0.25)
    assert candidate.metrics["false_match_rate"] <= 0.25 + 1e-9


def test_balanced_threshold_selection_is_deterministic():
    scores = [0.95, 0.9, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
    labels = [1, 1, 1, 0, 1, 0, 0, 0]

    first = select_threshold(scores, labels, strategy="balanced_accuracy")
    second = select_threshold(scores, labels, strategy="balanced_accuracy")
    assert first.threshold == second.threshold

    # Brute-force confirm no other candidate threshold beats it on balanced accuracy.
    best_balanced_accuracy = None
    for threshold in sorted(set(scores)):
        matrix = confusion_matrix(scores, labels, threshold)
        rates = rates_from_confusion(matrix)
        tnr = 1.0 - rates["false_match_rate"]
        balanced = (rates["true_match_rate"] + tnr) / 2.0
        if best_balanced_accuracy is None or balanced > best_balanced_accuracy:
            best_balanced_accuracy = balanced

    selected_matrix = confusion_matrix(scores, labels, first.threshold)
    selected_rates = rates_from_confusion(selected_matrix)
    selected_balanced = (selected_rates["true_match_rate"] + (1.0 - selected_rates["false_match_rate"])) / 2.0
    assert selected_balanced == pytest.approx(best_balanced_accuracy)
