"""
Analysis Planner & Execution Planning module (Slice 8).
Formulates deterministic mechanical analysis execution plans from mechanical semantics,
engineering knowledge rules, and user controls.
"""

from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlanningRequest,
    AnalysisPlanItem,
    AnalysisPlan
)

__all__ = [
    "AnalysisType",
    "AnalysisStatus",
    "AnalysisPlanningRequest",
    "AnalysisPlanItem",
    "AnalysisPlan",
    "AnalysisSolverRegistry",
    "AnalysisPlanner",
    "generate_analysis_plan_report",
    "plan_analyses"
]


def plan_analyses(
    mechanical_semantics=None,
    engineering_knowledge=None,
    engineering_inputs=None,
    request=None
) -> AnalysisPlan:
    """Convenience functional interface for creating an analysis plan."""
    from analysis.planner import AnalysisPlanner
    planner = AnalysisPlanner()
    return planner.create_plan(
        mechanical_semantics=mechanical_semantics,
        engineering_knowledge=engineering_knowledge,
        engineering_inputs=engineering_inputs,
        request=request
    )


def __getattr__(name: str):
    if name == "AnalysisSolverRegistry":
        from analysis.applicability import AnalysisSolverRegistry
        return AnalysisSolverRegistry
    if name == "AnalysisPlanner":
        from analysis.planner import AnalysisPlanner
        return AnalysisPlanner
    if name == "generate_analysis_plan_report":
        from analysis.report import generate_analysis_plan_report
        return generate_analysis_plan_report
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
