"""
Comprehensive test suite for Slice 14.3: Validated EngineeringSpec -> Deterministic Engineering Solver.
Verifies closed-form shaft calculations, torque derivations, allowable shear stress,
minimum required diameter, standard integer diameter selection, defensive validation blocking,
explicit yield strength provenance verification, and end-to-end pipeline integration.
"""

import math
import pytest
from requirements import (
    EngineeringSpec,
    EngineeringResult,
    RequirementValidationStatus,
    solve_shaft,
    solve_engineering_spec,
    extract_requirements
)
from cad.generator import CADGenerator
from cad.models import CADSpecification, CADStatus


# ==============================================================================
# 1. Yield Strength Provenance & Blocking Tests (A, B, C, D, E)
# ==============================================================================

def test_missing_yield_strength_blocks_solver():
    """
    Test A: material="steel", yield_strength_mpa=None -> BLOCKED.
    Verifies missing_information contains 'yield_strength_mpa' and no diameter/torque is calculated.
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=None
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "yield_strength_mpa" in result.missing_information
    assert result.selected_diameter_mm is None
    assert result.torque_nm is None
    assert result.allowable_stress_mpa is None


def test_explicit_yield_strength_355_solves_benchmark():
    """
    Test B: material="steel", yield_strength_mpa=355 -> VALID.
    Verifies exact benchmark calculations:
    1. T = 31.831 N*m
    2. tau_allow = 102.48 MPa
    3. d_req = 11.65 mm
    4. selected_d = 12.0 mm
    5. tau_design = 93.82 MPa
    6. FoS_achieved = 2.18 >= 2.0 (PASS)
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is True
    assert result.status == RequirementValidationStatus.VALID
    assert result.yield_strength_mpa == 355.0
    assert result.torque_nm == pytest.approx(31.831, rel=1e-3)
    assert result.allowable_stress_mpa == pytest.approx(102.48, rel=1e-3)
    assert result.minimum_required_diameter_mm == pytest.approx(11.65, rel=1e-2)
    assert result.selected_diameter_mm == 12.0
    assert result.design_stress_mpa == pytest.approx(93.82, rel=1e-2)
    assert result.achieved_factor_of_safety == pytest.approx(2.18, rel=1e-2)
    assert result.is_safe is True
    assert len(result.calculation_steps) >= 6


def test_explicit_yield_strength_250_solves_larger_diameter():
    """
    Test C: material="steel", yield_strength_mpa=250 -> VALID.
    Verifies lower yield strength produces larger required diameter:
    tau_allow = (0.57735 * 250) / 2 = 72.17 MPa
    d_req = (16 * 31.831 / (pi * 72.17e6))^(1/3) = 13.10 mm -> selected_d = 14.0 mm
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=250.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is True
    assert result.status == RequirementValidationStatus.VALID
    assert result.yield_strength_mpa == 250.0
    assert result.allowable_stress_mpa == pytest.approx(72.17, rel=1e-3)
    assert result.minimum_required_diameter_mm == pytest.approx(13.10, rel=1e-2)
    assert result.selected_diameter_mm == 14.0
    assert result.is_safe is True


def test_no_silent_fallback_to_355_mpa():
    """
    Test D: Verify that no code path silently substitutes 355 MPa when yield strength is absent.
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    result = solve_shaft(spec)

    # Must be BLOCKED, not VALID
    assert result.status == RequirementValidationStatus.BLOCKED
    assert result.yield_strength_mpa is None
    assert result.allowable_stress_mpa is None
    assert result.selected_diameter_mm is None


def test_generic_steel_alone_never_implies_s355():
    """
    Test E: Regression test ensuring generic 'steel' alone never implies S355 or 355 MPa.
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=10.0,
        rpm=3000.0,
        factor_of_safety=1.5,
        length_mm=400.0
    )
    result = solve_shaft(spec)
    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "yield_strength_mpa" in result.missing_information
    # Ensure no calculation steps or derived stresses exist
    assert result.calculation_steps == []
    assert result.torque_nm is None


def test_extra_parameters_yield_strength_alias_supported():
    """
    Supports explicitly supplied yield strength via extra_parameters['yield_strength'].
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        extra_parameters={"yield_strength": 355.0}
    )
    result = solve_shaft(spec)
    assert result.is_valid is True
    assert result.yield_strength_mpa == 355.0
    assert result.selected_diameter_mm == 12.0


# ==============================================================================
# 2. Defensive Validation & Missing Information Rejection
# ==============================================================================

def test_solver_defensively_rejects_missing_length():
    """Missing length returns BLOCKED status without calculating diameter."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=None,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "length_mm" in result.missing_information
    assert result.selected_diameter_mm is None
    assert result.torque_nm is None


def test_solver_defensively_rejects_missing_power():
    """Missing power returns BLOCKED status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=None,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "power_kw" in result.missing_information
    assert result.selected_diameter_mm is None


def test_solver_defensively_rejects_missing_rpm():
    """Missing RPM returns BLOCKED status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=None,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "rpm" in result.missing_information


def test_solver_defensively_rejects_missing_factor_of_safety():
    """Missing factor of safety returns BLOCKED status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=None,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert "factor_of_safety" in result.missing_information


# ==============================================================================
# 3. Invalid Input Value Rejection
# ==============================================================================

def test_solver_rejects_negative_power():
    """Negative power returns INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=-5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)
    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.INVALID
    assert any("power" in e.lower() for e in result.errors)


def test_solver_rejects_zero_rpm():
    """Zero RPM returns INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=0.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)
    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.INVALID


def test_solver_rejects_negative_factor_of_safety():
    """Negative FoS returns INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=-2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)
    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.INVALID


def test_solver_rejects_negative_yield_strength():
    """Negative yield strength returns INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=-355.0
    )
    result = solve_shaft(spec)
    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.INVALID
    assert any("yield strength" in e.lower() for e in result.errors)


# ==============================================================================
# 4. End-to-End Pipeline Integration (NL -> LLM Extractor -> Solver -> CAD)
# ==============================================================================

def test_full_pipeline_nl_to_solver_to_cad(tmp_path):
    """
    Validates complete end-to-end flow:
    1. Natural Language Requirement Statement
    2. LLM Requirement Extraction with Provenance (Slice 14.2)
    3. Deterministic Validation & Analytical Sizing with explicit yield strength (Slice 14.3)
    4. Parametric 3D CAD & 2D Technical Drawing Generation (Slice 13)
    5. Dimensional Cross-Validation Agreement
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm."

    # Step 1: Extraction
    spec = extract_requirements(problem)
    assert spec.power_kw == 5.0
    assert spec.rpm == 1500.0
    assert spec.length_mm == 300.0
    # Explicitly supply yield strength (e.g. S355 grade from engineering inputs)
    spec.yield_strength_mpa = 355.0

    # Step 2: Solver
    solve_res = solve_engineering_spec(spec)
    assert solve_res.is_valid is True
    assert solve_res.selected_diameter_mm == 12.0
    assert solve_res.torque_nm == pytest.approx(31.831, rel=1e-3)

    # Step 3: CAD & Drawing Generation
    cad_spec = CADSpecification(
        part_name=f"SHAFT_{int(solve_res.selected_diameter_mm)}X{int(solve_res.length_mm)}",
        machine_element="shaft",
        material=solve_res.material,
        diameter=solve_res.selected_diameter_mm,
        length=solve_res.length_mm,
        units="mm",
        parameters={
            "torque_nm": solve_res.torque_nm,
            "design_stress_mpa": solve_res.design_stress_mpa,
            "achieved_fos": solve_res.achieved_factor_of_safety
        }
    )
    cad_gen = CADGenerator()
    cad_res = cad_gen.generate(cad_spec, output_dir=str(tmp_path))

    # Step 4: Verification of CAD & Drawing Outputs
    assert cad_res.status == CADStatus.GENERATED
    assert "step" in cad_res.artifacts
    assert "svg" in cad_res.artifacts
    assert cad_res.validation.is_valid is True
    assert cad_res.validation.bounding_box["dx"] == 300.0
    assert cad_res.validation.bounding_box["dy"] == 12.0
    assert cad_res.dimensional_cross_validation["all_match"] is True


def test_full_pipeline_unstated_yield_strength_blocks_safely_before_cad():
    """
    Unstated yield strength in NL prompt halts cleanly at solver level before CAD.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm."
    spec = extract_requirements(problem)
    # yield_strength_mpa is None
    assert spec.yield_strength_mpa is None

    solve_res = solve_shaft(spec)
    assert solve_res.is_valid is False
    assert solve_res.status == RequirementValidationStatus.BLOCKED
    assert "yield_strength_mpa" in solve_res.missing_information
    assert solve_res.selected_diameter_mm is None


def test_solver_consistency_with_design_engine_sizing():
    """
    Verifies that ShaftEngineeringSolver sizing is 100% consistent with
    canonical design_engine.shaft.calculate_required_diameter.
    """
    from design_engine.shaft import calculate_required_diameter
    from design_engine.config import DISTORTION_ENERGY_SHEAR_FACTOR

    # Benchmark: 5 kW @ 1500 RPM, Sy = 355 MPa, FoS = 2
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        yield_strength_mpa=355.0
    )
    result = solve_shaft(spec)

    # Direct canonical calculation
    omega = 2.0 * math.pi * 1500.0 / 60.0
    torque = (5.0 * 1000.0) / omega
    tau_allow_pa = (DISTORTION_ENERGY_SHEAR_FACTOR * 355.0e6) / 2.0
    d_req_m, d_req_mm, _ = calculate_required_diameter(torque, tau_allow_pa)

    assert result.torque_nm == pytest.approx(torque, rel=1e-3)
    assert result.minimum_required_diameter_mm == pytest.approx(d_req_mm, rel=1e-2)
    assert result.selected_diameter_mm == 12.0
