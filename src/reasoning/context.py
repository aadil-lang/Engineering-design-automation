import json
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
from core.models import AnalyzeResponse
from reasoning.models import QuestionType


class DrawingContext(BaseModel):
    """
    Canonical structured representation of drawing evidence suitable for
    deterministic reasoning and prompting.
    """
    image: Dict[str, Any] = Field(default_factory=dict)
    line_features: List[Dict[str, Any]] = Field(default_factory=list)
    circle_features: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    symbols: List[Dict[str, Any]] = Field(default_factory=list)
    associations: List[Dict[str, Any]] = Field(default_factory=list)
    ocr_results: List[Dict[str, Any]] = Field(default_factory=list)
    mechanical_features: List[Dict[str, Any]] = Field(default_factory=list)
    engineering_knowledge: Optional[Dict[str, Any]] = None
    summary: Dict[str, Any] = Field(default_factory=dict)


def build_drawing_context(analysis: AnalyzeResponse) -> DrawingContext:
    """Transform an AnalyzeResponse into a canonical DrawingContext."""
    image_meta = {
        "width": analysis.image.width,
        "height": analysis.image.height
    }

    line_feats: List[Dict[str, Any]] = []
    circle_feats: List[Dict[str, Any]] = []
    rels: List[Dict[str, Any]] = []
    bbox = None
    summary: Dict[str, Any] = {}

    if analysis.engineering_features:
        ef = analysis.engineering_features
        if ef.line_features:
            line_feats = [
                {
                    "id": lf.id,
                    "length": round(lf.length, 2),
                    "angle_degrees": round(lf.angle_degrees, 1),
                    "orientation": lf.orientation.value if hasattr(lf.orientation, "value") else str(lf.orientation),
                    "start": (round(lf.x1, 1), round(lf.y1, 1)),
                    "end": (round(lf.x2, 1), round(lf.y2, 1))
                }
                for lf in ef.line_features
            ]
        if ef.circle_features:
            circle_feats = [
                {
                    "id": cf.id,
                    "center": (round(cf.center_x, 1), round(cf.center_y, 1)),
                    "radius": round(cf.radius, 2),
                    "diameter": round(cf.diameter, 2),
                    "likely_hole": cf.likely_hole,
                    "confidence": cf.confidence
                }
                for cf in ef.circle_features
            ]
        if ef.relationships:
            rels = [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.relationship_type.value if hasattr(r.relationship_type, "value") else str(r.relationship_type),
                    "metadata": r.metadata
                }
                for r in ef.relationships
            ]
        if ef.bounding_information:
            bbox = ef.bounding_information.bounding_box
        if ef.summary:
            summary.update(ef.summary)

    dims: List[Dict[str, Any]] = []
    syms: List[Dict[str, Any]] = []
    assocs: List[Dict[str, Any]] = []
    ocr_items: List[Dict[str, Any]] = []

    if analysis.annotations:
        ann = analysis.annotations
        if ann.dimensions:
            dims = [
                {
                    "id": d.id,
                    "raw_text": d.raw_text,
                    "value": d.value,
                    "unit": d.unit,
                    "type": d.dimension_type.value if hasattr(d.dimension_type, "value") else str(d.dimension_type),
                    "tolerance": d.tolerance.model_dump() if d.tolerance else None,
                    "confidence": d.confidence,
                    "bounding_box": d.bounding_box,
                    "source_text_id": d.source_text_id
                }
                for d in ann.dimensions
            ]
        if ann.symbols:
            syms = [
                {
                    "id": s.id,
                    "symbol_type": s.symbol_type.value if hasattr(s.symbol_type, "value") else str(s.symbol_type),
                    "raw_symbol": s.raw_symbol,
                    "confidence": s.confidence,
                    "source_text_id": s.source_text_id
                }
                for s in ann.symbols
            ]
        if ann.associations:
            assocs = [
                {
                    "dimension_id": a.dimension_id,
                    "feature_id": a.feature_id,
                    "type": a.association_type.value if hasattr(a.association_type, "value") else str(a.association_type),
                    "distance": a.distance,
                    "confidence": a.confidence,
                    "metadata": a.metadata
                }
                for a in ann.associations
            ]
        if ann.ocr_results:
            ocr_items = [
                {
                    "id": o.id,
                    "text": o.text,
                    "confidence": o.confidence,
                    "bounding_box": o.bounding_box
                }
                for o in ann.ocr_results
            ]
        if ann.summary:
            summary.update(ann.summary)

    # Slice 6: Mechanical Semantics Evidence
    mech_feats: List[Dict[str, Any]] = []
    if getattr(analysis, "mechanical_semantics", None):
        ms = analysis.mechanical_semantics
        if ms and ms.features:
            mech_feats = [f.model_dump() for f in ms.features]
        if ms and ms.summary:
            summary.update({"mechanical_summary": ms.summary})

    # Slice 7: Engineering Knowledge Evidence
    eng_knowledge: Optional[Dict[str, Any]] = None
    if getattr(analysis, "engineering_knowledge", None):
        ek = analysis.engineering_knowledge
        if ek:
            eng_knowledge = ek.model_dump()
            if ek.applicable_rules:
                summary.update({"applicable_engineering_rules_count": len(ek.applicable_rules)})

    return DrawingContext(
        image=image_meta,
        line_features=line_feats,
        circle_features=circle_feats,
        relationships=rels,
        bounding_box=bbox,
        dimensions=dims,
        symbols=syms,
        associations=assocs,
        ocr_results=ocr_items,
        mechanical_features=mech_feats,
        engineering_knowledge=eng_knowledge,
        summary=summary
    )


def select_context_for_question(
    context: DrawingContext,
    question_type: QuestionType
) -> Dict[str, Any]:
    """
    Cost / Token Efficiency Strategy:
    Filter structured drawing context to include only the elements directly
    relevant to the routed question category, avoiding sending redundant entities.
    """
    base_info = {
        "image": context.image,
        "bounding_box": context.bounding_box
    }

    if question_type == QuestionType.HOLE_ANALYSIS:
        # Prioritize circles, hole candidates, diameter/radius dimensions, circle associations, and hole semantics
        diameter_radius_dims = [
            d for d in context.dimensions if d.get("type") in ("diameter", "radius")
        ]
        circle_ids = {c["id"] for c in context.circle_features}
        circle_assocs = [
            a for a in context.associations if a.get("feature_id") in circle_ids
        ]
        result = {
            **base_info,
            "circle_features": context.circle_features,
            "dimensions": diameter_radius_dims or context.dimensions,
            "associations": circle_assocs,
            "summary": {
                "total_circles": len(context.circle_features),
                "hole_candidates": sum(1 for c in context.circle_features if c.get("likely_hole"))
            }
        }
        if context.mechanical_features:
            result["mechanical_features"] = [
                mf for mf in context.mechanical_features
                if mf.get("feature_type") in ("hole", "hole_pattern", "circular_feature")
            ]
        if context.engineering_knowledge:
            ek = context.engineering_knowledge
            filtered_rules = [
                r for r in ek.get("applicable_rules", [])
                if any(k in r.get("rule_id", "") for k in ("hole", "pattern", "material"))
            ]
            filtered_items = [
                it for it in ek.get("items", [])
                if any(f in it.get("related_features", []) for f in ("hole", "hole_pattern"))
            ]
            result["engineering_knowledge"] = {
                "applicable_rules": filtered_rules,
                "items": filtered_items,
                "missing_information": [
                    m for m in ek.get("missing_information", [])
                    if not m.get("rule_id") or any(k in m.get("rule_id", "") for k in ("hole", "pattern", "material"))
                ]
            }
        return result

    if question_type == QuestionType.DIMENSION_SUMMARY:
        # Prioritize dimensions, tolerances, units, symbols, and associations
        result = {
            **base_info,
            "dimensions": context.dimensions,
            "symbols": context.symbols,
            "associations": context.associations,
            "summary": {
                "total_dimensions": len(context.dimensions),
                "total_symbols": len(context.symbols)
            }
        }
        return result

    if question_type == QuestionType.RELATIONSHIP_ANALYSIS:
        # Prioritize lines, orientations, geometric relationships, and relational mechanical features
        result = {
            **base_info,
            "line_features": context.line_features,
            "relationships": context.relationships,
            "summary": {
                "total_lines": len(context.line_features),
                "total_relationships": len(context.relationships)
            }
        }
        if context.mechanical_features:
            result["mechanical_features"] = [
                mf for mf in context.mechanical_features
                if mf.get("feature_type") in ("parallel_feature", "perpendicular_feature", "symmetric_feature")
            ]
        if context.engineering_knowledge:
            result["engineering_knowledge"] = context.engineering_knowledge
        return result

    if question_type == QuestionType.GEOMETRY_SUMMARY:
        # Prioritize lines, circles, bounding box, and macroscopic mechanical features
        result = {
            **base_info,
            "line_features": context.line_features,
            "circle_features": context.circle_features,
            "relationships": context.relationships,
            "summary": {
                "total_lines": len(context.line_features),
                "total_circles": len(context.circle_features)
            }
        }
        if context.mechanical_features:
            result["mechanical_features"] = [
                mf for mf in context.mechanical_features
                if mf.get("feature_type") in ("rectangular_plate", "slot", "shaft", "stepped_feature", "symmetric_feature", "circular_feature", "hole")
            ]
        if context.engineering_knowledge:
            result["engineering_knowledge"] = context.engineering_knowledge
        return result

    if question_type == QuestionType.ANNOTATION_SUMMARY:
        # Prioritize OCR results, symbols, and dimensions
        return {
            **base_info,
            "ocr_results": context.ocr_results,
            "symbols": context.symbols,
            "dimensions": context.dimensions,
            "summary": {
                "total_ocr": len(context.ocr_results),
                "total_symbols": len(context.symbols)
            }
        }

    # General Engineering Question: include full context in compact form
    result = {
        **base_info,
        "line_features": context.line_features,
        "circle_features": context.circle_features,
        "relationships": context.relationships,
        "dimensions": context.dimensions,
        "symbols": context.symbols,
        "associations": context.associations,
        "summary": context.summary
    }
    if context.mechanical_features:
        result["mechanical_features"] = context.mechanical_features
    if context.engineering_knowledge:
        result["engineering_knowledge"] = context.engineering_knowledge
    return result


def drawing_context_to_json(
    context: DrawingContext,
    question_type: Optional[QuestionType] = None
) -> str:
    """
    Deterministic serializer returning a stable, sorted JSON string
    suitable for prompt inclusion and regression testing.
    """
    if question_type is not None:
        data = select_context_for_question(context, question_type)
    else:
        data = context.model_dump()

    return json.dumps(data, indent=2, sort_keys=True)
