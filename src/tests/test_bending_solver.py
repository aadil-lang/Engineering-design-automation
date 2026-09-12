"""
Unit tests for deterministic circular solid shaft bending solver (py_mech_bending_v1).
"""

import math
import pytest
from solvers import solve_bending, ShaftBendingSolver
from solvers.models import CertificateStatus, AssessmentStatus


def test_bending_standard_case():
    """
    Standard engineering case:
    d = 25 mm (0.025 m)
    M = 50.0 N*m
    I = pi * d^4 / 64 = 1.91748e-8 m^4
    Z = pi * d^3 / 32 = 1.53398e-6 m^3
    sigma_b = M / Z = 32.595 MPa
    """
    cert = solve_bending(bending_moment=50.0, shaft_diameter=25.0)

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_bending_v1"
    assert cert.analysis_type == "shaft_bending"

    res = cert.results
    assert res["shaft_diameter"] == pytest.approx(0.025, rel=1e-6)
    assert res["bending_moment"] == pytest.approx(50.0, rel=1e-6)

    # Area moment of inertia I
    expected_i = (math.pi * (0.025 ** 4)) / 64.0
    assert res["moment_of_inertia"] == pytest.approx(expected_i, rel=1e-6)
    assert res["moment_of_inertia"] == pytest.approx(1.91748e-8, rel=1e-4)

    # Section modulus Z
    expected_z = (math.pi * (0.025 ** 3)) / 32.0
    assert res["section_modulus"] == pytest.approx(expected_z, rel=1e-6)
    assert res["section_modulus"] == pytest.approx(1.53398e-6, rel=1e-4)

    # Maximum normal bending stress sigma_b
    expected_sigma = 50.0 / expected_z
    assert res["bending_stress"] == pytest.approx(expected_sigma, rel=1e-6)
    assert res["bending_stress_mpa"] == pytest.approx(32.595, rel=1e-3)

    formulas = [c.formula for c in cert.calculations]
    assert any("π * d⁴ / 64" in f for f in formulas)
    assert any("I / c" in f for f in formulas)
    assert any("(M * c) / I" in f for f in formulas)


def test_bending_independent_formula_check():
    """Verify M/Z numerically equals (M * c) / I and 32M/(pi * d^3)."""
    solver = ShaftBendingSolver()
    cert = solver.solve({"bending_moment": 120.0, "shaft_diameter": 35.0})

    d = 0.035
    c = d / 2.0
    i = (math.pi * (d ** 4)) / 64.0
    z = (math.pi * (d ** 3)) / 32.0

    sigma_mz = 120.0 / z
    sigma_mc_i = (120.0 * c) / i
    sigma_32m = (32.0 * 120.0) / (math.pi * (d ** 3))

    assert math.isclose(sigma_mz, sigma_mc_i, rel_tol=1e-9)
    assert math.isclose(sigma_mz, sigma_32m, rel_tol=1e-9)
    assert cert.results["bending_stress"] == pytest.approx(sigma_mz, rel=1e-7)


def test_bending_allowable_stress_pass():
    """Calculated stress 32.6 MPa <= allowable 100 MPa -> PASS."""
    cert = solve_bending(
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_bending_stress=100.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(100.0 / 32.595, rel=1e-2)
    assert "is below the supplied allowable" in ass.summary


def test_bending_allowable_stress_fail():
    """Calculated stress 32.6 MPa > allowable 25 MPa -> FAIL."""
    cert = solve_bending(
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_bending_stress=25.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.factor_of_safety == pytest.approx(25.0 / 32.595, rel=1e-2)
    assert "exceeds the supplied allowable" in ass.summary


def test_bending_not_assessed():
    """When allowable stress is omitted, assessment status is NOT_ASSESSED."""
    cert = solve_bending(bending_moment=50.0, shaft_diameter=25.0)
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.NOT_ASSESSED
    assert ass.factor_of_safety is None


def test_bending_design_factor():
    """Allowable 100 MPa with design factor 4.0 yields effective allowable 25 MPa -> FAIL."""
    cert = solve_bending(
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_bending_stress=100.0,
        design_factor=4.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.design_factor == 4.0


def test_bending_signed_moment():
    """Negative bending moment preserves sign in results and evaluates magnitude for peak stress."""
    cert = solve_bending(bending_moment=-50.0, shaft_diameter=25.0)
    assert cert.results["bending_moment"] == -50.0
    assert cert.results["bending_stress_mpa"] == pytest.approx(32.595, rel=1e-3)


def test_bending_unit_conversions():
    """Verify kN*m and cm conversions."""
    cert = solve_bending(
        bending_moment={"value": 0.05, "unit": "kN*m"},  # 50 N*m
        shaft_diameter={"value": 2.5, "unit": "cm"}      # 25 mm
    )
    assert cert.results["bending_moment"] == pytest.approx(50.0, rel=1e-6)
    assert cert.results["shaft_diameter"] == pytest.approx(0.025, rel=1e-6)
    assert cert.results["bending_stress_mpa"] == pytest.approx(32.595, rel=1e-3)
