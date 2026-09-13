"""
Parametric Shaft Designer orchestrating requirement ingestion,
analytical sizing, candidate generation, deterministic solver evaluation,
and candidate ranking.
"""

import uuid
from typing import Optional, Dict, Any, List

from design.models import (
    EngineeringSpecification,
    MissingInformation,
    RequirementConflict,
    DerivedEngineeringValue
)
from design.extractor import DesignSpecificationExtractor
from design_engine.models import (
    ShaftDesignRequirements,
    DesignResult,
    DesignStatus,
    DesignObjective
)
from design_engine.variables import create_shaft_diameter_variable
from design_engine.candidates import ShaftDiameterCandidateGenerator
from design_engine.shaft import (
    resolve_shaft_torque,
    resolve_allowable_stress,
    calculate_required_diameter
)
from design_engine.evaluator import CandidateEvaluator
from design_engine.ranker import CandidateRanker
from design_engine.report import generate_design_report
from design_engine.config import (
    ASSUMPTION_DEFAULT_SEARCH_RANGE,
    ASSUMPTION_SOLID_CIRCULAR,
    ASSUMPTION_STATIC_TORSION,
    ASSUMPTION_NO_STRESS_CONCENTRATION
)


class ShaftDesigner:
    """
    Parametric mechanical design synthesizer for solid circular shafts.
    Combines closed-form analytical sizing with candidate exploration and
    rigorous evaluation through deterministic solver engines.
    """

    def __init__(
        self,
        candidate_generator: Optional[ShaftDiameterCandidateGenerator] = None,
        evaluator: Optional[CandidateEvaluator] = None,
        ranker: Optional[CandidateRanker] = None
    ):
        self.candidate_generator = candidate_generator or ShaftDiameterCandidateGenerator()
        self.evaluator = evaluator or CandidateEvaluator()
        self.ranker = ranker or CandidateRanker()

    def design(
        self,
        req: ShaftDesignRequirements,
        spec: Optional[EngineeringSpecification] = None,
        objective: DesignObjective = DesignObjective.MINIMIZE_SHAFT_DIAMETER
    ) -> DesignResult:
        """
        Executes deterministic shaft design search and evaluation.
        """
        design_id = f"design-{uuid.uuid4().hex[:8]}"
        spec_id = spec.specification_id if spec else None
        problem_statement = spec.problem_statement if spec else None

        missing_info: List[MissingInformation] = []
        conflicts: List[RequirementConflict] = []
        assumptions: List[str] = [
            ASSUMPTION_SOLID_CIRCULAR,
            ASSUMPTION_STATIC_TORSION,
            ASSUMPTION_NO_STRESS_CONCENTRATION
        ]
        derived_values: List[DerivedEngineeringValue] = []
        review_reasons: List[str] = []
        human_review_required = False

        if spec:
            missing_info.extend(spec.missing_information)
            conflicts.extend(spec.conflicts)
            assumptions.extend(spec.assumptions)
            derived_values.extend(spec.derived_values)
            if spec.requires_human_review:
                human_review_required = True
                review_reasons.append("Upstream specification requires engineering review.")

        # 1. Resolve Torque
        torque_val, derived_torque_obj, torque_conflict = resolve_shaft_torque(req)
        if derived_torque_obj and not any(d.name == "torque" for d in derived_values):
            derived_values.append(derived_torque_obj)

        if torque_conflict:
            conflicts.append(torque_conflict)
            human_review_required = True
            review_reasons.append(torque_conflict.description)

        if torque_val is None or torque_val <= 0:
            missing_info.append(MissingInformation(
                field="torque",
                reason="Shaft sizing requires either torque or power with rotational speed.",
                importance=MissingInformation.__annotations__["importance"].__args__[0].REQUIRED_FOR_ANALYSIS if hasattr(MissingInformation, "__annotations__") else "REQUIRED_FOR_ANALYSIS",
                blocks_analysis=True,
                suggested_input="Specify operating torque (e.g., 50 N*m) or power and speed."
            ))
            res = DesignResult(
                design_id=design_id,
                specification_id=spec_id,
                problem_statement=problem_statement,
                machine_element="shaft",
                design_variables=[],
                governing_analysis="shaft_torsion",
                objective=objective,
                missing_information=missing_info,
                assumptions=assumptions,
                conflicts=conflicts,
                human_review_required=True,
                review_reasons=["Transmitted torque could not be resolved from inputs."],
                design_status=DesignStatus.BLOCKED,
                derived_values=derived_values
            )
            res.report = generate_design_report(res)
            return res

        # 2. Resolve Allowable Stress
        tau_allow_pa, derived_allow_obj, allow_assumptions, allow_missing = resolve_allowable_stress(req)
        assumptions.extend(allow_assumptions)
        if derived_allow_obj:
            derived_values.append(derived_allow_obj)

        if allow_missing:
            missing_info.append(allow_missing)
            res = DesignResult(
                design_id=design_id,
                specification_id=spec_id,
                problem_statement=problem_statement,
                machine_element="shaft",
                design_variables=[],
                governing_analysis="shaft_torsion",
                objective=objective,
                missing_information=missing_info,
                assumptions=assumptions,
                conflicts=conflicts,
                human_review_required=True,
                review_reasons=["Allowable stress or material yield strength with design factor not supplied."],
                design_status=DesignStatus.BLOCKED,
                derived_values=derived_values
            )
            res.report = generate_design_report(res)
            return res

        # 3. Check for Bending Moments (Transverse Loading)
        if req.bending_moment is not None and req.bending_moment > 0:
            human_review_required = True
            review_reasons.append(
                f"Transverse loading (bending moment = {req.bending_moment} N*m) is present; "
                "torsion-only sizing is incomplete for full shaft integrity."
            )

        # 4. Analytical Sizing (d_req = (16T / (pi * tau_allow))^(1/3))
        d_req_m, d_req_mm, sizing_steps = calculate_required_diameter(torque_val, tau_allow_pa)
        derived_values.append(DerivedEngineeringValue(
            name="minimum_required_diameter",
            formula="d_req = (16 * T / (pi * tau_allow))^(1/3)",
            inputs={
                "torque": f"{torque_val:.3f} N*m",
                "allowable_shear_stress": f"{tau_allow_pa / 1e6:.2f} MPa"
            },
            output_value=round(d_req_mm, 2),
            output_unit="mm",
            calculation_steps=sizing_steps,
            provenance="derived_calculation"
        ))

        # 5. Create Parametric Design Variable
        dia_var = create_shaft_diameter_variable(
            diameter_min=req.diameter_min,
            diameter_max=req.diameter_max,
            diameter_step=req.diameter_step
        )
        if dia_var.is_assumed:
            assumptions.append(ASSUMPTION_DEFAULT_SEARCH_RANGE)

        # 6. Generate Discrete Candidates
        raw_candidates = self.candidate_generator.generate(
            variable=dia_var,
            required_min_diameter_mm=d_req_mm
        )

        # 7. Evaluate Candidates with Deterministic Solver
        tau_allow_mpa = tau_allow_pa / 1e6

        if derived_allow_obj and "shear_yield_strength_mpa" in derived_allow_obj.inputs:
            solver_allow_mpa = float(derived_allow_obj.inputs["shear_yield_strength_mpa"])
            solver_df = req.design_factor or req.minimum_factor_of_safety
        elif req.allowable_shear_stress is not None:
            solver_allow_mpa = float(req.allowable_shear_stress)
            solver_df = req.design_factor or req.minimum_factor_of_safety
        else:
            solver_allow_mpa = tau_allow_mpa
            solver_df = None

        evaluated_candidates = self.evaluator.evaluate_all_shafts(
            candidate_configs=raw_candidates,
            torque_nm=torque_val,
            allowable_shear_mpa=solver_allow_mpa,
            design_factor=solver_df
        )

        # 8. Rank Candidates and Select Optimal
        selected, alternatives, rank_status = self.ranker.rank(
            candidates=evaluated_candidates,
            target_min_fos=req.minimum_factor_of_safety or req.design_factor
        )

        # 9. Determine Overall Status
        if rank_status == DesignStatus.FAIL:
            final_status = DesignStatus.FAIL
        elif human_review_required:
            final_status = DesignStatus.REQUIRES_REVIEW
        else:
            final_status = DesignStatus.PASS

        constraints_dict = {
            "torque_nm": torque_val,
            "allowable_shear_stress_mpa": round(tau_allow_mpa, 2),
            "design_factor": req.design_factor,
            "minimum_required_diameter_mm": round(d_req_mm, 2)
        }
        if req.bending_moment:
            constraints_dict["bending_moment_nm"] = req.bending_moment

        result = DesignResult(
            design_id=design_id,
            specification_id=spec_id,
            problem_statement=problem_statement,
            machine_element="shaft",
            selected_candidate=selected,
            alternative_candidates=alternatives,
            design_variables=[dia_var],
            governing_analysis="shaft_torsion",
            objective=objective,
            constraints=constraints_dict,
            missing_information=missing_info,
            assumptions=list(dict.fromkeys(assumptions)),
            conflicts=conflicts,
            human_review_required=human_review_required,
            review_reasons=review_reasons,
            design_status=final_status,
            derived_values=derived_values
        )

        result.report = generate_design_report(result)
        return result


def design_from_specification(
    spec: EngineeringSpecification,
    extra_inputs: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    objective: Optional[DesignObjective] = None
) -> DesignResult:
    """
    Synthesizes candidate designs directly from a structured EngineeringSpecification (Slice 11).
    """
    inputs = dict(extra_inputs or {})
    c_dict = dict(constraints or {})

    # Extract Power & Speed from Operating Conditions
    power_val = inputs.get("power")
    power_unit = inputs.get("power_unit", "kW")
    speed_val = inputs.get("speed_rpm") or inputs.get("speed")

    for op in spec.operating_conditions:
        if op.parameter == "power" and power_val is None:
            power_val = op.value
            power_unit = op.unit
        elif op.parameter in ("speed", "rotational_speed") and speed_val is None:
            speed_val = op.value

    # Extract Torque & Bending from Loads
    torque_val = inputs.get("torque")
    bending_val = inputs.get("bending_moment")

    for l in spec.load_requirements:
        l_type = l.load_type.lower()
        if l_type == "torque" and torque_val is None and l.magnitude:
            torque_val = l.magnitude.value
        elif l_type in ("bending_moment", "transverse_load", "moment") and bending_val is None and l.magnitude:
            bending_val = l.magnitude.value

    # Extract Material & Yield Strengths
    mat_name = inputs.get("material") or (spec.material_requirements.material_name if spec.material_requirements else None)
    mat_grade = inputs.get("material_grade") or (spec.material_requirements.material_grade if spec.material_requirements else None)
    yield_strength = inputs.get("yield_strength")
    allowable_shear = inputs.get("allowable_shear_stress")

    # Extract Design Factor / Safety Factor
    design_factor = inputs.get("design_factor") or inputs.get("minimum_factor_of_safety")
    if design_factor is None:
        for s in spec.safety_requirements:
            if s.value is not None:
                design_factor = s.value
                break

    # Bounds and Steps
    d_min = inputs.get("diameter_min") or c_dict.get("diameter_min")
    d_max = inputs.get("diameter_max") or c_dict.get("diameter_max")
    d_step = inputs.get("diameter_step") or c_dict.get("diameter_step")

    req = ShaftDesignRequirements(
        power=power_val,
        power_unit=power_unit,
        speed_rpm=speed_val,
        torque=torque_val,
        material=mat_name,
        material_grade=mat_grade,
        allowable_shear_stress=allowable_shear,
        yield_strength=yield_strength,
        design_factor=design_factor,
        minimum_factor_of_safety=design_factor,
        diameter_min=d_min,
        diameter_max=d_max,
        diameter_step=d_step,
        bending_moment=bending_val
    )

    designer = ShaftDesigner()
    return designer.design(
        req=req,
        spec=spec,
        objective=objective or DesignObjective.MINIMIZE_SHAFT_DIAMETER
    )


def design_from_problem_statement(
    statement: str,
    extra_inputs: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    objective: Optional[DesignObjective] = None
) -> DesignResult:
    """
    End-to-end entry point: Natural Language Problem Statement -> Specification -> Design Synthesis.
    """
    extractor = DesignSpecificationExtractor()
    spec = extractor.extract(statement, structured_inputs=extra_inputs)
    return design_from_specification(
        spec=spec,
        extra_inputs=extra_inputs,
        constraints=constraints,
        objective=objective
    )
