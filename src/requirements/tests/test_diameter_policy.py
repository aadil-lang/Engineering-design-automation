"""
Comprehensive test suite for Slice 14.5: Explicit Nominal Diameter Selection Policy.
Verifies deterministic nominal shaft diameter selection from configured standard metric series,
boundary conditions, out-of-bounds blocking, audit provenance, and solver integration.
"""

import math
import pytest
from requirements.diameter_policy import (
    DEFAULT_NOMINAL_SHAFT_SERIES,
    NominalDiameterSelectionPolicy,
    NominalDiameterSelectionResult,
    select_nominal_diameter
)
from requirements.models import (
    EngineeringSpec,
    RequirementValidationStatus,
    EngineeringResult
)
from requirements.solver import ShaftEngineeringSolver, solve_shaft


# ==============================================================================
# 1. Nominal Diameter Selection Policy Unit Tests
# ==============================================================================

def test_nominal_selection_11_65_to_12():
    """
    Test 1: Required diameter 11.65 mm selects nominal 12.0 mm.
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(11.65)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 12.0
    assert res.required_diameter_mm == 11.65
    assert "12.0 mm" in res.selection_reason
    assert res.error_message is None


def test_nominal_selection_exact_boundary_12_0_to_12_0():
    """
    Test 2: Exactly 12.0 mm selects nominal 12.0 mm (no unnecessary up-sizing).
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(12.0)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 12.0
    assert res.required_diameter_mm == 12.0


def test_nominal_selection_boundary_step_12_01_to_14_0():
    """
    Test 3: 12.01 mm steps to next available nominal size in series (14.0 mm).
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(12.01)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 14.0
    assert res.required_diameter_mm == 12.01


def test_nominal_selection_13_10_to_14_0():
    """
    Test 4: 13.10 mm selects nominal 14.0 mm.
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(13.10)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 14.0
    assert res.required_diameter_mm == 13.10


def test_nominal_selection_exact_boundary_14_0_to_14_0():
    """
    Test 5: Exactly 14.0 mm selects nominal 14.0 mm.
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(14.0)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 14.0


def test_nominal_selection_boundary_step_14_01_to_15_0():
    """
    Test 6: 14.01 mm steps to next nominal size in series (15.0 mm).
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(14.01)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 15.0


def test_nominal_selection_exceeds_max_series_diameter_fails_cleanly():
    """
    Test 7: Required diameter exceeding max configured series (e.g. 250 mm > 200 mm)
    fails cleanly with is_supported=False and explicit error message.
    """
    policy = NominalDiameterSelectionPolicy()
    max_d = policy.max_diameter  # 200.0 mm
    res = policy.select(250.0)

    assert res.is_supported is False
    assert res.selected_diameter_mm is None
    assert res.required_diameter_mm == 250.0
    assert "exceeds maximum nominal diameter" in res.error_message
    assert f"{max_d:.1f} mm" in res.error_message


def test_nominal_selection_deterministic_repeatability():
    """
    Test 8: Repeated calls for identical inputs yield identical selection results.
    """
    policy = NominalDiameterSelectionPolicy()
    for _ in range(50):
        res1 = policy.select(11.65)
        res2 = select_nominal_diameter(11.65)
        assert res1.selected_diameter_mm == 12.0
        assert res2.selected_diameter_mm == 12.0
        assert res1.selection_reason == res2.selection_reason


def test_custom_nominal_series_injection():
    """
    Test 9: Custom diameter series can be configured and properly utilized.
    """
    custom_series = [10.0, 25.0, 50.0, 100.0]
    policy = NominalDiameterSelectionPolicy(series=custom_series, policy_name="custom_portfolio_series")

    assert policy.select(8.0).selected_diameter_mm == 10.0
    assert policy.select(10.0).selected_diameter_mm == 10.0
    assert policy.select(10.01).selected_diameter_mm == 25.0
    assert policy.select(30.0).selected_diameter_mm == 50.0
    assert policy.select(75.0).selected_diameter_mm == 100.0
    assert policy.select(100.01).is_supported is False


# ==============================================================================
# 2. Solver Integration & Audit Provenance Tests
# ==============================================================================

def test_solver_records_nominal_diameter_policy_provenance():
    """
    Test 10: Validates that ShaftEngineeringSolver records explicit diameter selection audit fields.
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
    assert result.minimum_required_diameter_mm == pytest.approx(11.65, rel=1e-2)
    assert result.selected_diameter_mm == 12.0
    assert result.diameter_selection_policy == "metric_nominal_shaft_series_r20_custom"
    assert len(result.diameter_series_used) > 0
    assert "Selected smallest nominal diameter 12.0 mm" in result.diameter_selection_reason
    assert any("Selected nominal diameter from configured series" in step for step in result.calculation_steps)


def test_solver_blocks_when_power_requires_diameter_beyond_series():
    """
    Test 11: When extreme power / low RPM produces a required diameter > 200 mm,
    solver explicitly blocks with BLOCKED status and detailed error message.
    """
    # 5000 kW (5 MW) at 10 RPM with FoS 3 -> required diameter > 400 mm
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5000.0,
        rpm=10.0,
        factor_of_safety=3.0,
        length_mm=1000.0,
        yield_strength_mpa=250.0
    )
    result = solve_shaft(spec)

    assert result.is_valid is False
    assert result.status == RequirementValidationStatus.BLOCKED
    assert result.selected_diameter_mm is None
    assert result.minimum_required_diameter_mm > 200.0
    assert any("exceeds maximum nominal diameter in configured series" in err for err in result.errors)
    assert result.diameter_selection_policy == "metric_nominal_shaft_series_r20_custom"


def test_nominal_selection_floating_point_epsilon_boundary():
    """
    Test 12: d_req = 11.999999 mm selects d_nominal = 12.0 mm
    without floating-point threshold instability or premature jump to 14.0 mm.
    """
    policy = NominalDiameterSelectionPolicy()
    res = policy.select(11.999999)

    assert res.is_supported is True
    assert res.selected_diameter_mm == 12.0
    assert res.required_diameter_mm == 11.999999
