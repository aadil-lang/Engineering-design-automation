"""
Unit tests for deterministic combined shaft bending and torsion solver (py_mech_combined_stress_v1).
"""

import math
import pytest
from solvers import solve_combined_stress, ShaftCombinedStressSolver
from solvers.models import CertificateStatus, AssessmentStatus


def test_combined_stress_standard_case():
    """
    Combined bending + torsion benchmark:
    d = 25 mm
    T = 31.8 N*m -> tau = 10.365 MPa
    M = 50.0 N*m -> sigma = 32.595 MPa
    sigma_vm = sqrt(sigma^2 + 3 * tau^2) = 37.228 MPa
    tau_tresca = sqrt((sigma/2)^2 + tau^2) = 19.314 MPa
    sigma_1 = sigma/2 + tau_tresca = 35.612 MPa
    sigma_2 = sigma/2 - tau_tresca = -3.017 MPa
    """
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.solver_id == "py_mech_combined_stress_v1"
    assert cert.analysis_type == "shaft_combined_stress"

    res = cert.results
    tau = res["torsional_shear_stress_mpa"]
    sigma = res["bending_normal_stress_mpa"]
    sigma_vm = res["von_mises_stress_mpa"]
    tau_tresca = res["tresca_shear_mpa"]
    s1 = res["principal_stress_1_mpa"]
    s2 = res["principal_stress_2_mpa"]

    assert tau == pytest.approx(10.365, rel=1e-3)
    assert sigma == pytest.approx(32.595, rel=1e-3)

    # Von Mises: sqrt(sigma^2 + 3 * tau^2)
    expected_vm = math.sqrt((sigma ** 2) + 3.0 * (tau ** 2))
    assert sigma_vm == pytest.approx(expected_vm, rel=1e-6)
    assert sigma_vm == pytest.approx(37.228, rel=1e-3)

    # Tresca: sqrt((sigma/2)^2 + tau^2)
    expected_tresca = math.sqrt(((sigma / 2.0) ** 2) + (tau ** 2))
    assert tau_tresca == pytest.approx(expected_tresca, rel=1e-6)
    assert tau_tresca == pytest.approx(19.314, rel=1e-3)

    # Principal stresses
    assert s1 == pytest.approx((sigma / 2.0) + expected_tresca, rel=1e-6)
    assert s2 == pytest.approx((sigma / 2.0) - expected_tresca, rel=1e-6)
    assert s1 == pytest.approx(35.612, rel=1e-3)
    assert s2 == pytest.approx(-3.017, rel=1e-3)

    # Mohr's circle consistency: (s1 - s2) / 2 == tau_tresca
    assert (s1 - s2) / 2.0 == pytest.approx(tau_tresca, rel=1e-6)


def test_combined_pure_torsion_limit():
    """When bending moment is 0, von Mises is sqrt(3)*tau and Tresca is tau."""
    cert = solve_combined_stress(
        torque=50.0,
        bending_moment=0.0,
        shaft_diameter=30.0
    )
    res = cert.results
    tau = res["torsional_shear_stress_mpa"]
    sigma_vm = res["von_mises_stress_mpa"]
    tau_tresca = res["tresca_shear_mpa"]

    assert res["bending_normal_stress_mpa"] == 0.0
    assert sigma_vm == pytest.approx(math.sqrt(3.0) * tau, rel=1e-6)
    assert tau_tresca == pytest.approx(tau, rel=1e-6)


def test_combined_pure_bending_limit():
    """When torque is 0, von Mises is sigma and Tresca is sigma/2."""
    cert = solve_combined_stress(
        torque=0.0,
        bending_moment=80.0,
        shaft_diameter=30.0
    )
    res = cert.results
    sigma = res["bending_normal_stress_mpa"]
    sigma_vm = res["von_mises_stress_mpa"]
    tau_tresca = res["tresca_shear_mpa"]

    assert res["torsional_shear_stress_mpa"] == 0.0
    assert sigma_vm == pytest.approx(sigma, rel=1e-6)
    assert tau_tresca == pytest.approx(sigma / 2.0, rel=1e-6)


def test_combined_allowable_stress_pass():
    """Calculated Von Mises 37.2 MPa <= allowable 150 MPa -> PASS."""
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_equivalent_stress=150.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(150.0 / 37.228, rel=1e-2)
    assert "is below the supplied allowable" in ass.summary


def test_combined_allowable_stress_fail():
    """Calculated Von Mises 37.2 MPa > allowable 30 MPa -> FAIL."""
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_equivalent_stress=30.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.factor_of_safety == pytest.approx(30.0 / 37.228, rel=1e-2)
    assert "exceeds the supplied allowable" in ass.summary


def test_combined_yield_strength_pass():
    """Using yield_strength directly for equivalent stress assessment."""
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0,
        yield_strength=250.0  # MPa (e.g. mild structural steel)
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.PASS
    assert ass.factor_of_safety == pytest.approx(250.0 / 37.228, rel=1e-2)


def test_combined_not_assessed():
    """When allowable and yield strength are omitted, assessment is NOT_ASSESSED."""
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.NOT_ASSESSED
    assert ass.factor_of_safety is None


def test_combined_design_factor():
    """Allowable 100 MPa with design factor 3.0 -> effective allowable 33.3 MPa < 37.2 MPa -> FAIL."""
    cert = solve_combined_stress(
        torque=31.8,
        bending_moment=50.0,
        shaft_diameter=25.0,
        allowable_equivalent_stress=100.0,
        design_factor=3.0
    )
    ass = cert.assessments[0]
    assert ass.status == AssessmentStatus.FAIL
    assert ass.design_factor == 3.0
