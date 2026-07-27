from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from face_verification.gallery_evaluator import (
    GalleryError,
    build_manifest,
    evaluate_gallery,
    summarize_gallery_metrics,
)
from tests.conftest import FakeDetector, FakeEmbedder, make_test_image


def _hand_crafted_gallery(tmp_path: Path):
    """Three identities: alice/bob get two images each (gallery-eligible),
    carol gets one image (unknown probe). Embeddings are hand-picked so the
    correct ranking is unambiguous and computable by hand."""
    alice_a, alice_a_key = make_test_image(tmp_path, "alice_0001.jpg", fill=10)
    alice_b, alice_b_key = make_test_image(tmp_path, "alice_0002.jpg", fill=11)
    bob_a, bob_a_key = make_test_image(tmp_path, "bob_0001.jpg", fill=20)
    bob_b, bob_b_key = make_test_image(tmp_path, "bob_0002.jpg", fill=21)
    carol_a, carol_a_key = make_test_image(tmp_path, "carol_0001.jpg", fill=30)

    identity_to_images = {
        "alice": [alice_a, alice_b],
        "bob": [bob_a, bob_b],
        "carol": [carol_a],
    }

    # Orthonormal-ish basis vectors so cosine similarity is exact and predictable.
    overrides = {
        alice_a_key: np.array([1.0, 0.0, 0.0]),
        alice_b_key: np.array([0.9, 0.1, 0.0]),  # close to alice's gallery vector
        bob_a_key: np.array([0.0, 1.0, 0.0]),
        bob_b_key: np.array([0.0, 0.9, 0.1]),  # close to bob's gallery vector
        carol_a_key: np.array([0.0, 0.0, 1.0]),  # far from both
    }

    detector = FakeDetector()
    embedder = FakeEmbedder(dimensions=3, overrides=overrides)
    return identity_to_images, detector, embedder


def test_gallery_ranking_is_deterministic(tmp_path):
    identity_to_images, detector, embedder = _hand_crafted_gallery(tmp_path)
    manifest = build_manifest(identity_to_images, seed=7)

    first = evaluate_gallery(manifest, detector=detector, embedder=embedder, duplicate_review_threshold=0.5)
    second = evaluate_gallery(manifest, detector=detector, embedder=embedder, duplicate_review_threshold=0.5)

    first_by_id = {r.sample_id: r for r in first.probe_results}
    second_by_id = {r.sample_id: r for r in second.probe_results}
    assert first_by_id.keys() == second_by_id.keys()
    for sample_id, result in first_by_id.items():
        other = second_by_id[sample_id]
        assert result.top_candidate_identity_hash == other.top_candidate_identity_hash
        assert result.top_similarity == pytest.approx(other.top_similarity)


def test_gallery_ranking_picks_the_correct_nearest_identity(tmp_path):
    identity_to_images, detector, embedder = _hand_crafted_gallery(tmp_path)
    manifest = build_manifest(identity_to_images, seed=7)

    result = evaluate_gallery(manifest, detector=detector, embedder=embedder, duplicate_review_threshold=0.5)
    duplicate_probes = {r.identity_hash: r for r in result.probe_results if r.role == "duplicate_probe"}

    # Both duplicate probes should rank their own identity's gallery entry first.
    for probe in duplicate_probes.values():
        assert probe.rank1_correct is True

    summary = summarize_gallery_metrics(result)
    assert summary["duplicate_detection_rate"] == pytest.approx(1.0)
    assert summary["rank1_identification_rate"] == pytest.approx(1.0)
    # Carol is an unknown probe far from both gallery identities.
    assert summary["false_duplicate_review_rate"] == pytest.approx(0.0)


def test_one_image_cannot_occupy_two_manifest_roles(tmp_path):
    shared_path, _ = make_test_image(tmp_path, "shared.jpg", fill=5)
    other_path, _ = make_test_image(tmp_path, "alice_0002.jpg", fill=6)

    identity_to_images = {
        "alice": [shared_path, other_path],  # gallery identity, uses shared_path as one of its two images
        "bob": [shared_path],  # unknown identity, reuses the exact same image
    }

    with pytest.raises(GalleryError):
        build_manifest(identity_to_images, seed=1)


def test_invalid_identity_partition_fails(tmp_path):
    # Every identity has exactly one image: no possible gallery identity.
    only_ones = {}
    for index, name in enumerate(["alice", "bob", "carol"]):
        path, _ = make_test_image(tmp_path, f"{name}.jpg", fill=10 + index)
        only_ones[name] = [path]

    with pytest.raises(GalleryError):
        build_manifest(only_ones, seed=1)
