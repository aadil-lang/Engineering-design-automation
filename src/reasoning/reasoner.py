from typing import Optional, Dict, Any
from core.models import AnalyzeResponse
from reasoning.models import (
    ReasoningRequest,
    ReasoningResponse,
    QuestionType
)
from reasoning.context import (
    DrawingContext,
    build_drawing_context,
    select_context_for_question
)
from reasoning.router import route_question
from reasoning.prompts import build_reasoning_prompt
from reasoning.provider import LLMProvider, get_llm_provider
from reasoning.validation import validate_reasoning_response


def reason_about_drawing(
    request: ReasoningRequest,
    provider: Optional[LLMProvider] = None
) -> ReasoningResponse:
    """
    Main service function orchestrating grounded engineering reasoning:
    1. Canonical context extraction
    2. Deterministic question routing
    3. Token-efficient context selection & prompt construction
    4. LLM generation
    5. Deterministic evidence validation & hallucination prevention
    6. Observability enrichment
    """
    if provider is None:
        provider = get_llm_provider()

    # 1. Build canonical drawing context
    context = build_drawing_context(request.drawing)

    # 2. Deterministic question routing
    q_type = route_question(request.question)

    # 3. Build prompts using selected context
    system_prompt, user_prompt = build_reasoning_prompt(
        question=request.question,
        context=context,
        question_type=q_type
    )

    # 4. Generate completion
    raw_response = provider.generate(system_prompt, user_prompt)

    # 5. Validate evidence and response schema
    validated_response = validate_reasoning_response(raw_response, context)

    # 6. Observability enrichment
    selected_data = select_context_for_question(context, q_type)
    metadata: Dict[str, Any] = validated_response.metadata or {}
    metadata.update({
        "question_type": q_type.value,
        "provider": provider.__class__.__name__,
        "model": getattr(provider, "model", "deterministic_mock"),
        "context_counts": {
            "lines": len(context.line_features),
            "circles": len(context.circle_features),
            "dimensions": len(context.dimensions),
            "symbols": len(context.symbols),
            "relationships": len(context.relationships),
            "associations": len(context.associations)
        },
        "estimated_prompt_tokens": len(system_prompt + user_prompt) // 4
    })
    validated_response.metadata = metadata

    return validated_response
