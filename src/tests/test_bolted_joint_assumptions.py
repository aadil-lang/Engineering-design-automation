"""
Unit and integration tests for the Slice 10 Engineering Assumption Audit:
- Distinguish USER_PROVIDED vs ASSUMED/DEFAULT parameters
- Distinguish explicitly supplied, derived approximation, and nominal tensile stress areas
- Auditable provenance tracking (is_assumed, assumption_rationale, source)
- Configurable preload factor and torque coefficient
- Inclusion in calculation steps and report generation
"""

import pytest
from solvers import (
    solve_bolt_preload,
    solve_bolt_tension,
    solve_bolt_shear,
    solve_bolt_combined_stress,
    generate_calculation_report,
    CalculationCertificate,
    CertificateStatus
)


# ==============================================================================
# 1. Preload Factor Audit: User-Provided vs Assumed Default
# ==============================================================================

def test_user_provided_preload_factor():
    """Explicitly provided preload factor must be marked as user-provided (not assumed)."""
    cert = solve_bolt_preload(
        bolt_diameter=16.0,
        proof_stress=600.0,
        preload_factor=0.85
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.results["preload_factor"] == 0.85
    assert cert.results["preload_factor_assumed"] is False

    # Check provenance
    prov = cert.provenance["preload_factor"]
    assert prov.value == 0.85
    assert prov.is_assumed is False
    assert prov.source == "engineering_inputs"

    # Must NOT be recorded as an assumed default in tracked_assumptions
    assumed_params = [a.parameter for a in cert.tracked_assumptions if a.parameter == "preload_factor"]
    assert len(assumed_params) == 0


def test_assumed_default_preload_factor():
    """Omitted preload factor must safely default to 0.75 and be explicitly flagged as assumed."""
    cert = solve_bolt_preload(
        bolt_diameter=16.0,
        proof_stress=600.0
        # preload_factor omitted
    )

    assert cert.status == CertificateStatus.SUCCESS
    assert cert.results["preload_factor"] == 0.75
    assert cert.results["preload_factor_assumed"] is True

    # Check provenance
    prov = cert.provenance["preload_factor"]
    assert prov.value == 0.75
    assert prov.is_assumed is True
    assert prov.source == "assumed_default"
    assert "0.75" in prov.assumption_rationale

    # Must be recorded in tracked_assumptions
    tracked = [a for a in cert.tracked_assumptions if a.parameter == "preload_factor"]
    assert len(tracked) == 1
    assert tracked[0].value == 0.75
    assert tracked[0].category == "assumed_default"
    assert tracked[0].is_user_provided is False

    # Must be recorded in general assumptions list
    assert any("preload factor assumed as k=0.75" in s.lower() for s in cert.assumptions)


# ==============================================================================
# 2. Torque Coefficient K Audit: User-Provided vs Assumed Default
# ==============================================================================

def test_user_provided_torque_coefficient():
    """User-provided torque coefficient K=0.15 is tracked as user data."""
    cert = solve_bolt_preload(
        bolt_diameter=12.0,
        proof_stress=600.0,
        preload_factor=0.75,
        torque_coefficient=0.15
    )

    assert cert.results["torque_coefficient"] == 0.15
    assert cert.results["torque_coefficient_assumed"] is False

    prov = cert.provenance["torque_coefficient"]
    assert prov.value == 0.15
    assert prov.is_assumed is False
    assert prov.source == "engineering_inputs"

    # Tightening torque calculated: T = 0.15 * F_preload * d
    f_preload = cert.results["preload_force"]
    expected_torque = 0.15 * f_preload * 0.012
    assert cert.results["tightening_torque"] == pytest.approx(expected_torque, rel=1e-4)


def test_assumed_default_torque_coefficient():
    """Omitted torque coefficient defaults to 0.20 and is tracked as an empirical assumption."""
    cert = solve_bolt_preload(
        bolt_diameter=12.0,
        proof_stress=600.0,
        preload_factor=0.75
        # torque_coefficient omitted
    )

    assert cert.results["torque_coefficient"] == 0.20
    assert cert.results["torque_coefficient_assumed"] is True

    prov = cert.provenance["torque_coefficient"]
    assert prov.value == 0.20
    assert prov.is_assumed is True
    assert prov.source == "assumed_default"
    assert "K=0.20" in prov.assumption_rationale

    # Must be recorded in tracked_assumptions
    tracked = [a for a in cert.tracked_assumptions if a.parameter == "torque_coefficient"]
    assert len(tracked) == 1
    assert tracked[0].value == 0.20
    assert tracked[0].category == "assumed_default"
    assert tracked[0].is_user_provided is False

    # Check calculation step mentions assumed K=0.20
    step = next(s for s in cert.calculations if s.step_id == "step_tightening_torque")
    assert "assumed torque coefficient" in step.description.lower()


# ==============================================================================
# 3. Tensile Stress Area: Supplied vs Derived vs Nominal Approximation
# ==============================================================================

def test_tensile_area_explicitly_supplied():
    """Supplied tensile area must be marked explicitly_supplied and not assumed."""
    cert = solve_bolt_tension(
        bolt_diameter=16.0,
        tensile_load=20000.0,
        tensile_stress_area=157.0  # mm^2
    )

    assert cert.results["tensile_stress_area_method"] == "explicitly_supplied"
    assert cert.results["tensile_stress_area_assumed"] is False
    assert cert.results["tensile_stress_area_mm2"] == pytest.approx(157.0, rel=1e-3)

    prov = cert.provenance["tensile_stress_area"]
    assert prov.is_assumed is False
    assert prov.source == "engineering_inputs"


def test_tensile_area_derived_approximation_from_pitch():
    """Supplied pitch derives At using metric coarse thread formula, marked derived_approximation."""
    cert = solve_bolt_tension(
        bolt_diameter=16.0,
        tensile_load=20000.0,
        thread_pitch=2.0  # M16 x 2.0 coarse pitch
    )

    assert cert.results["tensile_stress_area_method"] == "derived_approximation"
    assert cert.results["tensile_stress_area_assumed"] is True

    # At ≈ 0.7854 * (16 - 0.9382 * 2.0)^2 = 0.7854 * (14.1236)^2 = 156.67 mm^2
    assert cert.results["tensile_stress_area_mm2"] == pytest.approx(156.67, rel=1e-2)

    prov = cert.provenance["tensile_stress_area"]
    assert prov.is_assumed is True
    assert prov.source == "derived_approximation"
    assert "not certified" in prov.assumption_rationale.lower()

    # Tracked assumption check
    tracked = [a for a in cert.tracked_assumptions if a.parameter == "tensile_stress_area"]
    assert len(tracked) == 1
    assert tracked[0].category == "derived_approximation"
    assert tracked[0].is_user_provided is False

    # Does not claim ISO certification in assumptions
    assert any("does not claim exact standards table certification" in s for s in cert.assumptions)


def test_tensile_area_nominal_geometric_approximation():
    """Without explicit area or pitch, falls back to nominal geometric approximation."""
    cert = solve_bolt_tension(
        bolt_diameter=16.0,
        tensile_load=20000.0
        # No area, no pitch
    )

    assert cert.results["tensile_stress_area_method"] == "nominal_geometric_approximation"
    assert cert.results["tensile_stress_area_assumed"] is True

    # Gross area = pi * 16^2 / 4 = 201.06 mm^2, At ≈ 0.78 * 201.06 = 156.83 mm^2
    assert cert.results["tensile_stress_area_mm2"] == pytest.approx(156.83, rel=1e-2)

    prov = cert.provenance["tensile_stress_area"]
    assert prov.is_assumed is True
    assert prov.source == "nominal_geometric_approximation"
    assert "nominal geometric reduction" in prov.assumption_rationale.lower()

    tracked = [a for a in cert.tracked_assumptions if a.parameter == "tensile_stress_area"]
    assert len(tracked) == 1
    assert tracked[0].category == "nominal_geometric_approximation"


# ==============================================================================
# 4. Bolt Shear & Combined Stress Assumptions Audit
# ==============================================================================

def test_bolt_shear_assumed_parameters():
    """Shear planes and bolt counts are tracked as assumed when defaulted."""
    cert = solve_bolt_shear(
        bolt_diameter=10.0,
        shear_load=5000.0
    )

    assert cert.results["shear_planes"] == 1
    assert cert.results["shear_planes_assumed"] is True
    assert cert.results["num_bolts"] == 1
    assert cert.results["num_bolts_assumed"] is True

    assert cert.provenance["shear_planes"].is_assumed is True
    assert cert.provenance["shear_planes"].source == "assumed_default"

    assert cert.provenance["num_bolts"].is_assumed is True
    assert cert.provenance["num_bolts"].source == "assumed_default"


def test_bolt_combined_stress_assumed_parameters():
    """Combined stress solver captures area approximation and plane defaults."""
    cert = solve_bolt_combined_stress(
        bolt_diameter=12.0,
        tensile_load=8000.0,
        shear_load=4000.0,
        thread_pitch=1.75
    )

    assert cert.results["tensile_stress_area_method"] == "derived_approximation"
    assert cert.results["tensile_stress_area_assumed"] is True
    assert cert.results["shear_planes_assumed"] is True
    assert cert.results["num_bolts_assumed"] is True

    assert any(a.parameter == "tensile_stress_area" for a in cert.tracked_assumptions)
    assert any(a.parameter == "shear_planes" for a in cert.tracked_assumptions)


# ==============================================================================
# 5. Calculation Report Renders Assumptions Table
# ==============================================================================

def test_calculation_report_renders_explicit_assumptions():
    """Calculation report includes the tracked assumptions table with rationale and category."""
    cert = solve_bolt_preload(
        bolt_diameter=16.0,
        proof_stress=600.0
    )

    report = generate_calculation_report([cert])
    assert "Explicit Engineering Assumptions & Defaults" in report
    assert "| Parameter | Value | Category | Rationale | User Provided? |" in report
    assert "`preload_factor`" in report
    assert "`torque_coefficient`" in report
    assert "`tensile_stress_area`" in report
    assert "No (Assumed)" in report
