"""
Comprehensive tests for Slice 8: Analysis Planner & Execution Planning.
Tests analysis models, planner logic, calculation vs assessment input distinction,
user control overrides, solver registry, deterministic reports, API integration, and reasoning context.
"""

import io
import json
import pytest
import cv2
import numpy as np
from fastapi.testclient import TestClient
from api.main import app
from core.models import ImageMetadata, AnalyzeResponse
from semantics.models import (
    MechanicalFeature,
    MechanicalFeatureType,
    MechanicalSemanticsResult
)
from knowledge.models import (
    EngineeringRuleMatch,
    EngineeringKnowledgeResult
)
from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlanningRequest,
    AnalysisPlanItem,
    AnalysisPlan
)
from analysis.applicability import AnalysisSolverRegistry
from analysis.inputs import resolve_analysis_inputs
from analysis.planner import AnalysisPlanner
from analysis.report import generate_analysis_plan_report
from reasoning.context import (
    build_drawing_context,
    select_context_for_question
)
from reasoning.models import QuestionType


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Model & Enum Validation Tests
# ---------------------------------------------------------------------------

def test_analysis_type_and_status_enums():
    """Validates AnalysisType and AnalysisStatus enum values."""
    assert AnalysisType.TORSION == "torsion"
    assert AnalysisType.BENDING == "bending"
    assert AnalysisType.COMBINED_STRESS == "combined_stress"
    assert AnalysisType.DEFLECTION == "deflection"
    assert AnalysisType.FATIGUE == "fatigue"
    assert AnalysisType.BUCKLING == "buckling"
    assert AnalysisType.BEARING_STRESS == "bearing_stress"
    assert AnalysisType.HOLE_PATTERN_LOAD == "hole_pattern_load"
    assert AnalysisType.VON_MISES == "von_mises"
    assert AnalysisType.THERMAL_EXPANSION == "thermal_expansion"

    assert AnalysisStatus.RECOMMENDED == "recommended"
    assert AnalysisStatus.READY == "ready"
    assert AnalysisStatus.MISSING_INPUTS == "missing_inputs"
    assert AnalysisStatus.NOT_APPLICABLE == "not_applicable"
    assert AnalysisStatus.USER_DISABLED == "user_disabled"
    assert AnalysisStatus.BLOCKED == "blocked"


def test_planning_request_defaults_and_validation():
    """Validates AnalysisPlanningRequest default configuration."""
    req = AnalysisPlanningRequest()
    assert req.recommend_analyses is True
    assert req.requested_analyses == []
    assert req.disabled_analyses == []
    assert req.engineering_inputs == {}
    assert req.human_requested is False


# ---------------------------------------------------------------------------
# 2. Solver Registry Tests
# ---------------------------------------------------------------------------

def test_solver_registry_mapping_and_availability():
    """Tests solver registry ID mapping and explicitly unavailable execution status."""
    registry = AnalysisSolverRegistry()
    assert registry.get_solver_id(AnalysisType.TORSION) == "shaft_torsion_v1"
    assert registry.get_solver_id(AnalysisType.BENDING) == "beam_bending_v1"
    assert registry.get_solver_id(AnalysisType.COMBINED_STRESS) == "combined_shaft_stress_v1"
    assert registry.get_solver_id(AnalysisType.DEFLECTION) == "beam_deflection_v1"
    assert registry.get_solver_id(AnalysisType.FATIGUE) == "fatigue_assessment_v1"
    assert registry.get_solver_id(AnalysisType.BUCKLING) == "euler_buckling_v1"

    # In Slice 8, numerical solvers are NOT implemented yet
    assert registry.is_solver_available("shaft_torsion_v1") is False
    note = registry.get_solver_status_note("shaft_torsion_v1")
    assert "Slice 9+" in note


# ---------------------------------------------------------------------------
# 3. Calculation vs Assessment Input Distinction Tests
# ---------------------------------------------------------------------------

def test_calculation_vs_assessment_inputs_torsion():
    """Verifies segregation between calculation inputs (torque, diameter) and assessment inputs (allowable)."""
    # Case 1: All inputs present
    resolved = resolve_analysis_inputs(
        AnalysisType.TORSION,
        engineering_inputs={"torque": 50.0, "shaft_diameter": 25.0, "material_allowable_stress": 120.0}
    )
    assert resolved["missing_calculation_inputs"] == []
    assert resolved["missing_assessment_inputs"] == []

    # Case 2: Only calculation inputs present
    resolved_calc_only = resolve_analysis_inputs(
        AnalysisType.TORSION,
        engineering_inputs={"torque": 50.0, "shaft_diameter": 25.0}
    )
    assert resolved_calc_only["missing_calculation_inputs"] == []
    assert "material_allowable_stress" in resolved_calc_only["missing_assessment_inputs"]

    # Case 3: Calculation input missing (diameter missing)
    resolved_missing_calc = resolve_analysis_inputs(
        AnalysisType.TORSION,
        engineering_inputs={"torque": 50.0}
    )
    assert "shaft_diameter" in resolved_missing_calc["missing_calculation_inputs"]


# ---------------------------------------------------------------------------
# 4. Shaft Scenario Tests (Cases A through F)
# ---------------------------------------------------------------------------

def test_case_a_shaft_all_inputs_ready():
    """Case A: shaft + torque + diameter + material -> Torsion is READY."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_0",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft geometry",
        attributes={"diameter": 28.0, "length": 200.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    match = EngineeringRuleMatch(
        rule_id="shaft_torsion_applicability",
        applicability=True,
        rationale="Shaft feature present with torque supplied.",
        evidence_ids=["mech_shaft_0", "input:torque"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[match])
    inputs = {"torque": 40.0, "material_allowable_stress": 150.0}

    plan = planner.create_plan(semantics, ek, inputs)
    torsion_item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)

    assert torsion_item is not None
    assert torsion_item.status == AnalysisStatus.READY
    assert torsion_item.solver_id == "shaft_torsion_v1"
    assert "mech_shaft_0" in torsion_item.feature_ids
    assert len(torsion_item.missing_calculation_inputs) == 0
    assert AnalysisType.TORSION in plan.ready_analyses


def test_case_b_shaft_torque_missing_diameter():
    """Case B: shaft + torque but no diameter -> Torsion is MISSING_INPUTS."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_nodiam",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft geometry",
        attributes={"length": 200.0}  # diameter absent
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    match = EngineeringRuleMatch(
        rule_id="shaft_torsion_applicability",
        applicability=True,
        rationale="Shaft feature present with torque supplied.",
        evidence_ids=["mech_shaft_nodiam", "input:torque"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[match])
    inputs = {"torque": 40.0}

    plan = planner.create_plan(semantics, ek, inputs)
    torsion_item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)

    assert torsion_item is not None
    assert torsion_item.status == AnalysisStatus.MISSING_INPUTS
    assert "shaft_diameter" in torsion_item.missing_calculation_inputs
    assert AnalysisType.TORSION not in plan.ready_analyses


def test_case_c_shaft_torsion_bending_combined():
    """Case C: shaft + torque + diameter + bending moment -> Torsion, Bending, Combined all planned."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_c",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 30.0, "length": 250.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    matches = [
        EngineeringRuleMatch(rule_id="shaft_torsion_applicability", applicability=True, rationale="Torsion applicable"),
        EngineeringRuleMatch(rule_id="shaft_bending_applicability", applicability=True, rationale="Bending applicable"),
        EngineeringRuleMatch(rule_id="shaft_combined_stress_applicability", applicability=True, rationale="Combined applicable")
    ]
    ek = EngineeringKnowledgeResult(applicable_rules=matches)
    inputs = {
        "torque": 60.0,
        "transverse_load": 400.0,
        "bending_moment": 120.0,
        "support_conditions": "simple_bearings",
        "yield_strength": 250.0
    }

    plan = planner.create_plan(semantics, ek, inputs)
    types = {it.analysis_type for it in plan.items if it.status == AnalysisStatus.READY}
    assert AnalysisType.TORSION in types
    assert AnalysisType.BENDING in types
    assert AnalysisType.COMBINED_STRESS in types


def test_case_d_shaft_no_bending_load_not_assumed():
    """Case D: shaft + torque + NO bending load -> bending must NOT be recommended or planned."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_d",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 30.0, "length": 250.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    matches = [
        EngineeringRuleMatch(rule_id="shaft_torsion_applicability", applicability=True, rationale="Torsion applicable")
    ]
    ek = EngineeringKnowledgeResult(applicable_rules=matches)
    inputs = {"torque": 60.0}

    plan = planner.create_plan(semantics, ek, inputs)
    assert not any(it.analysis_type == AnalysisType.BENDING for it in plan.items)


def test_case_e_fatigue_cyclic_loading():
    """Case E: cyclic loading present -> Fatigue is planned; without cyclic loading -> not planned."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_e",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])

    fatigue_match = EngineeringRuleMatch(rule_id="fatigue_analysis_applicability", applicability=True, rationale="Cyclic loading present.")
    ek = EngineeringKnowledgeResult(applicable_rules=[fatigue_match])
    inputs = {"cyclic_loading": True, "stress_amplitude": 80.0, "mean_stress": 20.0}

    plan = planner.create_plan(semantics, ek, inputs)
    fatigue_item = next((i for i in plan.items if i.analysis_type == AnalysisType.FATIGUE), None)
    assert fatigue_item is not None
    assert fatigue_item.status == AnalysisStatus.READY
    assert "endurance_limit" in fatigue_item.missing_assessment_inputs


def test_fatigue_missing_material_data():
    """Fatigue analysis identifies missing S-N / endurance limit data."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_fat",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    fatigue_match = EngineeringRuleMatch(rule_id="fatigue_analysis_applicability", applicability=True, rationale="Cyclic loading present.")
    ek = EngineeringKnowledgeResult(applicable_rules=[fatigue_match])
    # Cyclic loading indicated but stress amplitude is missing
    inputs = {"cyclic_loading": True}

    plan = planner.create_plan(semantics, ek, inputs)
    fatigue_item = next((i for i in plan.items if i.analysis_type == AnalysisType.FATIGUE), None)
    assert fatigue_item is not None
    assert fatigue_item.status == AnalysisStatus.MISSING_INPUTS
    assert "stress_amplitude" in fatigue_item.missing_calculation_inputs
    assert "endurance_limit" in fatigue_item.missing_assessment_inputs


def test_case_f_shaft_no_torque_missing_inputs():
    """Case F: shaft without torque -> Torsion is not silently ready, surfaces missing torque."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_f",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 25.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    torsion_match = EngineeringRuleMatch(
        rule_id="shaft_torsion_applicability",
        applicability=True,
        rationale="Shaft present, torque missing.",
        missing_inputs=["torque"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[torsion_match])

    plan = planner.create_plan(semantics, ek, engineering_inputs={})
    torsion_item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)
    assert torsion_item is not None
    assert torsion_item.status == AnalysisStatus.MISSING_INPUTS
    assert "torque" in torsion_item.missing_calculation_inputs
    assert AnalysisType.TORSION not in plan.ready_analyses


# ---------------------------------------------------------------------------
# 5. Buckling, Deflection, Hole & Pattern Tests
# ---------------------------------------------------------------------------

def test_buckling_slender_shaft_with_compression():
    """Buckling is planned only when compressive load is supplied."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_buckle",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Slender shaft",
        attributes={"diameter": 15.0, "length": 300.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    buckle_match = EngineeringRuleMatch(
        rule_id="buckling_analysis_applicability",
        applicability=True,
        rationale="Compressive load on slender column.",
        missing_inputs=["elastic_modulus"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[buckle_match])
    inputs = {"compressive_load": 1200.0}  # missing elastic_modulus

    plan = planner.create_plan(semantics, ek, inputs)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.BUCKLING), None)
    assert item is not None
    assert item.status == AnalysisStatus.MISSING_INPUTS
    assert "elastic_modulus" in item.missing_calculation_inputs


def test_buckling_missing_effective_length():
    """Buckling analysis explicitly flags missing effective length."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_buckle_no_len",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Slender shaft",
        attributes={"diameter": 15.0}  # length missing
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    buckle_match = EngineeringRuleMatch(
        rule_id="buckling_analysis_applicability",
        applicability=True,
        rationale="Compressive load on slender column."
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[buckle_match])
    inputs = {"compressive_load": 1200.0, "elastic_modulus": 200000.0}

    plan = planner.create_plan(semantics, ek, inputs)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.BUCKLING), None)
    assert item is not None
    assert "effective_length" in item.missing_calculation_inputs


def test_deflection_missing_boundary_conditions():
    """Deflection analysis is flagged as missing_inputs when boundary conditions are absent."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_defl",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 20.0, "length": 150.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    defl_match = EngineeringRuleMatch(
        rule_id="deflection_analysis_applicability",
        applicability=True,
        rationale="Applied load on beam.",
        missing_inputs=["support_conditions", "elastic_modulus"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[defl_match])
    inputs = {"applied_load": 300.0}  # support_conditions and elastic_modulus missing

    plan = planner.create_plan(semantics, ek, inputs)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.DEFLECTION), None)
    assert item is not None
    assert item.status == AnalysisStatus.MISSING_INPUTS
    assert "support_conditions" in item.missing_calculation_inputs
    assert "elastic_modulus" in item.missing_calculation_inputs


def test_hole_without_load_no_numerical_stress_analysis():
    """A hole with no applied load does not trigger numerical stress calculation."""
    planner = AnalysisPlanner()
    hole = MechanicalFeature(
        id="mech_hole_1",
        feature_type=MechanicalFeatureType.HOLE,
        confidence=0.92,
        evidence=[],
        reasoning_basis="Hole geometry",
        attributes={"diameter": 10.0}
    )
    semantics = MechanicalSemanticsResult(features=[hole])
    hole_rule = EngineeringRuleMatch(
        rule_id="hole_engineering_requirements",
        applicability=True,
        rationale="Hole sizing and tolerancing."
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[hole_rule])

    plan = planner.create_plan(semantics, ek, engineering_inputs={})
    # Tolerancing review is knowledge; no numerical stress analysis is scheduled without load
    assert not any(it.analysis_type == AnalysisType.BEARING_STRESS for it in plan.items)


def test_hole_pattern_with_load():
    """Hole pattern with pattern load plans hole_pattern_load analysis."""
    planner = AnalysisPlanner()
    pattern = MechanicalFeature(
        id="mech_pat_0",
        feature_type=MechanicalFeatureType.HOLE_PATTERN,
        confidence=0.85,
        evidence=[],
        reasoning_basis="Radial bolt pattern",
        attributes={"count": 6, "pitch_circle_diameter": 100.0}
    )
    semantics = MechanicalSemanticsResult(features=[pattern])
    pat_match = EngineeringRuleMatch(
        rule_id="hole_pattern_engineering_requirements",
        applicability=True,
        rationale="Bolt circle pattern."
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[pat_match])
    inputs = {"pattern_load": 5000.0}

    plan = planner.create_plan(semantics, ek, inputs)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.HOLE_PATTERN_LOAD), None)
    assert item is not None
    assert item.status == AnalysisStatus.READY
    assert item.solver_id == "bolt_pattern_shear_v1"
    assert "Equal load sharing" in item.assumptions[0]


# ---------------------------------------------------------------------------
# 6. User Control & Override Tests
# ---------------------------------------------------------------------------

def test_user_explicitly_disables_analysis():
    """User disabled analysis takes precedence and is marked user_disabled."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_dis",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={"diameter": 20.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    torsion_match = EngineeringRuleMatch(rule_id="shaft_torsion_applicability", applicability=True, rationale="Torsion rule")
    ek = EngineeringKnowledgeResult(applicable_rules=[torsion_match])

    # User explicitly disables torsion
    req = AnalysisPlanningRequest(
        disabled_analyses=[AnalysisType.TORSION],
        engineering_inputs={"torque": 50.0, "shaft_diameter": 20.0}
    )

    plan = planner.create_plan(semantics, ek, request=req)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)
    assert item is not None
    assert item.status == AnalysisStatus.USER_DISABLED
    assert item.user_disabled is True
    assert AnalysisType.TORSION not in plan.ready_analyses


def test_user_explicitly_requests_analysis_with_missing_inputs():
    """User requested analysis is included, but never fabricates missing inputs."""
    planner = AnalysisPlanner()
    semantics = MechanicalSemanticsResult(features=[])
    ek = EngineeringKnowledgeResult(applicable_rules=[])

    # User explicitly requests bending on an unspecified part
    req = AnalysisPlanningRequest(
        requested_analyses=[AnalysisType.BENDING],
        engineering_inputs={}
    )

    plan = planner.create_plan(semantics, ek, request=req)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.BENDING), None)
    assert item is not None
    assert item.user_selected is True
    assert item.status == AnalysisStatus.MISSING_INPUTS
    assert len(item.missing_calculation_inputs) > 0


def test_no_fabricated_inputs():
    """The planner never fabricates default engineering inputs."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="mech_shaft_real",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.75,
        evidence=[],
        reasoning_basis="Shaft",
        attributes={}  # empty attributes
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    match = EngineeringRuleMatch(rule_id="shaft_torsion_applicability", applicability=True, rationale="Torsion rule")
    ek = EngineeringKnowledgeResult(applicable_rules=[match])

    plan = planner.create_plan(semantics, ek, engineering_inputs={})
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)
    assert item is not None
    assert item.status == AnalysisStatus.MISSING_INPUTS
    assert "torque" in item.missing_calculation_inputs
    assert "shaft_diameter" in item.missing_calculation_inputs


def test_evidence_propagation_and_rationale():
    """Ensures feature IDs, evidence IDs, and rationales propagate cleanly into plan items."""
    planner = AnalysisPlanner()
    shaft = MechanicalFeature(
        id="shaft_42",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.88,
        evidence=[],
        reasoning_basis="Detected shaft",
        attributes={"diameter": 22.0}
    )
    semantics = MechanicalSemanticsResult(features=[shaft])
    match = EngineeringRuleMatch(
        rule_id="shaft_torsion_applicability",
        applicability=True,
        rationale="Shaft 42 torque analysis.",
        evidence_ids=["shaft_42", "input:torque"]
    )
    ek = EngineeringKnowledgeResult(applicable_rules=[match])
    inputs = {"torque": 15.0}

    plan = planner.create_plan(semantics, ek, inputs)
    item = next((i for i in plan.items if i.analysis_type == AnalysisType.TORSION), None)
    assert item is not None
    assert "shaft_42" in item.feature_ids
    assert "input:torque" in item.evidence_ids
    assert "shaft_torsion_v1" == item.solver_id
    assert "shaft_torsion_v1" in item.rationale


# ---------------------------------------------------------------------------
# 7. Deterministic Report Generation Tests
# ---------------------------------------------------------------------------

def test_deterministic_report_generation():
    """Verifies that generate_analysis_plan_report produces a structured, auditable summary."""
    plan_item = AnalysisPlanItem(
        analysis_type=AnalysisType.TORSION,
        status=AnalysisStatus.READY,
        priority="high",
        rationale="Shaft feature present with torque supplied.",
        feature_ids=["mech_shaft_0"],
        required_inputs=["torque", "shaft_diameter", "material_allowable_stress"],
        available_inputs=["torque", "shaft_diameter"],
        missing_inputs=["material_allowable_stress"],
        calculation_inputs=["torque", "shaft_diameter"],
        assessment_inputs=["material_allowable_stress"],
        missing_calculation_inputs=[],
        missing_assessment_inputs=["material_allowable_stress"],
        solver_id="shaft_torsion_v1",
        assumptions=["Saint-Venant torsional shear distribution assumed."],
        limitations=["Execution target is planned deterministic solver shaft_torsion_v1."]
    )
    plan = AnalysisPlan(
        plan_id="plan_test_01",
        items=[plan_item],
        recommended_analyses=[AnalysisType.TORSION],
        ready_analyses=[AnalysisType.TORSION],
        blocked_analyses=[],
        missing_inputs=["material_allowable_stress"],
        warnings=["Mechanical calculations are pending solver implementation."]
    )

    report_text = generate_analysis_plan_report(plan)
    assert "# Mechanical Analysis Execution Plan (plan_test_01)" in report_text
    assert "[READY] TORSION" in report_text
    assert "shaft_torsion_v1" in report_text
    assert "material_allowable_stress" in report_text
    assert "qualified human engineer review" in report_text


# ---------------------------------------------------------------------------
# 8. API Integration Tests
# ---------------------------------------------------------------------------

def test_api_analyze_returns_analysis_plan():
    """POST /analyze returns analysis_plan with items, ready_analyses, and warnings."""
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

    assert "analysis_plan" in data
    plan = data["analysis_plan"]
    assert "plan_id" in plan
    assert "items" in plan
    assert "ready_analyses" in plan
    assert "warnings" in plan


def test_api_analyze_with_planning_request():
    """POST /analyze with planning_request JSON string respects user disabled and requested analyses."""
    img = np.full((200, 300, 3), 255, dtype=np.uint8)
    cv2.circle(img, (150, 100), 20, (0, 0, 0), 2)
    success, encoded = cv2.imencode(".png", img)
    assert success

    plan_req_json = json.dumps({
        "disabled_analyses": ["fatigue"],
        "requested_analyses": ["torsion"],
        "engineering_inputs": {"torque": 75.0, "shaft_diameter": 30.0}
    })

    response = client.post(
        "/analyze",
        files={"file": ("drawing.png", io.BytesIO(encoded.tobytes()), "image/png")},
        data={"planning_request": plan_req_json}
    )
    assert response.status_code == 200
    data = response.json()
    items = data["analysis_plan"]["items"]

    fatigue_item = next((it for it in items if it["analysis_type"] == "fatigue"), None)
    assert fatigue_item is not None
    assert fatigue_item["status"] == "user_disabled"

    torsion_item = next((it for it in items if it["analysis_type"] == "torsion"), None)
    assert torsion_item is not None
    assert torsion_item["status"] == "ready"


# ---------------------------------------------------------------------------
# 9. Reasoning Context Integration Tests
# ---------------------------------------------------------------------------

def test_reasoning_drawing_context_consumes_analysis_plan():
    """Verifies that DrawingContext and select_context_for_question receive analysis_plan."""
    plan_item = AnalysisPlanItem(
        analysis_type=AnalysisType.HOLE_PATTERN_LOAD,
        status=AnalysisStatus.READY,
        rationale="Hole pattern with fastener load.",
        solver_id="bolt_pattern_shear_v1"
    )
    plan = AnalysisPlan(
        plan_id="plan_reasoning",
        items=[plan_item],
        recommended_analyses=[AnalysisType.HOLE_PATTERN_LOAD],
        ready_analyses=[AnalysisType.HOLE_PATTERN_LOAD],
        blocked_analyses=[],
        missing_inputs=[]
    )

    resp = AnalyzeResponse(
        image=ImageMetadata(width=300, height=200),
        lines=[],
        circles=[],
        contours=[],
        analysis_plan=plan
    )

    context = build_drawing_context(resp)
    assert context.analysis_plan is not None
    assert len(context.analysis_plan["items"]) == 1

    # Hole analysis question receives filtered hole pattern analysis plan
    hole_ctx = select_context_for_question(context, QuestionType.HOLE_ANALYSIS)
    assert "analysis_plan" in hole_ctx
    assert hole_ctx["analysis_plan"]["ready_analyses"] == ["hole_pattern_load"]

    # General engineering question receives full analysis plan
    gen_ctx = select_context_for_question(context, QuestionType.GENERAL_ENGINEERING_QUESTION)
    assert "analysis_plan" in gen_ctx
    assert gen_ctx["analysis_plan"]["plan_id"] == "plan_reasoning"
