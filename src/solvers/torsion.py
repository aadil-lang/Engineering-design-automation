"""
Deterministic solver for circular solid shaft torsion: py_mech_torsion_v1.
"""

import math
from typing import Dict, List, Optional, Any
from solvers.base import MechanicalSolver
from solvers.models import (
    CalculationCertificate,
    CalculationStep,
    CertificateStatus,
    MachineElementType
)
from solvers.units import normalize_unit, parse_input_value
from solvers.validation import (
    validate_required,
    validate_numeric,
    validate_positive,
    validate_non_negative
)


class ShaftTorsionSolver(MechanicalSolver):
    """
    Deterministic closed-form mechanical solver for solid circular shaft torsion.
    Calculates polar moment of inertia, maximum torsional shear stress,
    optional angle of twist, and evaluates safety margin against allowable shear limits.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_torsion_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "shaft_torsion"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.SHAFT

    @property
    def required_inputs(self) -> List[str]:
        return ["torque", "shaft_diameter"]

    @property
    def optional_inputs(self) -> List[str]:
        return ["allowable_shear_stress", "design_factor", "shear_modulus", "shaft_length"]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Solid circular cross-section with uniform diameter along the evaluated section.",
            "Linear elastic, homogeneous, isotropic material behavior.",
            "Idealized Saint-Venant pure torsion with uniform shear distribution across radial fibers.",
            "Cross-sections remain plane and circular without out-of-plane warping."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Closed-form calculation does not account for stress concentrations (keyways, splines, snap ring grooves, shoulder fillets).",
            "Valid only within the elastic proportional limit (no plastic deformation or yield propagation).",
            "Does not evaluate torsional fatigue life, cumulative cyclic damage, or surface finish debit factors.",
            "Does not replace 3D finite element analysis (FEA) where non-uniform geometry or dynamic shock loads occur."
        ]

    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        # 1. Validate required fields
        validate_required(inputs, self.required_inputs)

        conversions = []
        normalized = {}
        calculations: List[CalculationStep] = []
        warnings = []

        # 2. Extract and normalize torque
        raw_t, t_unit = parse_input_value(inputs["torque"], default_unit="N*m")
        t_val = validate_numeric("torque", raw_t)
        t_norm, t_u, conv_t = normalize_unit("torque", t_val, t_unit, "torque", default_unit="N*m")
        normalized["torque"] = t_norm
        conversions.append(conv_t)

        # 3. Extract and normalize shaft diameter
        raw_d, d_unit = parse_input_value(inputs["shaft_diameter"], default_unit="mm")
        d_val = validate_numeric("shaft_diameter", raw_d)
        validate_positive("shaft_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("shaft_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("shaft_diameter", d_norm, d_u)
        normalized["shaft_diameter"] = d_norm
        conversions.append(conv_d)

        # 4. Optional parameters
        allowable_shear_norm: Optional[float] = None
        if "allowable_shear_stress" in inputs and inputs["allowable_shear_stress"] is not None:
            raw_allow, allow_unit = parse_input_value(inputs["allowable_shear_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_shear_stress", raw_allow)
            validate_non_negative("allowable_shear_stress", allow_val, allow_unit or "MPa")
            allowable_shear_norm, _, conv_allow = normalize_unit(
                "allowable_shear_stress", allow_val, allow_unit, "stress", default_unit="MPa"
            )
            normalized["allowable_shear_stress"] = allowable_shear_norm
            conversions.append(conv_allow)

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        shear_modulus_norm: Optional[float] = None
        if "shear_modulus" in inputs and inputs["shear_modulus"] is not None:
            raw_g, g_unit = parse_input_value(inputs["shear_modulus"], default_unit="GPa")
            g_val = validate_numeric("shear_modulus", raw_g)
            validate_positive("shear_modulus", g_val, g_unit or "GPa")
            shear_modulus_norm, _, conv_g = normalize_unit("shear_modulus", g_val, g_unit, "modulus", default_unit="GPa")
            normalized["shear_modulus"] = shear_modulus_norm
            conversions.append(conv_g)

        shaft_length_norm: Optional[float] = None
        if "shaft_length" in inputs and inputs["shaft_length"] is not None:
            raw_l, l_unit = parse_input_value(inputs["shaft_length"], default_unit="mm")
            l_val = validate_numeric("shaft_length", raw_l)
            validate_positive("shaft_length", l_val, l_unit or "mm")
            shaft_length_norm, _, conv_l = normalize_unit("shaft_length", l_val, l_unit, "length", default_unit="mm")
            normalized["shaft_length"] = shaft_length_norm
            conversions.append(conv_l)

        # 5. Core closed-form calculations
        # Step 1: Outer radius
        radius = d_norm / 2.0
        calculations.append(CalculationStep(
            step_id="step_radius",
            description="Shaft outer radius",
            formula="r = d / 2",
            substituted_expression=f"{d_norm:.6g} / 2",
            result=radius,
            unit="m",
            display_result=f"{radius * 1e3:.3f} mm"
        ))

        # Step 2: Polar moment of inertia J = pi * d^4 / 32
        polar_moment = (math.pi * (d_norm ** 4)) / 32.0
        calculations.append(CalculationStep(
            step_id="step_polar_moment",
            description="Polar moment of inertia for solid circular cross-section",
            formula="J = π * d⁴ / 32",
            substituted_expression=f"π * ({d_norm:.6g})⁴ / 32",
            result=polar_moment,
            unit="m⁴",
            display_result=f"{polar_moment:.6e} m⁴"
        ))

        # Step 3: Maximum torsional shear stress tau_max = T * r / J = 16 * T / (pi * d^3)
        abs_torque = abs(t_norm)
        tau_primary = (abs_torque * radius) / polar_moment
        tau_alt = (16.0 * abs_torque) / (math.pi * (d_norm ** 3))

        # Double check numerical equivalence
        if not math.isclose(tau_primary, tau_alt, rel_tol=1e-7):
            warnings.append("Minor numerical divergence detected between Tr/J and 16T/(πd³).")

        calculations.append(CalculationStep(
            step_id="step_shear_stress",
            description="Maximum torsional shear stress on outer shaft fiber",
            formula="τ_max = (T * r) / J = 16 * T / (π * d³)",
            substituted_expression=f"({abs_torque:.6g} * {radius:.6g}) / {polar_moment:.6e}",
            result=tau_primary,
            unit="Pa",
            display_result=f"{tau_primary / 1e6:.3f} MPa"
        ))

        # Step 4 (optional): Twist angle theta = (T * L) / (J * G)
        twist_rad: Optional[float] = None
        twist_deg: Optional[float] = None
        if shear_modulus_norm is not None and shaft_length_norm is not None:
            twist_rad = (t_norm * shaft_length_norm) / (polar_moment * shear_modulus_norm)
            twist_deg = math.degrees(twist_rad)
            calculations.append(CalculationStep(
                step_id="step_twist_angle",
                description="Total angle of torsional twist over shaft length",
                formula="θ = (T * L) / (J * G)",
                substituted_expression=f"({t_norm:.6g} * {shaft_length_norm:.6g}) / ({polar_moment:.6e} * {shear_modulus_norm:.6e})",
                result=twist_rad,
                unit="rad",
                display_result=f"{twist_rad:.5f} rad ({twist_deg:.3f}°)"
            ))

        # 6. Structured results
        results = {
            "torque": t_norm,
            "shaft_diameter": d_norm,
            "shaft_diameter_mm": d_norm * 1e3,
            "radius": radius,
            "polar_moment": polar_moment,
            "shear_stress": tau_primary,
            "shear_stress_mpa": tau_primary / 1e6,
            "twist_angle_rad": twist_rad,
            "twist_angle_deg": twist_deg
        }

        # 7. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="torsional_shear_stress",
            calculated_stress_pa=tau_primary,
            allowable_stress_pa=allowable_shear_norm,
            design_factor=design_factor,
            stress_name="torsional shear stress"
        )
        if assessment.factor_of_safety is not None:
            results["factor_of_safety"] = assessment.factor_of_safety

        prov_map = self._build_provenance_map(inputs, provenance)

        return CalculationCertificate(
            certificate_id=self._generate_certificate_id(),
            solver_id=self.solver_id,
            solver_version=self.solver_version,
            analysis_type=self.analysis_type,
            status=CertificateStatus.SUCCESS,
            machine_element=self.machine_element,
            inputs=inputs,
            normalized_inputs=normalized,
            conversions=conversions,
            calculations=calculations,
            results=results,
            assessments=[assessment],
            assumptions=self.default_assumptions,
            limitations=self.default_limitations,
            warnings=warnings,
            provenance=prov_map
        )
