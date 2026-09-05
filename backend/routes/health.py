"""Health and status endpoint for Corvit AI Advisor."""
from fastapi import APIRouter
from backend.config import settings
from backend.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
@router.api_route("/health/", methods=["GET", "HEAD"], response_model=HealthResponse)
@router.api_route("/api/v1/health", methods=["GET", "HEAD"], response_model=HealthResponse)
@router.api_route("/api/v1/health/", methods=["GET", "HEAD"], response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return health and active configuration status without sensitive system internals."""
    return HealthResponse(
        status="healthy",
        app_name="Corvit AI Advisor",
        version="1.0.0",
        primary_model=settings.PRIMARY_MODEL,
        fallback_model=settings.FALLBACK_MODEL,
        online_research_enabled=settings.ENABLE_ONLINE_RESEARCH
    )
