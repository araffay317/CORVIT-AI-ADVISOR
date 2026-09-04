"""
Automated PyTest suite for Phase 3 (Dataset Ingestion & Preprocessing).
Validates read-only preservation, factual fidelity, metadata integrity, and chunking.
"""
import hashlib
from pathlib import Path
from typing import Dict, Tuple

import pytest
from backend.config import settings
from backend.rag.loader import (
    DATASET_REGISTRY,
    DEFAULT_CACHE_PATH,
    DocumentChunk,
    export_chunks_to_json,
    get_dataset_chunks,
    ingest_all_dataset_files,
    load_chunks_from_json,
    parse_dataset_file,
)


def _get_dataset_state(dataset_dir: Path) -> Dict[str, Tuple[str, float]]:
    """Helper to record SHA-256 hash and modification time of all dataset files."""
    state = {}
    for cat, filename in DATASET_REGISTRY.items():
        file_path = dataset_dir / cat / filename
        assert file_path.is_file(), f"Expected file missing: {file_path}"

        hasher = hashlib.sha256()
        with open(file_path, mode="rb") as f:
            hasher.update(f.read())
        sha = hasher.hexdigest()
        mtime = file_path.stat().st_mtime
        state[cat] = (sha, mtime)
    return state


def test_discovery_all_eight_files():
    """Verify that all 8 canonical Corvit dataset files exist and are discoverable."""
    dataset_dir = settings.dataset_dir
    assert dataset_dir.is_dir(), f"Dataset directory not found: {dataset_dir}"
    for cat, filename in DATASET_REGISTRY.items():
        target = dataset_dir / cat / filename
        assert target.is_file(), f"Missing dataset file for category '{cat}': {target}"


def test_dataset_immutability_and_readonly():
    """
    CRITICAL TEST: Guarantees raw Dataset files remain 100% untouched.
    Computes SHA-256 hashes and mtimes before ingestion and asserts they remain identical.
    """
    dataset_dir = settings.dataset_dir

    # 1. State before ingestion
    pre_state = _get_dataset_state(dataset_dir)

    # 2. Run full ingestion from raw files
    chunks = ingest_all_dataset_files(dataset_dir)
    assert len(chunks) > 0

    # 3. State after ingestion
    post_state = _get_dataset_state(dataset_dir)

    # 4. Compare every category file
    for cat in DATASET_REGISTRY.keys():
        pre_sha, pre_mtime = pre_state[cat]
        post_sha, post_mtime = post_state[cat]

        assert pre_sha == post_sha, f"CRITICAL: SHA-256 changed for {cat}! File was modified."
        assert pre_mtime == post_mtime, f"CRITICAL: Modification time changed for {cat}! File was touched."


def test_category_chunk_generation_and_counts():
    """
    Verify every category produces at least one valid chunk.
    Reports actual chunk counts without enforcing artificial bounds (Correction 2).
    """
    dataset_dir = settings.dataset_dir
    chunks_by_category = {}

    for cat, filename in DATASET_REGISTRY.items():
        cat_chunks = parse_dataset_file(cat, filename, dataset_dir)
        assert len(cat_chunks) >= 1, f"Category '{cat}' must produce at least 1 chunk!"
        chunks_by_category[cat] = len(cat_chunks)

    total_chunks = sum(chunks_by_category.values())

    # Print report to stdout for pytest -s inspection
    print("\n--- ACTUAL CHUNK COUNTS PER CATEGORY ---")
    for cat, count in chunks_by_category.items():
        print(f"  * {cat:15s}: {count} chunks")
    print(f"Total Chunks Ingested: {total_chunks}\n")

    assert total_chunks > 0


def test_zero_empty_or_invalid_chunks():
    """Verify that no chunk is empty, whitespace-only, or below minimum character threshold."""
    chunks = ingest_all_dataset_files()
    for chunk in chunks:
        assert isinstance(chunk, DocumentChunk)
        assert len(chunk.text.strip()) >= 20, f"Chunk {chunk.chunk_id} has insufficient text: {chunk.text}"
        assert chunk.char_count == len(chunk.text)
        assert chunk.token_estimate >= 1


def test_metadata_integrity():
    """Verify that all metadata fields are properly populated on every chunk."""
    chunks = ingest_all_dataset_files()
    seen_ids = set()

    for chunk in chunks:
        # Unique deterministic chunk_id
        assert chunk.chunk_id not in seen_ids, f"Duplicate chunk_id found: {chunk.chunk_id}"
        seen_ids.add(chunk.chunk_id)

        # Valid category
        assert chunk.category in DATASET_REGISTRY

        # Valid source file
        assert chunk.source_file == DATASET_REGISTRY[chunk.category]

        # Valid section title
        assert len(chunk.section_title.strip()) > 0


def test_factual_fidelity_verbatim_preservation():
    """
    Verify Correction 1: Words, numbers, and facts from the raw dataset
    exist verbatim in the chunks without rewriting, summarizing, or translation.
    """
    chunks = ingest_all_dataset_files()
    all_text = "\n".join(chunk.text for chunk in chunks)

    # Core factual terms from the Corvit dataset across categories
    critical_facts = [
        "ARTIFICIAL INTELLIGENCE",
        "MACHINE LEARNING & DEEP LEARNING",
        "Duration:\n3 Months",
        "NAVTTC",
        "National Vocational and Technical",
        "GENERAL CORVIT TIMINGS",
        "9:00 AM to 9:00 PM",
        "PAID COURSES",
        "CCNA",
        "Lahore",
        "HOW TO APPLY",
        "GENERAL ADMISSION PROCESS",
        "TRAINING ENVIRONMENT",
    ]

    for fact in critical_facts:
        assert fact in all_text, f"Factual fidelity failure: Term '{fact}' was lost or altered during ingestion!"


def test_json_cache_lifecycle_and_regeneration():
    """
    Verify Correction 3:
    1. processed_chunks.json can be exported and reloaded.
    2. Original dataset remains primary: get_dataset_chunks works even if cache is absent.
    """
    chunks = ingest_all_dataset_files()

    # 1. Export
    cache_path = export_chunks_to_json(chunks)
    assert cache_path.is_file()
    assert cache_path.stat().st_size > 0

    # 2. Reload from JSON
    reloaded_chunks = load_chunks_from_json(cache_path)
    assert len(reloaded_chunks) == len(chunks)
    assert reloaded_chunks[0].chunk_id == chunks[0].chunk_id
    assert reloaded_chunks[0].text == chunks[0].text

    # 3. Test on-the-fly regeneration bypassing cache
    fresh_chunks = get_dataset_chunks(force_reload=True, use_cache=False)
    assert len(fresh_chunks) == len(chunks)
