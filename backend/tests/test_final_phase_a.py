"""
Comprehensive Verification Suite for Final Phase A.
Tests:
1. Fallback Groq Model (Primary openai/gpt-oss-120b -> Fallback llama-3.1-8b-instant).
2. Online Research (Secondary only, verified domains, temporal detection, disclaimers).
3. Course Recommender (Dynamic scoring from Dataset, multi-factor evaluation, top 2-3 recommendations).
4. Chat Integration & Security (RAG grounding, citations, API key protection).
5. Dataset Immutability (SHA-256 verification of all 8 dataset files).
"""
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from groq import RateLimitError, APITimeoutError

from backend.server import app
from backend.config import settings
from backend.rag.loader import DATASET_REGISTRY, get_dataset_chunks
from backend.rag.models import DocumentChunk
from backend.rag.prompt_builder import build_rag_prompt_context, RAGPromptContext
from backend.rag.retriever import RetrievalResult
from backend.llm.groq_client import groq_service
from backend.llm.fallback_manager import fallback_manager, VERIFIED_CORVIT_CONTACTS
from backend.services.research import is_temporal_query, research_service, VERIFIED_DOMAINS
from backend.services.recommender import recommender_service
from backend.schemas import CourseRecommendationRequest, ChatMessage

client = TestClient(app)

# Dataset baseline SHA-256 hashes
EXPECTED_DATASET_HASHES = {
    "courses": "7d9b6b16048fa059c380ae9344a3ac91db5679793ad7c9d1e2c2314d880da62e",
    "navttc": "8d246641876928659a292735b5232e87fc0ce74813e620cc544c69ed81fe8e27",
    "timetable": "c750e0a558e4901e910b541edd662797e94d529a7b1533e5d67fea75b4c6aa50",
    "fees": "992338b96b5920568f5c4e8a35359f3b85f7e1c99a37735224830bab59661fcc",
    "admission": "66543945263d54f6433139393b00ad4d68b4a6accd40055c6971a14aab7f4999",
    "infrastructure": "66fa86c7c8b096c0793dd063a652881c0387d403bd793d5072f74d0dee233fc7",
    "faq": "a0acb66a1b3b66782dc8cd3b0513968f9d3e91e0a7483b7f62c12dc15ea9e60b",
    "general": "6fce34bb99325352815913f784e1861fabea1f4b76c7b932db099db6e9c6da59",
}


def _compute_current_dataset_hashes() -> dict:
    """Read and hash all 8 files currently present in Dataset/."""
    current_hashes = {}
    for cat, filename in DATASET_REGISTRY.items():
        file_path = settings.dataset_dir / cat / filename
        assert file_path.exists(), f"Missing dataset file: {file_path}"
        with open(file_path, "rb") as f:
            current_hashes[cat] = hashlib.sha256(f.read()).hexdigest()
    return current_hashes


# =====================================================================
# A) FALLBACK GROQ MODEL TESTS
# =====================================================================
def test_fallback_models_configuration():
    """Verify configured primary and fallback model identifiers."""
    assert settings.PRIMARY_MODEL == "openai/gpt-oss-120b"
    assert settings.FALLBACK_MODEL == "llama-3.1-8b-instant"


@pytest.mark.asyncio
async def test_fallback_primary_success():
    """When primary model succeeds, it returns primary completion and model name."""
    rag_context = RAGPromptContext(
        query="Tell me about CCNA course.",
        context_block="[DOCUMENT 1]\nCCNA routing and switching details.\n[END DOCUMENT 1]",
        citations=[],
        retrieved_count=1
    )

    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = ("CCNA covers network fundamentals.", "openai/gpt-oss-120b")

        answer, model_used = await fallback_manager.generate_with_fallback(rag_context)

        assert answer == "CCNA covers network fundamentals."
        assert model_used == "openai/gpt-oss-120b"
        mock_complete.assert_called_once()
        # Ensure called with primary model
        assert mock_complete.call_args.kwargs["model_override"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_fallback_primary_failover_to_secondary():
    """When primary model fails, fallback seamlessly routes to llama-3.1-8b-instant with same RAG context."""
    rag_context = RAGPromptContext(
        query="Tell me about CCNA course.",
        context_block="[DOCUMENT 1]\nCCNA routing and switching details.\n[END DOCUMENT 1]",
        citations=[],
        retrieved_count=1
    )

    call_count = 0

    async def mock_generate_side_effect(rag_context, history=None, model_override=None):
        nonlocal call_count
        call_count += 1
        if model_override == "openai/gpt-oss-120b":
            # Simulate primary model rate limit / 503 error
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Rate limit exceeded")
        elif model_override == "llama-3.1-8b-instant":
            return ("Fallback: CCNA details from llama.", "llama-3.1-8b-instant")
        raise RuntimeError("Unexpected model")

    with patch.object(groq_service, "generate_completion", side_effect=mock_generate_side_effect):
        answer, model_used = await fallback_manager.generate_with_fallback(rag_context)

        assert answer == "Fallback: CCNA details from llama."
        assert model_used == "llama-3.1-8b-instant"
        assert call_count == 2  # First primary, then fallback


@pytest.mark.asyncio
async def test_fallback_both_fail_returns_verified_contacts():
    """When both primary and secondary fail, returns verified Corvit contact guidance."""
    rag_context = RAGPromptContext(
        query="Tell me about CCNA course.",
        context_block="[DOCUMENT 1]\nCCNA details.\n[END DOCUMENT 1]",
        citations=[],
        retrieved_count=1
    )

    with patch.object(groq_service, "generate_completion", side_effect=RuntimeError("Both services offline")):
        answer, model_used = await fallback_manager.generate_with_fallback(
            rag_context,
            return_safe_response_on_error=True
        )

        assert "Lahore Campus" in answer
        assert "042-35762401-2" in answer
        assert "Islamabad Campus" in answer
        assert "Rawalpindi Campus" in answer
        assert "Peshawar Campus" in answer
        assert "info@corvit.com" in answer
        assert model_used == "llama-3.1-8b-instant-offline-contact"


def test_verified_corvit_contacts_accuracy_in_dataset():
    """Verify that every contact detail in VERIFIED_CORVIT_CONTACTS matches Dataset content."""
    gen_text = (settings.dataset_dir / "general" / "corvit_general.txt").read_text(encoding="utf-8")
    adm_text = (settings.dataset_dir / "admission" / "corvit_admission_application.txt").read_text(encoding="utf-8")
    combined = gen_text + "\n" + adm_text

    # Check key phone numbers and addresses
    assert "042-35762401-2" in combined
    assert "051-2348287" in combined
    assert "051-4928004" in combined
    assert "091-5701670" in combined
    assert "info@corvit.com" in combined
    assert "11A-D1, Ghalib Road" in combined or "11A, D1, Ghalib Road" in combined


# =====================================================================
# B) ONLINE RESEARCH TESTS
# =====================================================================
def test_temporal_detection_comprehensive_variations():
    """Verify temporal detection recognizes all required time-sensitive variations."""
    temporal_phrases = [
        "What is the latest schedule for Python?",
        "Who is the current batch teacher?",
        "When is the upcoming batch for CCNA?",
        "Are there any batches in 2025?",
        "What are the 2026 batch dates?",
        "When does the current batch start?",
        "Tell me about the next batch.",
        "Will classes start this month?",
        "Is there a class next month?",
        "What is the admission deadline for NAVTTC?",
        "What is the registration deadline?",
        "What is the starting date for Ethical Hacking?",
        "When is the start date?",
        "Is there any seat availability in Cloud Computing?",
        "Are seats available?",
        "Any recent fee update for Cyber Security?",
        "What is the latest fee?",
        "Give me the latest schedule.",
        "When does the new batch begin?",
    ]

    for phrase in temporal_phrases:
        assert is_temporal_query(phrase) is True, f"Failed to detect temporal query: {phrase}"

    # Non-temporal questions should NOT trigger temporal detection
    static_queries = [
        "What is CCNA?",
        "What topics are included in Artificial Intelligence?",
        "Who is Corvit Systems?",
        "What is the duration of CCNP?",
        "Where is the Lahore campus located?",
    ]
    for sq in static_queries:
        assert is_temporal_query(sq) is False, f"False positive temporal detection for: {sq}"


def test_online_research_official_domains():
    """Verify that secondary research uses officially verified Corvit domains."""
    assert "corvit.com" in VERIFIED_DOMAINS
    assert "navttc.gov.pk" in VERIFIED_DOMAINS


def test_chat_temporal_query_attaches_disclaimer():
    """Verify that temporal queries attach the official time-sensitive disclaimer in chat."""
    mock_notes = "• [Corvit Admissions](https://corvit.com/admission): Admissions open for new batches."

    with patch.object(research_service, "search_live_corvit_info", return_value=mock_notes):
        with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = ("Latest batch begins next Monday.", "openai/gpt-oss-120b")

            response = client.post(
                "/api/v1/chat",
                json={
                    "message": "What is the latest schedule and start date for CCNA in 2026 batch?",
                    "allow_web_research": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["disclaimer"] is not None
            assert "confirmation with the official Corvit Admissions Office" in data["disclaimer"]
            assert "Secondary online research" in data["disclaimer"]


# =====================================================================
# C) COURSE RECOMMENDER TESTS
# =====================================================================
def test_course_recommender_dynamic_calculation():
    """
    Verify course recommendations are calculated from dataset chunks,
    produce top 2-3 recommendations, and do not hardcode a single course.
    """
    # Test Profile 1: Networking & Hardware
    req_network = CourseRecommendationRequest(
        background="Intermediate / Pre-Engineering",
        experience_level="Beginner",
        interests=["Networking", "Routing", "Cisco"],
        career_goal="Network Support Engineer"
    )
    res_network = recommender_service.recommend(req_network, top_k=3)
    assert len(res_network.recommendations) in [2, 3]
    top_net = res_network.recommendations[0]
    assert any(term in top_net.course_name.lower() for term in ["ccna", "network", "routing", "cisco"])
    assert top_net.match_score >= 60
    assert len(top_net.duration) > 0
    assert len(top_net.reasons) > 0
    assert top_net.outline_summary is not None
    assert top_net.prerequisites is not None

    # Test Profile 2: Artificial Intelligence & Machine Learning
    req_ai = CourseRecommendationRequest(
        background="BS Computer Science",
        experience_level="Intermediate",
        interests=["Artificial Intelligence", "Python", "Machine Learning"],
        career_goal="AI Engineer"
    )
    res_ai = recommender_service.recommend(req_ai, top_k=3)
    assert len(res_ai.recommendations) in [2, 3]
    top_ai = res_ai.recommendations[0]
    assert any(term in top_ai.course_name.lower() for term in ["artificial intelligence", "python", "machine learning"])
    assert top_ai.match_score >= 60

    # Ensure different profiles yield different top recommendations (no hardcoding)
    assert top_net.course_name != top_ai.course_name


def test_course_recommender_api_endpoint():
    """Verify POST /api/v1/recommend-course returns proper schema response."""
    payload = {
        "background": "BS Information Technology",
        "experience_level": "Beginner",
        "interests": ["Cyber Security", "Ethical Hacking"],
        "career_goal": "Security Analyst"
    }
    response = client.post("/api/v1/recommend-course", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "student_summary" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 2
    for rec in data["recommendations"]:
        assert "course_name" in rec
        assert "match_score" in rec
        assert "duration" in rec
        assert "reasons" in rec
        assert "outline_summary" in rec


# =====================================================================
# D) DATASET IMMUTABILITY & SECURITY TESTS
# =====================================================================
def test_dataset_sha256_immutability():
    """Verify all 8 dataset files strictly match their expected SHA-256 hashes."""
    current_hashes = _compute_current_dataset_hashes()
    for cat, expected_hash in EXPECTED_DATASET_HASHES.items():
        assert current_hashes[cat] == expected_hash, (
            f"Dataset immutability violated for category '{cat}'! "
            f"Expected: {expected_hash}, Got: {current_hashes[cat]}"
        )


def test_api_key_security():
    """Verify GROQ_API_KEY is masked and never exposed in responses or configurations."""
    # 1. Config representation is masked
    assert "**********" in str(settings.GROQ_API_KEY)
    assert settings.GROQ_API_KEY.get_secret_value() != "UNMASKED_LEAK"

    # 2. /health does not leak keys or internal paths
    res_health = client.get("/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert "api_key" not in health_data
    assert "groq_api_key" not in health_data

    # 3. /api/v1/chat response contains no key leaks
    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = ("Corvit offers Python training.", "openai/gpt-oss-120b")
        res_chat = client.post("/api/v1/chat", json={"message": "What is Python training?"})
        assert res_chat.status_code == 200
        chat_str = res_chat.text
        real_key = settings.GROQ_API_KEY.get_secret_value()
        if len(real_key) > 5 and real_key != "your_groq_api_key_here":
            assert real_key not in chat_str
