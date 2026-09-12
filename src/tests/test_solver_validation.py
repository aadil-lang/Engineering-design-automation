"""
Unit tests for deterministic solver input validation and error rejection.
"""

import pytest
from solvers import solve_torsion, solve_bending, solve_combined_stress
from solvers.validation import SolverValidationError


def test_validation_missing_torque():
    """Torsion solver must reject missing torque."""
    with pytest.raises(SolverValidationError, match="torque"):
        solve_torsion(torque=None, shaft_diameter=25.0)


def test_validation_missing_diameter():
    """Torsion solver must reject missing diameter."""
    with pytest.raises(SolverValidationError, match="shaft_diameter"):
        solve_torsion(torque=31.8, shaft_diameter=None)


def test_validation_zero_diameter():
    """Zero diameter must be rejected as unphysical."""
    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_torsion(torque=31.8, shaft_diameter=0.0)


def test_validation_negative_diameter():
    """Negative diameter must be rejected."""
    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_torsion(torque=31.8, shaft_diameter=-25.0)


def test_validation_zero_length():
    """Zero length when length is supplied must be rejected."""
    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_torsion(torque=31.8, shaft_diameter=25.0, shaft_length=0.0, shear_modulus=79.0)


def test_validation_negative_material_strength():
    """Negative allowable stress must be rejected."""
    with pytest.raises(SolverValidationError, match="non-negative"):
        solve_torsion(torque=31.8, shaft_diameter=25.0, allowable_shear_stress=-50.0)


def test_validation_negative_yield_strength():
    """Negative yield strength must be rejected."""
    with pytest.raises(SolverValidationError, match="non-negative"):
        solve_combined_stress(
            torque=31.8,
            bending_moment=50.0,
            shaft_diameter=25.0,
            yield_strength=-250.0
        )


def test_validation_invalid_unit():
    """Unsupported unit strings must be rejected."""
    with pytest.raises(ValueError, match="Unsupported unit"):
        solve_torsion(
            torque={"value": 31.8, "unit": "smoots*furlong"},
            shaft_diameter=25.0
        )


def test_validation_nan_value():
    """NaN values must be rejected."""
    with pytest.raises(SolverValidationError, match="finite real number"):
        solve_torsion(torque=float("nan"), shaft_diameter=25.0)


def test_validation_inf_value():
    """Inf values must be rejected."""
    with pytest.raises(SolverValidationError, match="finite real number"):
        solve_bending(bending_moment=float("inf"), shaft_diameter=25.0)


def test_validation_non_numeric_string():
    """Non-numeric strings must be rejected."""
    with pytest.raises(SolverValidationError, match="valid numeric value"):
        solve_bending(bending_moment="not_a_number", shaft_diameter=25.0)


def test_validation_negative_design_factor():
    """Negative design factor must be rejected."""
    with pytest.raises(SolverValidationError, match="strictly positive"):
        solve_torsion(torque=31.8, shaft_diameter=25.0, design_factor=-2.0)
