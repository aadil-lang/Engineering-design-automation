"""
Unit tests for deterministic circular solid shaft torsion solver (py_mech_torsion_v1).
"""

import math
import pytest
from solvers import solve_torsion, ShaftTorsionSolver
from solvers.models import CertificateStatus, AssessmentStatus


def test_torsion_standard_case():
    """
    Standard engineering case:
    d = 25 mm (0.025 m)
    T = 31.8 N*m
    J = pi * d^4 / 32 = 3.83495e-8 m^4
    tau = 16 * T / (pi * d^3) = 10.365 MPa
    """
    cert = solve_torsion(torque=31.8, shaft_diameter=25.0)

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_torsion_v1"
    assert cert.analysis_type == "shaft_torsion"

    res = cert.results
    assert res["shaft_diameter"] == pytest.approx(0.025, rel=1e-6)
    assert res["radius"] == pytest.approx(0.0125, rel=1e-6)
    assert res["torque"] == pytest.approx(31.8, rel=1e-6)

    # Polar moment of inertia J
    expected_j = (math.pi * (0.025 ** 4)) / 32.0
    assert res["polar_moment"] == pytest.approx(expected_j, rel=1e-6)
    assert res["polar_moment"] == pytest.approx(3.83495e-8, rel=1e-4)

    # Maximum torsional shear stress tau
    expected_tau = (16.0 * 31.8) / (math.pi * (0.025 ** 3))
    assert res["shear_stress"] == pytest.approx(expected_tau, rel=1e-6)
    assert res["shear_stress_mpa"] == pytest.approx(10.365, rel=1e-3)

    # Calculations list
    assert len(cert.calculations) >= 3
    formulas = [c.formula for c in cert.calculations]
    assert any("π * d⁴ / 32" in f for f in formulas)
    assert any("16 * T / (π * d³)" in f for f in formulas)


def test_torsion_independent_formula_check():
    """Verify Tr/J numerically equals 16T/(pi * d^3)."""
    solver = ShaftTorsionSolver()
    cert = solver.solve({"torque": 150.0, "shaft_diameter": 40.0})

    d = 0.040
    r = d / 2.0
    j = (math.pi * (d ** 4)) / 32.0
    tau_tr_j = (150.0 * r) / j
    tau_16t = (16.0 * 150.0) / (math.pi * (d ** 3))

    assert math.isclose(tau_tr_j, tau_16t, rel_tol=1e-9)
    assert cert.results["shear_stress"] == pytest.approx(tau_tr_j, rel=1e-7)


def test_torsion_twist_angle():
    """Verify twist angle theta = T * L / (J * G)."""
    cert = solve_torsion(
        torque=31.8,
        shaft_diameter=25.0,
        shaft_length=500.0,  # 500 mm = 0.5 m
        shear_modulus=79.0    # 79 GPa
    )

    res = cert.results
    assert res["twist_angle_rad"] is not None
    assert res["twist_angle_deg"] is not None

    j = (math.pi * (0.025 ** 4)) / 32.0
    g = 79.0 * 1e9
    l = 0.5
    expected_theta = (31.8 * l) / (j * g)

    assert res["twist_angle_rad"] == pytest.approx(expected_theta, rel=1e-5)
    assert res["twist_angle_deg"] == pytest.approx(math.degrees(expected_theta), rel=1e-5)


def test_torsion_unit_conversions():
    """Verify conversion of N*mm, cm, and explicit unit dictionaries."""
    cert = solve_torsion(
        torque={"value": 31800.0, "unit": "N*mm"},
        shaft_diameter={"value": 2.5, "unit": "cm"}
    )
    assert cert.results["torque"] == pytest.approx(31.8, rel=1e-6)
    assert cert.results["shaft_diameter"] == pytest.approx(0.025, rel=1e-6)
    assert cert.results["shear_stress_mpa"] == pytest.approx(10.365, rel=1e-3)

    conv_params = {c.parameter: c for c in cert.conversions}
    assert "torque" in conv_params
    assert conv_params["torque"].original_unit == "N*mm"
    assert conv_params["torque"].normalized_unit == "N*m"
    assert conv_params["torque"].conversion_factor == 0.001


def test_torsion_allowable_stress_pass():
    """Calculated stress 10.37 MPa <= allowable 50 MPa -> PASS."""
    cert = solve_torsion(
        torque=31.8,
        shaft_diameter=25.0,
        allowable_shear_stress=50.0  # MPa
    )
    assert len(cert.assessments) == 1
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(50.0 / 10.365, rel=1e-2)
    assert "is below the supplied allowable" in ass.summary


def test_torsion_allowable_stress_fail():
    """Calculated stress 10.37 MPa > allowable 8 MPa -> FAIL."""
    cert = solve_torsion(
        torque=31.8,
        shaft_diameter=25.0,
        allowable_shear_stress=8.0  # MPa
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.factor_of_safety == pytest.approx(8.0 / 10.365, rel=1e-2)
    assert "exceeds the supplied allowable" in ass.summary


def test_torsion_not_assessed():
    """When allowable stress is omitted, assessment is NOT_ASSESSED."""
    cert = solve_torsion(torque=31.8, shaft_diameter=25.0)
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.NOT_ASSESSED
    assert ass.factor_of_safety is None
    assert "cannot be completed" in ass.summary


def test_torsion_design_factor():
    """Allowable 50 MPa with design factor 6.0 yields effective allowable 8.33 MPa -> FAIL."""
    cert = solve_torsion(
        torque=31.8,
        shaft_diameter=25.0,
        allowable_shear_stress=50.0,
        design_factor=6.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.design_factor == 6.0


def test_torsion_signed_torque():
    """Negative torque preserves sign in result but evaluates magnitude for stress."""
    cert = solve_torsion(torque=-31.8, shaft_diameter=25.0)
    assert cert.results["torque"] == -31.8
    assert cert.results["shear_stress_mpa"] == pytest.approx(10.365, rel=1e-3)
