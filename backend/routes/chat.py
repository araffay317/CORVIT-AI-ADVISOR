"""Chat route handler for Corvit AI Advisor."""
from fastapi import APIRouter
from backend.config import settings
from backend.schemas import ChatRequest, ChatResponse
from backend.rag.retriever import get_retriever
from backend.rag.prompt_builder import (
    build_rag_prompt_context,
    FALLBACK_OUT_OF_SCOPE_MESSAGE,
    OFFICIAL_DISCLAIMER
)
from backend.llm.fallback_manager import fallback_manager
from backend.services.research import is_temporal_query, research_service

router = APIRouter(prefix="/api/v1", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
    """
    Handle student queries with grounded Corvit guidance.
    - Uses Phase 4 hybrid retrieval as primary authority.
    - Performs secondary online verification for temporal/time-sensitive queries.
    - Employs dual-model failover (Primary: gpt-oss-120b -> Fallback: llama-3.1-8b-instant).
    - Short-circuits on low-confidence/no-match queries to prevent hallucinations.
    """
    # 1. Retrieve top-k verified chunks from Phase 4
    retriever = get_retriever()
    results = retriever.search(request.message, top_k=4)

    # 2. Build grounded context, citations, and disclaimers
    rag_context = build_rag_prompt_context(
        query=request.message,
        results=results,
        history=request.history
    )

    # 3. Secondary Online Research (for temporal/time-sensitive queries only)
    is_temporal = is_temporal_query(request.message)
    if is_temporal and request.allow_web_research and not rag_context.is_fallback:
        live_notes = research_service.search_live_corvit_info(request.message)
        if live_notes:
            rag_context.context_block += (
                f"\n\n[SECONDARY ONLINE VERIFICATION (corvit.com)]\n"
                f"{live_notes}\n"
                f"[END SECONDARY ONLINE VERIFICATION]"
            )
            rag_context.disclaimer = (
                f"{OFFICIAL_DISCLAIMER} Note: Secondary online research was consulted for time-sensitive context; "
                "current batch dates, seat availability, and fee updates must be directly confirmed with the Corvit Admissions Office."
            )
        else:
            rag_context.disclaimer = OFFICIAL_DISCLAIMER

    # 4. Generate answer with dual-model fallback or short-circuit if query is out of scope
    if rag_context.is_fallback:
        answer = FALLBACK_OUT_OF_SCOPE_MESSAGE
        model_used = settings.PRIMARY_MODEL
    else:
        answer, model_used = await fallback_manager.generate_with_fallback(
            rag_context=rag_context,
            history=request.history
        )

    # 5. Construct response adhering to Phase 2 ChatResponse schema
    return ChatResponse(
        answer=answer,
        model_used=model_used,
        sources=rag_context.citations,
        images=[],
        is_verified=not rag_context.is_fallback,
        disclaimer=rag_context.disclaimer
    )
