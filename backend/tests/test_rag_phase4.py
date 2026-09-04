"""
Automated PyTest suite for Phase 4 (Retrieval / RAG Engine).
Tests indexing, precision across all categories, thresholding, citations, and dataset immutability.
"""
import time
import hashlib
from pathlib import Path
from typing import Dict, Tuple

import pytest
from backend.config import settings
from backend.rag.loader import DATASET_REGISTRY, get_dataset_chunks
from backend.rag.retriever import CorvitRetriever, get_retriever, RetrievalResult
from backend.rag.prompt_builder import (
    build_rag_prompt_context,
    format_citations,
    OFFICIAL_DISCLAIMER,
    RAGPromptContext
)


def _get_dataset_hashes(dataset_dir: Path) -> Dict[str, str]:
    """Helper to compute SHA-256 hash of all 8 dataset files."""
    hashes = {}
    for cat, filename in DATASET_REGISTRY.items():
        file_path = dataset_dir / cat / filename
        assert file_path.is_file()
        with open(file_path, "rb") as f:
            hashes[cat] = hashlib.sha256(f.read()).hexdigest()
    return hashes


def test_retriever_indexing_all_chunks():
    """Verify that the retriever indexes all 154 DocumentChunks from Phase 3."""
    retriever = CorvitRetriever()
    total_indexed = retriever.index()
    assert total_indexed == 154
    assert len(retriever.chunks) == 154
    assert retriever.vectorizer is not None
    assert retriever.tfidf_matrix is not None
    assert retriever.tfidf_matrix.shape[0] == 154


def test_courses_retrieval_accuracy():
    """Verify high-relevance retrieval for course outlines."""
    retriever = get_retriever()
    start_t = time.perf_counter()
    results = retriever.search("machine learning and deep learning course outline and topics", top_k=4)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    print(f"\n[Search Latency: {elapsed_ms:.2f}ms for Courses Query]")
    assert len(results) > 0
    top = results[0]
    assert top.category == "courses"
    assert "ARTIFICIAL INTELLIGENCE" in top.section_title
    assert top.similarity_score >= 0.15


def test_fees_retrieval_accuracy():
    """Verify retrieval accuracy for paid course fees and installments."""
    retriever = get_retriever()
    results = retriever.search("paid courses fee structure and installment options", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category == "fees"
    assert "PAID COURSES" in top.section_title or "FEES" in top.section_title


def test_navttc_retrieval_accuracy():
    """Verify retrieval accuracy for NAVTTC government free training."""
    retriever = get_retriever()
    results = retriever.search("NAVTTC free technical training funded by government", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category == "navttc"
    assert "NAVTTC" in top.section_title


def test_timetable_retrieval_accuracy():
    """Verify retrieval accuracy for class schedules and batch timings."""
    retriever = get_retriever()
    results = retriever.search("general Corvit class timings morning evening batches", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category == "timetable"
    assert "TIMINGS" in top.section_title or "TIMETABLE" in top.source_file.upper()


def test_infrastructure_retrieval_accuracy():
    """Verify retrieval accuracy for campus lab facilities."""
    retriever = get_retriever()
    results = retriever.search("Cisco networking lab facilities routers switches practical", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category == "infrastructure"
    assert "LAB" in top.section_title.upper() or "TRAINING" in top.section_title.upper()


def test_admission_retrieval_accuracy():
    """Verify retrieval accuracy for admission and application procedures."""
    retriever = get_retriever()
    results = retriever.search("how to apply for admission enrollment process and contact form", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category == "admission"
    assert "APPLY" in top.section_title.upper() or "ADMISSION" in top.section_title.upper()


def test_faq_retrieval_accuracy():
    """Verify retrieval accuracy for campus locations and general FAQs."""
    retriever = get_retriever()
    results = retriever.search("where is Corvit located in Lahore or Islamabad?", top_k=4)
    assert len(results) > 0
    top = results[0]
    assert top.category in ["faq", "general"]


def test_threshold_rejects_irrelevant_query():
    """
    Verify that completely unrelated queries (e.g. food recipes)
    fall below the 0.08 threshold and return zero results.
    """
    retriever = get_retriever()
    results = retriever.search("how to cook spicy chicken biryani recipe with basmati rice and saffron", top_k=4)
    assert len(results) == 0, f"Expected 0 results for irrelevant query, got {len(results)}"


def test_top_k_parameter_enforcement():
    """Verify that top_k strictly bounds the maximum number of returned results."""
    retriever = get_retriever()
    results_k2 = retriever.search("Python programming web development", top_k=2)
    assert len(results_k2) <= 2

    results_k5 = retriever.search("Python programming web development", top_k=5)
    assert len(results_k5) <= 5


def test_prompt_builder_structure_and_disclaimer():
    """Verify prompt context building, source citations, and time-sensitive disclaimer injection."""
    retriever = get_retriever()
    # Query about fees (time-sensitive category)
    results = retriever.search("What are the fee payment installments for courses?", top_k=3)
    assert len(results) > 0

    context = build_rag_prompt_context("What are the fee payment installments for courses?", results)
    assert isinstance(context, RAGPromptContext)
    assert context.is_fallback is False
    assert context.retrieved_count == len(results)
    assert len(context.citations) > 0
    assert "[DOCUMENT 1" in context.context_block
    assert "[END DOCUMENT 1]" in context.context_block

    # Check that time-sensitive disclaimer was attached
    assert context.disclaimer == OFFICIAL_DISCLAIMER


def test_prompt_builder_fallback_on_no_match():
    """Verify prompt builder behavior when retrieval returns no matching chunks."""
    context = build_rag_prompt_context("Unrelated query", results=[])
    assert context.is_fallback is True
    assert context.confidence_tier == "no_match"
    assert context.retrieved_count == 0
    assert len(context.citations) == 0
    assert context.disclaimer is None


def test_raw_dataset_untouched_during_retrieval():
    """
    CRITICAL TEST: Verifies SHA-256 hashes of all 8 files in Dataset/
    remain 100% identical after multiple retrieval operations.
    """
    dataset_dir = settings.dataset_dir
    pre_hashes = _get_dataset_hashes(dataset_dir)

    # Perform multiple diverse searches
    retriever = get_retriever()
    retriever.search("Artificial Intelligence", top_k=3)
    retriever.search("Fee structure", top_k=3)
    retriever.search("NAVTTC programs", top_k=3)
    retriever.search("Timetable morning", top_k=3)

    post_hashes = _get_dataset_hashes(dataset_dir)
    for cat in DATASET_REGISTRY.keys():
        assert pre_hashes[cat] == post_hashes[cat], f"Dataset file for {cat} was altered during retrieval!"
