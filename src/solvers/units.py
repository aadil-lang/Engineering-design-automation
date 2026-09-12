"""
Deterministic unit normalization layer for mechanical engineering calculations.
"""

import math
from typing import Dict, Optional, Tuple, Any
from solvers.models import UnitConversion

# Canonical SI units by physical dimension
CANONICAL_SI_UNITS: Dict[str, str] = {
    "length": "m",
    "area": "m^2",
    "force": "N",
    "torque": "N*m",
    "bending_moment": "N*m",
    "stress": "Pa",
    "pressure": "Pa",
    "modulus": "Pa",
    "angle": "rad",
    "dimensionless": ""
}

# Supported conversion multipliers to canonical SI unit
UNIT_CONVERSIONS: Dict[str, Dict[str, float]] = {
    "length": {
        "m": 1.0,
        "mm": 1e-3,
        "cm": 1e-2,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
    },
    "area": {
        "m^2": 1.0,
        "m2": 1.0,
        "mm^2": 1e-6,
        "mm2": 1e-6,
        "cm^2": 1e-4,
        "cm2": 1e-4,
        "in^2": 0.00064516,
        "in2": 0.00064516,
    },
    "force": {
        "N": 1.0,
        "kN": 1e3,
        "MN": 1e6,
        "lbf": 4.4482216152605,
    },
    "torque": {
        "N*m": 1.0,
        "Nm": 1.0,
        "N.m": 1.0,
        "N·m": 1.0,
        "N*mm": 1e-3,
        "Nmm": 1e-3,
        "kN*m": 1e3,
        "kNm": 1e3,
    },
    "bending_moment": {
        "N*m": 1.0,
        "Nm": 1.0,
        "N.m": 1.0,
        "N·m": 1.0,
        "N*mm": 1e-3,
        "Nmm": 1e-3,
        "kN*m": 1e3,
        "kNm": 1e3,
    },
    "stress": {
        "Pa": 1.0,
        "kPa": 1e3,
        "MPa": 1e6,
        "GPa": 1e9,
        "N/mm^2": 1e6,
        "N/mm2": 1e6,
        "psi": 6894.757293168,
        "ksi": 6.894757293168e6,
    },
    "pressure": {
        "Pa": 1.0,
        "kPa": 1e3,
        "MPa": 1e6,
        "GPa": 1e9,
        "bar": 1e5,
        "psi": 6894.757293168,
    },
    "modulus": {
        "Pa": 1.0,
        "kPa": 1e3,
        "MPa": 1e6,
        "GPa": 1e9,
        "N/mm^2": 1e6,
        "N/mm2": 1e6,
        "psi": 6894.757293168,
        "ksi": 6.894757293168e6,
    },
    "angle": {
        "rad": 1.0,
        "radian": 1.0,
        "radians": 1.0,
        "deg": math.pi / 180.0,
        "degree": math.pi / 180.0,
        "degrees": math.pi / 180.0,
    },
    "dimensionless": {
        "": 1.0,
        "-": 1.0,
        "ratio": 1.0,
        "unitless": 1.0,
    }
}


def clean_unit_string(unit: str) -> str:
    """Standardizes unit strings (removes spaces, normalizes dots)."""
    if not unit:
        return ""
    u = unit.strip()
    u = u.replace("·", "*").replace("⋅", "*")
    return u


def normalize_unit(
    param_name: str,
    value: float,
    unit: Optional[str],
    dimension: str,
    default_unit: Optional[str] = None
) -> Tuple[float, str, UnitConversion]:
    """
    Normalizes a numerical value and unit to standard SI.
    Returns: (normalized_value, normalized_unit, unit_conversion_record)
    Raises: ValueError if unit is unsupported or invalid.
    """
    dim_conversions = UNIT_CONVERSIONS.get(dimension)
    if not dim_conversions:
        raise ValueError(f"Unknown physical dimension '{dimension}' for parameter '{param_name}'.")

    target_si_unit = CANONICAL_SI_UNITS[dimension]

    if unit is None or unit == "":
        if default_unit is not None:
            unit = default_unit
        else:
            unit = target_si_unit

    clean_u = clean_unit_string(unit)

    factor = dim_conversions.get(clean_u)
    matched_unit = clean_u
    if factor is None:
        lower_map = {k.lower(): (k, v) for k, v in dim_conversions.items()}
        match = lower_map.get(clean_u.lower())
        if match:
            matched_unit, factor = match
        else:
            supported = list(dim_conversions.keys())
            raise ValueError(
                f"Unsupported unit '{unit}' for parameter '{param_name}' of dimension '{dimension}'. "
                f"Supported units: {supported}"
            )

    normalized_value = float(value) * factor

    conversion = UnitConversion(
        parameter=param_name,
        original_value=float(value),
        original_unit=matched_unit,
        normalized_value=normalized_value,
        normalized_unit=target_si_unit,
        conversion_factor=factor
    )

    return normalized_value, target_si_unit, conversion


def parse_input_value(
    val: Any,
    default_unit: Optional[str] = None
) -> Tuple[Any, Optional[str]]:
    """
    Parses an input parameter that may be a raw value, a dict with 'value' and 'unit',
    or a tuple/list of (value, unit).
    """
    if isinstance(val, dict):
        if "value" not in val:
            from solvers.validation import SolverValidationError
            raise SolverValidationError("Dictionary input must contain 'value' key.")
        return val["value"], val.get("unit", default_unit)
    elif isinstance(val, (tuple, list)) and len(val) >= 2:
        return val[0], str(val[1])
    else:
        return val, default_unit
