"""Grounded Engineering Reasoning Layer (Slice 4)."""

from reasoning.models import (
    QuestionType,
    EvidenceSourceType,
    EvidenceReference,
    FactItem,
    InferenceItem,
    UncertaintyItem,
    ConfidenceScore,
    ReasoningRequest,
    ReasoningResponse,
    AnalyzeAndReasonResponse
)
from reasoning.context import (
    DrawingContext,
    build_drawing_context,
    select_context_for_question,
    drawing_context_to_json
)
from reasoning.router import route_question
from reasoning.prompts import GROUNDED_SYSTEM_PROMPT, build_reasoning_prompt
from reasoning.provider import (
    LLMProvider,
    MockLLMProvider,
    GeminiProvider,
    get_llm_provider
)
from reasoning.validation import validate_reasoning_response
from reasoning.reasoner import reason_about_drawing

__all__ = [
    "QuestionType",
    "EvidenceSourceType",
    "EvidenceReference",
    "FactItem",
    "InferenceItem",
    "UncertaintyItem",
    "ConfidenceScore",
    "ReasoningRequest",
    "ReasoningResponse",
    "AnalyzeAndReasonResponse",
    "DrawingContext",
    "build_drawing_context",
    "select_context_for_question",
    "drawing_context_to_json",
    "route_question",
    "GROUNDED_SYSTEM_PROMPT",
    "build_reasoning_prompt",
    "LLMProvider",
    "MockLLMProvider",
    "GeminiProvider",
    "get_llm_provider",
    "validate_reasoning_response",
    "reason_about_drawing"
]
