"""
Missing information analyzer for engineering specifications.
Identifies unspecified parameters and classifies their importance for design vs analysis.
"""

from typing import List, Set
from design.models import (
    EngineeringSpecification,
    MissingInformation,
    MissingImportance
)
from design.config import MISSING_INFO_TEMPLATES


def detect_missing_information(spec: EngineeringSpecification) -> List[MissingInformation]:
    """
    Analyzes an EngineeringSpecification to determine missing parameters
    required for sizing, detailing, and numerical analysis.
    """
    element = (spec.machine_element or "unknown").lower()
    missing: List[MissingInformation] = []

    # Gather known fields across geometry, loads, operating conditions, material
    known_fields: Set[str] = set()

    for g in spec.geometry_requirements:
        ev_id = (g.evidence_id or "").lower()
        if ev_id:
            known_fields.add(ev_id)
        if "diameter" in ev_id or "dia" in ev_id or "radius" in ev_id:
            known_fields.add("shaft_diameter")
            known_fields.add("bolt_diameter")
            known_fields.add("diameter")
        if "length" in ev_id or "span" in ev_id:
            known_fields.add("shaft_length")
            known_fields.add("span_length")
            known_fields.add("length")

    for l in spec.load_requirements:
        known_fields.add(l.load_type.lower())
        if l.load_type.lower() in ("bending", "bending_moment", "transverse_load"):
            known_fields.add("bending_loads")

    for op in spec.operating_conditions:
        known_fields.add(op.parameter.lower())

    for d in spec.derived_values:
        known_fields.add(d.name.lower())

    for c in spec.safety_requirements + spec.design_constraints:
        known_fields.add(c.constraint_type.lower())
        if "safety" in c.constraint_type.lower() or "fos" in c.constraint_type.lower():
            known_fields.add("required_factor_of_safety")

    if spec.material_requirements:
        if spec.material_requirements.material_name:
            known_fields.add("material")
        if spec.material_requirements.material_grade:
            known_fields.add("material_grade")

    # Evaluate element-specific templates
    templates = MISSING_INFO_TEMPLATES.get(element, [])
    for t in templates:
        field_name = t["field"]
        if field_name not in known_fields:
            missing.append(
                MissingInformation(
                    field=field_name,
                    reason=t["reason"],
                    importance=t["importance"],
                    blocks_analysis=t["blocks_analysis"],
                    suggested_input=t["suggested_input"]
                )
            )

    return missing
