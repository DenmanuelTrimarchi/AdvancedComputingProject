"""Deterministic 1:N duplicate-profile gallery experiment on real images.

Simulates existing registered profiles (the gallery) plus two kinds of
probes: a second image of a gallery identity (a duplicate-registration
attempt) and an image of an identity absent from the gallery (a legitimate
new registration). Every manifest entry uses an opaque, one-way identifier —
never the real identity name — and each image is restricted to exactly one
role. Nothing here labels a result a "scammer"; the threshold only opens a
human-review case (see docs/EVALUATION_PROTOCOL.md).
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import metrics as metrics_module
from .config import DEFAULT_RANDOM_SEED
from .detector import FaceCountError, YuNetDetector
from .embedder import SFaceEmbedder
from .image_io import ImageLoadError, load_image_bgr
from .privacy import opaque_id
from .similarity import SimilarityError, cosine_similarity, l2_normalize


class GalleryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestEntry:
    sample_id: str
    identity_hash: str
    image_path: Path
    role: str  # "gallery" | "duplicate_probe" | "unknown_probe"


@dataclass(frozen=True)
class GalleryManifest:
    entries: List[ManifestEntry]
    seed: int


def build_manifest(
    identity_to_images: Dict[str, List[Path]],
    *,
    excluded_images: Sequence[Path] = (),
    seed: int = DEFAULT_RANDOM_SEED,
    max_unknown_identities: Optional[int] = None,
) -> GalleryManifest:
    excluded = {Path(p) for p in excluded_images}
    rng = random.Random(seed)

    eligible = {
        identity: sorted((Path(p) for p in images if Path(p) not in excluded), key=lambda p: p.name)
        for identity, images in identity_to_images.items()
    }
    eligible = {identity: images for identity, images in eligible.items() if images}

    gallery_identities = sorted(identity for identity, images in eligible.items() if len(images) >= 2)
    unknown_identities = sorted(identity for identity, images in eligible.items() if len(images) == 1)

    if max_unknown_identities is not None:
        rng.shuffle(unknown_identities)
        unknown_identities = sorted(unknown_identities[:max_unknown_identities])

    if not gallery_identities:
        raise GalleryError("No identity has at least two usable images; cannot build a gallery.")
    if not unknown_identities:
        raise GalleryError("No identity with exactly one usable image is available as an unknown probe.")

    entries: List[ManifestEntry] = []

    for identity in gallery_identities:
        images = eligible[identity]
        gallery_image, duplicate_image = images[0], images[1]
        identity_hash = opaque_id(identity)
        entries.append(ManifestEntry(opaque_id(f"{identity}:{gallery_image.name}"), identity_hash, gallery_image, "gallery"))
        entries.append(
            ManifestEntry(opaque_id(f"{identity}:{duplicate_image.name}"), identity_hash, duplicate_image, "duplicate_probe")
        )

    for identity in unknown_identities:
        image = eligible[identity][0]
        identity_hash = opaque_id(identity)
        entries.append(ManifestEntry(opaque_id(f"{identity}:{image.name}"), identity_hash, image, "unknown_probe"))

    seen_paths: set = set()
    for entry in entries:
        if entry.image_path in seen_paths:
            raise GalleryError(f"Image assigned to more than one manifest role: {entry.image_path}")
        seen_paths.add(entry.image_path)

    return GalleryManifest(entries=entries, seed=seed)


@dataclass(frozen=True)
class ProbeResult:
    sample_id: str
    role: str
    identity_hash: str
    top_candidate_identity_hash: Optional[str]
    top_similarity: Optional[float]
    rank1_correct: Optional[bool]
    exceeds_duplicate_threshold: Optional[bool]
    failure_code: Optional[str]


@dataclass(frozen=True)
class GalleryEvaluationResult:
    gallery_size: int
    probe_results: List[ProbeResult]
    search_times_seconds: List[float] = field(default_factory=list)


def _embed_entry(
    entry: ManifestEntry, detector: YuNetDetector, embedder: SFaceEmbedder
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    try:
        loaded = load_image_bgr(entry.image_path)
        face_row = detector.detect_single_face(loaded.bgr)
        raw = embedder.embed(loaded.bgr, face_row)
        return l2_normalize(raw), None
    except FaceCountError as exc:
        return None, "zero_faces" if exc.face_count == 0 else "multiple_faces"
    except (ImageLoadError, SimilarityError) as exc:
        return None, f"image_error:{exc}"


def evaluate_gallery(
    manifest: GalleryManifest,
    *,
    detector: YuNetDetector,
    embedder: SFaceEmbedder,
    duplicate_review_threshold: float,
) -> GalleryEvaluationResult:
    gallery_entries = [e for e in manifest.entries if e.role == "gallery"]
    probe_entries = [e for e in manifest.entries if e.role in ("duplicate_probe", "unknown_probe")]

    gallery_embeddings: List[Tuple[ManifestEntry, np.ndarray]] = []
    for entry in gallery_entries:
        embedding, _failure = _embed_entry(entry, detector, embedder)
        if embedding is not None:
            gallery_embeddings.append((entry, embedding))
    if not gallery_embeddings:
        raise GalleryError("No gallery entry could be embedded; cannot run the experiment.")

    results: List[ProbeResult] = []
    search_times: List[float] = []
    for probe in probe_entries:
        probe_embedding, failure = _embed_entry(probe, detector, embedder)
        if probe_embedding is None:
            results.append(ProbeResult(probe.sample_id, probe.role, probe.identity_hash, None, None, None, None, failure))
            continue

        search_start = time.perf_counter()
        similarities = sorted(
            (
                (candidate_entry, cosine_similarity(probe_embedding, candidate_embedding))
                for candidate_entry, candidate_embedding in gallery_embeddings
            ),
            key=lambda item: (-item[1], item[0].sample_id),
        )
        search_times.append(time.perf_counter() - search_start)
        top_entry, top_similarity = similarities[0]
        rank1_correct = top_entry.identity_hash == probe.identity_hash if probe.role == "duplicate_probe" else None

        results.append(
            ProbeResult(
                probe.sample_id,
                probe.role,
                probe.identity_hash,
                top_entry.identity_hash,
                top_similarity,
                rank1_correct,
                top_similarity >= duplicate_review_threshold,
                None,
            )
        )

    return GalleryEvaluationResult(
        gallery_size=len(gallery_embeddings), probe_results=results, search_times_seconds=search_times
    )


def summarize_gallery_metrics(result: GalleryEvaluationResult) -> Dict[str, object]:
    duplicate_probes = [r for r in result.probe_results if r.role == "duplicate_probe"]
    unknown_probes = [r for r in result.probe_results if r.role == "unknown_probe"]
    scored_duplicates = [r for r in duplicate_probes if r.failure_code is None]
    scored_unknowns = [r for r in unknown_probes if r.failure_code is None]

    duplicate_detection_rate = (
        sum(1 for r in scored_duplicates if r.exceeds_duplicate_threshold) / len(scored_duplicates)
        if scored_duplicates
        else float("nan")
    )
    false_duplicate_review_rate = (
        sum(1 for r in scored_unknowns if r.exceeds_duplicate_threshold) / len(scored_unknowns)
        if scored_unknowns
        else float("nan")
    )
    rank1_identification_rate = (
        sum(1 for r in scored_duplicates if r.rank1_correct) / len(scored_duplicates)
        if scored_duplicates
        else float("nan")
    )
    true_duplicate_miss_rate = (
        1.0 - duplicate_detection_rate if duplicate_detection_rate == duplicate_detection_rate else float("nan")
    )

    search_times_ms = [t * 1000.0 for t in result.search_times_seconds]

    return {
        "gallery_size": result.gallery_size,
        "duplicate_probe_count": len(duplicate_probes),
        "unknown_probe_count": len(unknown_probes),
        "duplicate_probe_failures": len(duplicate_probes) - len(scored_duplicates),
        "unknown_probe_failures": len(unknown_probes) - len(scored_unknowns),
        "duplicate_detection_rate": duplicate_detection_rate,
        "false_duplicate_review_rate": false_duplicate_review_rate,
        "rank1_identification_rate": rank1_identification_rate,
        "true_duplicate_miss_rate": true_duplicate_miss_rate,
        "gallery_search_time_mean_ms": statistics.fmean(search_times_ms) if search_times_ms else float("nan"),
        "gallery_search_time_p95_ms": metrics_module.percentile(search_times_ms, 95) if search_times_ms else float("nan"),
    }
