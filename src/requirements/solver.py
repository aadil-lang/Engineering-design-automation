"""
Deterministic Engineering Calculation Solver for Mechanical Shaft Sizing (Slice 14.3 & 14.5).
Executes closed-form analytical sizing from validated EngineeringSpec inputs.
Applies von Mises distortion energy theory for allowable shear stress,
calculates theoretical minimum required diameter, and deterministically selects
nominal shaft diameter from a configured nominal series via an explicit policy.
"""

import math
from typing import Optional, List, Dict, Any

from requirements.models import (
    EngineeringSpec,
    EngineeringResult,
    RequirementValidationStatus
)
from requirements.validator import validate_engineering_spec
from requirements.diameter_policy import (
    NominalDiameterSelectionPolicy,
    NominalDiameterSelectionResult,
    select_nominal_diameter
)
from design_engine.shaft import calculate_required_diameter

# von Mises distortion energy shear factor: 1 / sqrt(3) ≈ 0.577350269
DISTORTION_ENERGY_SHEAR_FACTOR = 0.5773502691896257

# Standard explicit assumptions for solid circular transmission shafts
ASSUMPTION_SOLID_CIRCULAR = "Shaft is assumed to have a uniform solid circular cross-section."
ASSUMPTION_STATIC_TORSION = "Pure steady-state torsional loading without severe cyclic shock or impact."
ASSUMPTION_NO_STRESS_CONCENTRATION = "Stress concentration factors (e.g. keyways, shoulders) are neglected in preliminary sizing."


class ShaftEngineeringSolver:
    """
    Deterministic mechanical shaft engineering solver.
    Executes pure analytical closed-form sizing without LLM inference, hallucinations,
    or implicit material property defaults.
    """

    def __init__(self, diameter_policy: Optional[NominalDiameterSelectionPolicy] = None):
        self.diameter_policy = diameter_policy or NominalDiameterSelectionPolicy()

    def solve(self, spec: EngineeringSpec) -> EngineeringResult:
        """
        Calculates mechanical shaft metrics from an EngineeringSpec:
        1. Validates presence and physical validity of required parameters.
        2. Computes transmitted torque: T = P / omega.
        3. Computes shear yield strength & allowable shear stress: S_sy = 0.57735 * S_y, tau_allow = S_sy / FoS.
        4. Calculates theoretical required diameter: d_req = (16 * T / (pi * tau_allow))^(1/3).
        5. Selects nominal diameter from configured series via explicit selection policy.
        6. Evaluates design torsional shear stress & achieved factor of safety.
        """
        # 1. Defensive validation
        val_res = validate_engineering_spec(spec)
        errors = list(val_res.errors)
        missing_info = list(val_res.missing_information)
        warnings = list(val_res.warnings)

        # 2. Extract explicit yield strength without hallucination or default fallback
        raw_sy = (
            spec.yield_strength_mpa
            if spec.yield_strength_mpa is not None
            else (
                spec.extra_parameters.get("yield_strength_mpa")
                if spec.extra_parameters.get("yield_strength_mpa") is not None
                else spec.extra_parameters.get("yield_strength")
            )
        )

        yield_strength_mpa: Optional[float] = None
        if raw_sy is None:
            if "yield_strength_mpa" not in missing_info:
                missing_info.append("yield_strength_mpa")
        else:
            if not isinstance(raw_sy, (int, float)) or math.isnan(raw_sy) or math.isinf(raw_sy):
                errors.append(f"Yield strength (yield_strength_mpa) must be a finite number; received {raw_sy}.")
            elif raw_sy <= 0:
                errors.append(f"Yield strength (yield_strength_mpa) must be strictly positive (> 0); received {raw_sy} MPa.")
            else:
                yield_strength_mpa = float(raw_sy)

        # If any validation errors exist, halt immediately with INVALID status
        if errors:
            return EngineeringResult(
                is_valid=False,
                status=RequirementValidationStatus.INVALID,
                spec=spec,
                component=spec.component,
                material=spec.material,
                power_kw=spec.power_kw,
                rpm=spec.rpm,
                factor_of_safety=spec.factor_of_safety,
                length_mm=spec.length_mm,
                yield_strength_mpa=yield_strength_mpa,
                missing_information=missing_info,
                errors=errors,
                warnings=warnings,
                assumptions=[
                    ASSUMPTION_SOLID_CIRCULAR,
                    ASSUMPTION_STATIC_TORSION,
                    ASSUMPTION_NO_STRESS_CONCENTRATION
                ]
            )

        # If any required information is missing, halt immediately with BLOCKED status
        if missing_info:
            return EngineeringResult(
                is_valid=False,
                status=RequirementValidationStatus.BLOCKED,
                spec=spec,
                component=spec.component,
                material=spec.material,
                power_kw=spec.power_kw,
                rpm=spec.rpm,
                factor_of_safety=spec.factor_of_safety,
                length_mm=spec.length_mm,
                yield_strength_mpa=yield_strength_mpa,
                missing_information=missing_info,
                errors=errors,
                warnings=warnings,
                assumptions=[
                    ASSUMPTION_SOLID_CIRCULAR,
                    ASSUMPTION_STATIC_TORSION,
                    ASSUMPTION_NO_STRESS_CONCENTRATION
                ]
            )

        # 3. All inputs verified present and physically valid
        power_kw = spec.power_kw
        rpm = spec.rpm
        fos_req = spec.factor_of_safety
        length_mm = spec.length_mm

        steps: List[str] = []
        assumptions: List[str] = [
            ASSUMPTION_SOLID_CIRCULAR,
            ASSUMPTION_STATIC_TORSION,
            ASSUMPTION_NO_STRESS_CONCENTRATION
        ]

        # 4. Torque calculation: T = P / omega = (P * 1000) / (2 * pi * N / 60)
        omega_rad_s = (2.0 * math.pi * rpm) / 60.0
        power_w = power_kw * 1000.0
        torque_nm = power_w / omega_rad_s

        steps.append(
            f"1. Rotational speed in rad/s: omega = 2 * pi * {rpm:.1f} / 60 = {omega_rad_s:.4f} rad/s"
        )
        steps.append(
            f"2. Transmitted torque: T = P / omega = {power_w:.1f} W / {omega_rad_s:.4f} rad/s = {torque_nm:.3f} N*m"
        )

        # 5. Allowable shear stress calculation via von Mises distortion energy theory
        # S_sy = 0.57735 * S_y,  tau_allow = S_sy / FoS
        shear_yield_strength_mpa = DISTORTION_ENERGY_SHEAR_FACTOR * yield_strength_mpa
        allowable_stress_mpa = shear_yield_strength_mpa / fos_req
        allowable_stress_pa = allowable_stress_mpa * 1e6

        steps.append(
            f"3. Tensile yield strength explicitly supplied: S_y = {yield_strength_mpa:.1f} MPa"
        )
        steps.append(
            f"4. Shear yield strength via von Mises distortion energy theory: "
            f"S_sy = {DISTORTION_ENERGY_SHEAR_FACTOR:.5f} * {yield_strength_mpa:.1f} MPa = {shear_yield_strength_mpa:.2f} MPa"
        )
        steps.append(
            f"5. Allowable shear stress: tau_allow = S_sy / FoS = {shear_yield_strength_mpa:.2f} MPa / {fos_req:.2f} = {allowable_stress_mpa:.2f} MPa"
        )

        # 6. Theoretical minimum diameter calculation
        # tau = 16 * T / (pi * d^3) ==> d_req = (16 * T / (pi * tau_allow))^(1/3)
        d_req_m, d_req_mm, sizing_steps = calculate_required_diameter(torque_nm, allowable_stress_pa)
        steps.extend(sizing_steps)

        # 7. Explicit nominal shaft diameter selection via configured diameter policy (Slice 14.5)
        policy_res = self.diameter_policy.select(d_req_mm)
        if not policy_res.is_supported:
            # Out of series bounds or unsupported diameter
            return EngineeringResult(
                is_valid=False,
                status=RequirementValidationStatus.BLOCKED,
                spec=spec,
                component=spec.component,
                material=spec.material,
                power_kw=power_kw,
                rpm=rpm,
                factor_of_safety=fos_req,
                length_mm=length_mm,
                yield_strength_mpa=yield_strength_mpa,
                torque_nm=round(torque_nm, 3),
                allowable_stress_mpa=round(allowable_stress_mpa, 2),
                minimum_required_diameter_mm=round(d_req_mm, 2),
                selected_diameter_mm=None,
                diameter_selection_policy=policy_res.policy_name,
                diameter_series_used=policy_res.series_used,
                diameter_selection_reason=policy_res.selection_reason,
                missing_information=[],
                errors=[policy_res.error_message or policy_res.selection_reason],
                warnings=[f"Required diameter exceeds maximum configured nominal series diameter ({self.diameter_policy.max_diameter:.1f} mm)."],
                assumptions=assumptions,
                calculation_steps=steps
            )

        selected_d_mm = policy_res.selected_diameter_mm
        selected_d_m = selected_d_mm / 1000.0

        # 8. Design stress evaluation at selected nominal diameter
        # tau_design = 16 * T / (pi * d^3)
        design_stress_pa = (16.0 * torque_nm) / (math.pi * (selected_d_m ** 3))
        design_stress_mpa = design_stress_pa / 1e6

        # 9. Achieved Factor of Safety
        # FoS_achieved = S_sy / tau_design
        achieved_fos = shear_yield_strength_mpa / design_stress_mpa
        is_safe = (design_stress_mpa <= allowable_stress_mpa) and (achieved_fos >= fos_req)

        steps.append(
            f"6. Selected nominal diameter from configured series ({policy_res.policy_name}): "
            f"d_selected = {selected_d_mm:.1f} mm ({policy_res.selection_reason})"
        )
        steps.append(
            f"7. Design torsional shear stress: tau_design = 16 * {torque_nm:.3f} / (pi * ({selected_d_m:.4f})^3) = {design_stress_mpa:.2f} MPa"
        )
        steps.append(
            f"8. Achieved factor of safety: FoS_achieved = {shear_yield_strength_mpa:.2f} MPa / {design_stress_mpa:.2f} MPa = {achieved_fos:.2f} (Required: {fos_req:.2f})"
        )

        return EngineeringResult(
            is_valid=True,
            status=RequirementValidationStatus.VALID,
            spec=spec,
            component=spec.component,
            material=spec.material,
            power_kw=power_kw,
            rpm=rpm,
            factor_of_safety=fos_req,
            length_mm=length_mm,
            yield_strength_mpa=yield_strength_mpa,
            torque_nm=round(torque_nm, 3),
            allowable_stress_mpa=round(allowable_stress_mpa, 2),
            minimum_required_diameter_mm=round(d_req_mm, 2),
            selected_diameter_mm=selected_d_mm,
            design_stress_mpa=round(design_stress_mpa, 2),
            achieved_factor_of_safety=round(achieved_fos, 2),
            is_safe=is_safe,
            diameter_selection_policy=policy_res.policy_name,
            diameter_series_used=policy_res.series_used,
            diameter_selection_reason=policy_res.selection_reason,
            calculation_steps=steps,
            assumptions=assumptions,
            missing_information=[],
            errors=[],
            warnings=[]
        )


def solve_shaft(
    spec: EngineeringSpec,
    diameter_policy: Optional[NominalDiameterSelectionPolicy] = None
) -> EngineeringResult:
    """Convenience function for deterministic shaft sizing from an EngineeringSpec."""
    return ShaftEngineeringSolver(diameter_policy=diameter_policy).solve(spec)


def solve_engineering_spec(
    spec: EngineeringSpec,
    diameter_policy: Optional[NominalDiameterSelectionPolicy] = None
) -> EngineeringResult:
    """General dispatcher for engineering problem solving from an EngineeringSpec."""
    if spec.component and spec.component.lower() in ("shaft", "solid_shaft", "circular_shaft"):
        return solve_shaft(spec, diameter_policy=diameter_policy)

    # Unsupported element
    val_res = validate_engineering_spec(spec)
    return EngineeringResult(
        is_valid=False,
        status=RequirementValidationStatus.INVALID,
        spec=spec,
        missing_information=val_res.missing_information,
        errors=[f"Unsupported component type: '{spec.component}'"] if not val_res.errors else val_res.errors
    )
