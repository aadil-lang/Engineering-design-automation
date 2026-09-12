import json
import re
from typing import Set, List, Dict, Any, Tuple
from reasoning.models import (
    ReasoningResponse,
    FactItem,
    InferenceItem,
    UncertaintyItem,
    ConfidenceScore
)
from reasoning.context import DrawingContext


def extract_valid_entity_ids(context: DrawingContext) -> Set[str]:
    """Collect all valid entity and feature IDs from the DrawingContext."""
    valid_ids: Set[str] = set()

    for lf in context.line_features:
        if "id" in lf:
            valid_ids.add(str(lf["id"]))

    for cf in context.circle_features:
        if "id" in cf:
            valid_ids.add(str(cf["id"]))

    for d in context.dimensions:
        if "id" in d:
            valid_ids.add(str(d["id"]))

    for s in context.symbols:
        if "id" in s:
            valid_ids.add(str(s["id"]))

    for o in context.ocr_results:
        if "id" in o:
            valid_ids.add(str(o["id"]))

    for r in context.relationships:
        if "source_id" in r:
            valid_ids.add(str(r["source_id"]))
        if "target_id" in r:
            valid_ids.add(str(r["target_id"]))

    for a in context.associations:
        if "dimension_id" in a:
            valid_ids.add(str(a["dimension_id"]))
        if "feature_id" in a:
            valid_ids.add(str(a["feature_id"]))

    return valid_ids


def parse_and_clean_json(raw_text: str) -> Dict[str, Any]:
    """
    Attempt safe extraction and normalization of JSON from raw LLM output,
    handling markdown code blocks and trailing whitespace.
    """
    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed LLM JSON output: {str(e)}") from e


def validate_reasoning_response(
    raw_response: str,
    context: DrawingContext
) -> ReasoningResponse:
    """
    Deterministically validate the LLM's reasoning output against the grounded DrawingContext.

    Checks:
    1. Schema conformance (Pydantic model validation).
    2. Existence of all cited evidence IDs against the real context.
    3. Flags and demotes any facts or inferences citing nonexistent IDs to uncertainties.
    4. Enforces confidence range [0.0, 1.0] and applies penalty for unsupported claims.
    """
    parsed_data = parse_and_clean_json(raw_response)

    # Normalize confidence field if returned as raw float or nested dict
    conf_data = parsed_data.get("confidence")
    if isinstance(conf_data, (int, float)):
        conf_score = max(0.0, min(1.0, float(conf_data)))
        parsed_data["confidence"] = {"score": conf_score, "source": "model_heuristic"}
    elif isinstance(conf_data, dict):
        score = conf_data.get("score", 0.8)
        conf_score = max(0.0, min(1.0, float(score)))
        parsed_data["confidence"] = {
            "score": conf_score,
            "source": conf_data.get("source", "model_heuristic")
        }
    else:
        parsed_data["confidence"] = {"score": 0.5, "source": "fallback"}

    # Validate against ReasoningResponse schema
    response = ReasoningResponse.model_validate(parsed_data)

    valid_ids = extract_valid_entity_ids(context)
    unsupported_ids: Set[str] = set()

    validated_facts: List[FactItem] = []
    validated_inferences: List[InferenceItem] = []
    validated_uncertainties: List[UncertaintyItem] = list(response.uncertainties)

    # 1. Validate Facts
    for fact in response.facts:
        missing_ids = [eid for eid in fact.evidence if eid not in valid_ids]
        if missing_ids:
            unsupported_ids.update(missing_ids)
            # Demote unsupported fact to uncertainty
            validated_uncertainties.append(
                UncertaintyItem(
                    statement=f"[UNVERIFIED ID {', '.join(missing_ids)}] {fact.statement}",
                    evidence=[eid for eid in fact.evidence if eid in valid_ids]
                )
            )
        else:
            validated_facts.append(fact)

    # 2. Validate Inferences
    for inf in response.inferences:
        missing_ids = [eid for eid in inf.evidence if eid not in valid_ids]
        if missing_ids:
            unsupported_ids.update(missing_ids)
            validated_uncertainties.append(
                UncertaintyItem(
                    statement=f"[UNVERIFIED ID {', '.join(missing_ids)}] {inf.statement}",
                    evidence=[eid for eid in inf.evidence if eid in valid_ids]
                )
            )
        else:
            validated_inferences.append(inf)

    # 3. Filter Overall Evidence List
    validated_evidence = [eid for eid in response.evidence if eid in valid_ids]

    # 4. Confidence Penalty for Hallucinated / Unsupported IDs
    final_score = response.confidence.score
    if unsupported_ids:
        final_score = round(final_score * 0.5, 2)
        source = "penalized_unsupported_evidence"
    else:
        source = "validated_grounded_evidence"

    metadata: Dict[str, Any] = response.metadata or {}
    metadata["validation_status"] = "passed" if not unsupported_ids else "unsupported_ids_flagged"
    if unsupported_ids:
        metadata["unsupported_ids"] = list(unsupported_ids)

    return ReasoningResponse(
        answer=response.answer,
        facts=validated_facts,
        inferences=validated_inferences,
        uncertainties=validated_uncertainties,
        evidence=validated_evidence,
        confidence=ConfidenceScore(score=final_score, source=source),
        metadata=metadata
    )
