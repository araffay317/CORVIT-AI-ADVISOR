"""
Hybrid BM25/TF-IDF Retrieval Engine for Corvit AI Advisor.
Operates deterministically over the ingested Corvit dataset chunks with category-intent ranking.
"""
import re
import time
import logging
from typing import List, Optional, Dict, Set
from pydantic import BaseModel, Field
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.rag.models import DocumentChunk
from backend.rag.loader import get_dataset_chunks

logger = logging.getLogger("corvit_advisor.retriever")


class RetrievalResult(BaseModel):
    """Represents a ranked, retrieved chunk with relevance scoring and provenance."""
    chunk_id: str
    text: str
    category: str
    source_file: str
    section_title: str
    similarity_score: float
    relevance_tier: str
    char_count: int
    token_estimate: int


# Mapping of common topical keywords to primary categories as a ranking aid
CATEGORY_KEYWORD_MAP: Dict[str, Set[str]] = {
    "fees": {"fee", "fees", "cost", "charges", "installment", "installments", "payment", "pkr", "price"},
    "timetable": {"timing", "timings", "batch", "batches", "schedule", "morning", "evening", "weekend", "weekday", "hours"},
    "navttc": {"navttc", "free", "government", "scholarship", "funded", "vocational", "technical education"},
    "admission": {"admission", "apply", "enroll", "enrollment", "registration", "procedure", "process", "eligibility", "documents"},
    "infrastructure": {"lab", "labs", "facility", "facilities", "cisco", "rack", "racks", "router", "routers", "switch", "switches", "hardware", "classroom", "training environment"},
    "courses": {
        "course", "courses", "outline", "syllabus", "topics", "curriculum",
        "duration", "prerequisites", "learn", "study", "offer", "offered",
        "offers", "offering", "available", "program", "programs", "track", "tracks"
    },
    "general": {"about", "history", "vision", "mission", "head office", "branches", "campuses"},
    "faq": {"question", "faq", "frequently asked", "general information"}
}


class CorvitRetriever:
    """
    In-memory TF-IDF retriever utilizing sublinear TF scaling (BM25 term-frequency style),
    unigram + bigram representations, and category-intent ranking aids.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.08,
        category_boost: float = 1.3
    ):
        self.similarity_threshold = similarity_threshold
        self.category_boost = category_boost
        self.chunks: List[DocumentChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self._is_indexed = False

    def index(self, chunks: Optional[List[DocumentChunk]] = None) -> int:
        """
        Build the TF-IDF vector space over the provided or loaded dataset chunks.
        """
        if chunks is None:
            self.chunks = get_dataset_chunks()
        else:
            self.chunks = list(chunks)

        if not self.chunks:
            raise ValueError("Cannot index an empty list of DocumentChunks.")

        corpus = [chunk.text for chunk in self.chunks]

        # Vectorizer with sublinear TF (BM25 saturation principle) and (1, 2) n-grams
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            norm="l2",
            stop_words="english",
            lowercase=True
        )

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self._is_indexed = True
        logger.info(f"Indexed {len(self.chunks)} DocumentChunks into TF-IDF vector space.")
        return len(self.chunks)

    def detect_category_intent(self, query: str) -> Optional[str]:
        """
        Identify if query contains strong keyword indicators for any of the 8 categories.
        Acts strictly as a ranking aid, not a hard filter.
        """
        tokens = set(re.sub(r"[^\w\s]", " ", query.lower()).split())
        matched_category = None
        max_matches = 0

        for cat, keywords in CATEGORY_KEYWORD_MAP.items():
            matches = len(tokens.intersection(keywords))
            if matches > max_matches:
                max_matches = matches
                matched_category = cat

        return matched_category if max_matches > 0 else None

    def search(
        self,
        query: str,
        top_k: int = 4,
        threshold: Optional[float] = None
    ) -> List[RetrievalResult]:
        """
        Search for top-k matching DocumentChunks for a student's query.
        Returns empty list if no chunks satisfy the threshold.
        """
        if not self._is_indexed or self.vectorizer is None or self.tfidf_matrix is None:
            self.index()

        min_threshold = self.similarity_threshold if threshold is None else threshold
        clean_query = query.strip()
        if not clean_query:
            return []

        clean_lower = clean_query.lower()
        expanded_query = clean_query
        if "offered" in clean_lower and "offer" not in clean_lower.split():
            expanded_query += " offer"

        # Transform query into TF-IDF vector space
        query_vec = self.vectorizer.transform([expanded_query])

        # Compute raw cosine similarity against all chunks
        raw_similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Check for category intent ranking aid
        intent_cat = self.detect_category_intent(clean_query)

        # Check if query is asking generally about what courses/programs Corvit offers
        is_general_course_query = bool(
            re.search(r"\b(what|which|list|tell|available|all)\b", clean_lower) and
            re.search(r"\b(courses?|programs?)\b", clean_lower) and
            re.search(r"\b(offer(ed|s|ing)?|available|provide|have)\b", clean_lower)
        )

        # Apply category ranking aid to raw scores
        adjusted_scores = []
        for idx, score in enumerate(raw_similarities):
            adj_score = float(score)
            chunk = self.chunks[idx]
            if intent_cat and chunk.category == intent_cat:
                adj_score *= self.category_boost

            # If user asks generally what courses/programs are offered, boost authoritative faq_007 chunk
            if is_general_course_query and chunk.chunk_id == "faq_007":
                adj_score *= (self.category_boost * 1.5)

            adjusted_scores.append((idx, adj_score, float(score)))

        # Sort descending by adjusted score
        adjusted_scores.sort(key=lambda x: x[1], reverse=True)

        results: List[RetrievalResult] = []
        for idx, adj_score, raw_score in adjusted_scores:
            # Enforce similarity threshold against adjusted score
            if adj_score < min_threshold:
                continue

            chunk = self.chunks[idx]

            # Categorize relevance tier
            if adj_score >= 0.25:
                tier = "high"
            elif adj_score >= 0.12:
                tier = "moderate"
            else:
                tier = "low"

            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    category=chunk.category,
                    source_file=chunk.source_file,
                    section_title=chunk.section_title,
                    similarity_score=round(adj_score, 4),
                    relevance_tier=tier,
                    char_count=chunk.char_count,
                    token_estimate=chunk.token_estimate
                )
            )

            if len(results) >= top_k:
                break

        return results


# Global singleton instance
_RETRIEVER_INSTANCE: Optional[CorvitRetriever] = None


def get_retriever() -> CorvitRetriever:
    """Access the global initialized CorvitRetriever singleton."""
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        _RETRIEVER_INSTANCE = CorvitRetriever()
        _RETRIEVER_INSTANCE.index()
    return _RETRIEVER_INSTANCE
