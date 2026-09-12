"""
Strict validation rules for mechanical solver inputs.
"""

import math
from typing import Dict, List, Any


class SolverValidationError(ValueError):
    """Raised when solver inputs fail deterministic validation rules."""
    pass


def validate_required(inputs: Dict[str, Any], required_fields: List[str]) -> None:
    """Verifies all required keys are present and not None in inputs dict."""
    missing = [f for f in required_fields if f not in inputs or inputs[f] is None]
    if missing:
        raise SolverValidationError(
            f"Missing required input parameter(s): {', '.join(repr(m) for m in missing)}"
        )


def validate_numeric(param_name: str, value: Any) -> float:
    """Validates that a value is a finite, real numeric number (rejects NaN, Inf, non-numbers)."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        raise SolverValidationError(
            f"Parameter '{param_name}' must be a valid numeric value, got: {value!r}"
        )
    if math.isnan(val) or math.isinf(val):
        raise SolverValidationError(
            f"Parameter '{param_name}' must be a finite real number, got: {val}"
        )
    return val


def validate_positive(param_name: str, value: float, unit: str = "") -> None:
    """Ensures parameter is strictly positive (> 0), e.g. diameter, length, modulus."""
    if value <= 0.0:
        u_str = f" {unit}" if unit else ""
        raise SolverValidationError(
            f"Parameter '{param_name}' must be strictly positive (> 0), got: {value}{u_str}"
        )


def validate_non_negative(param_name: str, value: float, unit: str = "") -> None:
    """Ensures parameter is non-negative (>= 0), e.g. allowable stress, yield strength, design factor."""
    if value < 0.0:
        u_str = f" {unit}" if unit else ""
        raise SolverValidationError(
            f"Parameter '{param_name}' must be non-negative (>= 0), got: {value}{u_str}"
        )
