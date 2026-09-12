"""
Deterministic Mechanical Solver Registry.
Maintains mappings between canonical analysis types, solver identifiers, and solver instances.
"""

from typing import Dict, List, Optional, Any, Union
from solvers.base import MechanicalSolver
from solvers.torsion import ShaftTorsionSolver
from solvers.bending import ShaftBendingSolver
from solvers.combined_stress import ShaftCombinedStressSolver


class SolverRegistry:
    """
    Registry for managing available deterministic mechanical solvers.
    Maps canonical solver IDs, analysis types, and legacy aliases to solver implementations.
    """

    def __init__(self):
        self._solvers: Dict[str, MechanicalSolver] = {}
        self._type_to_solver_id: Dict[str, str] = {}

    def register_solver(
        self,
        solver_id: str,
        solver: MechanicalSolver,
        analysis_types: Optional[Union[str, List[str]]] = None
    ) -> None:
        """Registers a solver instance under its primary solver ID and associated analysis type keys."""
        self._solvers[solver_id] = solver
        if analysis_types:
            types = [analysis_types] if isinstance(analysis_types, str) else analysis_types
            for t in types:
                clean_t = self._normalize_key(t)
                self._type_to_solver_id[clean_t] = solver_id

    def get_solver(self, key: Any) -> Optional[MechanicalSolver]:
        """
        Retrieves a solver by solver_id or analysis type (accepts str, Enum, etc.).
        Returns None if not found.
        """
        norm_key = self._normalize_key(key)

        # 1. Direct match on solver_id
        if norm_key in self._solvers:
            return self._solvers[norm_key]

        # 2. Match via analysis_type mapping
        if norm_key in self._type_to_solver_id:
            solver_id = self._type_to_solver_id[norm_key]
            return self._solvers.get(solver_id)

        return None

    def is_available(self, key: Any) -> bool:
        """Checks if an executable solver is available for the given solver ID or analysis type."""
        return self.get_solver(key) is not None

    def list_available_solvers(self) -> List[str]:
        """Returns sorted list of all registered primary solver IDs."""
        return sorted(list(self._solvers.keys()))

    def _normalize_key(self, key: Any) -> str:
        """Normalizes string or Enum key to a consistent lowercase identifier."""
        if hasattr(key, "value"):
            k = str(key.value)
        else:
            k = str(key)
        return k.strip().lower()


_GLOBAL_REGISTRY: Optional[SolverRegistry] = None


def get_solver_registry() -> SolverRegistry:
    """Returns the singleton solver registry with all built-in deterministic solvers pre-registered."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        registry = SolverRegistry()

        # 1. Torsion solver
        torsion_solver = ShaftTorsionSolver()
        registry.register_solver(
            "py_mech_torsion_v1",
            torsion_solver,
            [
                "py_mech_torsion_v1",
                "shaft_torsion_v1",
                "shaft_torsion",
                "torsion",
                "SHAFT_TORSION",
                "TORSION"
            ]
        )

        # 2. Bending solver
        bending_solver = ShaftBendingSolver()
        registry.register_solver(
            "py_mech_bending_v1",
            bending_solver,
            [
                "py_mech_bending_v1",
                "beam_bending_v1",
                "shaft_bending_v1",
                "shaft_bending",
                "bending",
                "SHAFT_BENDING",
                "BENDING"
            ]
        )

        # 3. Combined stress solver
        combined_solver = ShaftCombinedStressSolver()
        registry.register_solver(
            "py_mech_combined_stress_v1",
            combined_solver,
            [
                "py_mech_combined_stress_v1",
                "combined_shaft_stress_v1",
                "shaft_combined_stress_v1",
                "shaft_combined_stress",
                "combined_stress",
                "SHAFT_COMBINED_STRESS",
                "COMBINED_STRESS"
            ]
        )

        _GLOBAL_REGISTRY = registry

    return _GLOBAL_REGISTRY
