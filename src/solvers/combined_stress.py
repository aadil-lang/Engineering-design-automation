"""
Deterministic solver for combined shaft bending and torsion: py_mech_combined_stress_v1.
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


class ShaftCombinedStressSolver(MechanicalSolver):
    """
    Deterministic closed-form mechanical solver for combined bending and torsion on solid circular shafts.
    Calculates torsional shear, bending normal stress, Von Mises equivalent stress, Tresca maximum shear,
    and principal normal stresses.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_combined_stress_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "shaft_combined_stress"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.SHAFT

    @property
    def required_inputs(self) -> List[str]:
        return ["torque", "bending_moment", "shaft_diameter"]

    @property
    def optional_inputs(self) -> List[str]:
        return [
            "allowable_equivalent_stress",
            "yield_strength",
            "design_factor"
        ]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Bending moment and torsional moment act simultaneously on a critical outer fiber experiencing maximum normal flexural stress.",
            "Linear elastic superposition applies under small strain kinematics.",
            "Plane stress state exists on the outer free boundary surface (radial and transverse through-thickness normal stresses are zero).",
            "Homogeneous, isotropic, ductile material governed by Von Mises (distortion energy) and Tresca (maximum shear) yield theories."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Does not account for geometric notch stress concentrations (stepped shoulders, keyways, transverse oil holes).",
            "Valid only within the elastic regime (linear superposition ceases once local yielding initiates).",
            "Does not account for phase lag, alternating multi-axial fatigue, or out-of-phase cyclic bending-torsion histories.",
            "Does not replace 3D finite element analysis (FEA) for non-uniform shaft geometries or triaxial stress states."
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

        # 3. Extract and normalize bending moment
        raw_m, m_unit = parse_input_value(inputs["bending_moment"], default_unit="N*m")
        m_val = validate_numeric("bending_moment", raw_m)
        m_norm, m_u, conv_m = normalize_unit("bending_moment", m_val, m_unit, "bending_moment", default_unit="N*m")
        normalized["bending_moment"] = m_norm
        conversions.append(conv_m)

        # 4. Extract and normalize shaft diameter
        raw_d, d_unit = parse_input_value(inputs["shaft_diameter"], default_unit="mm")
        d_val = validate_numeric("shaft_diameter", raw_d)
        validate_positive("shaft_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("shaft_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("shaft_diameter", d_norm, d_u)
        normalized["shaft_diameter"] = d_norm
        conversions.append(conv_d)

        # 5. Optional parameters
        allowable_eq_norm: Optional[float] = None
        if "allowable_equivalent_stress" in inputs and inputs["allowable_equivalent_stress"] is not None:
            raw_allow, allow_u = parse_input_value(inputs["allowable_equivalent_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_equivalent_stress", raw_allow)
            validate_non_negative("allowable_equivalent_stress", allow_val, allow_u or "MPa")
            allowable_eq_norm, _, conv_allow = normalize_unit(
                "allowable_equivalent_stress", allow_val, allow_u, "stress", default_unit="MPa"
            )
            normalized["allowable_equivalent_stress"] = allowable_eq_norm
            conversions.append(conv_allow)
        elif "yield_strength" in inputs and inputs["yield_strength"] is not None:
            raw_ys, ys_u = parse_input_value(inputs["yield_strength"], default_unit="MPa")
            ys_val = validate_numeric("yield_strength", raw_ys)
            validate_non_negative("yield_strength", ys_val, ys_u or "MPa")
            allowable_eq_norm, _, conv_ys = normalize_unit(
                "yield_strength", ys_val, ys_u, "stress", default_unit="MPa"
            )
            normalized["yield_strength"] = allowable_eq_norm
            conversions.append(conv_ys)

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        # 6. Core calculations
        # Step 1: Torsional shear stress tau = 16 * |T| / (pi * d^3)
        abs_torque = abs(t_norm)
        tau = (16.0 * abs_torque) / (math.pi * (d_norm ** 3))
        calculations.append(CalculationStep(
            step_id="step_torsional_shear",
            description="Torsional shear stress on outer surface",
            formula="τ = 16 * T / (π * d³)",
            substituted_expression=f"(16 * {abs_torque:.6g}) / (π * ({d_norm:.6g})³)",
            result=tau,
            unit="Pa",
            display_result=f"{tau / 1e6:.3f} MPa"
        ))

        # Step 2: Bending normal stress sigma = 32 * |M| / (pi * d^3)
        abs_moment = abs(m_norm)
        sigma = (32.0 * abs_moment) / (math.pi * (d_norm ** 3))
        calculations.append(CalculationStep(
            step_id="step_bending_stress",
            description="Maximum bending normal stress on outer fiber",
            formula="σ = 32 * M / (π * d³)",
            substituted_expression=f"(32 * {abs_moment:.6g}) / (π * ({d_norm:.6g})³)",
            result=sigma,
            unit="Pa",
            display_result=f"{sigma / 1e6:.3f} MPa"
        ))

        # Step 3: Von Mises equivalent stress sigma_vm = sqrt(sigma^2 + 3 * tau^2)
        sigma_vm = math.sqrt(sigma ** 2 + 3.0 * (tau ** 2))
        calculations.append(CalculationStep(
            step_id="step_von_mises",
            description="Von Mises equivalent (distortion energy) stress",
            formula="σ_vm = √(σ² + 3 * τ²)",
            substituted_expression=f"√(({sigma / 1e6:.4g} MPa)² + 3 * ({tau / 1e6:.4g} MPa)²)",
            result=sigma_vm,
            unit="Pa",
            display_result=f"{sigma_vm / 1e6:.3f} MPa"
        ))

        # Step 4: Tresca maximum shear stress tau_max,Tresca = sqrt((sigma / 2)^2 + tau^2)
        half_sigma = sigma / 2.0
        r_mohr = math.sqrt((half_sigma ** 2) + (tau ** 2))
        tau_tresca = r_mohr
        calculations.append(CalculationStep(
            step_id="step_tresca_shear",
            description="Tresca maximum shear stress (radius of Mohr's circle)",
            formula="τ_max,Tresca = √((σ / 2)² + τ²)",
            substituted_expression=f"√(({half_sigma / 1e6:.4g} MPa)² + ({tau / 1e6:.4g} MPa)²)",
            result=tau_tresca,
            unit="Pa",
            display_result=f"{tau_tresca / 1e6:.3f} MPa"
        ))

        # Step 5: Principal stresses sigma_1, sigma_2 = sigma / 2 +/- sqrt((sigma / 2)^2 + tau^2)
        sigma_1 = half_sigma + r_mohr
        sigma_2 = half_sigma - r_mohr
        calculations.append(CalculationStep(
            step_id="step_principal_stresses",
            description="Principal normal stresses (σ₁, σ₂)",
            formula="σ₁, σ₂ = (σ / 2) ± √((σ / 2)² + τ²)",
            substituted_expression=f"({half_sigma / 1e6:.4g} MPa) ± ({r_mohr / 1e6:.4g} MPa)",
            result=sigma_1,
            unit="Pa",
            display_result=f"σ₁ = {sigma_1 / 1e6:.3f} MPa, σ₂ = {sigma_2 / 1e6:.3f} MPa"
        ))

        # 7. Structured results
        results = {
            "torque": t_norm,
            "bending_moment": m_norm,
            "shaft_diameter": d_norm,
            "shaft_diameter_mm": d_norm * 1e3,
            "torsional_shear_stress": tau,
            "torsional_shear_stress_mpa": tau / 1e6,
            "bending_normal_stress": sigma,
            "bending_normal_stress_mpa": sigma / 1e6,
            "von_mises_stress": sigma_vm,
            "von_mises_stress_mpa": sigma_vm / 1e6,
            "tresca_shear": tau_tresca,
            "tresca_shear_mpa": tau_tresca / 1e6,
            "principal_stress_1": sigma_1,
            "principal_stress_1_mpa": sigma_1 / 1e6,
            "principal_stress_2": sigma_2,
            "principal_stress_2_mpa": sigma_2 / 1e6
        }

        # 8. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="von_mises_equivalent_stress",
            calculated_stress_pa=sigma_vm,
            allowable_stress_pa=allowable_eq_norm,
            design_factor=design_factor,
            stress_name="Von Mises equivalent stress"
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
