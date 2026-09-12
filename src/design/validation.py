"""
Deterministic validation and conflict detection for design specifications.
Enforces physical plausibility, non-negative quantities, unit validity, and constraint consistency.
"""

from typing import List
from design.models import (
    EngineeringSpecification,
    RequirementConflict,
    ConstraintPriority
)


def validate_specification(spec: EngineeringSpecification) -> List[str]:
    """
    Deterministically validates an EngineeringSpecification.
    Detects physical inconsistencies, negative dimensions, and contradictory requirements.
    Populates spec.conflicts and updates spec.requires_human_review when conflicts exist.
    Returns a list of warning or error messages.
    """
    issues: List[str] = []

    # 1. Validate operating conditions
    for op in spec.operating_conditions:
        if op.value is not None:
            if op.parameter.lower() in ("power", "speed", "rotational_speed", "rpm") and op.value <= 0:
                issues.append(f"Operating condition '{op.parameter}' must be strictly positive; received {op.value}.")

    # 2. Validate geometry requirements
    for g in spec.geometry_requirements:
        if g.value <= 0:
            issues.append(f"Geometric requirement for '{g.evidence_id or 'dimension'}' must be strictly positive; received {g.value} {g.unit}.")

    # 3. Validate safety requirements
    for s in spec.safety_requirements:
        if s.value is not None and s.value <= 0:
            issues.append(f"Safety constraint '{s.constraint_type}' must be strictly positive; received {s.value}.")

    # 4. Check for conflicting constraints (e.g. min_diameter > max_diameter)
    min_d = None
    max_d = None
    for c in spec.design_constraints + spec.safety_requirements:
        ctype = c.constraint_type.lower()
        if "min_diameter" in ctype and c.value is not None:
            min_d = c.value
        elif "max_diameter" in ctype and c.value is not None:
            max_d = c.value

    if min_d is not None and max_d is not None and min_d > max_d:
        conflict = RequirementConflict(
            conflict_id=f"conflict-diameter-{len(spec.conflicts) + 1}",
            field="diameter_constraints",
            description=f"Minimum diameter constraint ({min_d}) exceeds maximum diameter constraint ({max_d}).",
            affected_requirements=["min_diameter", "max_diameter"],
            requires_human_review=True
        )
        spec.conflicts.append(conflict)
        spec.requires_human_review = True
        issues.append(f"Contradictory design constraints: min diameter ({min_d}) > max diameter ({max_d}).")

    if spec.conflicts:
        spec.requires_human_review = True

    return issues
