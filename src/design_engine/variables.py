"""
Design Variable management and validation for mechanical parametric optimization.
"""

from typing import Optional
from design_engine.models import DesignVariable
from design_engine.config import (
    DEFAULT_DIAMETER_MIN_MM,
    DEFAULT_DIAMETER_MAX_MM,
    DEFAULT_DIAMETER_STEP_MM
)


def create_shaft_diameter_variable(
    diameter_min: Optional[float] = None,
    diameter_max: Optional[float] = None,
    diameter_step: Optional[float] = None,
    preferred_value: Optional[float] = None
) -> DesignVariable:
    """
    Creates and validates a DesignVariable specifically for shaft diameter.
    Enforces positive bounds, upper_bound >= lower_bound, positive steps,
    and tracks assumption provenance when default search brackets are used.
    """
    is_assumed = False
    rationales = []

    # 1. Lower Bound
    if diameter_min is not None:
        lb = float(diameter_min)
        if lb <= 0:
            raise ValueError(f"Shaft diameter lower bound must be strictly positive; received {lb}.")
    else:
        lb = DEFAULT_DIAMETER_MIN_MM
        is_assumed = True
        rationales.append(f"Minimum diameter defaulted to {lb} mm.")

    # 2. Upper Bound
    if diameter_max is not None:
        ub = float(diameter_max)
        if ub < lb:
            raise ValueError(f"Shaft diameter upper bound ({ub} mm) cannot be less than lower bound ({lb} mm).")
    else:
        ub = DEFAULT_DIAMETER_MAX_MM
        is_assumed = True
        rationales.append(f"Maximum diameter defaulted to {ub} mm.")

    # 3. Step Increment
    if diameter_step is not None:
        st = float(diameter_step)
        if st <= 0:
            raise ValueError(f"Shaft diameter search step must be strictly positive; received {st}.")
    else:
        st = DEFAULT_DIAMETER_STEP_MM
        is_assumed = True
        rationales.append(f"Diameter search step defaulted to {st} mm.")

    rationale_str = "; ".join(rationales) if rationales else None

    return DesignVariable(
        name="shaft_diameter",
        value=float(preferred_value) if preferred_value is not None else None,
        unit="mm",
        lower_bound=lb,
        upper_bound=ub,
        step=st,
        source="user_input" if not is_assumed else "assumed_default",
        is_assumed=is_assumed,
        rationale=rationale_str
    )
