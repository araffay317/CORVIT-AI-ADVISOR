"""Automated verification tests for Phase 2 (Backend / API Architecture)."""
import pytest
from fastapi.testclient import TestClient
from backend.server import app
from backend.config import settings

client = TestClient(app)


def test_root_endpoint():
    """Verify that GET / returns HTTP 200 and root info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["version"] == "1.0.0"
    assert data["docs"] == "/docs"


def test_health_endpoint():
    """Verify that GET /health conforms to Correction 2 (focused on health/config, no sensitive leaks)."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Corvit AI Advisor"
    assert data["version"] == "1.0.0"
    assert data["primary_model"] == settings.PRIMARY_MODEL
    assert data["fallback_model"] == settings.FALLBACK_MODEL
    assert data["online_research_enabled"] is True
    # Ensure no internal server paths or telemetry leaked
    assert "cpu" not in data
    assert "memory" not in data
    assert "dataset_path" not in data


def test_health_endpoint_alias():
    """Verify that GET /api/v1/health functions identically."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_cors_headers():
    """Verify CORS middleware headers on preflight requests."""
    response = client.options(
        "/api/v1/chat",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5500"


def test_cors_production_netlify_health():
    """Verify CORS headers when production Netlify frontend queries /health."""
    # Preflight OPTIONS
    opt_res = client.options(
        "/health",
        headers={
            "Origin": "https://corvit-ai-advisor.netlify.app",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert opt_res.status_code == 200
    assert opt_res.headers.get("access-control-allow-origin") == "https://corvit-ai-advisor.netlify.app"

    # Actual GET request with Origin
    get_res = client.get(
        "/health",
        headers={"Origin": "https://corvit-ai-advisor.netlify.app"}
    )
    assert get_res.status_code == 200
    assert get_res.headers.get("access-control-allow-origin") == "https://corvit-ai-advisor.netlify.app"
    assert get_res.json()["status"] == "healthy"


def test_cors_netlify_preview_domain():
    """Verify CORS regex accepts Netlify deploy preview subdomains."""
    preview_origin = "https://deploy-preview-12--corvit-ai-advisor.netlify.app"
    res = client.get(
        "/health",
        headers={"Origin": preview_origin}
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == preview_origin


def test_cors_origins_list_sanitization():
    """Verify Settings.cors_origins_list handles quotes and trailing slashes defensively."""
    from backend.config import Settings
    custom_settings = Settings(
        CORS_ORIGINS='"https://custom.netlify.app/", \'https://another.com/\', http://localhost:8000/'
    )
    cleaned = custom_settings.cors_origins_list
    assert "https://custom.netlify.app" in cleaned
    assert "https://another.com" in cleaned
    assert "http://localhost:8000" in cleaned
    assert "https://corvit-ai-advisor.netlify.app" in cleaned  # Always guaranteed


def test_health_head_method():
    """Verify HEAD method is supported on /health."""
    response = client.head("/health")
    assert response.status_code == 200


def test_health_trailing_slash():
    """Verify both /health/ and /api/v1/health/ resolve directly with 200 OK."""
    res1 = client.get("/health/")
    assert res1.status_code == 200
    assert res1.json()["status"] == "healthy"

    res2 = client.get("/api/v1/health/")
    assert res2.status_code == 200
    assert res2.json()["status"] == "healthy"


def test_health_head_cors():
    """Verify HEAD request with Origin receives appropriate CORS headers."""
    response = client.head(
        "/health",
        headers={"Origin": "https://corvit-ai-advisor.netlify.app"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://corvit-ai-advisor.netlify.app"



def test_chat_endpoint_valid_payload():
    """
    Verify POST /api/v1/chat with valid payload.
    Conforms to Correction 1: model_used contains the exact model identifier.
    """
    from unittest.mock import AsyncMock, patch
    from backend.llm.groq_client import groq_service

    payload = {
        "message": "What IT courses are offered at Corvit Systems?",
        "history": [],
        "allow_web_research": True
    }
    with patch.object(
        groq_service,
        "generate_completion",
        new_callable=AsyncMock,
        return_value=("Corvit Systems offers professional IT courses in networking, AI, and cybersecurity.", settings.PRIMARY_MODEL)
    ):
        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        # Correction 1 assertion: must be actual model identifier, NOT 'primary' or 'fallback'
        assert data["model_used"] == settings.PRIMARY_MODEL
        assert data["model_used"] != "primary"
        assert data["model_used"] != "fallback"
        assert isinstance(data["sources"], list)
        assert isinstance(data["images"], list)
        assert data["is_verified"] is True


def test_chat_endpoint_validation_error():
    """Verify that empty query triggers HTTP 422 Unprocessable Entity."""
    payload = {
        "message": "",  # Empty message violates min_length=1
        "history": []
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 422


def test_recommend_course_valid():
    """Verify POST /api/v1/recommend-course returns structured recommendations."""
    payload = {
        "background": "BS Computer Science",
        "experience_level": "Intermediate",
        "interests": ["Artificial Intelligence", "Python"],
        "career_goal": "Machine Learning Engineer",
        "preferred_mode": "Physical Evening"
    }
    response = client.post("/api/v1/recommend-course", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "student_summary" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0
    rec = data["recommendations"][0]
    assert "course_name" in rec
    assert rec["match_score"] >= 0
    assert "duration" in rec
    assert isinstance(rec["reasons"], list)
    assert "outline_summary" in rec


def test_recommend_course_missing_fields():
    """Verify that omitting required fields triggers HTTP 422."""
    payload = {
        "background": "Matric"
        # missing experience_level and interests
    }
    response = client.post("/api/v1/recommend-course", json=payload)
    assert response.status_code == 422


def test_dataset_info_endpoint():
    """
    Verify GET /api/v1/dataset-info.
    Conforms to Correction 3: ONLY inspects presence, does NOT load or mutate content.
    """
    response = client.get("/api/v1/dataset-info")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_name"] == "Corvit Knowledge Base"
    assert data["categories_detected"] == 8
    assert len(data["categories"]) == 8
    for item in data["categories"]:
        assert item["exists"] is True
        assert item["category"] in [
            "courses", "navttc", "timetable", "fees",
            "admission", "infrastructure", "faq", "general"
        ]
