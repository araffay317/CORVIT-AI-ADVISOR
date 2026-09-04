"""Data models for dataset ingestion, chunking, and RAG retrieval."""
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """
    A single factual chunk extracted from the Corvit dataset.
    Maintains provenance and verbatim text fidelity.
    """
    chunk_id: str = Field(..., description="Unique deterministic identifier e.g. courses_001")
    text: str = Field(..., min_length=20, description="Verbatim factual text content from the source dataset")
    category: str = Field(..., description="Category folder e.g. courses, fees, navttc")
    source_file: str = Field(..., description="Source filename e.g. corvit_courses.txt")
    section_title: str = Field(..., description="Extracted section heading or title")
    char_count: int = Field(..., ge=20, description="Character count of text")
    token_estimate: int = Field(..., ge=1, description="Word/token count estimate")
