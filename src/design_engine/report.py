"""
Deterministic Markdown Report Generator for Parametric Mechanical Design Results.
Provides structured presentation of problem statement, derivations, design variables,
candidate evaluation matrix, selected optimal design, assumptions, and human review flags.
"""

from typing import Optional
from design_engine.models import DesignResult, DesignStatus


def generate_design_report(result: DesignResult) -> str:
    """
    Generates a structured, auditable GitHub-flavored Markdown report of the design synthesis.
    """
    lines = []

    # Title & Notice
    lines.append("# Mechanical Design Result")
    lines.append("Parametric Mechanical Design Synthesis & Candidate Evaluation Audit")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> This report presents analytical candidate generation and deterministic solver evaluation.")
    lines.append("> It does not constitute formal regulatory certification, professional seal, or manufacturing release.")
    lines.append("")

    # Status Banner
    status_icon = "🟢" if result.design_status == DesignStatus.PASS else ("🟡" if result.design_status == DesignStatus.REQUIRES_REVIEW else "🔴")
    lines.append(f"- **Design ID:** `{result.design_id}`")
    if result.specification_id:
        lines.append(f"- **Specification ID:** `{result.specification_id}`")
    lines.append(f"- **Machine Element:** `{result.machine_element.upper()}`")
    lines.append(f"- **Design Status:** {status_icon} **`{result.design_status.value}`**")
    lines.append(f"- **Human Review Required:** `{'YES' if result.human_review_required else 'NO'}`")
    lines.append(f"- **Optimization Objective:** `{result.objective.value}`")
    lines.append(f"- **Timestamp:** `{result.created_at}`")
    lines.append("")

    # Human Review Callout if needed
    if result.human_review_required and result.review_reasons:
        lines.append("> [!WARNING]")
        lines.append("> **Human Engineering Review Required:**")
        for reason in result.review_reasons:
            lines.append(f"> - {reason}")
        lines.append("")

    # 1. Design Problem
    lines.append("## 1. Design Problem")
    if result.problem_statement:
        lines.append(f"> {result.problem_statement}")
    else:
        lines.append("Parametric mechanical sizing based on supplied engineering requirements.")
    lines.append("")

    # 2. Engineering Specification
    lines.append("## 2. Engineering Specification & Requirements")
    if result.constraints:
        lines.append("### Governing Criteria")
        lines.append("| Criterion | Value | Unit |")
        lines.append("|---|---|---|")
        for k, v in result.constraints.items():
            lines.append(f"| `{k}` | {v} | - |")
        lines.append("")

    # 3. Derived Quantities
    lines.append("## 3. Deterministically Derived Quantities")
    if result.derived_values:
        for dv in result.derived_values:
            lines.append(f"### Parameter: `{dv.name.upper()}` = **{dv.output_value} {dv.output_unit}**")
            lines.append(f"- **Governing Formula:** `{dv.formula}`")
            lines.append(f"- **Provenance:** `{dv.provenance}`")
            if dv.calculation_steps:
                lines.append("- **Mathematical Steps:**")
                for s in dv.calculation_steps:
                    lines.append(f"  - {s}")
            if dv.assumptions:
                lines.append("- **Derivation Assumptions:**")
                for a in dv.assumptions:
                    lines.append(f"  - {a}")
            lines.append("")
    else:
        lines.append("No intermediate derived quantities required.")
        lines.append("")

    # 4. Design Variables
    lines.append("## 4. Parametric Design Variables")
    if result.design_variables:
        lines.append("| Variable | Unit | Lower Bound | Upper Bound | Step | Search Source | Assumed? |")
        lines.append("|---|---|---|---|---|---|---|")
        for v in result.design_variables:
            assumed_tag = "YES" if v.is_assumed else "NO"
            lb_str = f"{v.lower_bound}" if v.lower_bound is not None else "-"
            ub_str = f"{v.upper_bound}" if v.upper_bound is not None else "-"
            st_str = f"{v.step}" if v.step is not None else "-"
            lines.append(f"| `{v.name}` | {v.unit} | {lb_str} | {ub_str} | {st_str} | {v.source} | {assumed_tag} |")
        lines.append("")

    # 5. Candidate Designs Table
    all_candidates = []
    if result.selected_candidate:
        all_candidates.append(result.selected_candidate)
    all_candidates.extend(result.alternative_candidates)

    lines.append("## 5. Candidate Designs & Evaluation Matrix")
    if all_candidates:
        lines.append("| Candidate | Diameter (mm) | Stress (MPa) | Allowable (MPa) | Factor of Safety | Assessment |")
        lines.append("|---|---|---|---|---|---|")
        for c in all_candidates:
            d_val = c.parameters.get("shaft_diameter_mm", c.parameters.get("shaft_diameter", "-"))
            stress_val = f"{c.calculated_stress_mpa:.2f}" if c.calculated_stress_mpa is not None else "-"
            allow_val = f"{c.allowable_stress_mpa:.2f}" if c.allowable_stress_mpa is not None else "-"
            fos_val = f"{c.factor_of_safety:.2f}" if c.factor_of_safety is not None else "-"
            status_val = f"**{c.assessment.value}**" if hasattr(c.assessment, "value") else str(c.assessment)
            is_sel = " ⭐ (Selected)" if result.selected_candidate and c.candidate_id == result.selected_candidate.candidate_id else ""
            lines.append(f"| `{c.candidate_id}`{is_sel} | {d_val} | {stress_val} | {allow_val} | {fos_val} | {status_val} |")
        lines.append("")
    else:
        lines.append("No candidates evaluated (design synthesis was blocked or aborted).")
        lines.append("")

    # 6. Selected Candidate
    lines.append("## 6. Selected Candidate")
    if result.selected_candidate:
        sc = result.selected_candidate
        d_sel = sc.parameters.get("shaft_diameter_mm", sc.parameters.get("shaft_diameter"))
        lines.append(f"**Recommended Nominal Dimension:** `{result.machine_element.capitalize()} Diameter = {d_sel:g} mm`")
        lines.append(f"- **Calculated Stress:** {sc.calculated_stress_mpa} MPa")
        lines.append(f"- **Allowable Limit:** {sc.allowable_stress_mpa} MPa")
        lines.append(f"- **Resulting Factor of Safety:** **{sc.factor_of_safety}**")
        lines.append(f"- **Assessment:** **{sc.assessment.value}**")
        lines.append("")
        if sc.calculation_certificates:
            cert = sc.calculation_certificates[0]
            lines.append(f"- **Calculation Certificate ID:** `{cert.certificate_id}`")
            lines.append(f"- **Deterministic Solver:** `{cert.solver_id} (v{cert.solver_version})`")
            if cert.assessments:
                lines.append(f"- **Assessment Rationale:** {cert.assessments[0].summary}")
        lines.append("")
    else:
        lines.append("No candidate was selected because requirements could not be satisfied or inputs were blocked.")
        lines.append("")

    # 7. Governing Analysis
    lines.append("## 7. Governing Analysis")
    gov = result.governing_analysis or "shaft_torsion"
    lines.append(f"- **Primary Sizing Mode:** `{gov}`")
    lines.append("- **Governing Formulation:** $\\tau = \\frac{16 T}{\\pi d^3} \\le \\tau_{allow}$")
    lines.append("")

    # 8. Assumptions
    lines.append("## 8. Tracked Engineering Assumptions")
    if result.assumptions:
        for a in result.assumptions:
            lines.append(f"- {a}")
    else:
        lines.append("No active assumptions logged.")
    lines.append("")

    # 9. Missing Information
    lines.append("## 9. Missing Information & Gaps")
    if result.missing_information:
        lines.append("| Field | Importance | Blocks Analysis? | Reason | Suggested Action |")
        lines.append("|---|---|---|---|---|")
        for m in result.missing_information:
            blocks = "🔴 YES" if m.blocks_analysis else "⚪ NO"
            lines.append(f"| `{m.field}` | `{m.importance.value}` | {blocks} | {m.reason} | {m.suggested_input or '-'} |")
        lines.append("")
    else:
        lines.append("All parameters required for candidate sizing were fully supplied.")
        lines.append("")

    # 10. Limitations
    lines.append("## 10. Analytical Limitations")
    lines.append("- Sizing is based on ideal, uniform solid circular geometry without stress risers (fillets, keyways, splines).")
    lines.append("- Dynamic fatigue cycles, reversing torsional loads, and rotating bending endurance limits are not evaluated.")
    lines.append("- Analytical closed-form solution valid for isotropic linear-elastic behavior only.")
    lines.append("")

    # 11. Human Engineering Review
    lines.append("## 11. Human Engineering Review")
    if result.human_review_required:
        lines.append("Review is **MANDATORY** prior to advancing this design candidate into detail drawing or CAD model generation.")
        for r in result.review_reasons:
            lines.append(f"- {r}")
    else:
        lines.append("Design calculations successfully satisfied all stated analytical torsional criteria.")
    lines.append("")

    return "\n".join(lines)
