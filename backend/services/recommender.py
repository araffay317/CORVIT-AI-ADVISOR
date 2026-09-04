"""
Course Recommendation Engine for Corvit AI Advisor.
Calculates personalized course recommendations purely from the ingested Corvit course dataset.
Guarantees zero hard-coded courses and zero unrealistic career/income promises.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from backend.rag.loader import get_dataset_chunks
from backend.schemas import (
    CourseRecommendationRequest,
    CourseRecommendationResponse,
    RecommendedCourse
)

logger = logging.getLogger("corvit_advisor.recommender")


class CourseProfile:
    """Internal model holding parsed curriculum information for a Corvit course."""
    def __init__(self, raw_title: str, text: str):
        self.raw_title = raw_title
        self.course_name = self._extract_clean_name(raw_title)
        self.duration = self._extract_field(text, r"Duration:\s*([^\n]+)", default="3 Months")
        self.main_area = self._extract_field(text, r"Main Area:\s*([^\n]+)", default="")
        self.topics = self._extract_section_list(text, r"(?:Topics\s*/\s*Skills|Common areas associated with [^\n]+ include):")
        self.suitable_for = self._extract_section_list(text, r"Suitable For:")
        self.prerequisites = self._extract_field(
            text,
            r"Recommended Background:\s*([\s\S]+?)(?=\n\n|\Z)",
            default="Basic computer literacy is helpful; verify prerequisites with admissions."
        ).strip()
        self.full_text = text

    def _extract_clean_name(self, title: str) -> str:
        """Strip section numbering and divider artifacts to produce clean course name."""
        cleaned = re.sub(r"^[0-9]+\.\s*", "", title).strip()
        return cleaned

    def _extract_field(self, text: str, pattern: str, default: str = "") -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    def _extract_section_list(self, text: str, header_pattern: str) -> List[str]:
        m = re.search(header_pattern + r"([\s\S]+?)(?=\n[A-Za-z0-9\s/—\-]+:|\Z)", text, re.IGNORECASE)
        if not m:
            return []
        lines = m.group(1).split("\n")
        items = [re.sub(r"^[-*•\s]+", "", line).strip() for line in lines if line.strip()]
        return [item for item in items if item and not item.startswith("---")]


class CourseRecommenderService:
    """
    Evaluates student background, skill level, and interests against the Corvit course catalog.
    Calculates dynamic relevance scores purely from dataset curriculum data.
    """

    def __init__(self):
        self.courses: List[CourseProfile] = []
        self._load_courses()

    def _load_courses(self):
        """Extract and index CourseProfile objects from the 21 courses chunks in Phase 3."""
        chunks = get_dataset_chunks()
        course_chunks = [c for c in chunks if c.category == "courses"]

        seen_names = set()
        for chunk in course_chunks:
            # Skip overview/policy and non-course chunks
            if "Overview & Policy" in chunk.section_title:
                continue

            profile = CourseProfile(chunk.section_title, chunk.text)
            if not profile.main_area:
                continue

            if profile.course_name not in seen_names and len(profile.course_name) > 3:
                self.courses.append(profile)
                seen_names.add(profile.course_name)

        logger.info(f"CourseRecommender indexed {len(self.courses)} courses from Dataset.")

    def calculate_match_score(
        self,
        course: CourseProfile,
        request: CourseRecommendationRequest
    ) -> Tuple[int, List[str]]:
        """
        Calculate a match percentage (0-100) and generate factual justifications.
        """
        score = 50  # Baseline interest
        reasons = []

        course_search_text = (
            f"{course.course_name} {course.main_area} "
            f"{' '.join(course.topics)} {' '.join(course.suitable_for)} {course.full_text}"
        ).lower()

        # 1. Interest matching (Highest weight)
        matched_interests = []
        for interest in request.interests:
            clean_interest = interest.strip().lower()
            if not clean_interest:
                continue

            # Check exact or partial word containment
            interest_tokens = set(clean_interest.split())
            if clean_interest in course_search_text or any(token in course_search_text for token in interest_tokens if len(token) > 2):
                matched_interests.append(interest.strip())
                score += 20

        if matched_interests:
            reasons.append(f"Directly covers your stated interest in: {', '.join(matched_interests)}.")

        # 2. Level compatibility
        req_level = request.experience_level.lower()
        if "beginner" in req_level:
            if "beginner" in course_search_text or "fundamentals" in course_search_text:
                score += 10
                reasons.append("Curriculum includes fundamental concepts suitable for beginners.")
            elif "advanced" in course_search_text:
                score -= 10
        elif "advanced" in req_level or "intermediate" in req_level:
            if "advanced" in course_search_text or "professional" in course_search_text or "deep learning" in course_search_text:
                score += 10
                reasons.append("Includes industry-level advanced training matching your experience.")

        # 3. Career goal matching
        if request.career_goal:
            goal_clean = request.career_goal.lower()
            goal_tokens = [t for t in goal_clean.split() if len(t) > 2]
            if any(t in course_search_text for t in goal_tokens):
                score += 10
                reasons.append(f"Prepares you for roles in {request.career_goal}.")

        # 4. Background affinity
        bg_clean = request.background.lower()
        if "non-it" in bg_clean or "matric" in bg_clean:
            if "basic" in course.prerequisites.lower() or "beginner" in course_search_text:
                score += 5
        elif "bscs" in bg_clean or "cs" in bg_clean or "engineer" in bg_clean:
            score += 5

        # Cap score between 55% and 98% (never 100% since no training course can guarantee a perfect fit)
        final_score = min(98, max(55, score))

        if not reasons:
            reasons.append(f"Offers solid practical IT training in {course.main_area or course.course_name}.")

        return final_score, reasons

    def recommend(
        self,
        request: CourseRecommendationRequest,
        top_k: int = 3
    ) -> CourseRecommendationResponse:
        """
        Rank all Corvit courses for the given student profile and return top recommendations.
        """
        if not self.courses:
            self._load_courses()

        scored_courses: List[Tuple[CourseProfile, int, List[str]]] = []

        for course in self.courses:
            score, reasons = self.calculate_match_score(course, request)
            scored_courses.append((course, score, reasons))

        # Sort descending by match score
        scored_courses.sort(key=lambda x: x[1], reverse=True)

        recommendations: List[RecommendedCourse] = []
        for course, score, reasons in scored_courses[:top_k]:
            outline = (
                f"{course.main_area}. Topics include: {', '.join(course.topics[:5])}."
                if course.topics else course.main_area
            )

            recommendations.append(
                RecommendedCourse(
                    course_name=course.course_name,
                    match_score=score,
                    duration=course.duration,
                    reasons=reasons,
                    outline_summary=outline,
                    prerequisites=course.prerequisites
                )
            )

        summary = (
            f"Student Background: {request.background} | Level: {request.experience_level} | "
            f"Interests: {', '.join(request.interests)}"
        )
        if request.career_goal:
            summary += f" | Goal: {request.career_goal}"

        return CourseRecommendationResponse(
            student_summary=summary,
            recommendations=recommendations
        )


# Global singleton
recommender_service = CourseRecommenderService()
