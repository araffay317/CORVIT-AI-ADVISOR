"""
Comprehensive Verification Suite for Final Phase B (Frontend & Full Integration).
Tests:
1. Frontend Files Integrity & Elements (index.html, style.css, script.js).
2. API Key Absence & Frontend Security.
3. Frontend JavaScript API Contract Integration (Chat, Recommender, Sources, Disclaimers).
4. Backend API Contract Functionality (/health, /api/v1/chat, /api/v1/recommend-course, /api/v1/dataset-info).
5. Grounded, Out-of-Scope, and Temporal Chat Handling.
6. Graceful Handling of Empty Image Assets (Zero invented images).
7. Dataset SHA-256 Immutability.
"""
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.server import app
from backend.config import settings
from backend.rag.loader import DATASET_REGISTRY
from backend.llm.groq_client import groq_service

client = TestClient(app)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INDEX_HTML = BASE_DIR / "index.html"
STYLE_CSS = BASE_DIR / "style.css"
SCRIPT_JS = BASE_DIR / "script.js"

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


# =====================================================================
# 1. FRONTEND FILES & STRUCTURE VERIFICATION
# =====================================================================
def test_frontend_files_exist_and_non_empty():
    """Verify index.html, style.css, and script.js exist and have substantive content."""
    assert INDEX_HTML.exists(), "index.html is missing"
    assert STYLE_CSS.exists(), "style.css is missing"
    assert SCRIPT_JS.exists(), "script.js is missing"

    assert INDEX_HTML.stat().st_size > 500, "index.html is unexpectedly small"
    assert STYLE_CSS.stat().st_size > 200, "style.css is unexpectedly small"
    assert SCRIPT_JS.stat().st_size > 1000, "script.js is unexpectedly small"


def test_frontend_has_no_api_keys_or_secrets():
    """Verify no secret API keys, tokens, or credentials are hard-coded in frontend files."""
    for file_path in [INDEX_HTML, STYLE_CSS, SCRIPT_JS]:
        content = file_path.read_text(encoding="utf-8")
        assert "GROQ_API_KEY" not in content, f"Secret reference leaked in {file_path.name}"
        assert "gsk_" not in content, f"Possible Groq API token leaked in {file_path.name}"
        assert "bearer" not in content.lower(), f"Bearer token reference in {file_path.name}"


def test_frontend_ui_elements_presence():
    """Verify essential interactive DOM elements exist in index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Branding & Accessibility
    assert "Corvit AI Advisor" in html
    assert "Official Course &amp; Career Guide" in html or "Academic & Professional Career Guidance" in html
    assert "<h1" in html

    # Chat elements
    assert 'id="chat-section"' in html
    assert 'id="chat-messages"' in html
    assert 'id="chat-form"' in html
    assert 'id="chat-input"' in html
    assert 'id="send-btn"' in html
    assert 'id="clear-chat-btn"' in html
    assert 'id="typing-indicator"' in html

    # Course Recommender elements
    assert 'id="recommend-section"' in html
    assert 'id="recommendation-form"' in html
    assert 'id="rec-background"' in html
    assert 'id="rec-interests"' in html
    assert 'id="get-recommendations-btn"' in html
    assert 'id="rec-results"' in html

    # Campus & Navigation elements
    assert 'id="contacts-modal"' in html
    assert 'id="tab-chat-btn"' in html
    assert 'id="tab-recommend-btn"' in html


def test_script_js_endpoints_and_contracts_integration():
    """Verify script.js integrates with existing Phase 2-5 & Phase A API routes."""
    js = SCRIPT_JS.read_text(encoding="utf-8")

    # Endpoints integration
    assert "/api/v1/chat" in js
    assert "/api/v1/recommend-course" in js

    # Payload contract handling
    assert "allow_web_research" in js
    assert "history" in js
    assert "background" in js
    assert "experience_level" in js
    assert "interests" in js

    # Response parsing & UI mapping
    assert "sources" in js
    assert "disclaimer" in js
    assert "model_used" in js
    assert "is_verified" in js
    assert "recommendations" in js
    assert "match_score" in js
    assert "outline_summary" in js


# =====================================================================
# 2. BACKEND API CONTRACT INTEGRATION TESTS
# =====================================================================
def test_backend_health_endpoints_functional():
    """Verify /health and /api/v1/health return 200 with proper non-sensitive telemetry."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["primary_model"] == settings.PRIMARY_MODEL
    assert data["fallback_model"] == settings.FALLBACK_MODEL
    assert "groq_api_key" not in data

    res_alias = client.get("/api/v1/health")
    assert res_alias.status_code == 200
    assert res_alias.json()["status"] == "healthy"


def test_backend_dataset_info_endpoint():
    """Verify /api/v1/dataset-info correctly identifies all 8 verified categories."""
    res = client.get("/api/v1/dataset-info")
    assert res.status_code == 200
    data = res.json()
    assert data["categories_detected"] == 8
    categories = [c["category"] for c in data["categories"]]
    for cat in DATASET_REGISTRY.keys():
        assert cat in categories


@pytest.mark.asyncio
async def test_chat_integration_normal_grounded_query():
    """Verify /api/v1/chat processes student queries, returning citations and verified status."""
    mock_answer = "Corvit Systems offers Cisco CCNA with practical lab sessions on real routers and switches."

    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = (mock_answer, "openai/gpt-oss-120b")

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "What hardware and equipment is used in CCNA training?",
                "history": [],
                "allow_web_research": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == mock_answer
        assert data["model_used"] == "openai/gpt-oss-120b"
        assert data["is_verified"] is True
        assert len(data["sources"]) > 0
        assert isinstance(data["images"], list)


@pytest.mark.asyncio
async def test_chat_integration_temporal_query_with_disclaimer():
    """Verify temporal query integrates disclaimer when web verification is enabled."""
    mock_answer = "Upcoming batch for Python starts next month."

    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = (mock_answer, "openai/gpt-oss-120b")

        response = client.post(
            "/api/v1/chat",
            json={
                "message": "When is the upcoming batch for Python in 2026?",
                "history": [],
                "allow_web_research": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["disclaimer"] is not None
        assert "confirmation with the official Corvit Admissions Office" in data["disclaimer"]


def test_chat_integration_out_of_scope_query():
    """Verify out-of-scope query short-circuits gracefully with zero external LLM calls."""
    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "How to bake a chocolate cake with chocolate chips?",
                "history": [],
                "allow_web_research": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_verified"] is False
        assert "could not find verified information in the official Corvit knowledge base" in data["answer"]
        assert len(data["sources"]) == 0
        mock_complete.assert_not_called()


def test_recommend_course_integration():
    """Verify /api/v1/recommend-course generates structured response compatible with UI rendering."""
    payload = {
        "background": "FSc Pre-Engineering",
        "experience_level": "Beginner",
        "interests": ["Networking", "Routing"],
        "career_goal": "Network Support Engineer"
    }

    response = client.post("/api/v1/recommend-course", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "student_summary" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) in [2, 3]

    top = data["recommendations"][0]
    assert "course_name" in top
    assert "match_score" in top
    assert top["match_score"] >= 60
    assert "duration" in top
    assert "reasons" in top
    assert len(top["reasons"]) > 0
    assert "outline_summary" in top
    assert "prerequisites" in top


# =====================================================================
# 3. IMAGE HANDLING & DATASET IMMUTABILITY
# =====================================================================
def test_image_handling_graceful_without_unverified_images():
    """Verify images array is empty and no fake image URLs are fabricated."""
    images_dir = settings.assets_dir / "images"
    # Ensure no random fake images exist
    image_files = list(images_dir.glob("*.*")) if images_dir.exists() else []
    assert len(image_files) == 0, "Unverified images found in assets/images!"

    # Verify chat returns clean empty list
    with patch.object(groq_service, "generate_completion", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = ("Corvit answer.", "openai/gpt-oss-120b")
        res = client.post("/api/v1/chat", json={"message": "What is Python?"})
        assert res.status_code == 200
        data = res.json()
        assert data["images"] == []


def test_dataset_sha256_immutability_phase_b():
    """Verify all 8 Dataset files remain strictly unmodified during Phase B."""
    for cat, filename in DATASET_REGISTRY.items():
        file_path = settings.dataset_dir / cat / filename
        assert file_path.exists()
        with open(file_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        assert digest == EXPECTED_DATASET_HASHES[cat], (
            f"Dataset immutability violated in {cat}/{filename}! Hash: {digest}"
        )
