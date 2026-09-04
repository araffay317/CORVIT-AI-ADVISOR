"""
Asynchronous Groq API Client for Corvit AI Advisor.
Connects to Primary Model (openai/gpt-oss-120b) with timeout and rate-limit handling.
"""
import logging
from typing import List, Dict, Optional, Tuple
from fastapi import HTTPException, status
from groq import AsyncGroq, GroqError, APIConnectionError, RateLimitError, APIStatusError, APITimeoutError

from backend.config import settings
from backend.schemas import ChatMessage
from backend.rag.prompt_builder import RAGPromptContext
from backend.llm.prompts import MASTER_SYSTEM_PROMPT, format_chat_messages

logger = logging.getLogger("corvit_advisor.llm")


class GroqClientService:
    """Service wrapping AsyncGroq client with strict error handling and timeouts."""

    def __init__(self):
        self._client: Optional[AsyncGroq] = None

    def _get_client(self) -> AsyncGroq:
        """Initialize or return the AsyncGroq client using server-side configuration."""
        api_key_str = settings.GROQ_API_KEY.get_secret_value()
        if not api_key_str or api_key_str == "your_groq_api_key_here":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groq API service is not configured. Please set a valid GROQ_API_KEY in the server .env configuration."
            )

        if self._client is None:
            self._client = AsyncGroq(
                api_key=api_key_str,
                timeout=10.0  # 10-second client timeout
            )
        return self._client

    async def generate_completion(
        self,
        rag_context: RAGPromptContext,
        history: Optional[List[ChatMessage]] = None,
        model_override: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Send grounded RAG prompt to primary Groq model.
        Returns (answer_text, actual_model_identifier).
        Adheres to Correction 2: captures actual model reported in API response.
        """
        client = self._get_client()
        target_model = model_override or settings.PRIMARY_MODEL

        # Format messages with XML boundaries and bounded history
        messages = format_chat_messages(
            system_prompt=MASTER_SYSTEM_PROMPT,
            context_block=rag_context.context_block,
            user_message=rag_context.query,
            history=history or []
        )

        try:
            logger.info(f"Calling Groq API with model: {target_model}")
            response = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=0.1,
                max_tokens=1024
            )

            # Extract response content
            answer_text = response.choices[0].message.content or ""

            # Correction 2: Extract actual model identifier confirmed by Groq response
            confirmed_model = getattr(response, "model", None) or target_model

            logger.info(f"Groq completion received successfully. Model confirmed: {confirmed_model}")
            return answer_text, confirmed_model

        except RateLimitError as e:
            logger.warning(f"Groq RateLimitError encountered: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The Corvit AI Advisor is currently experiencing high request volume. Please wait a moment and try again."
            )
        except APITimeoutError as e:
            logger.error(f"Groq APITimeoutError encountered after 10s: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The AI Advisor request timed out while connecting to the model. Please try your question again."
            )
        except APIConnectionError as e:
            logger.error(f"Groq APIConnectionError: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not establish connection to the Groq AI service. Please verify server connectivity."
            )
        except APIStatusError as e:
            logger.error(f"Groq APIStatusError ({e.status_code}): {e.message}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq service error ({e.status_code}). Please try again later."
            )
        except Exception as e:
            logger.error(f"Unexpected error in Groq completion: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while generating the advisor response."
            )


# Global singleton instance
groq_service = GroqClientService()
