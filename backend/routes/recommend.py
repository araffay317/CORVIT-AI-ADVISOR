"""Course recommendation wizard route for Corvit AI Advisor."""
from fastapi import APIRouter
from backend.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResponse
)
from backend.services.recommender import recommender_service

router = APIRouter(prefix="/api/v1", tags=["Course Recommendation"])


@router.post("/recommend-course", response_model=CourseRecommendationResponse)
async def post_recommend_course(request: CourseRecommendationRequest) -> CourseRecommendationResponse:
    """
    Evaluate student profile and return dynamically ranked Corvit courses.
    Genuinely calculated from the Corvit course curriculum dataset.
    """
    return recommender_service.recommend(request=request)
