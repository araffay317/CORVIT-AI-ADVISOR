"""
Secondary Online Research & Live Verification Service for Corvit AI Advisor.
Operates as a secondary source for temporal/time-sensitive queries.
The local Corvit Dataset remains the primary factual authority.
"""
import re
import time
import logging
from typing import Optional, Dict, List
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from backend.config import settings

logger = logging.getLogger("corvit_advisor.research")

# Verified official domains supported by Dataset evidence (corvit_general.txt & corvit_navttc.txt)
VERIFIED_DOMAINS = ["corvit.com", "navttc.gov.pk"]

# Comprehensive temporal keywords and regex patterns (Mandatory Correction 2)
TEMPORAL_PATTERNS = [
    r"\blatest\b",
    r"\bcurrent\b",
    r"\bupcoming\b",
    r"\b2025\b",
    r"\b2026\b",
    r"\bcurrent batch\b",
    r"\bnext batch\b",
    r"\bthis month\b",
    r"\bnext month\b",
    r"\badmission deadline\b",
    r"\bdeadline\b",
    r"\bstarting date\b",
    r"\bstart date\b",
    r"\bseat availability\b",
    r"\bseats available\b",
    r"\bfee update\b",
    r"\blatest fee\b",
    r"\blatest schedule\b",
    r"\bnew batch\b",
]

_TEMPORAL_REGEX = re.compile("|".join(TEMPORAL_PATTERNS), re.IGNORECASE)

# In-memory search cache (query -> (timestamp, result_summary))
_SEARCH_CACHE: Dict[str, tuple[float, str]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def is_temporal_query(query: str) -> bool:
    """
    Detect whether a query is time-sensitive or asks for current/live batch info.
    Supports all variations specified in Correction 2.
    """
    return bool(_TEMPORAL_REGEX.search(query))


class OnlineResearchService:
    """
    Secondary web search verification service.
    Prioritizes official Corvit and NAVTTC domains. Never invents facts.
    """

    def search_live_corvit_info(self, query: str) -> Optional[str]:
        """
        Execute a targeted search for time-sensitive Corvit or NAVTTC verification.
        Returns a concise verification excerpt or None if search is inconclusive.
        """
        if not settings.ENABLE_ONLINE_RESEARCH:
            return None

        clean_query = query.strip()
        if not clean_query:
            return None

        # Check in-memory cache
        now = time.time()
        if clean_query in _SEARCH_CACHE:
            cached_time, cached_res = _SEARCH_CACHE[clean_query]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_res

        # Formulate query prioritizing verified official domains
        search_query = f"site:{VERIFIED_DOMAINS[0]} {clean_query}"
        results_text = []

        try:
            logger.info(f"Executing secondary online research: '{search_query}'")
            with DDGS(timeout=4.0) as ddgs:
                raw_results = list(ddgs.text(search_query, max_results=3))

            # Fallback to broader search if site-specific search yields 0 results
            if not raw_results:
                broader_query = f"Corvit Systems {clean_query}"
                with DDGS(timeout=4.0) as ddgs:
                    raw_results = list(ddgs.text(broader_query, max_results=3))

            for item in raw_results:
                title = item.get("title", "")
                snippet = item.get("body", "")
                href = item.get("href", "")
                if snippet:
                    results_text.append(f"• [{title}]({href}): {snippet}")

            if results_text:
                summary = "\n".join(results_text[:2])
                _SEARCH_CACHE[clean_query] = (now, summary)
                return summary

        except Exception as e:
            logger.warning(f"Online research search encountered exception: {e}")

        return None


# Global singleton
research_service = OnlineResearchService()
