"""
Deterministic unit normalization for engineering requirements and operating conditions.
Reuses and extends solver unit utilities for power, speed, torque, forces, and dimensions.
"""

import math
from typing import Tuple, Optional, Dict
from solvers.units import normalize_unit, clean_unit_string, CANONICAL_SI_UNITS, UNIT_CONVERSIONS
from design.models import EngineeringQuantity

# Power conversions to Watts (W)
POWER_CONVERSIONS: Dict[str, float] = {
    "w": 1.0,
    "watt": 1.0,
    "watts": 1.0,
    "kw": 1e3,
    "kilowatt": 1e3,
    "kilowatts": 1e3,
    "mw": 1e6,
    "megawatt": 1e6,
    "hp": 745.699872,
    "horsepower": 745.699872
}

# Rotational speed conversions to RPM
SPEED_CONVERSIONS_TO_RPM: Dict[str, float] = {
    "rpm": 1.0,
    "rev/min": 1.0,
    "revolutions/min": 1.0,
    "rad/s": 60.0 / (2.0 * math.pi),
    "rad/sec": 60.0 / (2.0 * math.pi),
    "hz": 60.0,
    "rps": 60.0,
    "rev/s": 60.0
}


def normalize_power(value: float, unit: str) -> Tuple[float, str, float]:
    """
    Normalizes a power quantity to Watts (W).
    Returns: (normalized_watts, "W", conversion_factor)
    """
    clean_u = clean_unit_string(unit).lower()
    factor = POWER_CONVERSIONS.get(clean_u)
    if factor is None:
        raise ValueError(f"Unsupported power unit '{unit}'. Supported: {list(POWER_CONVERSIONS.keys())}")
    norm_val = float(value) * factor
    return norm_val, "W", factor


def normalize_rotational_speed(value: float, unit: str) -> Tuple[float, str, float, str]:
    """
    Normalizes rotational speed to standard RPM and angular velocity rad/s.
    Returns: (rpm_value, "RPM", rad_s_value, "rad/s")
    """
    clean_u = clean_unit_string(unit).lower()
    factor_to_rpm = SPEED_CONVERSIONS_TO_RPM.get(clean_u)
    if factor_to_rpm is None:
        raise ValueError(f"Unsupported rotational speed unit '{unit}'. Supported: {list(SPEED_CONVERSIONS_TO_RPM.keys())}")
    rpm_val = float(value) * factor_to_rpm
    rad_s_val = rpm_val * (2.0 * math.pi / 60.0)
    return rpm_val, "RPM", rad_s_val, "rad/s"


def normalize_quantity_data(
    value: float,
    unit: str,
    dimension: str
) -> Tuple[float, str]:
    """
    General deterministic normalization across mechanical dimensions.
    Returns: (normalized_value, canonical_unit)
    """
    clean_u = clean_unit_string(unit)
    dim_lower = dimension.lower()

    if dim_lower in ("power",):
        norm_v, norm_u, _ = normalize_power(value, clean_u)
        return norm_v, norm_u

    if dim_lower in ("speed", "rotational_speed"):
        rpm_v, _, _, _ = normalize_rotational_speed(value, clean_u)
        return rpm_v, "RPM"

    # Use standard solver dimension conversions
    norm_v, norm_u, _ = normalize_unit(dimension, value, clean_u, dim_lower)
    return norm_v, norm_u
