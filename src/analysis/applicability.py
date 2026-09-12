"""
Solver registry and prerequisite validation for execution planning.
"""

from typing import Dict, List, Optional
from analysis.models import AnalysisType
from analysis.config import DEFAULT_SOLVER_MAP


PREREQUISITES_MAP: Dict[AnalysisType, List[AnalysisType]] = {
    AnalysisType.COMBINED_STRESS: [AnalysisType.TORSION, AnalysisType.BENDING],
    AnalysisType.VON_MISES: [AnalysisType.BENDING, AnalysisType.TORSION]
}


class AnalysisSolverRegistry:
    """
    Lightweight deterministic registry mapping high-level analysis types to
    planned deterministic mechanical solvers.
    Explicitly tracks solver availability and execution readiness.
    """

    def __init__(self, solver_map: Optional[Dict[AnalysisType, str]] = None):
        self._map = dict(solver_map or DEFAULT_SOLVER_MAP)
        # In Slice 8, future deterministic solvers are registered but not yet implemented
        self._implemented_solvers: set[str] = set()

    def get_solver_id(self, analysis_type: AnalysisType) -> str:
        """Returns the registered solver ID for an analysis type."""
        return self._map.get(analysis_type, f"{analysis_type.value}_solver_v1")

    def is_solver_available(self, solver_id: str) -> bool:
        """
        Indicates whether the solver is implemented and ready for execution.
        In Slice 8, this always returns False as numerical solvers are deferred to Slice 9+.
        """
        return solver_id in self._implemented_solvers

    def get_solver_status_note(self, solver_id: str) -> str:
        """Returns audit note on solver implementation status."""
        if self.is_solver_available(solver_id):
            return f"Deterministic solver '{solver_id}' is implemented and available for execution."
        return f"Deterministic solver '{solver_id}' is registered in execution plan; execution is unavailable until solver is implemented (Slice 9+)."

    def get_prerequisites(self, analysis_type: AnalysisType) -> List[AnalysisType]:
        """Returns prerequisite analysis types required before executing this analysis."""
        return list(PREREQUISITES_MAP.get(analysis_type, []))
