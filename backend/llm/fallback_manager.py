"""
Dual-Model Fallback Manager for Corvit AI Advisor.
Orchestrates seamless failover from Primary Model (openai/gpt-oss-120b)
to Fallback Model (llama-3.1-8b-instant) with graceful degradation.
"""
import logging
from typing import List, Optional, Tuple
from fastapi import HTTPException

from backend.config import settings
from backend.schemas import ChatMessage
from backend.rag.prompt_builder import RAGPromptContext
from backend.llm.groq_client import groq_service

logger = logging.getLogger("corvit_advisor.fallback")

# Exact contact information verified in Dataset (corvit_general.txt & corvit_admission_application.txt)
VERIFIED_CORVIT_CONTACTS = (
    "Our automated AI advisor is currently experiencing high demand. "
    "For immediate, verified course schedules, fees, and admission guidance, please contact Corvit Systems directly:\n\n"
    "• Lahore Campus (Head Office): 11A-D1, Ghalib Road, Gulberg III, Lahore\n"
    "  Phone: +92-303-8888555 / 042-35762401-2 | Email: info@corvit.com\n"
    "• Islamabad Campus: Al Malik Center, 70 West, Jinnah Avenue, Blue Area | Phone: 051-2348287\n"
    "• Rawalpindi Campus: 2nd Floor, Zarwar Center, Murree Road | Phone: 051-4928004\n"
    "• Peshawar Campus: 1st Floor, Ali Tower, University Road | Phone: 091-5701670\n"
    "• Hours: Monday to Saturday, 9:00 AM – 9:00 PM"
)


class FallbackManager:
    """Manages primary to secondary model failover with contact-card graceful degradation."""

    async def generate_with_fallback(
        self,
        rag_context: RAGPromptContext,
        history: Optional[List[ChatMessage]] = None,
        return_safe_response_on_error: bool = False
    ) -> Tuple[str, str]:
        """
        Attempt completion with Primary Model.
        If primary model times out, hits rate limits, or errors, route to Fallback Model.
        If both fail, return verified Corvit contact guidance.
        """
        # 1. Attempt Primary Model
        primary_model = settings.PRIMARY_MODEL
        try:
            logger.info(f"Attempting primary model: {primary_model}")
            answer, confirmed_model = await groq_service.generate_completion(
                rag_context=rag_context,
                history=history,
                model_override=primary_model
            )
            return answer, confirmed_model

        except HTTPException as primary_err:
            logger.warning(
                f"Primary model ({primary_model}) encountered HTTP {primary_err.status_code}: {primary_err.detail}. "
                f"Switching to fallback model: {settings.FALLBACK_MODEL}..."
            )
        except Exception as primary_err:
            logger.warning(
                f"Primary model ({primary_model}) failed: {primary_err}. "
                f"Switching to fallback model: {settings.FALLBACK_MODEL}..."
            )

        # 2. Attempt Fallback Model
        fallback_model = settings.FALLBACK_MODEL
        try:
            logger.info(f"Attempting fallback model: {fallback_model}")
            answer, confirmed_model = await groq_service.generate_completion(
                rag_context=rag_context,
                history=history,
                model_override=fallback_model
            )
            return answer, confirmed_model

        except Exception as fallback_err:
            logger.error(
                f"Both Primary ({primary_model}) and Fallback ({fallback_model}) models failed: {fallback_err}. "
                "Serving verified Corvit admission contacts fallback."
            )
            if return_safe_response_on_error:
                return VERIFIED_CORVIT_CONTACTS, f"{fallback_model}-offline-contact"

            if isinstance(fallback_err, HTTPException):
                if fallback_err.status_code == 504:
                    raise HTTPException(
                        status_code=504,
                        detail=f"The AI Advisor request timed out while connecting to the model. Please try your question again.\n\n{VERIFIED_CORVIT_CONTACTS}"
                    )
                raise HTTPException(
                    status_code=fallback_err.status_code,
                    detail=VERIFIED_CORVIT_CONTACTS
                )
            raise HTTPException(
                status_code=503,
                detail=VERIFIED_CORVIT_CONTACTS
            )


# Global singleton
fallback_manager = FallbackManager()
