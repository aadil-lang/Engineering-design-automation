"""
Analytical solid circular shaft sizing calculations, torque derivations,
and allowable shear stress resolution.
"""

import math
from typing import Tuple, Optional, List, Dict, Any
from solvers.units import normalize_unit, parse_input_value
from design.derivation import PowerSpeedToTorqueRule
from design.models import DerivedEngineeringValue, RequirementConflict, MissingInformation, MissingImportance
from design_engine.models import ShaftDesignRequirements
from design_engine.config import (
    TORQUE_CONFLICT_TOLERANCE_PCT,
    DISTORTION_ENERGY_SHEAR_FACTOR
)


def resolve_shaft_torque(
    req: ShaftDesignRequirements
) -> Tuple[Optional[float], Optional[DerivedEngineeringValue], Optional[RequirementConflict]]:
    """
    Resolves operating shaft torque from explicit torque or power + rotational speed.
    Detects and reports conflicts if explicit torque diverges from derived torque.
    """
    derived_torque_val: Optional[float] = None
    derived_obj: Optional[DerivedEngineeringValue] = None
    conflict: Optional[RequirementConflict] = None

    # 1. Derive from power and rotational speed if available
    if req.power is not None and req.speed_rpm is not None:
        rule = PowerSpeedToTorqueRule()
        context = {
            "power": req.power,
            "power_unit": req.power_unit or "kW",
            "speed": req.speed_rpm,
            "speed_unit": "RPM"
        }
        if rule.can_derive(context):
            derived_obj = rule.derive(context)
            if derived_obj:
                derived_torque_val = derived_obj.output_value

    # 2. Extract explicit torque
    explicit_torque_val: Optional[float] = None
    if req.torque is not None:
        t_raw, t_unit = parse_input_value(req.torque, default_unit=req.torque_unit or "N*m")
        t_norm, _, _ = normalize_unit("torque", float(t_raw), t_unit, "torque", default_unit="N*m")
        explicit_torque_val = t_norm

    # 3. Check for conflict if both exist
    if explicit_torque_val is not None and derived_torque_val is not None:
        rel_diff = abs(explicit_torque_val - derived_torque_val) / derived_torque_val
        if rel_diff > (TORQUE_CONFLICT_TOLERANCE_PCT / 100.0):
            conflict = RequirementConflict(
                conflict_id="conf-torque-divergence",
                field="torque",
                description=(
                    f"Explicit torque ({explicit_torque_val:.2f} N*m) diverges from torque derived from "
                    f"power ({req.power} {req.power_unit}) and speed ({req.speed_rpm} RPM) "
                    f"({derived_torque_val:.2f} N*m) by {rel_diff * 100:.1f}% "
                    f"(tolerance: {TORQUE_CONFLICT_TOLERANCE_PCT}%)."
                ),
                affected_requirements=["torque", "power", "speed_rpm"],
                requires_human_review=True
            )
            # Retain user-specified torque when explicit, but flag for review
            return explicit_torque_val, derived_obj, conflict

    final_torque = explicit_torque_val if explicit_torque_val is not None else derived_torque_val
    return final_torque, derived_obj, None


def resolve_allowable_stress(
    req: ShaftDesignRequirements
) -> Tuple[Optional[float], Optional[DerivedEngineeringValue], List[str], Optional[MissingInformation]]:
    """
    Deterministically resolves allowable torsional shear stress (Pa).
    Rules:
    - If allowable_shear_stress is provided, normalize and use directly.
    - If yield_strength and (design_factor or minimum_factor_of_safety) are provided,
      derive allowable shear stress via von Mises Distortion Energy Theory:
      tau_allow = (0.57735 * S_y) / n_d.
    - If neither is provided, returns None and a blocking MissingInformation record.
      Never invents or fabricates steel material strength.
    """
    assumptions: List[str] = []

    # Case 1: Explicit allowable shear stress
    if req.allowable_shear_stress is not None:
        raw_val, raw_unit = parse_input_value(
            req.allowable_shear_stress,
            default_unit=req.allowable_shear_stress_unit or "MPa"
        )
        norm_pa, _, _ = normalize_unit("allowable_shear_stress", float(raw_val), raw_unit, "stress", default_unit="MPa")
        return norm_pa, None, assumptions, None

    # Case 2: Derive from yield strength and design factor
    df = req.design_factor or req.minimum_factor_of_safety
    if req.yield_strength is not None and df is not None:
        if df <= 0:
            raise ValueError(f"Design factor must be strictly positive; received {df}.")
        raw_sy, sy_unit = parse_input_value(req.yield_strength, default_unit=req.yield_strength_unit or "MPa")
        sy_pa, _, _ = normalize_unit("yield_strength", float(raw_sy), sy_unit, "stress", default_unit="MPa")

        ssy_pa = DISTORTION_ENERGY_SHEAR_FACTOR * sy_pa
        tau_allow_pa = ssy_pa / df

        sy_mpa = sy_pa / 1e6
        ssy_mpa = ssy_pa / 1e6
        tau_allow_mpa = tau_allow_pa / 1e6

        steps = [
            f"1. Extract tensile yield strength: S_y = {sy_mpa:.2f} MPa",
            f"2. Compute shear yield strength via von Mises distortion energy theory: "
            f"S_sy = 0.57735 * S_y = 0.57735 * {sy_mpa:.2f} MPa = {ssy_mpa:.2f} MPa",
            f"3. Apply design factor: tau_allow = S_sy / n_d = {ssy_mpa:.2f} MPa / {df:.2f} = {tau_allow_mpa:.2f} MPa"
        ]

        assumptions.append(
            f"Allowable torsional shear stress derived from tensile yield strength ({sy_mpa:.1f} MPa) using "
            f"von Mises distortion energy theory (factor = 0.577) with design factor {df:.2f}."
        )

        derived_obj = DerivedEngineeringValue(
            name="allowable_shear_stress",
            formula="tau_allow = (0.57735 * S_y) / n_d",
            inputs={
                "yield_strength": f"{sy_mpa:.2f} MPa",
                "shear_yield_strength_mpa": round(ssy_mpa, 2),
                "design_factor": df
            },
            output_value=round(tau_allow_mpa, 3),
            output_unit="MPa",
            calculation_steps=steps,
            provenance="derived_calculation",
            assumptions=assumptions
        )

        return tau_allow_pa, derived_obj, assumptions, None

    # Case 3: Incomplete material strength data -> BLOCKED
    missing = MissingInformation(
        field="allowable_shear_stress",
        reason="Shaft sizing requires either allowable_shear_stress or tensile yield_strength with design_factor.",
        importance=MissingImportance.REQUIRED_FOR_ANALYSIS,
        blocks_analysis=True,
        suggested_input="Specify allowable_shear_stress (e.g., 50 MPa) or yield_strength with design_factor."
    )
    return None, None, assumptions, missing


def calculate_required_diameter(
    torque_nm: float,
    allowable_shear_stress_pa: float
) -> Tuple[float, float, List[str]]:
    """
    Computes theoretical minimum circular shaft diameter required to withstand torsional shear:
    tau = 16 * T / (pi * d^3)  ==>  d_req = (16 * T / (pi * tau_allow))^(1/3)

    Returns:
        (d_req_meters, d_req_mm, calculation_steps)
    """
    if torque_nm <= 0:
        raise ValueError(f"Torque must be strictly positive for sizing; received {torque_nm} N*m.")
    if allowable_shear_stress_pa <= 0:
        raise ValueError(f"Allowable shear stress must be strictly positive; received {allowable_shear_stress_pa} Pa.")

    cubed_d = (16.0 * torque_nm) / (math.pi * allowable_shear_stress_pa)
    d_req_m = cubed_d ** (1.0 / 3.0)
    d_req_mm = d_req_m * 1e3

    steps = [
        f"1. Transmitted torque: T = {torque_nm:.3f} N*m",
        f"2. Allowable shear stress: tau_allow = {allowable_shear_stress_pa / 1e6:.3f} MPa",
        f"3. Sizing formula: d_req = (16 * T / (pi * tau_allow))^(1/3)",
        f"4. Substitute values: d_req = (16 * {torque_nm:.3f} / (pi * {allowable_shear_stress_pa:.3e}))^(1/3) = {d_req_m:.5f} m ({d_req_mm:.2f} mm)"
    ]

    return d_req_m, d_req_mm, steps
