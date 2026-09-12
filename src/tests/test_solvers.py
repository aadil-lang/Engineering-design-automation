"""
Integration tests for deterministic mechanical solver registry, runner, reporting, and API.
"""

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from api.main import app
from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlan,
    AnalysisPlanItem
)
from semantics.models import MechanicalFeature, MechanicalFeatureType
from solvers import (
    get_solver_registry,
    SolverRegistry,
    SolverRunner,
    generate_calculation_report,
    ShaftTorsionSolver,
    solve_torsion
)
from solvers.models import CertificateStatus
from solvers.validation import SolverValidationError

client = TestClient(app)


def test_registry_operations():
    """Verify solver registration, availability check, and alias lookups."""
    reg = get_solver_registry()

    # Canonical IDs
    assert reg.is_available("py_mech_torsion_v1")
    assert reg.is_available("py_mech_bending_v1")
    assert reg.is_available("py_mech_combined_stress_v1")

    # Slice 8 legacy aliases
    assert reg.is_available("shaft_torsion_v1")
    assert reg.is_available("beam_bending_v1")
    assert reg.is_available("combined_shaft_stress_v1")

    # Analysis type keys
    assert reg.is_available("torsion")
    assert reg.is_available("shaft_torsion")
    assert reg.is_available(AnalysisType.TORSION)
    assert reg.is_available(AnalysisType.BENDING)
    assert reg.is_available(AnalysisType.COMBINED_STRESS)

    # Unavailable
    assert not reg.is_available("non_existent_solver")
    assert reg.get_solver("non_existent_solver") is None

    # List available solvers
    available = reg.list_available_solvers()
    assert "py_mech_torsion_v1" in available
    assert "py_mech_bending_v1" in available
    assert "py_mech_combined_stress_v1" in available


def test_custom_registry_registration():
    """Verify registering a custom solver in a fresh registry."""
    custom_reg = SolverRegistry()
    assert not custom_reg.is_available("custom_torsion")

    custom_reg.register_solver("custom_torsion", ShaftTorsionSolver(), ["custom_type"])
    assert custom_reg.is_available("custom_torsion")
    assert custom_reg.is_available("custom_type")
    assert isinstance(custom_reg.get_solver("custom_type"), ShaftTorsionSolver)


def test_runner_executes_ready_plan_item():
    """Runner should successfully execute a READY analysis item and return certificate."""
    runner = SolverRunner()

    item = AnalysisPlanItem(
        analysis_type=AnalysisType.TORSION,
        status=AnalysisStatus.READY,
        priority="high",
        rationale="Shaft torsion calculation triggered",
        feature_ids=["feat-shaft-01"],
        solver_id="py_mech_torsion_v1",
        available_inputs=["torque", "shaft_diameter"],
        missing_calculation_inputs=[]
    )

    feature = MechanicalFeature(
        id="feat-shaft-01",
        feature_type=MechanicalFeatureType.SHAFT,
        confidence=0.95,
        reasoning_basis="Detected cylinder geometry",
        attributes={"nominal_diameter": 25.0, "length": 200.0}
    )

    cert = runner.execute_item(
        item=item,
        features=[feature],
        operating_inputs={"torque": 31.8}
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_torsion_v1"
    assert cert.results["shaft_diameter"] == pytest.approx(0.025, rel=1e-6)
    assert cert.results["torque"] == pytest.approx(31.8, rel=1e-6)
    assert cert.results["shear_stress_mpa"] == pytest.approx(10.365, rel=1e-3)

    # Provenance checks
    assert "shaft_diameter" in cert.provenance
    assert cert.provenance["shaft_diameter"].source == "mechanical_semantics"
    assert cert.provenance["shaft_diameter"].source_id == "feat-shaft-01"

    assert "torque" in cert.provenance
    assert cert.provenance["torque"].source == "engineering_inputs"


def test_runner_rejects_disabled_item():
    """Runner must reject items that are user-disabled or marked DISABLED."""
    runner = SolverRunner()

    item = AnalysisPlanItem(
        analysis_type=AnalysisType.TORSION,
        status=AnalysisStatus.USER_DISABLED,
        priority="high",
        rationale="Disabled by user",
        user_disabled=True,
        solver_id="py_mech_torsion_v1"
    )

    with pytest.raises(SolverValidationError, match="user_disabled|USER_DISABLED"):
        runner.execute_item(item, operating_inputs={"torque": 31.8, "shaft_diameter": 25.0})


def test_runner_rejects_missing_calculation_inputs():
    """Runner must reject items flagged with missing calculation inputs."""
    runner = SolverRunner()

    item = AnalysisPlanItem(
        analysis_type=AnalysisType.TORSION,
        status=AnalysisStatus.MISSING_INPUTS,
        priority="high",
        rationale="Missing diameter",
        solver_id="py_mech_torsion_v1",
        missing_calculation_inputs=["shaft_diameter"]
    )

    with pytest.raises(SolverValidationError, match="missing calculation input"):
        runner.execute_item(item, operating_inputs={"torque": 31.8})


def test_runner_rejects_unavailable_solver():
    """Runner must reject items pointing to unimplemented solvers."""
    runner = SolverRunner()

    item = AnalysisPlanItem(
        analysis_type=AnalysisType.BUCKLING,
        status=AnalysisStatus.READY,
        priority="high",
        rationale="Slender column buckling",
        solver_id="euler_buckling_v1"
    )

    with pytest.raises(SolverValidationError, match="No deterministic solver available"):
        runner.execute_item(item, operating_inputs={"compressive_load": 5000.0})


def test_runner_execute_plan():
    """execute_plan should process ready items and skip disabled/blocked ones."""
    runner = SolverRunner()

    ready_item = AnalysisPlanItem(
        analysis_type=AnalysisType.TORSION,
        status=AnalysisStatus.READY,
        priority="high",
        rationale="Ready item",
        solver_id="py_mech_torsion_v1",
        available_inputs=["torque", "shaft_diameter"],
        missing_calculation_inputs=[]
    )

    disabled_item = AnalysisPlanItem(
        analysis_type=AnalysisType.BENDING,
        status=AnalysisStatus.USER_DISABLED,
        priority="high",
        rationale="Disabled item",
        user_disabled=True,
        solver_id="py_mech_bending_v1"
    )

    plan = AnalysisPlan(
        plan_id="plan-test-001",
        items=[ready_item, disabled_item],
        recommended_analyses=[AnalysisType.TORSION],
        ready_analyses=[AnalysisType.TORSION]
    )

    certs = runner.execute_plan(
        plan=plan,
        operating_inputs={"torque": 31.8, "shaft_diameter": 25.0}
    )

    assert len(certs) == 1
    assert certs[0].solver_id == "py_mech_torsion_v1"


def test_report_generation():
    """Verify deterministic markdown report generator."""
    cert = solve_torsion(
        torque=31.8,
        shaft_diameter=25.0,
        allowable_shear_stress=50.0
    )

    report = generate_calculation_report([cert])
    assert "# Mechanical Engineering Calculation Report" in report
    assert "py_mech_torsion_v1" in report
    assert "π * d⁴ / 32" in report
    assert "10.365" in report
    assert "🟢 PASS" in report
    assert "Physical Assumptions" in report
    assert "Formulation Limitations" in report


def test_api_execute_analyses_false():
    """By default (execute_analyses=False), /analyze returns analysis_plan but calculation_certificates is None."""
    # Create synthetic blank image
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post(
        "/analyze",
        files={"file": ("test.png", buf, "image/png")}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis_plan" in data
    assert data["calculation_certificates"] is None


def test_api_execute_analyses_true():
    """When execute_analyses=True, /analyze returns populated calculation_certificates for eligible items."""
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    import json
    engineering_inputs = json.dumps({
        "torque": 31.8,
        "shaft_diameter": 25.0
    })
    planning_request = json.dumps({
        "requested_analyses": ["torsion"]
    })

    resp = client.post(
        "/analyze",
        files={"file": ("test.png", buf, "image/png")},
        data={
            "engineering_inputs": engineering_inputs,
            "planning_request": planning_request,
            "execute_analyses": "true"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["calculation_certificates"] is not None
    assert len(data["calculation_certificates"]) >= 1
    torsion_cert = next(
        (c for c in data["calculation_certificates"] if c["solver_id"] == "py_mech_torsion_v1"),
        None
    )
    assert torsion_cert is not None
    assert torsion_cert["status"] == "success"
    assert torsion_cert["results"]["shear_stress_mpa"] == pytest.approx(10.365, rel=1e-3)
