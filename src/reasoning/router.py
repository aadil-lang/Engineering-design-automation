import re
from reasoning.models import QuestionType

# Deterministic regex patterns for question routing
HOLE_KEYWORDS = re.compile(r"\b(hole|holes|bore|bores|drilled|drill|boreholes?)\b", re.IGNORECASE)
RELATIONSHIP_KEYWORDS = re.compile(
    r"\b(relationship|relationships|parallel|perpendicular|connected|connectivity|collinear)\b",
    re.IGNORECASE
)
DIMENSION_KEYWORDS = re.compile(
    r"\b(dimension|dimensions|tolerance|tolerances|measurement|measurements|nominal|radius|diameter)\b",
    re.IGNORECASE
)
ANNOTATION_KEYWORDS = re.compile(
    r"\b(annotation|annotations|symbol|symbols|ocr|text|callout|label|labels)\b",
    re.IGNORECASE
)
GEOMETRY_KEYWORDS = re.compile(
    r"\b(geometry|geometric|line|lines|circle|circles|contour|contours|shape|shapes|bounding|extent)\b",
    re.IGNORECASE
)


def route_question(question: str) -> QuestionType:
    """
    Deterministically route an engineering question to an appropriate category
    without invoking an LLM.

    Precedence order:
    1. Holes / Bores (hole_analysis)
    2. Relationships (relationship_analysis)
    3. Dimensions & Tolerances (dimension_summary)
    4. Annotations & Symbols (annotation_summary)
    5. General Geometry (geometry_summary)
    6. Fallback (general_engineering_question)
    """
    if not question or not question.strip():
        return QuestionType.GENERAL_ENGINEERING_QUESTION

    q = question.strip()

    # 1. Hole analysis
    if HOLE_KEYWORDS.search(q):
        return QuestionType.HOLE_ANALYSIS

    # 2. Geometric relationships
    if RELATIONSHIP_KEYWORDS.search(q):
        return QuestionType.RELATIONSHIP_ANALYSIS

    # 3. Dimensions & tolerances
    if DIMENSION_KEYWORDS.search(q):
        return QuestionType.DIMENSION_SUMMARY

    # 4. Annotations, OCR, and Symbols
    if ANNOTATION_KEYWORDS.search(q):
        return QuestionType.ANNOTATION_SUMMARY

    # 5. Low-level geometry
    if GEOMETRY_KEYWORDS.search(q):
        return QuestionType.GEOMETRY_SUMMARY

    # 6. Fallback
    return QuestionType.GENERAL_ENGINEERING_QUESTION
