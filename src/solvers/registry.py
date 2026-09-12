"""
Deterministic Mechanical Solver Registry.
Maintains mappings between machine elements, analysis types, capability metadata, and solver implementations.
"""

from typing import Dict, List, Optional, Any, Union
from solvers.models import MachineElementType, AnalysisCapability
from solvers.base import MechanicalSolver
from solvers.torsion import ShaftTorsionSolver
from solvers.bending import ShaftBendingSolver
from solvers.combined_stress import ShaftCombinedStressSolver
from solvers.bolted_joint import (
    BoltTensionSolver,
    BoltShearSolver,
    BoltCombinedStressSolver,
    BoltPreloadSolver
)


class SolverRegistry:
    """
    Generalized machine-element solver registry.
    Maps machine elements (SHAFT, BOLTED_JOINT, etc.) to available analyses and solvers.
    Allows discovery of solver capabilities and deterministic solver execution.
    """

    def __init__(self):
        self._solvers: Dict[str, MechanicalSolver] = {}
        self._type_to_solver_id: Dict[str, str] = {}
        self._element_to_solver_ids: Dict[MachineElementType, List[str]] = {}

    def register_solver(
        self,
        solver_id: str,
        solver: MechanicalSolver,
        analysis_types: Optional[Union[str, List[str]]] = None,
        machine_element: Optional[MachineElementType] = None
    ) -> None:
        """Registers a solver instance under its primary solver ID and associated analysis type keys."""
        self._solvers[solver_id] = solver
        elem = machine_element or getattr(solver, "machine_element", MachineElementType.GENERAL)

        if elem not in self._element_to_solver_ids:
            self._element_to_solver_ids[elem] = []
        if solver_id not in self._element_to_solver_ids[elem]:
            self._element_to_solver_ids[elem].append(solver_id)

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

    def list_machine_elements(self) -> List[MachineElementType]:
        """Returns list of machine elements currently supported by registered solvers."""
        return list(self._element_to_solver_ids.keys())

    def get_capabilities_for_element(self, element: MachineElementType) -> List[AnalysisCapability]:
        """Returns all analysis capabilities registered for a given machine element."""
        solver_ids = self._element_to_solver_ids.get(element, [])
        capabilities = []
        for sid in solver_ids:
            solver = self._solvers.get(sid)
            if solver:
                cap = solver.get_capability()
                cap.solver_id = sid
                cap.machine_element = element
                capabilities.append(cap)
        return capabilities

    def get_capability(self, key: Any) -> Optional[AnalysisCapability]:
        """Returns the capability metadata for a specific analysis type or solver ID."""
        solver = self.get_solver(key)
        if solver:
            norm_key = self._normalize_key(key)
            sid = self._type_to_solver_id.get(norm_key, norm_key if norm_key in self._solvers else solver.solver_id)
            cap = solver.get_capability()
            cap.solver_id = sid
            return cap
        return None

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

        # ==========================================
        # 1. Shaft Machine Element Solvers
        # ==========================================
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
            ],
            machine_element=MachineElementType.SHAFT
        )

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
            ],
            machine_element=MachineElementType.SHAFT
        )

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
            ],
            machine_element=MachineElementType.SHAFT
        )

        # ==========================================
        # 2. Bolted Joint Machine Element Solvers
        # ==========================================
        bolt_tension_solver = BoltTensionSolver()
        registry.register_solver(
            "py_mech_bolt_tension_v1",
            bolt_tension_solver,
            [
                "py_mech_bolt_tension_v1",
                "bolt_tension",
                "BOLT_TENSION"
            ],
            machine_element=MachineElementType.BOLTED_JOINT
        )

        bolt_shear_solver = BoltShearSolver()
        registry.register_solver(
            "py_mech_bolt_shear_v1",
            bolt_shear_solver,
            [
                "py_mech_bolt_shear_v1",
                "bolt_shear",
                "BOLT_SHEAR"
            ],
            machine_element=MachineElementType.BOLTED_JOINT
        )

        bolt_combined_solver = BoltCombinedStressSolver()
        registry.register_solver(
            "py_mech_bolt_combined_stress_v1",
            bolt_combined_solver,
            [
                "py_mech_bolt_combined_stress_v1",
                "bolt_combined_stress",
                "BOLT_COMBINED_STRESS"
            ],
            machine_element=MachineElementType.BOLTED_JOINT
        )

        bolt_preload_solver = BoltPreloadSolver()
        registry.register_solver(
            "py_mech_bolt_preload_v1",
            bolt_preload_solver,
            [
                "py_mech_bolt_preload_v1",
                "bolt_preload",
                "BOLT_PRELOAD"
            ],
            machine_element=MachineElementType.BOLTED_JOINT
        )

        _GLOBAL_REGISTRY = registry

    return _GLOBAL_REGISTRY


class _LazyDefaultRegistry:
    """Proxy object that delegates attribute lookups to get_solver_registry()."""
    def __getattr__(self, name: str):
        return getattr(get_solver_registry(), name)


default_registry = _LazyDefaultRegistry()
