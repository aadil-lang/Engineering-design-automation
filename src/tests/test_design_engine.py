"""
Comprehensive test suite for Slice 12: Parametric Mechanical Design Engine.
Covers design variables, closed-form shaft sizing, candidate generation,
solver evaluation via py_mech_torsion_v1, candidate ranking, assumption tracking,
conflict detection, and acceptance benchmarks.
"""

import math
import pytest
from fastapi.testclient import TestClient
from api.main import app

from design_engine import (
    DesignStatus,
    DesignObjective,
    DesignVariable,
    ShaftDesignRequirements,
    DesignCandidate,
    DesignResult,
    create_shaft_diameter_variable,
    ShaftDiameterCandidateGenerator,
    resolve_shaft_torque,
    resolve_allowable_stress,
    calculate_required_diameter,
    CandidateEvaluator,
    CandidateRanker,
    ShaftDesigner,
    design_from_specification,
    design_from_problem_statement,
    generate_design_report
)
from design import extract_specification
from solvers.models import AssessmentStatus


# ==============================================================================
# 1. Design Variable Tests
# ==============================================================================

def test_design_variable_creation_and_defaults():
    """Verify default search brackets are applied and marked as assumed when omitted."""
    var = create_shaft_diameter_variable()
    assert var.name == "shaft_diameter"
    assert var.unit == "mm"
    assert var.lower_bound == 5.0
    assert var.upper_bound == 250.0
    assert var.step == 1.0
    assert var.is_assumed is True
    assert "defaulted" in var.rationale.lower()


def test_design_variable_explicit_bounds():
    """Explicit bounds and step are preserved as user input without assumed flags."""
    var = create_shaft_diameter_variable(
        diameter_min=20.0,
        diameter_max=80.0,
        diameter_step=2.5
    )
    assert var.lower_bound == 20.0
    assert var.upper_bound == 80.0
    assert var.step == 2.5
    assert var.is_assumed is False
    assert var.source == "user_input"


def test_design_variable_invalid_bounds_and_steps():
    """Invalid bounds and step increments raise descriptive ValueErrors."""
    # Negative lower bound
    with pytest.raises(ValueError, match="strictly positive"):
        create_shaft_diameter_variable(diameter_min=-5.0)

    # Upper bound smaller than lower bound
    with pytest.raises(ValueError, match="cannot be less than lower bound"):
        create_shaft_diameter_variable(diameter_min=50.0, diameter_max=30.0)

    # Non-positive step
    with pytest.raises(ValueError, match="strictly positive"):
        create_shaft_diameter_variable(diameter_step=0.0)


# ==============================================================================
# 2. Torque Derivation & Conflict Tests
# ==============================================================================

def test_torque_derivation_from_power_and_speed():
    """5 kW @ 1500 RPM derives 31.831 N*m deterministically."""
    req = ShaftDesignRequirements(power=5.0, power_unit="kW", speed_rpm=1500.0)
    t_val, derived_obj, conflict = resolve_shaft_torque(req)

    assert t_val == pytest.approx(31.831, rel=1e-3)
    assert derived_obj is not None
    assert derived_obj.name == "torque"
    assert conflict is None


def test_torque_explicit_preserved():
    """Explicit torque is preserved directly."""
    req = ShaftDesignRequirements(torque=120.0, torque_unit="N*m")
    t_val, derived_obj, conflict = resolve_shaft_torque(req)

    assert t_val == 120.0
    assert derived_obj is None
    assert conflict is None


def test_torque_conflict_detection():
    """Conflicting explicit torque and derived torque (>1%) triggers requirement conflict."""
    # 5 kW @ 1500 RPM gives ~31.83 N*m. Caller explicitly supplies 50.0 N*m (large mismatch)
    req = ShaftDesignRequirements(power=5.0, speed_rpm=1500.0, torque=50.0)
    t_val, derived_obj, conflict = resolve_shaft_torque(req)

    assert t_val == 50.0  # Preserves explicit
    assert conflict is not None
    assert conflict.requires_human_review is True
    assert "diverges" in conflict.description


def test_torque_missing_power_or_speed():
    """Incomplete operating parameters return None without crashing."""
    req1 = ShaftDesignRequirements(power=5.0)
    t1, _, _ = resolve_shaft_torque(req1)
    assert t1 is None

    req2 = ShaftDesignRequirements(speed_rpm=1500.0)
    t2, _, _ = resolve_shaft_torque(req2)
    assert t2 is None


# ==============================================================================
# 3. Allowable Stress & Sizing Tests
# ==============================================================================

def test_resolve_allowable_stress_explicit():
    """Explicit allowable shear stress is normalized and returned directly."""
    req = ShaftDesignRequirements(allowable_shear_stress=60.0, allowable_shear_stress_unit="MPa")
    tau_pa, derived_obj, assumptions, missing = resolve_allowable_stress(req)

    assert tau_pa == 60e6
    assert derived_obj is None
    assert missing is None


def test_resolve_allowable_stress_from_yield_strength_and_factor():
    """Yield strength 355 MPa with design factor 2.0 derives tau_allow = 0.57735 * 355 / 2 = 102.48 MPa."""
    req = ShaftDesignRequirements(yield_strength=355.0, design_factor=2.0)
    tau_pa, derived_obj, assumptions, missing = resolve_allowable_stress(req)

    assert missing is None
    assert tau_pa == pytest.approx(102.48e6, rel=1e-3)
    assert derived_obj is not None
    assert derived_obj.name == "allowable_shear_stress"
    assert any("von mises" in a.lower() for a in assumptions)


def test_resolve_allowable_stress_missing_triggers_blocked():
    """Generic material without yield strength or allowable stress returns blocking missing info."""
    req = ShaftDesignRequirements(material="steel")
    tau_pa, derived_obj, assumptions, missing = resolve_allowable_stress(req)

    assert tau_pa is None
    assert missing is not None
    assert missing.blocks_analysis is True
    assert "allowable_shear_stress" in missing.field


def test_calculate_required_diameter_formula():
    """Verify d_req = (16 * T / (pi * tau))^(1/3)."""
    # T = 31.831 N*m, tau = 50 MPa = 50e6 Pa
    # 16 * 31.831 / (pi * 50e6) = 509.296 / 157079632.7 = 3.242278e-6
    # (3.242278e-6)^(1/3) = 0.01480 m = 14.80 mm
    d_m, d_mm, steps = calculate_required_diameter(31.831, 50e6)
    assert d_mm == pytest.approx(14.80, rel=1e-2)
    assert len(steps) >= 4


def test_calculate_required_diameter_invalid_inputs():
    """Non-positive torque or allowable stress raises ValueError."""
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_required_diameter(-10.0, 50e6)

    with pytest.raises(ValueError, match="strictly positive"):
        calculate_required_diameter(50.0, 0.0)


# ==============================================================================
# 4. Candidate Generation Tests
# ==============================================================================

def test_candidate_generation_sequence():
    """Candidate generator produces sequence of diameters around required minimum."""
    gen = ShaftDiameterCandidateGenerator(max_candidates=5)
    var = create_shaft_diameter_variable(diameter_min=10.0, diameter_max=50.0, diameter_step=2.0)

    # required = 23.4 mm -> step bracket starts at 24 - 2 = 22 mm
    cands = gen.generate(var, required_min_diameter_mm=23.4, include_sub_critical=True)
    assert len(cands) == 5
    d_vals = [c["shaft_diameter"] for c in cands]
    assert d_vals == [22.0, 24.0, 26.0, 28.0, 30.0]
    assert cands[0]["is_below_theoretical_min"] is True
    assert cands[1]["is_below_theoretical_min"] is False


# ==============================================================================
# 5. Solver Evaluation & Ranking Tests
# ==============================================================================

def test_candidate_evaluator_calls_existing_torsion_solver():
    """Evaluates candidates using py_mech_torsion_v1 and attaches CalculationCertificates."""
    evaluator = CandidateEvaluator()
    cands = [
        {"candidate_id": "c-10", "shaft_diameter": 10.0},
        {"candidate_id": "c-25", "shaft_diameter": 25.0}
    ]
    # T = 31.831 N*m, tau_allow = 50 MPa
    results = evaluator.evaluate_all_shafts(cands, torque_nm=31.831, allowable_shear_mpa=50.0)

    assert len(results) == 2
    # 10 mm shaft: tau = 16 * 31.831 / (pi * 0.01^3) = 162.1 MPa > 50 MPa -> FAIL
    assert results[0].parameters["shaft_diameter"] == 10.0
    assert results[0].calculated_stress_mpa == pytest.approx(162.1, rel=1e-1)
    assert results[0].assessment == AssessmentStatus.FAIL
    assert len(results[0].calculation_certificates) == 1
    assert results[0].calculation_certificates[0].solver_id == "py_mech_torsion_v1"

    # 25 mm shaft: tau = 16 * 31.831 / (pi * 0.025^3) = 10.37 MPa < 50 MPa -> PASS
    assert results[1].parameters["shaft_diameter"] == 25.0
    assert results[1].calculated_stress_mpa == pytest.approx(10.37, rel=1e-1)
    assert results[1].assessment == AssessmentStatus.PASS
    assert results[1].factor_of_safety > 1.0


def test_candidate_ranking_smallest_passing_selected():
    """Ranker chooses the smallest candidate meeting all safety criteria."""
    evaluator = CandidateEvaluator()
    ranker = CandidateRanker(objective=DesignObjective.MINIMIZE_SHAFT_DIAMETER)

    cands = [
        {"candidate_id": "c-12", "shaft_diameter": 12.0},  # Fails
        {"candidate_id": "c-16", "shaft_diameter": 16.0},  # Passes
        {"candidate_id": "c-20", "shaft_diameter": 20.0}   # Passes
    ]
    evaluated = evaluator.evaluate_all_shafts(cands, torque_nm=31.831, allowable_shear_mpa=50.0)
    selected, alternatives, status = ranker.rank(evaluated)

    assert status == DesignStatus.PASS
    assert selected is not None
    assert selected.parameters["shaft_diameter"] == 16.0  # Smallest passing
    assert len(alternatives) == 1
    assert alternatives[0].parameters["shaft_diameter"] == 20.0


def test_candidate_ranking_all_fail():
    """When all candidates exceed stress limits, status is FAIL and selected is None."""
    evaluator = CandidateEvaluator()
    ranker = CandidateRanker()

    cands = [
        {"candidate_id": "c-5", "shaft_diameter": 5.0},
        {"candidate_id": "c-6", "shaft_diameter": 6.0}
    ]
    evaluated = evaluator.evaluate_all_shafts(cands, torque_nm=500.0, allowable_shear_mpa=20.0)
    selected, alternatives, status = ranker.rank(evaluated)

    assert status == DesignStatus.FAIL
    assert selected is None
    assert len(alternatives) == 2


# ==============================================================================
# 6. Transverse Loading & Bending Awareness Tests
# ==============================================================================

def test_bending_loading_triggers_review():
    """Presence of bending moment prevents automatic PASS and triggers REQUIRES_REVIEW."""
    designer = ShaftDesigner()
    req = ShaftDesignRequirements(
        power=5.0,
        speed_rpm=1500.0,
        yield_strength=355.0,
        design_factor=2.0,
        bending_moment=150.0  # Transverse moment present!
    )
    res = designer.design(req)

    assert res.design_status == DesignStatus.REQUIRES_REVIEW
    assert res.human_review_required is True
    assert any("transverse loading" in r.lower() for r in res.review_reasons)


# ==============================================================================
# 7. Acceptance Benchmark 1: Missing Steel Strength Blocks Sizing
# ==============================================================================

def test_acceptance_benchmark_1_generic_steel_blocked():
    """
    Problem: 'Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.'
    Must extract 5 kW, 1500 RPM, FoS 2, derive T = 31.83 N*m, and return BLOCKED because generic 'steel'
    lacks yield strength. Must NOT invent AISI 1045 or material strength.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2."
    res = design_from_problem_statement(problem)

    assert res.design_status == DesignStatus.BLOCKED
    assert res.selected_candidate is None

    # Verify torque derived
    t_dv = next((d for d in res.derived_values if d.name == "torque"), None)
    assert t_dv is not None
    assert t_dv.output_value == pytest.approx(31.831, rel=1e-3)

    # Verify missing information recorded
    missing_fields = [m.field for m in res.missing_information]
    assert "allowable_shear_stress" in missing_fields

    # No fabricated material grade
    assert not any("1045" in a for a in res.assumptions)


# ==============================================================================
# 8. Acceptance Benchmark 2: Unblocked with Explicit Yield Strength
# ==============================================================================

def test_acceptance_benchmark_2_unblocked_yield_strength_sizing():
    """
    Problem: 'Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.'
    Supplying explicit yield_strength = 355 MPa and design_factor = 2 unblocks candidate sizing.
    tau_allow = 0.57735 * 355 / 2 = 102.48 MPa
    d_req = (16 * 31.831 / (pi * 102.48e6))^(1/3) = 0.01165 m = 11.65 mm
    Candidate sequence [11, 12, 13, ...] -> 11 fails, 12 passes. Selected diameter: 12 mm.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2."
    extra_inputs = {
        "yield_strength": 355.0,
        "design_factor": 2.0
    }
    res = design_from_problem_statement(problem, extra_inputs=extra_inputs)

    assert res.design_status == DesignStatus.PASS
    assert res.selected_candidate is not None

    selected_d = res.selected_candidate.parameters["shaft_diameter_mm"]
    assert selected_d == 12.0  # First integer step >= 11.65 mm
    assert res.selected_candidate.assessment == AssessmentStatus.PASS
    assert res.selected_candidate.factor_of_safety >= 2.0

    # Verify report is generated with required sections
    assert "# Mechanical Design Result" in res.report
    assert "Selected Candidate" in res.report
    assert ("12 mm" in res.report or "12.0 mm" in res.report)
    assert "py_mech_torsion_v1" in res.report


# ==============================================================================
# 9. API Endpoint Integration Tests
# ==============================================================================

def test_api_post_design_endpoint():
    """Test POST /design endpoint with FastAPI TestClient."""
    client = TestClient(app)

    payload = {
        "problem_statement": "Design a steel shaft to transmit 5 kW at 1500 RPM.",
        "engineering_inputs": {
            "yield_strength": 355.0,
            "design_factor": 2.0
        }
    }

    resp = client.post("/design", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "result" in data
    assert "report" in data

    res_data = data["result"]
    assert res_data["design_status"] == "PASS"
    assert res_data["selected_candidate"] is not None
    assert res_data["selected_candidate"]["parameters"]["shaft_diameter_mm"] == 12.0
