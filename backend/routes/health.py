"""Health and status endpoint for Corvit AI Advisor."""
from fastapi import APIRouter
from backend.config import settings
from backend.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/v1/health", response_model=HealthResponse)
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
