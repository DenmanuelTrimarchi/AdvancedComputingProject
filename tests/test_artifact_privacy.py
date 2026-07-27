from __future__ import annotations

from pathlib import Path

import pytest

from face_verification.gallery_evaluator import build_manifest, evaluate_gallery, summarize_gallery_metrics
from face_verification.privacy import PrivacyLeakError, assert_no_leakage, opaque_id, scrub_filename
from tests.conftest import FakeDetector, FakeEmbedder, make_test_image


def test_opaque_id_is_deterministic_and_one_way():
    first = opaque_id("Alice Smith")
    second = opaque_id("Alice Smith")
    different = opaque_id("Bob Jones")

    assert first == second
    assert first != different
    assert "Alice" not in first
    assert "Smith" not in first


def test_scrub_filename_strips_directories():
    assert scrub_filename(Path("/Users/researcher/secure/datasets/alice_0001.jpg")) == "alice_0001.jpg"


def test_assert_no_leakage_catches_absolute_path():
    with pytest.raises(PrivacyLeakError):
        assert_no_leakage({"image_path": "/Users/researcher/secure/alice_0001.jpg"})


def test_assert_no_leakage_catches_name_like_keys():
    with pytest.raises(PrivacyLeakError):
        assert_no_leakage({"identity_name": "Alice Smith"})
    with pytest.raises(PrivacyLeakError):
        assert_no_leakage({"candidate_name": "Bob Jones"})


def test_assert_no_leakage_catches_raw_embedding_vectors():
    with pytest.raises(PrivacyLeakError):
        assert_no_leakage({"embedding": [0.01 * i for i in range(128)]})


def test_assert_no_leakage_allows_opaque_and_aggregate_fields():
    # Should not raise: opaque hashes, scalar rates, and short lists are fine.
    assert_no_leakage(
        {
            "identity_hash": opaque_id("Alice Smith"),
            "candidate_identity_hash": opaque_id("Bob Jones"),
            "similarity": 0.87,
            "strategy": "balanced_accuracy",
            "duplicate_detection_rate": 0.92,
            "nested": {"identity_count": 12, "seed": 20260727},
        }
    )


def test_gallery_metrics_payload_has_no_leakage(tmp_path):
    alice_a, alice_a_key = make_test_image(tmp_path, "alice_0001.jpg", fill=10)
    alice_b, alice_b_key = make_test_image(tmp_path, "alice_0002.jpg", fill=11)
    carol_a, carol_a_key = make_test_image(tmp_path, "carol_0001.jpg", fill=30)

    identity_to_images = {"alice": [alice_a, alice_b], "carol": [carol_a]}
    detector = FakeDetector()
    embedder = FakeEmbedder(dimensions=3)

    manifest = build_manifest(identity_to_images, seed=3)
    result = evaluate_gallery(manifest, detector=detector, embedder=embedder, duplicate_review_threshold=0.5)
    summary = summarize_gallery_metrics(result)

    # This is the same shape scripts/evaluate_duplicate_gallery.py writes to disk.
    assert_no_leakage(summary, context="duplicate_gallery_metrics")
