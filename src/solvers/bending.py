"""
Deterministic solver for circular solid shaft bending stress: py_mech_bending_v1.
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


class ShaftBendingSolver(MechanicalSolver):
    """
    Deterministic closed-form mechanical solver for solid circular shaft bending stress.
    Calculates second moment of area (I), section modulus (Z), maximum normal bending stress,
    and evaluates margin against allowable bending stress limits.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_bending_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "shaft_bending"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.SHAFT

    @property
    def required_inputs(self) -> List[str]:
        return ["bending_moment", "shaft_diameter"]

    @property
    def optional_inputs(self) -> List[str]:
        return ["allowable_bending_stress", "design_factor"]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Solid circular cross-section with uniform diameter across the evaluated region.",
            "Euler-Bernoulli beam formulation applies (plane cross-sections remain plane and normal to the deformed beam axis).",
            "Homogeneous, isotropic, linear elastic material response.",
            "Transverse shear deformation is negligible compared to flexural deformation."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Closed-form beam solution does not model stress concentrations (grooves, fillets, press-fit seats, keyways).",
            "Valid only within the material elastic proportional limit (no plastic yielding or residual stresses).",
            "Assumes pure flexural moment or maximum moment section; does not evaluate transverse shear stress distribution.",
            "Does not replace full 3D finite element analysis (FEA) for short stubby shafts or complex indeterminate supports."
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

        # 2. Extract and normalize bending moment
        raw_m, m_unit = parse_input_value(inputs["bending_moment"], default_unit="N*m")
        m_val = validate_numeric("bending_moment", raw_m)
        m_norm, m_u, conv_m = normalize_unit("bending_moment", m_val, m_unit, "bending_moment", default_unit="N*m")
        normalized["bending_moment"] = m_norm
        conversions.append(conv_m)

        # 3. Extract and normalize shaft diameter
        raw_d, d_unit = parse_input_value(inputs["shaft_diameter"], default_unit="mm")
        d_val = validate_numeric("shaft_diameter", raw_d)
        validate_positive("shaft_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("shaft_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("shaft_diameter", d_norm, d_u)
        normalized["shaft_diameter"] = d_norm
        conversions.append(conv_d)

        # 4. Optional parameters
        allowable_bending_norm: Optional[float] = None
        if "allowable_bending_stress" in inputs and inputs["allowable_bending_stress"] is not None:
            raw_allow, allow_unit = parse_input_value(inputs["allowable_bending_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_bending_stress", raw_allow)
            validate_non_negative("allowable_bending_stress", allow_val, allow_unit or "MPa")
            allowable_bending_norm, _, conv_allow = normalize_unit(
                "allowable_bending_stress", allow_val, allow_unit, "stress", default_unit="MPa"
            )
            normalized["allowable_bending_stress"] = allowable_bending_norm
            conversions.append(conv_allow)

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        # 5. Core closed-form calculations
        # Step 1: Distance to extreme fiber c = d / 2
        c_dist = d_norm / 2.0
        calculations.append(CalculationStep(
            step_id="step_c_distance",
            description="Distance from neutral axis to extreme outer fiber",
            formula="c = d / 2",
            substituted_expression=f"{d_norm:.6g} / 2",
            result=c_dist,
            unit="m",
            display_result=f"{c_dist * 1e3:.3f} mm"
        ))

        # Step 2: Second moment of area I = pi * d^4 / 64
        moment_of_inertia = (math.pi * (d_norm ** 4)) / 64.0
        calculations.append(CalculationStep(
            step_id="step_moment_of_inertia",
            description="Second moment of area (area moment of inertia) for circular section",
            formula="I = π * d⁴ / 64",
            substituted_expression=f"π * ({d_norm:.6g})⁴ / 64",
            result=moment_of_inertia,
            unit="m⁴",
            display_result=f"{moment_of_inertia:.6e} m⁴"
        ))

        # Step 3: Section modulus Z = I / c = pi * d^3 / 32
        section_modulus = (math.pi * (d_norm ** 3)) / 32.0
        calculations.append(CalculationStep(
            step_id="step_section_modulus",
            description="Elastic section modulus for circular cross-section",
            formula="Z = I / c = π * d³ / 32",
            substituted_expression=f"π * ({d_norm:.6g})³ / 32",
            result=section_modulus,
            unit="m³",
            display_result=f"{section_modulus:.6e} m³"
        ))

        # Step 4: Maximum normal bending stress sigma_b = |M| * c / I = |M| / Z = 32 * |M| / (pi * d^3)
        abs_moment = abs(m_norm)
        sigma_b = abs_moment / section_modulus
        sigma_b_alt = (abs_moment * c_dist) / moment_of_inertia

        if not math.isclose(sigma_b, sigma_b_alt, rel_tol=1e-7):
            warnings.append("Minor numerical divergence detected between M/Z and Mc/I.")

        calculations.append(CalculationStep(
            step_id="step_bending_stress",
            description="Maximum normal bending stress on outermost fiber",
            formula="σ_b = (M * c) / I = M / Z = 32 * M / (π * d³)",
            substituted_expression=f"{abs_moment:.6g} / {section_modulus:.6e}",
            result=sigma_b,
            unit="Pa",
            display_result=f"{sigma_b / 1e6:.3f} MPa"
        ))

        # 6. Structured results
        results = {
            "bending_moment": m_norm,
            "shaft_diameter": d_norm,
            "shaft_diameter_mm": d_norm * 1e3,
            "c_distance": c_dist,
            "moment_of_inertia": moment_of_inertia,
            "section_modulus": section_modulus,
            "bending_stress": sigma_b,
            "bending_stress_mpa": sigma_b / 1e6
        }

        # 7. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="bending_normal_stress",
            calculated_stress_pa=sigma_b,
            allowable_stress_pa=allowable_bending_norm,
            design_factor=design_factor,
            stress_name="bending normal stress"
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
