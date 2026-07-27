from __future__ import annotations

import numpy as np
import pytest

from face_verification.protocols import Pair
from face_verification.similarity import SimilarityError, cosine_similarity, l2_normalize
from face_verification.verification_evaluator import evaluate_pairs
from tests.conftest import FakeDetector, FakeEmbedder, make_test_image


def test_zero_faces_counted_not_dropped(tmp_path):
    good_a, good_a_key = make_test_image(tmp_path, "good_a.jpg", fill=10)
    good_b, good_b_key = make_test_image(tmp_path, "good_b.jpg", fill=11)
    empty_image, empty_key = make_test_image(tmp_path, "empty.jpg", fill=99)

    detector = FakeDetector(face_counts={empty_key: 0}, default_count=1)
    embedder = FakeEmbedder(dimensions=8)

    pairs = [
        Pair(good_a, good_b, True, "alice", "alice"),
        Pair(empty_image, good_b, False, "nobody", "alice"),
    ]
    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)

    assert result.total_pairs == 2
    assert len(result.scored_pairs) == 2  # every pair is accounted for, none silently dropped
    assert len(result.valid_scores) == 1  # only the successfully-scored pair contributes a score
    assert result.failures.get("zero_faces_left") == 1
    assert result.failure_rate == pytest.approx(0.5)


def test_multiple_faces_counted_not_dropped(tmp_path):
    good_a, good_a_key = make_test_image(tmp_path, "good_a.jpg", fill=10)
    good_b, good_b_key = make_test_image(tmp_path, "good_b.jpg", fill=11)
    crowd_image, crowd_key = make_test_image(tmp_path, "crowd.jpg", fill=88)

    detector = FakeDetector(face_counts={crowd_key: 3}, default_count=1)
    embedder = FakeEmbedder(dimensions=8)

    pairs = [
        Pair(good_a, crowd_image, False, "alice", "crowd"),
    ]
    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)

    assert result.total_pairs == 1
    assert len(result.scored_pairs) == 1
    assert len(result.valid_scores) == 0
    assert result.failures.get("multiple_faces_right") == 1


def test_non_finite_embedding_is_rejected_not_silently_accepted(tmp_path):
    good_a, good_a_key = make_test_image(tmp_path, "good_a.jpg", fill=10)
    bad_b, bad_b_key = make_test_image(tmp_path, "bad_b.jpg", fill=77)

    detector = FakeDetector()
    embedder = FakeEmbedder(
        dimensions=8,
        overrides={bad_b_key: np.array([float("nan")] + [0.1] * 7)},
    )

    pairs = [Pair(good_a, bad_b, True, "alice", "alice")]
    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)

    assert result.total_pairs == 1
    assert len(result.scored_pairs) == 1
    assert result.valid_scores == []
    assert any(code.startswith("image_error_right") for code in result.failures)


def test_cosine_similarity_rejects_dimension_mismatch():
    with pytest.raises(SimilarityError):
        cosine_similarity(np.zeros(128), np.zeros(64))


def test_cosine_similarity_rejects_non_finite():
    with pytest.raises(SimilarityError):
        cosine_similarity(np.array([1.0, float("inf")]), np.array([1.0, 2.0]))


def test_l2_normalize_rejects_non_finite():
    with pytest.raises(SimilarityError):
        l2_normalize(np.array([1.0, float("nan"), 2.0]))


def test_l2_normalize_rejects_zero_vector():
    with pytest.raises(SimilarityError):
        l2_normalize(np.zeros(128))


def test_l2_normalize_produces_unit_norm():
    normalized = l2_normalize(np.array([3.0, 4.0]))
    assert np.linalg.norm(normalized) == pytest.approx(1.0)
