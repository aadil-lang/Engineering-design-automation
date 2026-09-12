"""
Bridge connecting EngineeringSpecification to AnalysisPlanner.
Converts structured design requirements into inputs for candidate solver scheduling.
"""

from typing import Dict, Any, Optional
from design.models import EngineeringSpecification
from analysis.models import (
    AnalysisPlan,
    AnalysisPlanningRequest,
    AnalysisType
)
from analysis.planner import AnalysisPlanner


def specification_to_planner_inputs(spec: EngineeringSpecification) -> Dict[str, Any]:
    """
    Converts an EngineeringSpecification into a flat dictionary of engineering inputs
    compatible with the AnalysisPlanner and SolverRunner layers.
    """
    inputs: Dict[str, Any] = {}

    if spec.machine_element:
        inputs["machine_element"] = spec.machine_element

    # 1. Loads (including deterministically derived torque)
    for l in spec.load_requirements:
        l_type = l.load_type.lower()
        if l.magnitude:
            val = l.magnitude.value
            u = l.magnitude.unit
            if l_type == "torque":
                inputs["torque"] = val
                inputs["torque_unit"] = u
            elif l_type in ("bending_moment", "moment"):
                inputs["bending_moment"] = val
                inputs["bending_moment_unit"] = u
            elif l_type in ("axial_tension", "tensile_load"):
                inputs["tensile_load"] = val
                inputs["tensile_load_unit"] = u
            elif l_type in ("direct_shear", "shear_load"):
                inputs["shear_load"] = val
                inputs["shear_load_unit"] = u

    # 2. Operating Conditions (power & speed)
    for op in spec.operating_conditions:
        if op.parameter == "power" and op.value is not None:
            inputs["power"] = op.value
            inputs["power_unit"] = op.unit
        elif op.parameter in ("speed", "rotational_speed") and op.value is not None:
            inputs["rotational_speed"] = op.value
            inputs["speed"] = op.value
            inputs["speed_unit"] = op.unit

    # 3. Geometry Requirements
    for g in spec.geometry_requirements:
        ev_id = (g.evidence_id or "").lower()
        if "shaft_diameter" in ev_id or (ev_id == "diameter" and spec.machine_element == "shaft"):
            inputs["shaft_diameter"] = g.value
            inputs["diameter"] = g.value
        elif "bolt_diameter" in ev_id or (ev_id == "diameter" and spec.machine_element == "bolted_joint"):
            inputs["bolt_diameter"] = g.value
            inputs["diameter"] = g.value
        elif "length" in ev_id or "span" in ev_id:
            inputs["shaft_length"] = g.value
            inputs["length"] = g.value

    # 4. Material
    if spec.material_requirements:
        if spec.material_requirements.material_name:
            inputs["material"] = spec.material_requirements.material_name
        if spec.material_requirements.material_grade:
            inputs["material_grade"] = spec.material_requirements.material_grade

    # 5. Safety Factors
    for s in spec.safety_requirements:
        if s.value is not None and "safety" in s.constraint_type.lower():
            inputs["design_factor"] = s.value

    # 6. Preserved Source Evidence / Extra Structured Inputs
    if getattr(spec, "source_evidence", None):
        for k, v in spec.source_evidence.items():
            if k not in inputs:
                inputs[k] = v

    return inputs


def plan_analyses_for_specification(
    spec: EngineeringSpecification,
    planner: Optional[AnalysisPlanner] = None,
    request: Optional[AnalysisPlanningRequest] = None
) -> AnalysisPlan:
    """
    Formulates a deterministic AnalysisPlan based on the EngineeringSpecification.
    Recommends candidate calculations (e.g. torsion for rotating shafts) and detects missing inputs.
    """
    p = planner or AnalysisPlanner()

    req = request or AnalysisPlanningRequest(recommend_analyses=True)

    # Honor any explicit analysis requirements declared in the specification
    for ar in spec.analysis_requirements:
        try:
            atype = AnalysisType(ar.lower())
            if atype not in req.requested_analyses:
                req.requested_analyses.append(atype)
        except ValueError:
            pass

    inputs = specification_to_planner_inputs(spec)

    return p.create_plan(
        engineering_inputs=inputs,
        request=req
    )
