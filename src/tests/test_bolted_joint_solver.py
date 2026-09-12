"""
Unit and integration tests for bolted joint mechanical solvers and planner integration:
- Bolt tension
- Bolt shear
- Combined bolt stress
- Bolt preload
- Input validation and rejection
- Provenance and runner execution
- Analysis planner conservative activation
"""

import math
import pytest
from solvers import (
    solve_bolt_tension,
    solve_bolt_shear,
    solve_bolt_combined_stress,
    solve_bolt_preload,
    SolverRunner,
    MachineElementType,
    CertificateStatus,
    AssessmentStatus
)
from solvers.validation import SolverValidationError
from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlan,
    AnalysisPlanItem,
    AnalysisPlanningRequest
)
from analysis.planner import AnalysisPlanner
from semantics.models import MechanicalFeature, MechanicalFeatureType


# ==============================================================================
# 1. Bolt Tension Tests
# ==============================================================================

def test_bolt_tension_standard_case():
    """
    Benchmark tension test:
    d = 12 mm -> A_gross = pi * (0.012)^2 / 4 = 1.13097e-4 m^2 = 113.1 mm^2
    A_t approx = 0.78 * A_gross = 88.216 mm^2
    F_t = 15,000 N
    sigma_t = 15,000 / 8.8216e-5 = 170.037 MPa
    """
    cert = solve_bolt_tension(bolt_diameter=12.0, tensile_load=15000.0)

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bolt_tension_v1"
    assert cert.analysis_type == "bolt_tension"
    assert cert.machine_element == MachineElementType.BOLTED_JOINT

    res = cert.results
    assert res["bolt_diameter"] == pytest.approx(0.012, rel=1e-6)
    assert res["tensile_load"] == pytest.approx(15000.0, rel=1e-6)

    expected_at = 0.78 * (math.pi * (0.012 ** 2)) / 4.0
    assert res["tensile_stress_area"] == pytest.approx(expected_at, rel=1e-6)
    expected_sigma = 15000.0 / expected_at
    assert res["tensile_stress"] == pytest.approx(expected_sigma, rel=1e-6)
    assert res["tensile_stress_mpa"] == pytest.approx(170.037, rel=1e-3)


def test_bolt_tension_supplied_stress_area():
    """Verify using explicitly supplied tensile stress area (e.g. ISO 898-1 M12 At = 84.3 mm^2)."""
    cert = solve_bolt_tension(
        bolt_diameter=12.0,
        tensile_load=15000.0,
        tensile_stress_area={"value": 84.3, "unit": "mm^2"}
    )
    res = cert.results
    assert res["tensile_stress_area"] == pytest.approx(84.3e-6, rel=1e-6)
    expected_sigma = 15000.0 / 84.3e-6
    assert res["tensile_stress_mpa"] == pytest.approx(expected_sigma / 1e6, rel=1e-4)
    assert res["tensile_stress_mpa"] == pytest.approx(177.936, rel=1e-3)


def test_bolt_tension_allowable_stress_pass():
    """Calculated 170.0 MPa <= allowable 300 MPa -> PASS."""
    cert = solve_bolt_tension(
        bolt_diameter=12.0,
        tensile_load=15000.0,
        allowable_tensile_stress=300.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(300.0 / 170.037, rel=1e-2)
    assert "is below the supplied allowable" in ass.summary


def test_bolt_tension_allowable_stress_fail():
    """Calculated 170.0 MPa > allowable 120 MPa -> FAIL."""
    cert = solve_bolt_tension(
        bolt_diameter=12.0,
        tensile_load=15000.0,
        allowable_tensile_stress=120.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.factor_of_safety == pytest.approx(120.0 / 170.037, rel=1e-2)
    assert "exceeds the supplied allowable" in ass.summary


def test_bolt_tension_not_assessed():
    """When allowable stress is omitted, assessment is NOT_ASSESSED."""
    cert = solve_bolt_tension(bolt_diameter=12.0, tensile_load=15000.0)
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.NOT_ASSESSED
    assert ass.factor_of_safety is None


def test_bolt_tension_unit_conversions():
    """Verify kN load and cm diameter conversions."""
    cert = solve_bolt_tension(
        bolt_diameter={"value": 1.2, "unit": "cm"},
        tensile_load={"value": 15.0, "unit": "kN"}
    )
    assert cert.results["bolt_diameter"] == pytest.approx(0.012, rel=1e-6)
    assert cert.results["tensile_load"] == pytest.approx(15000.0, rel=1e-6)
    assert cert.results["tensile_stress_mpa"] == pytest.approx(170.037, rel=1e-3)


# ==============================================================================
# 2. Bolt Shear Tests
# ==============================================================================

def test_bolt_shear_single_plane():
    """
    d = 10 mm
    V = 8000 N
    A = pi * (0.010)^2 / 4 = 7.85398e-5 m^2 = 78.54 mm^2
    tau = 8000 / 7.85398e-5 = 101.859 MPa
    """
    cert = solve_bolt_shear(bolt_diameter=10.0, shear_load=8000.0)

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bolt_shear_v1"
    assert cert.machine_element == MachineElementType.BOLTED_JOINT

    res = cert.results
    assert res["shear_planes"] == 1
    assert res["shear_stress_mpa"] == pytest.approx(101.859, rel=1e-3)


def test_bolt_shear_double_plane():
    """
    d = 10 mm, n = 2 shear planes
    A_eff = 2 * 78.54 mm^2 = 157.08 mm^2
    tau = 8000 / 157.08e-6 = 50.930 MPa
    """
    cert = solve_bolt_shear(bolt_diameter=10.0, shear_load=8000.0, shear_planes=2)

    res = cert.results
    assert res["shear_planes"] == 2
    assert res["effective_shear_area_mm2"] == pytest.approx(157.08, rel=1e-3)
    assert res["shear_stress_mpa"] == pytest.approx(50.930, rel=1e-3)


def test_bolt_shear_assessment_pass():
    """Calculated 50.9 MPa <= allowable 100 MPa -> PASS."""
    cert = solve_bolt_shear(
        bolt_diameter=10.0,
        shear_load=8000.0,
        shear_planes=2,
        allowable_shear_stress=100.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(100.0 / 50.930, rel=1e-2)


# ==============================================================================
# 3. Combined Bolt Stress Tests
# ==============================================================================

def test_bolt_combined_stress():
    """
    d = 12 mm, F_t = 15,000 N (sigma_t = 170.037 MPa)
    V = 8000 N, n = 1 (A = 113.097 mm^2 -> tau = 70.735 MPa)
    sigma_vm = sqrt(sigma_t^2 + 3 * tau^2)
    = sqrt((170.037)^2 + 3 * (70.735)^2) = sqrt(28912.6 + 15011.0) = 209.579 MPa
    """
    cert = solve_bolt_combined_stress(
        bolt_diameter=12.0,
        tensile_load=15000.0,
        shear_load=8000.0,
        allowable_equivalent_stress=250.0
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bolt_combined_stress_v1"

    res = cert.results
    assert res["tensile_stress_mpa"] == pytest.approx(170.037, rel=1e-3)
    assert res["shear_stress_mpa"] == pytest.approx(70.735, rel=1e-3)
    assert res["von_mises_stress_mpa"] == pytest.approx(209.579, rel=1e-3)

    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(250.0 / 209.579, rel=1e-2)

    # Check that failure criterion is explicitly recorded in calculation steps
    formulas = [c.formula for c in cert.calculations]
    assert any("√(σ_t² + 3 * τ²)" in f for f in formulas)


# ==============================================================================
# 4. Bolt Preload Tests
# ==============================================================================

def test_bolt_preload_standard_case():
    """
    d = 12 mm -> A_t approx = 88.216 mm^2
    k = 0.75 (tightening factor for reusable connections)
    S_p = 600 MPa (Class 8.8 proof strength)
    F_preload = k * A_t * S_p = 0.75 * 8.8216e-5 * 600e6 = 39,697.2 N = 39.70 kN
    """
    cert = solve_bolt_preload(
        bolt_diameter=12.0,
        preload_factor=0.75,
        proof_stress=600.0
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bolt_preload_v1"

    res = cert.results
    assert res["preload_factor"] == 0.75
    assert res["proof_stress_mpa"] == 600.0
    assert res["preload_force"] == pytest.approx(39697.2, rel=1e-3)
    assert res["preload_force_kn"] == pytest.approx(39.70, rel=1e-2)


def test_bolt_preload_supplied_area():
    """Preload with explicit standard tensile stress area."""
    cert = solve_bolt_preload(
        bolt_diameter=12.0,
        preload_factor=0.75,
        proof_stress=600.0,
        tensile_stress_area=84.3  # mm^2
    )
    # F_p = 0.75 * 84.3e-6 * 600e6 = 37,935 N = 37.935 kN
    assert cert.results["preload_force"] == pytest.approx(37935.0, rel=1e-4)
    assert cert.results["preload_force_kn"] == pytest.approx(37.935, rel=1e-4)


# ==============================================================================
# 5. Validation Rejection Tests
# ==============================================================================

def test_validation_zero_negative_bolt_diameter():
    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_bolt_tension(bolt_diameter=0.0, tensile_load=5000.0)

    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_bolt_shear(bolt_diameter=-10.0, shear_load=5000.0)


def test_validation_negative_loads():
    with pytest.raises(SolverValidationError, match="non-negative"):
        solve_bolt_tension(bolt_diameter=12.0, tensile_load=-1000.0)

    with pytest.raises(SolverValidationError, match="non-negative"):
        solve_bolt_shear(bolt_diameter=10.0, shear_load=-2000.0)


def test_validation_invalid_shear_planes():
    with pytest.raises(SolverValidationError, match="integer >= 1"):
        solve_bolt_shear(bolt_diameter=10.0, shear_load=5000.0, shear_planes=0)

    with pytest.raises(SolverValidationError, match="integer >= 1"):
        solve_bolt_shear(bolt_diameter=10.0, shear_load=5000.0, shear_planes=1.5)


def test_validation_missing_preload_inputs():
    """Bolt preload strictly rejects missing preload_factor or proof_stress (never fabricates)."""
    with pytest.raises(SolverValidationError, match="preload_factor"):
        solve_bolt_preload(bolt_diameter=12.0, preload_factor=None, proof_stress=600.0)

    with pytest.raises(SolverValidationError, match="proof_stress"):
        solve_bolt_preload(bolt_diameter=12.0, preload_factor=0.75, proof_stress=None)


# ==============================================================================
# 6. Runner and Provenance Integration
# ==============================================================================

def test_runner_executes_bolted_joint_item():
    """SolverRunner resolves bolted joint inputs and feature provenance."""
    runner = SolverRunner()

    item = AnalysisPlanItem(
        analysis_type=AnalysisType.BOLT_TENSION,
        status=AnalysisStatus.READY,
        priority="high",
        rationale="Bolt tension calculation",
        feature_ids=["feat-hole-pat-01"],
        solver_id="py_mech_bolt_tension_v1",
        available_inputs=["bolt_diameter", "tensile_load"],
        missing_calculation_inputs=[]
    )

    feature = MechanicalFeature(
        id="feat-hole-pat-01",
        feature_type=MechanicalFeatureType.HOLE_PATTERN,
        confidence=0.90,
        reasoning_basis="4-bolt circular pattern",
        attributes={"hole_diameter": 12.0, "count": 4}
    )

    cert = runner.execute_item(
        item=item,
        features=[feature],
        operating_inputs={"tensile_load": 15000.0}
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bolt_tension_v1"
    assert cert.machine_element == MachineElementType.BOLTED_JOINT
    assert cert.results["bolt_diameter"] == pytest.approx(0.012, rel=1e-6)
    assert cert.results["tensile_stress_mpa"] == pytest.approx(170.037, rel=1e-3)

    # Provenance audit
    assert cert.provenance["bolt_diameter"].source == "mechanical_semantics"
    assert cert.provenance["bolt_diameter"].source_id == "feat-hole-pat-01"
    assert cert.provenance["tensile_load"].source == "engineering_inputs"


# ==============================================================================
# 7. Analysis Planner Conservative Activation Tests
# ==============================================================================

def test_planner_does_not_assume_bolted_joint_by_default():
    """Planner must NOT automatically schedule bolted joint analyses without evidence."""
    planner = AnalysisPlanner()

    # Plain drawing with a hole feature
    feature = MechanicalFeature(
        id="feat-hole-1",
        feature_type=MechanicalFeatureType.HOLE,
        confidence=0.95,
        reasoning_basis="Simple through-hole",
        attributes={"diameter": 12.0}
    )

    from core.models import MechanicalSemanticsResult
    semantics = MechanicalSemanticsResult(features=[feature])

    plan = planner.create_plan(
        mechanical_semantics=semantics,
        request=AnalysisPlanningRequest()
    )

    # Bolted joint analyses should NOT be automatically scheduled
    bolted_planned = [
        it.analysis_type for it in plan.items
        if it.analysis_type in (
            AnalysisType.BOLT_TENSION,
            AnalysisType.BOLT_SHEAR,
            AnalysisType.BOLT_COMBINED_STRESS,
            AnalysisType.BOLT_PRELOAD
        )
    ]
    assert len(bolted_planned) == 0


def test_planner_schedules_bolted_joint_on_explicit_request():
    """User request for BOLT_TENSION activates planning and marks READY when inputs present."""
    planner = AnalysisPlanner()

    feature = MechanicalFeature(
        id="feat-hole-pat-1",
        feature_type=MechanicalFeatureType.HOLE_PATTERN,
        confidence=0.95,
        reasoning_basis="Bolt pattern",
        attributes={"hole_diameter": 10.0, "count": 6}
    )
    from core.models import MechanicalSemanticsResult
    semantics = MechanicalSemanticsResult(features=[feature])

    plan = planner.create_plan(
        mechanical_semantics=semantics,
        engineering_inputs={"tensile_load": 8000.0},
        request=AnalysisPlanningRequest(
            requested_analyses=[AnalysisType.BOLT_TENSION]
        )
    )

    item = next((it for it in plan.items if it.analysis_type == AnalysisType.BOLT_TENSION), None)
    assert item is not None
    assert item.status == AnalysisStatus.READY
    assert item.solver_id == "py_mech_bolt_tension_v1"
    assert AnalysisType.BOLT_TENSION in plan.ready_analyses


def test_planner_blocks_bolted_joint_when_inputs_missing():
    """User request for BOLT_TENSION without tensile load results in MISSING_INPUTS / BLOCKED."""
    planner = AnalysisPlanner()

    plan = planner.create_plan(
        engineering_inputs={"bolt_diameter": 10.0},
        request=AnalysisPlanningRequest(
            requested_analyses=[AnalysisType.BOLT_TENSION]
        )
    )

    item = next((it for it in plan.items if it.analysis_type == AnalysisType.BOLT_TENSION), None)
    assert item is not None
    assert item.status == AnalysisStatus.MISSING_INPUTS
    assert "tensile_load" in item.missing_calculation_inputs
    assert AnalysisType.BOLT_TENSION in plan.blocked_analyses


def test_planner_schedules_bolted_joint_on_explicit_classification():
    """Explicit machine_element='bolted_joint' activates bolted joint planning."""
    planner = AnalysisPlanner()

    plan = planner.create_plan(
        engineering_inputs={
            "machine_element": "bolted_joint",
            "bolt_diameter": 10.0,
            "shear_load": 5000.0
        },
        request=AnalysisPlanningRequest(recommend_analyses=True)
    )

    item = next((it for it in plan.items if it.analysis_type == AnalysisType.BOLT_SHEAR), None)
    assert item is not None
    assert item.status == AnalysisStatus.READY
