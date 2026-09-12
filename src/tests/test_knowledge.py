"""
Comprehensive tests for Slice 7: Engineering Knowledge & Rules.
Tests knowledge models, built-in rules, knowledge base, retriever, applicability engine,
missing information reporting, API integration, and reasoning context integration.
"""

import io
import json
import pytest
import cv2
import numpy as np
from fastapi.testclient import TestClient
from api.main import app
from core.models import (
    ImageMetadata,
    AnalyzeResponse
)
from semantics.models import (
    MechanicalFeature,
    MechanicalFeatureType,
    MechanicalSemanticsResult
)
from knowledge.models import (
    KnowledgeSourceType,
    EngineeringKnowledgeItem,
    EngineeringRule,
    EngineeringRuleMatch,
    EngineeringKnowledgeResult
)
from knowledge.rules import BUILT_IN_RULES, BUILT_IN_KNOWLEDGE_ITEMS
from knowledge.knowledge_base import BuiltInEngineeringKnowledgeBase
from knowledge.applicability import EngineeringApplicabilityEngine
from knowledge.retriever import BuiltInKnowledgeRetriever
from reasoning.context import (
    build_drawing_context,
    select_context_for_question
)
from reasoning.models import QuestionType


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Knowledge Item Validation & Sourcing Tests
# ---------------------------------------------------------------------------

def test_knowledge_item_validation():
    """Validates EngineeringKnowledgeItem fields and confidence constraints."""
    item = EngineeringKnowledgeItem(
        id="test_item_1",
        title="Test Principle",
        domain="strength",
        statement="Test statement about stress.",
        applicability=["shaft"],
        required_inputs=["torque"],
        related_features=["shaft"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference="internal-engineering-rule",
        confidence=0.95,
        limitations=["Applicability test only."],
        tags=["test", "torsion"]
    )
    assert item.id == "test_item_1"
    assert item.source_type == KnowledgeSourceType.BUILT_IN_RULE
    assert item.confidence == 0.95

    # Test confidence validation bounds [0.0, 1.0]
    with pytest.raises(Exception):
        EngineeringKnowledgeItem(
            id="bad_item",
            title="Bad",
            domain="strength",
            statement="Statement",
            confidence=1.5
        )


def test_provenance_preserved_built_in_rules():
    """Every built-in rule and item must explicitly identify provenance as built_in_rule."""
    for rule in BUILT_IN_RULES:
        assert rule.source_type == KnowledgeSourceType.BUILT_IN_RULE
        assert rule.source_reference == "internal-engineering-rule"
        assert len(rule.rationale) > 10
        assert len(rule.limitations) >= 1

    for item in BUILT_IN_KNOWLEDGE_ITEMS:
        assert item.source_type == KnowledgeSourceType.BUILT_IN_RULE
        assert item.source_reference == "internal-engineering-rule"
        assert len(item.statement) > 10
        assert len(item.limitations) >= 1


# ---------------------------------------------------------------------------
# 2. Knowledge Base & Retriever Tests
# ---------------------------------------------------------------------------

def test_built_in_knowledge_retrieval():
    """Tests retrieval by item ID and all items from BuiltInEngineeringKnowledgeBase."""
    kb = BuiltInEngineeringKnowledgeBase()
    items = kb.get_all_items()
    assert len(items) >= 10

    item = kb.get_item("know_shaft_torsion")
    assert item is not None
    assert "Torsional Shear Stress" in item.title
    assert "shaft" in item.related_features


def test_retrieval_by_domain():
    """Tests filtering knowledge items by domain."""
    kb = BuiltInEngineeringKnowledgeBase()
    strength_items = kb.get_items_by_domain("strength")
    assert len(strength_items) >= 3
    for it in strength_items:
        assert it.domain == "strength"

    fatigue_items = kb.get_items_by_domain("fatigue")
    assert len(fatigue_items) >= 1
    assert any("fatigue" in it.tags for it in fatigue_items)


def test_retrieval_by_feature_type():
    """Tests filtering knowledge items by related mechanical feature type."""
    kb = BuiltInEngineeringKnowledgeBase()
    shaft_items = kb.get_items_for_feature("shaft")
    assert len(shaft_items) >= 3

    hole_items = kb.get_items_for_feature("hole")
    assert len(hole_items) >= 1
    assert any("hole" in it.id for it in hole_items)


def test_built_in_retriever_query_and_filter():
    """Tests BuiltInKnowledgeRetriever deterministic keyword and feature filtering."""
    retriever = BuiltInKnowledgeRetriever()
    results = retriever.retrieve(query="shear stress", feature_types=["shaft"], top_k=3)
    assert len(results) > 0
    top = results[0]
    assert "shaft" in top.related_features
    assert "torsion" in top.tags or "shear" in top.statement.lower()


# ---------------------------------------------------------------------------
# 3. Rule A: Shaft Torsion Tests
# ---------------------------------------------------------------------------

def test_shaft_with_torque_torsion_rule_applicable():
    """Shaft present + torque supplied -> torsion rule is applicable and reports diameter/material missing."""
    engine = EngineeringApplicabilityEngine()
    shaft_feat = MechanicalFeature(
        id="mech_shaft_0",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Detected shaft segment",
        attributes={"length": 200.0}  # diameter missing from attributes
    )
    semantics = MechanicalSemanticsResult(features=[shaft_feat])
    inputs = {"torque": 31.8}

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs=inputs)

    match = next((r for r in result.applicable_rules if r.rule_id == "shaft_torsion_applicability"), None)
    assert match is not None
    assert match.applicability is True
    assert "input:torque" in match.evidence_ids
    assert "torque" not in match.missing_inputs
    assert "shaft_diameter" in match.missing_inputs
    assert "material_allowable_stress" in match.missing_inputs
    assert match.confidence == 0.95

    # Check surfaced missing information items
    missing_fields = {m.field for m in result.missing_information if m.rule_id == "shaft_torsion_applicability"}
    assert "shaft_diameter" in missing_fields
    assert "material_allowable_stress" in missing_fields


def test_shaft_without_torque_surfaces_missing_torque():
    """Shaft present without torque -> torsion rule identifies torque as missing."""
    engine = EngineeringApplicabilityEngine()
    shaft_feat = MechanicalFeature(
        id="mech_shaft_1",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Detected shaft segment",
        attributes={"length": 150.0, "diameter": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft_feat])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "shaft_torsion_applicability"), None)
    assert match is not None
    assert "torque" in match.missing_inputs
    assert match.confidence == 0.80  # Potential applicability confidence
    assert any(m.field == "torque" for m in result.missing_information)


# ---------------------------------------------------------------------------
# 4. Rule B & C: Shaft Bending & Combined Loading Tests
# ---------------------------------------------------------------------------

def test_shaft_with_bending_load_applicable():
    """Shaft present with transverse load -> bending analysis is applicable."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_b",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft segment",
        attributes={"length": 180.0, "diameter": 30.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    inputs = {"transverse_load": 500.0}

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs=inputs)
    match = next((r for r in result.applicable_rules if r.rule_id == "shaft_bending_applicability"), None)
    assert match is not None
    assert match.applicability is True
    assert "support_conditions" in match.missing_inputs


def test_shaft_without_bending_load_not_assumed():
    """Conservative behavior: Shaft present but NO bending load supplied -> bending must NOT be assumed."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_nobend",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft segment",
        attributes={"length": 180.0, "diameter": 30.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "shaft_bending_applicability"), None)
    assert match is None  # Conservative: bending is not assumed without load


def test_combined_shaft_loading():
    """Shaft with both torque and bending -> combined stress rule applies."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_comb",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft segment",
        attributes={"length": 200.0, "diameter": 35.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    inputs = {"torque": 120.0, "bending_moment": 250.0}

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs=inputs)
    match = next((r for r in result.applicable_rules if r.rule_id == "shaft_combined_stress_applicability"), None)
    assert match is not None
    assert match.applicability is True
    assert "yield_strength" in match.missing_inputs


# ---------------------------------------------------------------------------
# 5. Rule D & E: Fatigue & Buckling Tests
# ---------------------------------------------------------------------------

def test_cyclic_loading_fatigue_applicable():
    """Cyclic loading explicitly indicated -> fatigue analysis is applicable."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_fatigue",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft segment",
        attributes={"diameter": 20.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    inputs = {"cyclic_loading": True}

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs=inputs)
    match = next((r for r in result.applicable_rules if r.rule_id == "fatigue_analysis_applicability"), None)
    assert match is not None
    assert match.applicability is True
    assert "endurance_limit" in match.missing_inputs


def test_no_cyclic_loading_fatigue_not_assumed():
    """Conservative behavior: No cyclic loading indicated -> fatigue is NOT automatically recommended."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_static",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft segment",
        attributes={"diameter": 20.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "fatigue_analysis_applicability"), None)
    assert match is None


def test_buckling_rule_positive_and_negative():
    """Buckling applies only to slender members under compressive loading."""
    engine = EngineeringApplicabilityEngine()
    # Slender shaft (L=300, D=20 -> aspect ratio 15 >= 10)
    slender_shaft = MechanicalFeature(
        id="mech_slender",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Slender shaft",
        attributes={"length": 300.0, "diameter": 20.0}
    )
    semantics = MechanicalSemanticsResult(features=[slender_shaft])

    # Negative case: Slender shaft without compressive load -> no buckling
    res_no_comp = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    assert not any(r.rule_id == "buckling_analysis_applicability" for r in res_no_comp.applicable_rules)

    # Positive case: Slender shaft with compressive load -> buckling applicable
    res_comp = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={"compressive_load": 1500.0})
    match = next((r for r in res_comp.applicable_rules if r.rule_id == "buckling_analysis_applicability"), None)
    assert match is not None
    assert match.applicability is True
    assert "elastic_modulus" in match.missing_inputs


# ---------------------------------------------------------------------------
# 6. Rule G, H, I: Hole, Pattern, and Plate Requirements
# ---------------------------------------------------------------------------

def test_hole_relevant_engineering_knowledge():
    """Hole semantic triggers hole requirements and does NOT assume manufacturing intent."""
    engine = EngineeringApplicabilityEngine()
    hole = MechanicalFeature(
        id="mech_hole_1",
        feature_type=MechanicalFeatureType.HOLE,
        confidence=0.92,
        evidence=[],
        reasoning_basis="Strong hole",
        attributes={"diameter": 12.0}
    )
    semantics = MechanicalSemanticsResult(features=[hole])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "hole_engineering_requirements"), None)
    assert match is not None
    assert match.applicability is True
    assert "positional_tolerance" in match.missing_inputs
    assert any("Manufacturing method" in lim for lim in match.limitations)


def test_hole_pattern_knowledge():
    """Hole pattern triggers pattern spacing and positional tolerance rules."""
    engine = EngineeringApplicabilityEngine()
    pattern = MechanicalFeature(
        id="mech_pat_1",
        feature_type=MechanicalFeatureType.HOLE_PATTERN,
        confidence=0.88,
        evidence=[],
        reasoning_basis="Linear hole pattern",
        attributes={"count": 4, "spacing": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[pattern])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "hole_pattern_engineering_requirements"), None)
    assert match is not None
    assert "composite_positional_tolerance" in match.missing_inputs


def test_rectangular_plate_thickness_and_material_surfaced():
    """Rectangular plate triggers plate analysis rule; thickness, material, loading, boundary conditions are surfaced."""
    engine = EngineeringApplicabilityEngine()
    plate = MechanicalFeature(
        id="mech_plate_1",
        feature_type=MechanicalFeatureType.RECTANGULAR_PLATE,
        confidence=0.80,
        evidence=[],
        reasoning_basis="Plate candidate",
        attributes={"width": 300.0, "height": 150.0}
    )
    semantics = MechanicalSemanticsResult(features=[plate])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    match = next((r for r in result.applicable_rules if r.rule_id == "rectangular_plate_analysis_applicability"), None)
    assert match is not None
    assert match.applicability is True

    missing_fields = {m.field for m in result.missing_information if m.rule_id == "rectangular_plate_analysis_applicability"}
    assert "plate_thickness" in missing_fields
    assert "material" in missing_fields
    assert "boundary_conditions" in missing_fields


# ---------------------------------------------------------------------------
# 7. Rule J: Material Requirement & Absence of Fabricated Values
# ---------------------------------------------------------------------------

def test_missing_material_surfaced_no_fabrication():
    """Material specification rule triggers when features exist; values are NEVER fabricated."""
    engine = EngineeringApplicabilityEngine()
    shaft = MechanicalFeature(
        id="mech_shaft_mat",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])

    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})
    mat_match = next((r for r in result.applicable_rules if r.rule_id == "material_specification_requirement"), None)
    assert mat_match is not None
    assert "yield_strength" in mat_match.missing_inputs
    assert "ultimate_tensile_strength" in mat_match.missing_inputs
    assert "elastic_modulus" in mat_match.missing_inputs
    assert any("never be fabricated" in mat_match.rationale for _ in [1])


# ---------------------------------------------------------------------------
# 8. API Integration Tests
# ---------------------------------------------------------------------------

def test_api_analyze_contains_engineering_knowledge():
    """POST /analyze returns engineering_knowledge with rules, items, and missing_information."""
    img = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.circle(img, (150, 100), 20, (0, 0, 0), 2)
    success, encoded = cv2.imencode(".png", img)
    assert success

    response = client.post(
        "/analyze",
        files={"file": ("drawing.png", io.BytesIO(encoded.tobytes()), "image/png")}
    )
    assert response.status_code == 200
    data = response.json()

    # Verify Slice 7 additions
    assert "engineering_knowledge" in data
    ek = data["engineering_knowledge"]
    assert "items" in ek
    assert "applicable_rules" in ek
    assert "missing_information" in ek
    assert "warnings" in ek

    # Verify backward compatibility
    assert "image" in data
    assert "lines" in data
    assert "circles" in data
    assert "mechanical_semantics" in data


def test_api_analyze_with_engineering_inputs():
    """POST /analyze with engineering_inputs JSON string passes inputs to knowledge engine."""
    img = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.circle(img, (150, 100), 20, (0, 0, 0), 2)
    success, encoded = cv2.imencode(".png", img)
    assert success

    eng_inputs_json = json.dumps({"torque": 45.0, "cyclic_loading": True})
    response = client.post(
        "/analyze",
        files={"file": ("drawing.png", io.BytesIO(encoded.tobytes()), "image/png")},
        data={"engineering_inputs": eng_inputs_json}
    )
    assert response.status_code == 200
    data = response.json()
    ek = data["engineering_knowledge"]
    # With cyclic_loading=True in inputs, fatigue rule should trigger
    fatigue_rule = next((r for r in ek["applicable_rules"] if r["rule_id"] == "fatigue_analysis_applicability"), None)
    assert fatigue_rule is not None
    assert fatigue_rule["applicability"] is True


# ---------------------------------------------------------------------------
# 9. Reasoning Context Integration Tests
# ---------------------------------------------------------------------------

def test_reasoning_drawing_context_consumes_engineering_knowledge():
    """Verifies that DrawingContext and select_context_for_question receive engineering knowledge."""
    rule_match = EngineeringRuleMatch(
        rule_id="hole_engineering_requirements",
        applicability=True,
        rationale="Hole sizing and tolerancing",
        required_inputs=["hole_diameter", "positional_tolerance"],
        missing_inputs=["positional_tolerance"],
        evidence_ids=["hole_0"]
    )
    ek_res = EngineeringKnowledgeResult(
        items=[
            EngineeringKnowledgeItem(
                id="know_hole_tolerancing",
                title="Hole Tolerancing",
                domain="tolerancing",
                statement="Hole specification statement",
                related_features=["hole"]
            )
        ],
        applicable_rules=[rule_match],
        missing_information=[],
        warnings=[]
    )

    resp = AnalyzeResponse(
        image=ImageMetadata(width=300, height=200),
        lines=[],
        circles=[],
        contours=[],
        engineering_knowledge=ek_res
    )

    context = build_drawing_context(resp)
    assert context.engineering_knowledge is not None
    assert len(context.engineering_knowledge["applicable_rules"]) == 1

    # Hole analysis question receives filtered engineering knowledge
    hole_ctx = select_context_for_question(context, QuestionType.HOLE_ANALYSIS)
    assert "engineering_knowledge" in hole_ctx
    assert len(hole_ctx["engineering_knowledge"]["applicable_rules"]) == 1
    assert hole_ctx["engineering_knowledge"]["applicable_rules"][0]["rule_id"] == "hole_engineering_requirements"


# ---------------------------------------------------------------------------
# 10. Conservative Semantics Edge Case
# ---------------------------------------------------------------------------

def test_conservative_behavior_when_no_semantics():
    """When no mechanical features exist, engine does not overclaim domain rules."""
    engine = EngineeringApplicabilityEngine()
    semantics = MechanicalSemanticsResult(features=[])
    result = engine.evaluate(mechanical_semantics=semantics, engineering_inputs={})

    # No shaft, plate, or hole rules should be marked applicable
    assert not any("shaft" in r.rule_id for r in result.applicable_rules)
    assert not any("plate" in r.rule_id for r in result.applicable_rules)
    assert not any("hole" in r.rule_id for r in result.applicable_rules)
    assert len(result.warnings) >= 1
