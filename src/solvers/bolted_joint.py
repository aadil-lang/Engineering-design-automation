"""
Deterministic analytical solvers for bolted joint machine elements:
- BoltTensionSolver: py_mech_bolt_tension_v1
- BoltShearSolver: py_mech_bolt_shear_v1
- BoltCombinedStressSolver: py_mech_bolt_combined_stress_v1
- BoltPreloadSolver: py_mech_bolt_preload_v1
"""

import math
from typing import Dict, List, Optional, Any
from solvers.base import MechanicalSolver
from solvers.models import (
    CalculationCertificate,
    CalculationStep,
    CertificateStatus,
    AssessmentResult,
    AssessmentStatus,
    MachineElementType,
    EngineeringAssumption,
    InputProvenance
)
from solvers.units import normalize_unit, parse_input_value
from solvers.validation import (
    validate_required,
    validate_numeric,
    validate_positive,
    validate_non_negative,
    validate_integer_positive,
    SolverValidationError
)


class BoltTensionSolver(MechanicalSolver):
    """
    Deterministic closed-form solver for threaded bolt axial tension.
    Calculates tensile stress area, average tensile normal stress, and margin against allowable limits.
    Distinguishes explicitly supplied tensile area, derived pitch approximation, and nominal approximation.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_bolt_tension_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "bolt_tension"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.BOLTED_JOINT

    @property
    def required_inputs(self) -> List[str]:
        return ["bolt_diameter", "tensile_load"]

    @property
    def optional_inputs(self) -> List[str]:
        return [
            "tensile_stress_area",
            "thread_pitch",
            "pitch",
            "num_bolts",
            "allowable_tensile_stress",
            "yield_strength",
            "design_factor"
        ]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Pure concentric axial tensile loading acting symmetrically along the bolt longitudinal centerline.",
            "Uniform tensile stress distribution across the threaded tensile stress area.",
            "Homogeneous, isotropic, linear elastic fastener material response.",
            "Bending induced by flange prying or non-parallel contact faces is assumed negligible."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Does not account for thread root notch stress concentrations or thread shear stripping.",
            "Does not model prying forces, joint separation, or flange stiffness interaction.",
            "Valid only within the elastic regime below the fastener yield/proof limit.",
            "Does not replace finite element analysis (FEA) or ASME/VDI 2230 joint analysis for critical joints."
        ]

    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        validate_required(inputs, self.required_inputs)

        conversions = []
        normalized = {}
        calculations: List[CalculationStep] = []
        warnings = []
        assumed_prov: Dict[str, InputProvenance] = {}
        tracked_assumptions: List[EngineeringAssumption] = []
        active_assumptions = list(self.default_assumptions)

        # 1. Normalize bolt diameter
        raw_d, d_unit = parse_input_value(inputs["bolt_diameter"], default_unit="mm")
        d_val = validate_numeric("bolt_diameter", raw_d)
        validate_positive("bolt_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("bolt_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("bolt_diameter", d_norm, d_u)
        normalized["bolt_diameter"] = d_norm
        conversions.append(conv_d)

        # 2. Normalize tensile load
        raw_ft, ft_unit = parse_input_value(inputs["tensile_load"], default_unit="N")
        ft_val = validate_numeric("tensile_load", raw_ft)
        validate_non_negative("tensile_load", ft_val, ft_unit or "N")
        ft_norm, _, conv_ft = normalize_unit("tensile_load", ft_val, ft_unit, "force", default_unit="N")
        normalized["tensile_load"] = ft_norm
        conversions.append(conv_ft)

        # 3. Number of bolts
        num_bolts = 1
        if "num_bolts" in inputs and inputs["num_bolts"] is not None:
            raw_nb, _ = parse_input_value(inputs["num_bolts"], default_unit="")
            num_bolts = validate_integer_positive("num_bolts", raw_nb)
            num_bolts_assumed = False
        else:
            num_bolts_assumed = True
            assumed_prov["num_bolts"] = InputProvenance(
                value=1,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale="Single bolt assumed (num_bolts=1) carrying full tensile load"
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="num_bolts",
                value=1,
                category="assumed_default",
                rationale="Single bolt assumed (num_bolts=1) carrying full tensile load",
                is_user_provided=False
            ))
        normalized["num_bolts"] = float(num_bolts)

        # 4. Tensile stress area (strictly distinguishing user-supplied, derived from pitch, and nominal approximation)
        at_norm: float
        area_method: str
        area_assumed: bool

        if "tensile_stress_area" in inputs and inputs["tensile_stress_area"] is not None:
            area_method = "explicitly_supplied"
            area_assumed = False
            raw_at, at_u = parse_input_value(inputs["tensile_stress_area"], default_unit="mm^2")
            at_val = validate_numeric("tensile_stress_area", raw_at)
            validate_positive("tensile_stress_area", at_val, at_u or "mm^2")
            at_norm, _, conv_at = normalize_unit("tensile_stress_area", at_val, at_u, "area", default_unit="mm^2")
            conversions.append(conv_at)
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Explicitly supplied fastener tensile stress area",
                formula="A_t (user supplied)",
                substituted_expression=f"{at_val} {at_u or 'mm^2'}",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))
        elif ("thread_pitch" in inputs and inputs["thread_pitch"] is not None) or ("pitch" in inputs and inputs["pitch"] is not None):
            area_method = "derived_approximation"
            area_assumed = True
            raw_p = inputs.get("thread_pitch") if inputs.get("thread_pitch") is not None else inputs.get("pitch")
            raw_p_val, p_u = parse_input_value(raw_p, default_unit="mm")
            p_val = validate_numeric("thread_pitch", raw_p_val)
            validate_positive("thread_pitch", p_val, p_u or "mm")
            p_norm, _, conv_p = normalize_unit("thread_pitch", p_val, p_u, "length", default_unit="mm")
            conversions.append(conv_p)
            normalized["thread_pitch"] = p_norm

            # Derived metric coarse-thread formula: A_t ≈ 0.7854 * (d - 0.9382 * p)^2
            d_mm = d_norm * 1e3
            p_mm = p_norm * 1e3
            at_mm2 = 0.7854 * ((d_mm - 0.9382 * p_mm) ** 2)
            at_norm = at_mm2 * 1e-6

            rationale_text = "Metric coarse-thread geometric approximation At ≈ 0.7854*(d - 0.9382*p)^2 based on supplied pitch p; approximate geometric model, not certified against standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_mm2, 2),
                unit="mm^2",
                source="derived_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="derived_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area derived from thread pitch p using approximate formula At ≈ 0.7854*(d - 0.9382*p)^2; does not claim exact standards table certification."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (derived approximation from pitch p)",
                formula="A_t ≈ 0.7854 * (d - 0.9382 * p)²",
                substituted_expression=f"0.7854 * ({d_mm:.4g} mm - 0.9382 * {p_mm:.4g} mm)²",
                result=at_norm,
                unit="m²",
                display_result=f"{at_mm2:.2f} mm²"
            ))
        else:
            # Nominal geometric approximation: A_t ≈ 0.78 * A_gross
            area_method = "nominal_geometric_approximation"
            area_assumed = True
            gross_area = (math.pi * (d_norm ** 2)) / 4.0
            at_norm = 0.78 * gross_area
            rationale_text = "Nominal geometric reduction At ≈ 0.78 * (pi * d^2 / 4) in the absence of explicit thread pitch or standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_norm * 1e6, 2),
                unit="mm^2",
                source="nominal_geometric_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="nominal_geometric_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area estimated using nominal geometric reduction (At ≈ 0.78 * gross area); actual thread geometry not supplied."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (nominal geometric approximation At ≈ 0.78 * Agross)",
                formula="A_t ≈ 0.78 * (π * d² / 4)",
                substituted_expression=f"0.78 * (π * ({d_norm:.6g})² / 4)",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))

        normalized["tensile_stress_area"] = at_norm

        # 5. Optional allowable stress or yield strength
        allowable_norm: Optional[float] = None
        if "allowable_tensile_stress" in inputs and inputs["allowable_tensile_stress"] is not None:
            raw_allow, allow_u = parse_input_value(inputs["allowable_tensile_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_tensile_stress", raw_allow)
            validate_non_negative("allowable_tensile_stress", allow_val, allow_u or "MPa")
            allowable_norm, _, conv_allow = normalize_unit(
                "allowable_tensile_stress", allow_val, allow_u, "stress", default_unit="MPa"
            )
            conversions.append(conv_allow)
            normalized["allowable_tensile_stress"] = allowable_norm
        elif "yield_strength" in inputs and inputs["yield_strength"] is not None:
            raw_ys, ys_u = parse_input_value(inputs["yield_strength"], default_unit="MPa")
            ys_val = validate_numeric("yield_strength", raw_ys)
            validate_non_negative("yield_strength", ys_val, ys_u or "MPa")
            allowable_norm, _, conv_ys = normalize_unit(
                "yield_strength", ys_val, ys_u, "stress", default_unit="MPa"
            )
            conversions.append(conv_ys)
            normalized["yield_strength"] = allowable_norm

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        # 6. Total effective tensile area across all bolts: A_total = num_bolts * A_t
        total_tensile_area = num_bolts * at_norm
        if num_bolts > 1:
            calculations.append(CalculationStep(
                step_id="step_total_tensile_area",
                description="Total tensile stress area across all bolts",
                formula="A_total = n * A_t",
                substituted_expression=f"{num_bolts} * {at_norm:.6e} m²",
                result=total_tensile_area,
                unit="m²",
                display_result=f"{total_tensile_area * 1e6:.2f} mm²"
            ))

        # 7. Core calculation: sigma_t = F_t / (n * A_t)
        sigma_t = ft_norm / total_tensile_area
        calculations.append(CalculationStep(
            step_id="step_tensile_stress",
            description="Tensile nominal normal stress in threaded bolt(s)",
            formula="σ_t = F_t / (n * A_t)",
            substituted_expression=f"{ft_norm:.6g} N / {total_tensile_area:.6e} m²",
            result=sigma_t,
            unit="Pa",
            display_result=f"{sigma_t / 1e6:.3f} MPa"
        ))

        # 8. Structured results
        results = {
            "bolt_diameter": d_norm,
            "bolt_diameter_mm": d_norm * 1e3,
            "tensile_load": ft_norm,
            "num_bolts": num_bolts,
            "num_bolts_assumed": num_bolts_assumed,
            "tensile_stress_area": at_norm,
            "tensile_stress_area_mm2": at_norm * 1e6,
            "tensile_stress_area_method": area_method,
            "tensile_stress_area_assumed": area_assumed,
            "tensile_stress": sigma_t,
            "tensile_stress_mpa": sigma_t / 1e6
        }

        # 9. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="bolt_tensile_stress",
            calculated_stress_pa=sigma_t,
            allowable_stress_pa=allowable_norm,
            design_factor=design_factor,
            stress_name="bolt tensile stress"
        )
        if assessment.factor_of_safety is not None:
            results["factor_of_safety"] = assessment.factor_of_safety

        prov_map = self._build_provenance_map(inputs, provenance, assumed_provenance=assumed_prov)

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
            assumptions=active_assumptions,
            tracked_assumptions=tracked_assumptions,
            limitations=self.default_limitations,
            warnings=warnings,
            provenance=prov_map
        )


class BoltShearSolver(MechanicalSolver):
    """
    Deterministic closed-form solver for bolt direct shear.
    Calculates effective shear area across single or multiple shear planes,
    average shear stress, and margin against allowable shear limits.
    Distinguishes user-provided shear planes and bolt counts from assumed defaults.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_bolt_shear_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "bolt_shear"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.BOLTED_JOINT

    @property
    def required_inputs(self) -> List[str]:
        return ["bolt_diameter", "shear_load"]

    @property
    def optional_inputs(self) -> List[str]:
        return [
            "shear_planes",
            "num_bolts",
            "threads_in_shear_plane",
            "allowable_shear_stress",
            "design_factor"
        ]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Direct transverse shear load distributed uniformly across all declared shear planes.",
            "Shear plane passes through unthreaded bolt shank (cross-sectional area = π*d²/4).",
            "Equal load sharing without eccentric bending or hole edge localized bearing deformation.",
            "Linear elastic material response under pure transverse shear."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Does not account for shear plane passing through bolt threads unless explicitly specified.",
            "Does not model plate hole bearing stress, tear-out, or fastener hole clearance slip.",
            "Does not account for friction grip load transfer provided by bolt pre-tension.",
            "Does not replace complex multi-fastener elastic-plastic joint analysis."
        ]

    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        validate_required(inputs, self.required_inputs)

        conversions = []
        normalized = {}
        calculations: List[CalculationStep] = []
        warnings = []
        assumed_prov: Dict[str, InputProvenance] = {}
        tracked_assumptions: List[EngineeringAssumption] = []
        active_assumptions = list(self.default_assumptions)

        # 1. Normalize bolt diameter
        raw_d, d_unit = parse_input_value(inputs["bolt_diameter"], default_unit="mm")
        d_val = validate_numeric("bolt_diameter", raw_d)
        validate_positive("bolt_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("bolt_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("bolt_diameter", d_norm, d_u)
        normalized["bolt_diameter"] = d_norm
        conversions.append(conv_d)

        # 2. Normalize shear load
        raw_v, v_unit = parse_input_value(inputs["shear_load"], default_unit="N")
        v_val = validate_numeric("shear_load", raw_v)
        validate_non_negative("shear_load", v_val, v_unit or "N")
        v_norm, _, conv_v = normalize_unit("shear_load", v_val, v_unit, "force", default_unit="N")
        normalized["shear_load"] = v_norm
        conversions.append(conv_v)

        # 3. Shear planes (distinguish user-provided from assumed default)
        shear_planes = 1
        shear_planes_assumed = True
        if "shear_planes" in inputs and inputs["shear_planes"] is not None:
            raw_sp, _ = parse_input_value(inputs["shear_planes"], default_unit="")
            shear_planes = validate_integer_positive("shear_planes", raw_sp)
            shear_planes_assumed = False
        else:
            assumed_prov["shear_planes"] = InputProvenance(
                value=1,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale="Single shear plane assumed (shear_planes=1)"
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="shear_planes",
                value=1,
                category="assumed_default",
                rationale="Single shear plane assumed (shear_planes=1)",
                is_user_provided=False
            ))
        normalized["shear_planes"] = float(shear_planes)

        # 4. Number of bolts
        num_bolts = 1
        num_bolts_assumed = True
        if "num_bolts" in inputs and inputs["num_bolts"] is not None:
            raw_nb, _ = parse_input_value(inputs["num_bolts"], default_unit="")
            num_bolts = validate_integer_positive("num_bolts", raw_nb)
            num_bolts_assumed = False
        else:
            assumed_prov["num_bolts"] = InputProvenance(
                value=1,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale="Single bolt assumed (num_bolts=1) carrying full shear load"
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="num_bolts",
                value=1,
                category="assumed_default",
                rationale="Single bolt assumed (num_bolts=1) carrying full shear load",
                is_user_provided=False
            ))
        normalized["num_bolts"] = float(num_bolts)

        # 5. Optional allowable shear stress
        allowable_shear_norm: Optional[float] = None
        if "allowable_shear_stress" in inputs and inputs["allowable_shear_stress"] is not None:
            raw_allow, allow_u = parse_input_value(inputs["allowable_shear_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_shear_stress", raw_allow)
            validate_non_negative("allowable_shear_stress", allow_val, allow_u or "MPa")
            allowable_shear_norm, _, conv_allow = normalize_unit(
                "allowable_shear_stress", allow_val, allow_u, "stress", default_unit="MPa"
            )
            conversions.append(conv_allow)
            normalized["allowable_shear_stress"] = allowable_shear_norm

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        # 6. Core calculation
        # Step 1: Single bolt shank area A = pi * d^2 / 4
        single_area = (math.pi * (d_norm ** 2)) / 4.0
        calculations.append(CalculationStep(
            step_id="step_single_shear_area",
            description="Cross-sectional area of single unthreaded bolt shank",
            formula="A = π * d² / 4",
            substituted_expression=f"π * ({d_norm:.6g})² / 4",
            result=single_area,
            unit="m²",
            display_result=f"{single_area * 1e6:.2f} mm²"
        ))

        # Step 2: Effective shear area A_eff = n * m * A
        total_interfaces = shear_planes * num_bolts
        effective_area = total_interfaces * single_area
        calculations.append(CalculationStep(
            step_id="step_effective_shear_area",
            description="Total effective shear area across all bolts and shear planes",
            formula="A_eff = n_bolts * n_planes * A",
            substituted_expression=f"{num_bolts} * {shear_planes} * {single_area:.6e} m²",
            result=effective_area,
            unit="m²",
            display_result=f"{effective_area * 1e6:.2f} mm²"
        ))

        # Step 3: Average shear stress tau = V / A_eff
        tau = v_norm / effective_area
        calculations.append(CalculationStep(
            step_id="step_shear_stress",
            description="Average direct transverse shear stress in bolt(s)",
            formula="τ = V / A_eff",
            substituted_expression=f"{v_norm:.6g} N / {effective_area:.6e} m²",
            result=tau,
            unit="Pa",
            display_result=f"{tau / 1e6:.3f} MPa"
        ))

        # 7. Structured results
        results = {
            "bolt_diameter": d_norm,
            "bolt_diameter_mm": d_norm * 1e3,
            "shear_load": v_norm,
            "shear_planes": shear_planes,
            "shear_planes_assumed": shear_planes_assumed,
            "num_bolts": num_bolts,
            "num_bolts_assumed": num_bolts_assumed,
            "single_shear_area": single_area,
            "single_shear_area_mm2": single_area * 1e6,
            "effective_shear_area": effective_area,
            "effective_shear_area_mm2": effective_area * 1e6,
            "shear_stress": tau,
            "shear_stress_mpa": tau / 1e6
        }

        # 8. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="bolt_shear_stress",
            calculated_stress_pa=tau,
            allowable_stress_pa=allowable_shear_norm,
            design_factor=design_factor,
            stress_name="bolt shear stress"
        )
        if assessment.factor_of_safety is not None:
            results["factor_of_safety"] = assessment.factor_of_safety

        prov_map = self._build_provenance_map(inputs, provenance, assumed_provenance=assumed_prov)

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
            assumptions=active_assumptions,
            tracked_assumptions=tracked_assumptions,
            limitations=self.default_limitations,
            warnings=warnings,
            provenance=prov_map
        )


class BoltCombinedStressSolver(MechanicalSolver):
    """
    Deterministic solver for combined axial tension and direct shear on a threaded fastener.
    Calculates tensile stress, transverse shear stress, Von Mises equivalent stress,
    and evaluates margin against allowable equivalent stress limits.
    Distinguishes user-provided inputs from assumed parameters and approximations.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_bolt_combined_stress_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "bolt_combined_stress"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.BOLTED_JOINT

    @property
    def required_inputs(self) -> List[str]:
        return ["bolt_diameter", "tensile_load", "shear_load"]

    @property
    def optional_inputs(self) -> List[str]:
        return [
            "tensile_stress_area",
            "thread_pitch",
            "pitch",
            "shear_planes",
            "num_bolts",
            "allowable_equivalent_stress",
            "yield_strength",
            "design_factor"
        ]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Simultaneous action of axial tensile force and direct transverse shear load on the fastener.",
            "Distortion Energy (Von Mises) failure criterion governs multi-axial yielding in ductile steel bolts.",
            "Linear elastic superposition holds under static loading.",
            "Frictional slip resistance between joint clamping faces is not counted."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Does not account for thread root stress concentrations or interaction between torque-induced twist and tension.",
            "Valid only within the elastic regime below the material yield strength.",
            "Does not model cyclic fatigue loading under combined fluctuating tension-shear spectra.",
            "Does not replace comprehensive VDI 2230 bolted joint design standards."
        ]

    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        validate_required(inputs, self.required_inputs)

        conversions = []
        normalized = {}
        calculations: List[CalculationStep] = []
        warnings = []
        assumed_prov: Dict[str, InputProvenance] = {}
        tracked_assumptions: List[EngineeringAssumption] = []
        active_assumptions = list(self.default_assumptions)

        # 1. Normalize bolt diameter
        raw_d, d_unit = parse_input_value(inputs["bolt_diameter"], default_unit="mm")
        d_val = validate_numeric("bolt_diameter", raw_d)
        validate_positive("bolt_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("bolt_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("bolt_diameter", d_norm, d_u)
        normalized["bolt_diameter"] = d_norm
        conversions.append(conv_d)

        # 2. Normalize tensile load
        raw_ft, ft_unit = parse_input_value(inputs["tensile_load"], default_unit="N")
        ft_val = validate_numeric("tensile_load", raw_ft)
        validate_non_negative("tensile_load", ft_val, ft_unit or "N")
        ft_norm, _, conv_ft = normalize_unit("tensile_load", ft_val, ft_unit, "force", default_unit="N")
        normalized["tensile_load"] = ft_norm
        conversions.append(conv_ft)

        # 3. Normalize shear load
        raw_v, v_unit = parse_input_value(inputs["shear_load"], default_unit="N")
        v_val = validate_numeric("shear_load", raw_v)
        validate_non_negative("shear_load", v_val, v_unit or "N")
        v_norm, _, conv_v = normalize_unit("shear_load", v_val, v_unit, "force", default_unit="N")
        normalized["shear_load"] = v_norm
        conversions.append(conv_v)

        # 4. Number of bolts
        num_bolts = 1
        num_bolts_assumed = True
        if "num_bolts" in inputs and inputs["num_bolts"] is not None:
            raw_nb, _ = parse_input_value(inputs["num_bolts"], default_unit="")
            num_bolts = validate_integer_positive("num_bolts", raw_nb)
            num_bolts_assumed = False
        else:
            assumed_prov["num_bolts"] = InputProvenance(
                value=1,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale="Single bolt assumed (num_bolts=1)"
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="num_bolts",
                value=1,
                category="assumed_default",
                rationale="Single bolt assumed (num_bolts=1)",
                is_user_provided=False
            ))
        normalized["num_bolts"] = float(num_bolts)

        # 5. Tensile stress area
        at_norm: float
        area_method: str
        area_assumed: bool

        if "tensile_stress_area" in inputs and inputs["tensile_stress_area"] is not None:
            area_method = "explicitly_supplied"
            area_assumed = False
            raw_at, at_u = parse_input_value(inputs["tensile_stress_area"], default_unit="mm^2")
            at_val = validate_numeric("tensile_stress_area", raw_at)
            validate_positive("tensile_stress_area", at_val, at_u or "mm^2")
            at_norm, _, conv_at = normalize_unit("tensile_stress_area", at_val, at_u, "area", default_unit="mm^2")
            conversions.append(conv_at)
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Explicitly supplied fastener tensile stress area",
                formula="A_t (user supplied)",
                substituted_expression=f"{at_val} {at_u or 'mm^2'}",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))
        elif ("thread_pitch" in inputs and inputs["thread_pitch"] is not None) or ("pitch" in inputs and inputs["pitch"] is not None):
            area_method = "derived_approximation"
            area_assumed = True
            raw_p = inputs.get("thread_pitch") if inputs.get("thread_pitch") is not None else inputs.get("pitch")
            raw_p_val, p_u = parse_input_value(raw_p, default_unit="mm")
            p_val = validate_numeric("thread_pitch", raw_p_val)
            validate_positive("thread_pitch", p_val, p_u or "mm")
            p_norm, _, conv_p = normalize_unit("thread_pitch", p_val, p_u, "length", default_unit="mm")
            conversions.append(conv_p)
            normalized["thread_pitch"] = p_norm

            d_mm = d_norm * 1e3
            p_mm = p_norm * 1e3
            at_mm2 = 0.7854 * ((d_mm - 0.9382 * p_mm) ** 2)
            at_norm = at_mm2 * 1e-6

            rationale_text = "Metric coarse-thread geometric approximation At ≈ 0.7854*(d - 0.9382*p)^2 based on supplied pitch; approximate geometric model, not certified against standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_mm2, 2),
                unit="mm^2",
                source="derived_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="derived_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area derived from thread pitch p using approximate formula At ≈ 0.7854*(d - 0.9382*p)^2; does not claim exact standards table certification."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (derived approximation from pitch p)",
                formula="A_t ≈ 0.7854 * (d - 0.9382 * p)²",
                substituted_expression=f"0.7854 * ({d_mm:.4g} mm - 0.9382 * {p_mm:.4g} mm)²",
                result=at_norm,
                unit="m²",
                display_result=f"{at_mm2:.2f} mm²"
            ))
        else:
            area_method = "nominal_geometric_approximation"
            area_assumed = True
            gross_area = (math.pi * (d_norm ** 2)) / 4.0
            at_norm = 0.78 * gross_area
            rationale_text = "Nominal geometric reduction At ≈ 0.78 * (pi * d^2 / 4) in the absence of explicit thread pitch or standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_norm * 1e6, 2),
                unit="mm^2",
                source="nominal_geometric_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="nominal_geometric_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area estimated using nominal geometric reduction (At ≈ 0.78 * gross area); actual thread geometry not supplied."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (nominal geometric approximation At ≈ 0.78 * Agross)",
                formula="A_t ≈ 0.78 * (π * d² / 4)",
                substituted_expression=f"0.78 * (π * ({d_norm:.6g})² / 4)",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))

        normalized["tensile_stress_area"] = at_norm

        # 6. Shear planes
        shear_planes = 1
        shear_planes_assumed = True
        if "shear_planes" in inputs and inputs["shear_planes"] is not None:
            raw_sp, _ = parse_input_value(inputs["shear_planes"], default_unit="")
            shear_planes = validate_integer_positive("shear_planes", raw_sp)
            shear_planes_assumed = False
        else:
            assumed_prov["shear_planes"] = InputProvenance(
                value=1,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale="Single shear plane assumed (shear_planes=1)"
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="shear_planes",
                value=1,
                category="assumed_default",
                rationale="Single shear plane assumed (shear_planes=1)",
                is_user_provided=False
            ))
        normalized["shear_planes"] = float(shear_planes)

        single_area = (math.pi * (d_norm ** 2)) / 4.0
        effective_shear_area = shear_planes * num_bolts * single_area

        # 7. Optional allowable limits
        allowable_eq_norm: Optional[float] = None
        if "allowable_equivalent_stress" in inputs and inputs["allowable_equivalent_stress"] is not None:
            raw_allow, allow_u = parse_input_value(inputs["allowable_equivalent_stress"], default_unit="MPa")
            allow_val = validate_numeric("allowable_equivalent_stress", raw_allow)
            validate_non_negative("allowable_equivalent_stress", allow_val, allow_u or "MPa")
            allowable_eq_norm, _, conv_allow = normalize_unit(
                "allowable_equivalent_stress", allow_val, allow_u, "stress", default_unit="MPa"
            )
            conversions.append(conv_allow)
            normalized["allowable_equivalent_stress"] = allowable_eq_norm
        elif "yield_strength" in inputs and inputs["yield_strength"] is not None:
            raw_ys, ys_u = parse_input_value(inputs["yield_strength"], default_unit="MPa")
            ys_val = validate_numeric("yield_strength", raw_ys)
            validate_non_negative("yield_strength", ys_val, ys_u or "MPa")
            allowable_eq_norm, _, conv_ys = normalize_unit(
                "yield_strength", ys_val, ys_u, "stress", default_unit="MPa"
            )
            conversions.append(conv_ys)
            normalized["yield_strength"] = allowable_eq_norm

        design_factor: Optional[float] = None
        if "design_factor" in inputs and inputs["design_factor"] is not None:
            raw_df, _ = parse_input_value(inputs["design_factor"], default_unit="")
            df_val = validate_numeric("design_factor", raw_df)
            validate_positive("design_factor", df_val)
            design_factor = df_val
            normalized["design_factor"] = design_factor

        # 8. Core calculations
        # Step 1: Tensile stress
        total_tensile_area = num_bolts * at_norm
        sigma_t = ft_norm / total_tensile_area
        calculations.append(CalculationStep(
            step_id="step_tensile_stress",
            description="Axial tensile stress in threaded section",
            formula="σ_t = F_t / (n * A_t)",
            substituted_expression=f"{ft_norm:.6g} N / {total_tensile_area:.6e} m²",
            result=sigma_t,
            unit="Pa",
            display_result=f"{sigma_t / 1e6:.3f} MPa"
        ))

        # Step 2: Shear stress
        tau = v_norm / effective_shear_area
        calculations.append(CalculationStep(
            step_id="step_shear_stress",
            description="Average direct shear stress across shear plane(s)",
            formula="τ = V / A_eff",
            substituted_expression=f"{v_norm:.6g} N / {effective_shear_area:.6e} m²",
            result=tau,
            unit="Pa",
            display_result=f"{tau / 1e6:.3f} MPa"
        ))

        # Step 3: Von Mises equivalent stress
        sigma_vm = math.sqrt((sigma_t ** 2) + 3.0 * (tau ** 2))
        calculations.append(CalculationStep(
            step_id="step_von_mises",
            description="Von Mises equivalent combined stress",
            formula="σ_vm = √(σ_t² + 3 * τ²)",
            substituted_expression=f"√(({sigma_t / 1e6:.4g} MPa)² + 3 * ({tau / 1e6:.4g} MPa)²)",
            result=sigma_vm,
            unit="Pa",
            display_result=f"{sigma_vm / 1e6:.3f} MPa"
        ))

        # 9. Structured results
        results = {
            "bolt_diameter": d_norm,
            "bolt_diameter_mm": d_norm * 1e3,
            "tensile_load": ft_norm,
            "shear_load": v_norm,
            "num_bolts": num_bolts,
            "num_bolts_assumed": num_bolts_assumed,
            "shear_planes": shear_planes,
            "shear_planes_assumed": shear_planes_assumed,
            "tensile_stress_area": at_norm,
            "tensile_stress_area_mm2": at_norm * 1e6,
            "tensile_stress_area_method": area_method,
            "tensile_stress_area_assumed": area_assumed,
            "effective_shear_area": effective_shear_area,
            "effective_shear_area_mm2": effective_shear_area * 1e6,
            "tensile_stress": sigma_t,
            "tensile_stress_mpa": sigma_t / 1e6,
            "shear_stress": tau,
            "shear_stress_mpa": tau / 1e6,
            "von_mises_stress": sigma_vm,
            "von_mises_stress_mpa": sigma_vm / 1e6
        }

        # 10. Engineering assessment
        assessment = self._create_stress_assessment(
            assessment_type="bolt_combined_stress",
            calculated_stress_pa=sigma_vm,
            allowable_stress_pa=allowable_eq_norm,
            design_factor=design_factor,
            stress_name="Von Mises equivalent bolt stress"
        )
        if assessment.factor_of_safety is not None:
            results["factor_of_safety"] = assessment.factor_of_safety

        prov_map = self._build_provenance_map(inputs, provenance, assumed_provenance=assumed_prov)

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
            assumptions=active_assumptions,
            tracked_assumptions=tracked_assumptions,
            limitations=self.default_limitations,
            warnings=warnings,
            provenance=prov_map
        )


class BoltPreloadSolver(MechanicalSolver):
    """
    Deterministic solver for fastener preload clamping force and tightening torque.
    Calculates target bolt pre-tension: F_preload = k * A_t * S_p and tightening torque: T = K * F_preload * d.
    Distinguishes user-provided inputs from assumed defaults (k=0.75, K=0.20) and area approximations.
    """

    @property
    def solver_id(self) -> str:
        return "py_mech_bolt_preload_v1"

    @property
    def solver_version(self) -> str:
        return "1.0.0"

    @property
    def analysis_type(self) -> str:
        return "bolt_preload"

    @property
    def machine_element(self) -> MachineElementType:
        return MachineElementType.BOLTED_JOINT

    @property
    def required_inputs(self) -> List[str]:
        # Strictly requires diameter and proof stress; preload factor can be explicit or configured/assumed
        return ["bolt_diameter", "proof_stress"]

    @property
    def optional_inputs(self) -> List[str]:
        return [
            "preload_factor",
            "torque_coefficient",
            "tensile_stress_area",
            "thread_pitch",
            "pitch"
        ]

    @property
    def default_assumptions(self) -> List[str]:
        return [
            "Controlled tightening achieves target bolt pre-tension within specified preload fraction.",
            "Linear elastic fastener elongation under initial pre-load.",
            "Joint clamp faces are clean, flat, and parallel.",
            "Torque-tension relationship modeled using nominal short-form relation T = K * F_preload * d."
        ]

    @property
    def default_limitations(self) -> List[str]:
        return [
            "Does not model torque-tension scatter (nut factor uncertainty k_nut +/- 30%).",
            "Does not account for embedment relaxation, thermal expansion differential, or gasket creep.",
            "Requires user-specified proof stress; does not infer bolt grade from geometry alone.",
            "Does not replace formal VDI 2230 joint clamping analysis."
        ]

    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        # Require bolt_diameter and proof_stress
        validate_required(inputs, ["bolt_diameter"])

        # Check if preload_factor was explicitly passed as None (retaining validation failure when caller passes None)
        if "preload_factor" in inputs and inputs["preload_factor"] is None:
            raise SolverValidationError("preload_factor cannot be None; provide a valid positive number or omit to use default 0.75")

        if "proof_stress" not in inputs or inputs["proof_stress"] is None:
            raise SolverValidationError("proof_stress is required and cannot be None")

        conversions = []
        normalized = {}
        calculations: List[CalculationStep] = []
        warnings = []
        assumed_prov: Dict[str, InputProvenance] = {}
        tracked_assumptions: List[EngineeringAssumption] = []
        active_assumptions = list(self.default_assumptions)

        # 1. Normalize bolt diameter
        raw_d, d_unit = parse_input_value(inputs["bolt_diameter"], default_unit="mm")
        d_val = validate_numeric("bolt_diameter", raw_d)
        validate_positive("bolt_diameter", d_val, d_unit or "mm")
        d_norm, d_u, conv_d = normalize_unit("bolt_diameter", d_val, d_unit, "length", default_unit="mm")
        validate_positive("bolt_diameter", d_norm, d_u)
        normalized["bolt_diameter"] = d_norm
        conversions.append(conv_d)

        # 2. Preload factor k: user-provided or configurable assumed default 0.75
        k_val: float
        preload_factor_assumed: bool
        if "preload_factor" in inputs and inputs["preload_factor"] is not None:
            raw_k, _ = parse_input_value(inputs["preload_factor"], default_unit="")
            k_num = validate_numeric("preload_factor", raw_k)
            validate_positive("preload_factor", k_num)
            k_val = k_num
            preload_factor_assumed = False
        else:
            k_val = 0.75
            preload_factor_assumed = True
            k_rationale = "Preload factor assumed as k=0.75 for standard reusable bolted joint (not user-specified; recommended range 0.75-0.90)."
            assumed_prov["preload_factor"] = InputProvenance(
                value=0.75,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale=k_rationale
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="preload_factor",
                value=0.75,
                category="assumed_default",
                rationale=k_rationale,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Preload factor assumed as k=0.75 for standard reusable joint (not user-specified; recommended range 0.75-0.90)."
            )
        normalized["preload_factor"] = k_val

        # 3. Torque coefficient K: user-provided or configurable assumed default 0.20
        k_torque: float
        torque_coeff_assumed: bool
        if "torque_coefficient" in inputs and inputs["torque_coefficient"] is not None:
            raw_kt, _ = parse_input_value(inputs["torque_coefficient"], default_unit="")
            kt_num = validate_numeric("torque_coefficient", raw_kt)
            validate_positive("torque_coefficient", kt_num)
            k_torque = kt_num
            torque_coeff_assumed = False
        else:
            k_torque = 0.20
            torque_coeff_assumed = True
            kt_rationale = "Torque coefficient assumed as K=0.20 for standard as-received commercial steel fasteners (empirical scatter ±30%)."
            assumed_prov["torque_coefficient"] = InputProvenance(
                value=0.20,
                source="assumed_default",
                is_assumed=True,
                assumption_rationale=kt_rationale
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="torque_coefficient",
                value=0.20,
                category="assumed_default",
                rationale=kt_rationale,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Torque coefficient assumed as K=0.20 for standard as-received commercial fasteners (empirical scatter ±30%)."
            )
        normalized["torque_coefficient"] = k_torque

        # 4. Normalize proof stress S_p
        raw_sp, sp_u = parse_input_value(inputs["proof_stress"], default_unit="MPa")
        sp_val = validate_numeric("proof_stress", raw_sp)
        validate_positive("proof_stress", sp_val, sp_u or "MPa")
        sp_norm, _, conv_sp = normalize_unit("proof_stress", sp_val, sp_u, "stress", default_unit="MPa")
        conversions.append(conv_sp)
        normalized["proof_stress"] = sp_norm

        # 5. Tensile stress area (strictly distinguishing user-supplied, derived from pitch, and nominal approximation)
        at_norm: float
        area_method: str
        area_assumed: bool

        if "tensile_stress_area" in inputs and inputs["tensile_stress_area"] is not None:
            area_method = "explicitly_supplied"
            area_assumed = False
            raw_at, at_u = parse_input_value(inputs["tensile_stress_area"], default_unit="mm^2")
            at_val = validate_numeric("tensile_stress_area", raw_at)
            validate_positive("tensile_stress_area", at_val, at_u or "mm^2")
            at_norm, _, conv_at = normalize_unit("tensile_stress_area", at_val, at_u, "area", default_unit="mm^2")
            conversions.append(conv_at)
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Explicitly supplied fastener tensile stress area",
                formula="A_t (user supplied)",
                substituted_expression=f"{at_val} {at_u or 'mm^2'}",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))
        elif ("thread_pitch" in inputs and inputs["thread_pitch"] is not None) or ("pitch" in inputs and inputs["pitch"] is not None):
            area_method = "derived_approximation"
            area_assumed = True
            raw_p = inputs.get("thread_pitch") if inputs.get("thread_pitch") is not None else inputs.get("pitch")
            raw_p_val, p_u = parse_input_value(raw_p, default_unit="mm")
            p_val = validate_numeric("thread_pitch", raw_p_val)
            validate_positive("thread_pitch", p_val, p_u or "mm")
            p_norm, _, conv_p = normalize_unit("thread_pitch", p_val, p_u, "length", default_unit="mm")
            conversions.append(conv_p)
            normalized["thread_pitch"] = p_norm

            d_mm = d_norm * 1e3
            p_mm = p_norm * 1e3
            at_mm2 = 0.7854 * ((d_mm - 0.9382 * p_mm) ** 2)
            at_norm = at_mm2 * 1e-6

            rationale_text = "Metric coarse-thread geometric approximation At ≈ 0.7854*(d - 0.9382*p)^2 based on supplied pitch; approximate geometric model, not certified against standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_mm2, 2),
                unit="mm^2",
                source="derived_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="derived_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area derived from thread pitch p using approximate formula At ≈ 0.7854*(d - 0.9382*p)^2; does not claim exact standards table certification."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (derived approximation from pitch p)",
                formula="A_t ≈ 0.7854 * (d - 0.9382 * p)²",
                substituted_expression=f"0.7854 * ({d_mm:.4g} mm - 0.9382 * {p_mm:.4g} mm)²",
                result=at_norm,
                unit="m²",
                display_result=f"{at_mm2:.2f} mm²"
            ))
        else:
            area_method = "nominal_geometric_approximation"
            area_assumed = True
            gross_area = (math.pi * (d_norm ** 2)) / 4.0
            at_norm = 0.78 * gross_area
            rationale_text = "Nominal geometric reduction At ≈ 0.78 * (pi * d^2 / 4) in the absence of explicit thread pitch or standard tables."
            assumed_prov["tensile_stress_area"] = InputProvenance(
                value=round(at_norm * 1e6, 2),
                unit="mm^2",
                source="nominal_geometric_approximation",
                is_assumed=True,
                assumption_rationale=rationale_text
            )
            tracked_assumptions.append(EngineeringAssumption(
                parameter="tensile_stress_area",
                value=at_norm,
                unit="m²",
                category="nominal_geometric_approximation",
                rationale=rationale_text,
                is_user_provided=False
            ))
            active_assumptions.append(
                "Tensile stress area estimated using nominal geometric reduction (At ≈ 0.78 * gross area); actual thread geometry not supplied."
            )
            calculations.append(CalculationStep(
                step_id="step_tensile_area",
                description="Thread tensile stress area (nominal geometric approximation At ≈ 0.78 * Agross)",
                formula="A_t ≈ 0.78 * (π * d² / 4)",
                substituted_expression=f"0.78 * (π * ({d_norm:.6g})² / 4)",
                result=at_norm,
                unit="m²",
                display_result=f"{at_norm * 1e6:.2f} mm²"
            ))

        normalized["tensile_stress_area"] = at_norm

        # 6. Core calculations
        # Step 1: Proof load F_proof = S_p * A_t
        f_proof = sp_norm * at_norm
        calculations.append(CalculationStep(
            step_id="step_proof_load",
            description="Bolt proof load capacity",
            formula="F_proof = S_p * A_t",
            substituted_expression=f"({sp_norm / 1e6:.4g} MPa) * ({at_norm:.6e} m²)",
            result=f_proof,
            unit="N",
            display_result=f"{f_proof:.1f} N ({f_proof / 1e3:.2f} kN)"
        ))

        # Step 2: Target preload force F_preload = k * F_proof
        f_preload = k_val * f_proof
        preload_step_desc = (
            f"Target bolt pre-tension clamping force (using assumed preload factor k={k_val:.2f})"
            if preload_factor_assumed
            else f"Target bolt pre-tension clamping force (using user-specified preload factor k={k_val:.2f})"
        )
        calculations.append(CalculationStep(
            step_id="step_preload_force",
            description=preload_step_desc,
            formula="F_preload = k * S_p * A_t",
            substituted_expression=f"{k_val:.4g} * ({sp_norm / 1e6:.4g} MPa) * ({at_norm:.6e} m²)",
            result=f_preload,
            unit="N",
            display_result=f"{f_preload:.1f} N ({f_preload / 1e3:.2f} kN)"
        ))

        # Step 3: Fastener tightening torque T = K * F_preload * d
        tightening_torque = k_torque * f_preload * d_norm
        torque_step_desc = (
            f"Fastener tightening torque (using assumed torque coefficient K={k_torque:.2f})"
            if torque_coeff_assumed
            else f"Fastener tightening torque (using user-specified torque coefficient K={k_torque:.2f})"
        )
        calculations.append(CalculationStep(
            step_id="step_tightening_torque",
            description=torque_step_desc,
            formula="T = K * F_preload * d",
            substituted_expression=f"{k_torque:.3g} * {f_preload:.1f} N * {d_norm:.4g} m",
            result=tightening_torque,
            unit="N*m",
            display_result=f"{tightening_torque:.2f} N*m"
        ))

        # 7. Structured results
        results = {
            "bolt_diameter": d_norm,
            "bolt_diameter_mm": d_norm * 1e3,
            "proof_stress": sp_norm,
            "proof_stress_mpa": sp_norm / 1e6,
            "proof_load": f_proof,
            "proof_load_kn": f_proof / 1e3,
            "preload_factor": k_val,
            "preload_factor_assumed": preload_factor_assumed,
            "torque_coefficient": k_torque,
            "torque_coefficient_assumed": torque_coeff_assumed,
            "tensile_stress_area": at_norm,
            "tensile_stress_area_mm2": at_norm * 1e6,
            "tensile_stress_area_method": area_method,
            "tensile_stress_area_assumed": area_assumed,
            "preload_force": f_preload,
            "preload_force_kn": f_preload / 1e3,
            "tightening_torque": tightening_torque,
            "tightening_torque_nm": tightening_torque
        }

        # 8. Assessment
        preload_note = "assumed default" if preload_factor_assumed else "user-specified"
        assessment = AssessmentResult(
            assessment_type="bolt_preload_clamping",
            status=AssessmentStatus.PASS,
            calculated_value=f_preload / 1e3,
            calculated_unit="kN",
            summary=(
                f"Calculated target bolt preload clamping force is {f_preload / 1e3:.2f} kN "
                f"based on {preload_note} preload factor k={k_val:.2f} and proof strength S_p={sp_norm / 1e6:.1f} MPa. "
                f"Required tightening torque is {tightening_torque:.2f} N*m (K={k_torque:.2f})."
            )
        )

        prov_map = self._build_provenance_map(inputs, provenance, assumed_provenance=assumed_prov)

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
            assumptions=active_assumptions,
            tracked_assumptions=tracked_assumptions,
            limitations=self.default_limitations,
            warnings=warnings,
            provenance=prov_map
        )
