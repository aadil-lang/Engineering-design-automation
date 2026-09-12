"""
Deterministic markdown report generator for Engineering Specifications.
Clearly demarcates known requirements, deterministically derived values, assumptions,
missing inputs, and review items.
"""

from typing import Optional
from design.models import EngineeringSpecification
from analysis.models import AnalysisPlan


def generate_design_specification_report(
    spec: EngineeringSpecification,
    plan: Optional[AnalysisPlan] = None
) -> str:
    """
    Generates a structured, auditable Markdown report from an EngineeringSpecification.
    """
    lines = [
        "# Engineering Specification Report",
        "Deterministic Requirement Interpretation & Analysis Planning Audit",
        "",
        "> [!NOTE]",
        "> This document provides structured requirement interpretation and deterministic derivation steps.",
        "> It does not constitute formal regulatory design certification or manufacturing approval.",
        "",
        f"- **Specification ID:** `{spec.specification_id}`",
        f"- **Timestamp:** `{spec.created_at}`",
        f"- **Confidence:** `{spec.confidence:.2f}`",
        f"- **Human Review Required:** `{'YES' if spec.requires_human_review else 'NO'}`",
        "",
        "## 1. Problem Statement",
        f"> {spec.problem_statement}",
        "",
        "## 2. Machine Element Classification",
        f"- **Primary Element:** `{(spec.machine_element or 'unknown').upper()}`",
    ]

    if spec.system_type:
        lines.append(f"- **System Context:** {spec.system_type}")
    lines.append("")

    # 3. Known Requirements & Operating Conditions
    lines.append("## 3. Known Requirements & Operating Conditions")
    if spec.operating_conditions:
        lines.append("### Operating Parameters")
        lines.append("| Parameter | Stated Value | Normalized SI | Source |")
        lines.append("|---|---|---|---|")
        for op in spec.operating_conditions:
            val_str = f"{op.value} {op.unit or ''}" if op.value is not None else "Unspecified"
            norm_str = f"{op.normalized_value:.4g} {op.normalized_unit or ''}" if op.normalized_value is not None else "-"
            lines.append(f"| `{op.parameter}` | {val_str} | {norm_str} | {op.source} |")
        lines.append("")

    if spec.geometry_requirements:
        lines.append("### Stated Geometry")
        lines.append("| Dimension | Value | Normalized SI | Source |")
        lines.append("|---|---|---|---|")
        for g in spec.geometry_requirements:
            norm_str = f"{g.normalized_value:.4g} {g.normalized_unit or ''}" if g.normalized_value is not None else "-"
            lines.append(f"| `{g.evidence_id or 'dimension'}` | {g.value} {g.unit} | {norm_str} | {g.source} |")
        lines.append("")

    if spec.material_requirements:
        lines.append("### Material Specification")
        mat = spec.material_requirements
        lines.append(f"- **Material Category:** {mat.material_name or 'Unspecified'}")
        lines.append(f"- **Material Grade:** {mat.material_grade or 'Unspecified (Generic Alloy)'}")
        lines.append("")

    if spec.load_requirements:
        lines.append("### Applied & Transmitted Loads")
        lines.append("| Load Type | Magnitude | Direction | Source |")
        lines.append("|---|---|---|---|")
        for l in spec.load_requirements:
            mag_str = f"{l.magnitude.value} {l.magnitude.unit}" if l.magnitude else "Unspecified"
            lines.append(f"| `{l.load_type}` | {mag_str} | {l.direction or 'nominal'} | {l.source} |")
        lines.append("")

    # 4. Deterministically Derived Values
    lines.append("## 4. Deterministically Derived Values")
    if spec.derived_values:
        for dv in spec.derived_values:
            lines.append(f"### Parameter: `{dv.name.upper()}` = **{dv.output_value:.4g} {dv.output_unit}**")
            lines.append(f"- **Governing Formula:** `{dv.formula}`")
            lines.append(f"- **Calculation Provenance:** `{dv.provenance}`")
            lines.append("- **Mathematical Derivation Steps:**")
            for step in dv.calculation_steps:
                lines.append(f"  - {step}")
            if dv.assumptions:
                lines.append("- **Derivation Assumptions:**")
                for asm in dv.assumptions:
                    lines.append(f"  - {asm}")
            lines.append("")
    else:
        lines.append("No closed-form derivations applicable with current inputs.")
        lines.append("")

    # 5. Design Constraints
    if spec.design_constraints or spec.safety_requirements:
        lines.append("## 5. Design Constraints & Safety Factors")
        lines.append("| Constraint | Value | Priority | Source |")
        lines.append("|---|---|---|---|")
        for c in spec.safety_requirements + spec.design_constraints:
            val_str = f"{c.value} {c.unit or ''}" if c.value is not None else "True"
            lines.append(f"| `{c.constraint_type}` | {val_str} | `{c.priority.value}` | {c.source} |")
        lines.append("")

    # 6. Analysis Plan (if provided)
    if plan:
        lines.append("## 6. Downstream Analysis Plan")
        lines.append(f"- **Plan ID:** `{plan.plan_id}`")
        lines.append(f"- **Recommended Analyses:** {', '.join(a.value for a in plan.recommended_analyses) or 'None'}")
        lines.append(f"- **Ready for Execution:** {', '.join(a.value for a in plan.ready_analyses) or 'None'}")
        lines.append(f"- **Blocked Analyses:** {', '.join(a.value for a in plan.blocked_analyses) or 'None'}")
        lines.append("")
        for it in plan.items:
            lines.append(f"### Analysis Item: `{it.analysis_type.value}` (Priority: `{it.priority}`)")
            lines.append(f"- **Status:** `{it.status.value.upper()}`")
            lines.append(f"- **Solver:** `{it.solver_id or 'unassigned'}`")
            lines.append(f"- **Rationale:** {it.rationale}")
            if it.missing_inputs:
                lines.append(f"- **Missing Calculation Inputs:** `{', '.join(it.missing_inputs)}`")
            lines.append("")

    # 7. Missing Information
    lines.append("## 7. Missing Information & Downstream Gaps")
    if spec.missing_information:
        lines.append("| Parameter | Importance | Blocks Analysis? | Reason | Suggested Input |")
        lines.append("|---|---|---|---|---|")
        for m in spec.missing_information:
            blocks = "🔴 YES" if m.blocks_analysis else "⚪ NO"
            lines.append(
                f"| `{m.field}` | `{m.importance.value}` | {blocks} | {m.reason} | {m.suggested_input or '-'} |"
            )
        lines.append("")
    else:
        lines.append("No critical missing information detected for initial sizing.")
        lines.append("")

    # 8. Assumptions
    lines.append("## 8. Physical & Engineering Assumptions")
    if spec.assumptions:
        for a in spec.assumptions:
            lines.append(f"- {a}")
        lines.append("")
    else:
        lines.append("No explicit assumptions applied.")
        lines.append("")

    # 9. Conflicts & Human Review
    if spec.conflicts:
        lines.append("## 9. Requirement Conflicts & Review Actions")
        for c in spec.conflicts:
            lines.append(f"> [!WARNING]")
            lines.append(f"> **Conflict `{c.conflict_id}` in `{c.field}`:** {c.description}")
            lines.append(f"> Affected: `{', '.join(c.affected_requirements)}`\n")
        lines.append("")

    return "\n".join(lines).strip()
