"""Pydantic request and response schemas for Corvit AI Advisor."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ----------------------------------------------------------------
# Chat Schemas
# ----------------------------------------------------------------
class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """Payload for POST /api/v1/chat."""
    message: str = Field(..., min_length=1, max_length=2000, description="Student's query or question")
    history: List[ChatMessage] = Field(default_factory=list, description="Prior conversational context")
    allow_web_research: bool = Field(default=True, description="Whether secondary online research is permitted")


class SourceCitation(BaseModel):
    """Citation provenance for grounded answers."""
    title: str
    category: str
    source_file: str
    snippet: Optional[str] = None


class ImagePayload(BaseModel):
    """Verified image asset reference."""
    url: str
    caption: str
    alt: str


class ChatResponse(BaseModel):
    """Response returned by POST /api/v1/chat."""
    answer: str
    model_used: str = Field(..., description="Actual model identifier e.g. openai/gpt-oss-120b or llama-3.1-8b-instant")
    sources: List[SourceCitation] = Field(default_factory=list, description="Grounded source citations")
    images: List[ImagePayload] = Field(default_factory=list, description="Verified relevant images")
    is_verified: bool = Field(default=True, description="True if answer is verified from Corvit sources")
    disclaimer: Optional[str] = Field(default=None, description="Notice if info requires admission confirmation")


# ----------------------------------------------------------------
# Course Recommendation Schemas
# ----------------------------------------------------------------
class CourseRecommendationRequest(BaseModel):
    """Payload for POST /api/v1/recommend-course."""
    background: str = Field(..., min_length=2, max_length=100, description="Student background e.g. Matric, Inter, BSCS")
    experience_level: str = Field(..., min_length=2, max_length=50, description="Beginner, Intermediate, or Advanced")
    interests: List[str] = Field(..., min_length=1, description="List of interested areas e.g. Networking, AI, Cyber")
    career_goal: Optional[str] = Field(default=None, max_length=150, description="e.g. Freelancing, Job, Certification")
    preferred_mode: Optional[str] = Field(default=None, max_length=100, description="e.g. Physical, Online, Weekend, Evening")


class RecommendedCourse(BaseModel):
    """Structured course recommendation card."""
    course_name: str
    match_score: int = Field(..., ge=0, le=100)
    duration: str
    reasons: List[str]
    outline_summary: str
    prerequisites: Optional[str] = None


class CourseRecommendationResponse(BaseModel):
    """Response returned by POST /api/v1/recommend-course."""
    student_summary: str
    recommendations: List[RecommendedCourse]


# ----------------------------------------------------------------
# Health & Status Schemas
# ----------------------------------------------------------------
class HealthResponse(BaseModel):
    """Response returned by GET /health."""
    status: str = Field(default="healthy", description="Application status")
    app_name: str = Field(default="Corvit AI Advisor", description="Application name")
    version: str = Field(default="1.0.0", description="API version")
    primary_model: str = Field(..., description="Configured primary model identifier")
    fallback_model: str = Field(..., description="Configured fallback model identifier")
    online_research_enabled: bool = Field(..., description="Whether online verification is enabled")


# ----------------------------------------------------------------
# Dataset Metadata Schemas (Phase 2 Read-Only Inspection)
# ----------------------------------------------------------------
class DatasetCategoryItem(BaseModel):
    """Metadata for a single dataset category."""
    category: str
    folder: str
    file_name: str
    exists: bool


class DatasetInfoResponse(BaseModel):
    """Response returned by GET /api/v1/dataset-info."""
    dataset_name: str = "Corvit Knowledge Base"
    categories_detected: int
    categories: List[DatasetCategoryItem]
