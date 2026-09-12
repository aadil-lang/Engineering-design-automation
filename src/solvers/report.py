"""
Deterministic markdown calculation report generator for mechanical solver certificates.
Includes detailed tracking of engineering assumptions and fallback parameters.
"""

from typing import List, Union
from solvers.models import CalculationCertificate, AssessmentStatus


def generate_calculation_report(
    certificates: Union[CalculationCertificate, List[CalculationCertificate]]
) -> str:
    """
    Generates a clear, auditable markdown engineering calculation report
    from one or more CalculationCertificate objects.
    """
    certs = [certificates] if isinstance(certificates, CalculationCertificate) else certificates

    if not certs:
        return "# Mechanical Engineering Calculation Report\n\nNo calculation certificates generated."

    lines = [
        "# Mechanical Engineering Calculation Report",
        "Deterministic Closed-Form Mechanical Solver Audit Trail",
        "",
        "> [!NOTE]",
        "> This document provides analytical engineering calculation steps and stress evaluations.",
        "> It does not constitute formal regulatory certification, manufacturing sign-off, or structural warranty.",
        ""
    ]

    for i, cert in enumerate(certs, start=1):
        lines.append(f"## {i}. {cert.analysis_type.replace('_', ' ').title()} ({cert.solver_id})")
        lines.append(f"- **Certificate ID:** `{cert.certificate_id}`")
        lines.append(f"- **Solver Version:** `{cert.solver_version}`")
        lines.append(f"- **Execution Status:** `{cert.status.value.upper()}`")
        lines.append(f"- **Timestamp:** `{cert.created_at}`")
        lines.append("")

        # 1. Inputs and Unit Conversions
        lines.append("### 1. Inputs & Unit Conversions")
        lines.append("| Parameter | Input Value | Normalized SI | Conversion Factor | Source |")
        lines.append("|---|---|---|---|---|")
        for conv in cert.conversions:
            prov_entry = cert.provenance.get(conv.parameter)
            source_desc = f"{prov_entry.source} ({prov_entry.source_id})" if (prov_entry and prov_entry.source_id) else (prov_entry.source if prov_entry else "user")
            lines.append(
                f"| `{conv.parameter}` | {conv.original_value} {conv.original_unit} | "
                f"{conv.normalized_value:.6g} {conv.normalized_unit} | {conv.conversion_factor:g} | {source_desc} |"
            )
        lines.append("")

        # 2. Calculation Steps
        lines.append("### 2. Mathematical Calculations")
        for step in cert.calculations:
            disp = f" = **{step.display_result}**" if step.display_result else f" = **{step.result:.6g} {step.unit}**"
            lines.append(f"#### Step: {step.description}")
            lines.append(f"- **Formula:** `{step.formula}`")
            lines.append(f"- **Substituted:** `{step.substituted_expression}`")
            lines.append(f"- **Result:** {disp}")
            lines.append("")

        # 3. Engineering Assessment
        lines.append("### 3. Engineering Assessment")
        for ass in cert.assessments:
            badge = "🟢 PASS" if ass.status == AssessmentStatus.PASS else (
                "🔴 FAIL" if ass.status == AssessmentStatus.FAIL else "🟡 NOT ASSESSED"
            )
            lines.append(f"- **Assessment Status:** {badge}")
            lines.append(f"- **Evaluation:** {ass.summary}")
            if ass.allowable_value is not None:
                lines.append(f"- **Allowable Limit:** {ass.allowable_value:.2f} {ass.allowable_unit or 'MPa'}")
            if ass.factor_of_safety is not None:
                lines.append(f"- **Factor of Safety (FoS):** `{ass.factor_of_safety:.2f}`")
            if ass.margin_of_safety is not None:
                lines.append(f"- **Margin of Safety (MoS):** `{ass.margin_of_safety:+.2f}`")
            lines.append("")

        # 4. Physical Assumptions
        if cert.assumptions or cert.tracked_assumptions:
            lines.append("### 4. Physical Assumptions")
            if cert.tracked_assumptions:
                lines.append("#### Explicit Engineering Assumptions & Defaults")
                lines.append("| Parameter | Value | Category | Rationale | User Provided? |")
                lines.append("|---|---|---|---|---|")
                for ea in cert.tracked_assumptions:
                    unit_str = f" {ea.unit}" if ea.unit else ""
                    lines.append(
                        f"| `{ea.parameter}` | {ea.value}{unit_str} | `{ea.category}` | {ea.rationale} | {'Yes' if ea.is_user_provided else 'No (Assumed)'} |"
                    )
                lines.append("")

            if cert.assumptions:
                for asm in cert.assumptions:
                    lines.append(f"- {asm}")
                lines.append("")

        # 5. Engineering Limitations
        if cert.limitations:
            lines.append("### 5. Formulation Limitations & Scope Boundaries")
            for lim in cert.limitations:
                lines.append(f"- {lim}")
            lines.append("")

        # 6. Warnings
        if cert.warnings:
            lines.append("### 6. Diagnostic Warnings")
            for w in cert.warnings:
                lines.append(f"> [!WARNING]\n> {w}\n")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).strip()
