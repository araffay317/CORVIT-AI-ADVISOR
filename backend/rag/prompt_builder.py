"""
Prompt context builder, source citation assembler, and disclaimer injector.
Prepares grounded prompt structures for LLM consumption without invoking external APIs.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.rag.retriever import RetrievalResult
from backend.schemas import SourceCitation, ChatMessage

TIME_SENSITIVE_CATEGORIES = {"fees", "timetable", "admission"}

OFFICIAL_DISCLAIMER = (
    "Batch timings, start dates, campus offerings, and fee structures can change periodically. "
    "This information reflects standard Corvit Systems policies and requires confirmation with "
    "the official Corvit Admissions Office before enrollment."
)

FALLBACK_OUT_OF_SCOPE_MESSAGE = (
    "I am the Corvit AI Advisor, specialized in Corvit Systems IT courses, curriculum outlines, "
    "fee policies, batch timetables, NAVTTC free training, and campus labs. "
    "I could not find verified information in the official Corvit knowledge base regarding your question. "
    "Please ask a question related to Corvit IT training tracks or contact Corvit admissions directly."
)


class RAGPromptContext(BaseModel):
    """Structured context payload ready for downstream inference in Phase 5."""
    query: str
    context_block: str
    citations: List[SourceCitation]
    disclaimer: Optional[str] = None
    is_fallback: bool = False
    confidence_tier: str = "high"
    retrieved_count: int = 0


def format_citations(results: List[RetrievalResult]) -> List[SourceCitation]:
    """Convert RetrievalResults into public API SourceCitation models."""
    citations: List[SourceCitation] = []
    seen = set()

    for res in results:
        key = (res.category, res.source_file, res.section_title)
        if key in seen:
            continue
        seen.add(key)

        snippet = res.text[:180].strip() + ("..." if len(res.text) > 180 else "")
        citations.append(
            SourceCitation(
                title=res.section_title,
                category=res.category,
                source_file=res.source_file,
                snippet=snippet
            )
        )
    return citations


def build_rag_prompt_context(
    query: str,
    results: List[RetrievalResult],
    history: Optional[List[ChatMessage]] = None
) -> RAGPromptContext:
    """
    Assemble grounded context blocks and metadata from retrieved DocumentChunks.
    Does NOT call any external LLM or mutate data.
    """
    clean_query = query.strip()

    # Case 1: No retrieved chunks satisfied the similarity threshold
    if not results:
        return RAGPromptContext(
            query=clean_query,
            context_block="[NO RELEVANT CORVIT DATA FOUND]",
            citations=[],
            disclaimer=None,
            is_fallback=True,
            confidence_tier="no_match",
            retrieved_count=0
        )

    # Case 2: Assemble verified context blocks
    context_parts: List[str] = []
    has_time_sensitive = False

    for i, res in enumerate(results, start=1):
        if res.category in TIME_SENSITIVE_CATEGORIES:
            has_time_sensitive = True

        header = f"[DOCUMENT {i} | Category: {res.category} | Source: {res.source_file} | Section: {res.section_title}]"
        context_parts.append(f"{header}\n{res.text}\n[END DOCUMENT {i}]")

    combined_context = "\n\n".join(context_parts)
    citations = format_citations(results)

    # Determine highest confidence tier among retrieved results
    top_score = results[0].similarity_score
    if top_score >= 0.25:
        tier = "high"
    elif top_score >= 0.12:
        tier = "moderate"
    else:
        tier = "low"

    disclaimer = OFFICIAL_DISCLAIMER if has_time_sensitive else None

    return RAGPromptContext(
        query=clean_query,
        context_block=combined_context,
        citations=citations,
        disclaimer=disclaimer,
        is_fallback=False,
        confidence_tier=tier,
        retrieved_count=len(results)
    )
