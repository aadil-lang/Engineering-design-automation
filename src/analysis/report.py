"""
Deterministic report formatter for analysis execution plans.
Produces auditable, human-readable summaries without probabilistic LLM text generation.
"""

from analysis.models import AnalysisPlan, AnalysisStatus


def generate_analysis_plan_report(plan: AnalysisPlan) -> str:
    """
    Generates a deterministic markdown/text summary report of an AnalysisPlan.
    """
    lines = [
        f"# Mechanical Analysis Execution Plan ({plan.plan_id})",
        f"**Planner Version**: {plan.planner_version}",
        "",
        "## 1. Executive Summary",
        f"- **Total Planned Analyses**: {len(plan.items)}",
        f"- **Ready for Execution**: {len(plan.ready_analyses)}",
        f"- **Blocked Analyses**: {len(plan.blocked_analyses)}",
        f"- **Analyses Missing Inputs**: {sum(1 for i in plan.items if i.status == AnalysisStatus.MISSING_INPUTS)}",
        f"- **User Disabled**: {sum(1 for i in plan.items if i.status == AnalysisStatus.USER_DISABLED)}",
        "",
        "## 2. Analysis Item Breakdown"
    ]

    for item in plan.items:
        status_indicator = "READY" if item.status == AnalysisStatus.READY else item.status.value.upper()
        lines.append(f"### [{status_indicator}] {item.analysis_type.value.upper()} (Priority: {item.priority.upper()})")
        lines.append(f"- **Planned Solver**: `{item.solver_id or 'none'}`")
        lines.append(f"- **Rationale**: {item.rationale}")
        if item.feature_ids:
            lines.append(f"- **Target Features**: {', '.join(item.feature_ids)}")
        if item.available_inputs:
            lines.append(f"- **Available Inputs**: {', '.join(item.available_inputs)}")
        if item.missing_calculation_inputs:
            lines.append(f"- **Missing Calculation Inputs**: {', '.join(item.missing_calculation_inputs)}")
        if item.missing_assessment_inputs:
            lines.append(f"- **Missing Assessment Inputs**: {', '.join(item.missing_assessment_inputs)}")
        if item.assumptions:
            lines.append(f"- **Assumptions**: {'; '.join(item.assumptions)}")
        if item.limitations:
            lines.append(f"- **Limitations**: {'; '.join(item.limitations)}")
        lines.append("")

    lines.append("## 3. Global Missing Inputs")
    if plan.missing_inputs:
        for m in plan.missing_inputs:
            lines.append(f"- `{m}`")
    else:
        lines.append("- None (all calculation and assessment inputs satisfied).")
    lines.append("")

    lines.append("## 4. Warnings & Operational Disclaimers")
    for w in plan.warnings:
        lines.append(f"- {w}")
    lines.append("- **Safety Boundary**: This document is an analysis plan and execution schedule only. It does not certify design safety; certified engineering sign-off requires qualified human engineer review.")

    return "\n".join(lines)
