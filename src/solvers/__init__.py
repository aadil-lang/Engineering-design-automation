"""
Deterministic Closed-Form Mechanical Engineering Solver Engine.
Provides machine-element agnostic analytical solvers, calculation certificates,
and capability discovery for mechanical components.
"""

from typing import Dict, List, Optional, Any
from solvers.models import (
    CalculationCertificate,
    CalculationStep,
    AssessmentResult,
    CertificateStatus,
    AssessmentStatus,
    UnitConversion,
    InputProvenance,
    MachineElementType,
    AnalysisCapability,
    ProvenanceSource,
    EngineeringAssumption
)
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
from solvers.registry import SolverRegistry, default_registry, get_solver_registry
from solvers.runner import SolverRunner
from solvers.report import generate_calculation_report
from solvers.validation import SolverValidationError


def solve_torsion(
    torque: Any,
    shaft_diameter: Any,
    allowable_shear_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    shear_modulus: Optional[Any] = None,
    shaft_length: Optional[Any] = None,
    length: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic shaft torsion solver."""
    inputs: Dict[str, Any] = {
        "torque": torque,
        "shaft_diameter": shaft_diameter
    }
    if allowable_shear_stress is not None:
        inputs["allowable_shear_stress"] = allowable_shear_stress
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor
    if shear_modulus is not None:
        inputs["shear_modulus"] = shear_modulus
    eff_length = shaft_length if shaft_length is not None else length
    if eff_length is not None:
        inputs["shaft_length"] = eff_length

    solver = ShaftTorsionSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_bending(
    bending_moment: Any,
    shaft_diameter: Any,
    allowable_bending_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic shaft bending solver."""
    inputs: Dict[str, Any] = {
        "bending_moment": bending_moment,
        "shaft_diameter": shaft_diameter
    }
    if allowable_bending_stress is not None:
        inputs["allowable_bending_stress"] = allowable_bending_stress
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = ShaftBendingSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_combined_stress(
    torque: Any,
    bending_moment: Any,
    shaft_diameter: Any,
    allowable_equivalent_stress: Optional[Any] = None,
    allowable_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic shaft combined stress solver."""
    inputs: Dict[str, Any] = {
        "torque": torque,
        "bending_moment": bending_moment,
        "shaft_diameter": shaft_diameter
    }
    eff_allowable = allowable_equivalent_stress if allowable_equivalent_stress is not None else allowable_stress
    if eff_allowable is not None:
        inputs["allowable_equivalent_stress"] = eff_allowable
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = ShaftCombinedStressSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_bolt_tension(
    bolt_diameter: Any,
    tensile_load: Any,
    tensile_stress_area: Optional[Any] = None,
    thread_pitch: Optional[Any] = None,
    num_bolts: Optional[Any] = None,
    allowable_tensile_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic bolt tension solver."""
    inputs: Dict[str, Any] = {
        "bolt_diameter": bolt_diameter,
        "tensile_load": tensile_load
    }
    if tensile_stress_area is not None:
        inputs["tensile_stress_area"] = tensile_stress_area
    if thread_pitch is not None:
        inputs["thread_pitch"] = thread_pitch
    if num_bolts is not None:
        inputs["num_bolts"] = num_bolts
    if allowable_tensile_stress is not None:
        inputs["allowable_tensile_stress"] = allowable_tensile_stress
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = BoltTensionSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_bolt_shear(
    bolt_diameter: Any,
    shear_load: Any,
    shear_planes: Optional[Any] = None,
    num_bolts: Optional[Any] = None,
    allowable_shear_stress: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic bolt shear solver."""
    inputs: Dict[str, Any] = {
        "bolt_diameter": bolt_diameter,
        "shear_load": shear_load
    }
    if shear_planes is not None:
        inputs["shear_planes"] = shear_planes
    if num_bolts is not None:
        inputs["num_bolts"] = num_bolts
    if allowable_shear_stress is not None:
        inputs["allowable_shear_stress"] = allowable_shear_stress
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = BoltShearSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_bolt_combined_stress(
    bolt_diameter: Any,
    tensile_load: Any,
    shear_load: Any,
    tensile_stress_area: Optional[Any] = None,
    thread_pitch: Optional[Any] = None,
    shear_planes: Optional[Any] = None,
    num_bolts: Optional[Any] = None,
    allowable_equivalent_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic bolt combined stress solver."""
    inputs: Dict[str, Any] = {
        "bolt_diameter": bolt_diameter,
        "tensile_load": tensile_load,
        "shear_load": shear_load
    }
    if tensile_stress_area is not None:
        inputs["tensile_stress_area"] = tensile_stress_area
    if thread_pitch is not None:
        inputs["thread_pitch"] = thread_pitch
    if shear_planes is not None:
        inputs["shear_planes"] = shear_planes
    if num_bolts is not None:
        inputs["num_bolts"] = num_bolts
    if allowable_equivalent_stress is not None:
        inputs["allowable_equivalent_stress"] = allowable_equivalent_stress
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = BoltCombinedStressSolver()
    return solver.solve(inputs, provenance=provenance)


_UNSET = object()


def solve_bolt_preload(
    bolt_diameter: Any,
    preload_factor: Any = _UNSET,
    proof_stress: Any = _UNSET,
    torque_coefficient: Optional[Any] = None,
    tensile_stress_area: Optional[Any] = None,
    thread_pitch: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic bolt preload solver."""
    inputs: Dict[str, Any] = {
        "bolt_diameter": bolt_diameter
    }
    if preload_factor is not _UNSET:
        inputs["preload_factor"] = preload_factor
    if proof_stress is not _UNSET:
        inputs["proof_stress"] = proof_stress
    if torque_coefficient is not None:
        inputs["torque_coefficient"] = torque_coefficient
    if tensile_stress_area is not None:
        inputs["tensile_stress_area"] = tensile_stress_area
    if thread_pitch is not None:
        inputs["thread_pitch"] = thread_pitch

    solver = BoltPreloadSolver()
    return solver.solve(inputs, provenance=provenance)


__all__ = [
    "CalculationCertificate",
    "CalculationStep",
    "AssessmentResult",
    "CertificateStatus",
    "AssessmentStatus",
    "UnitConversion",
    "InputProvenance",
    "MachineElementType",
    "AnalysisCapability",
    "ProvenanceSource",
    "EngineeringAssumption",
    "MechanicalSolver",
    "ShaftTorsionSolver",
    "ShaftBendingSolver",
    "ShaftCombinedStressSolver",
    "BoltTensionSolver",
    "BoltShearSolver",
    "BoltCombinedStressSolver",
    "BoltPreloadSolver",
    "SolverRegistry",
    "default_registry",
    "get_solver_registry",
    "SolverRunner",
    "generate_calculation_report",
    "SolverValidationError",
    "solve_torsion",
    "solve_bending",
    "solve_combined_stress",
    "solve_bolt_tension",
    "solve_bolt_shear",
    "solve_bolt_combined_stress",
    "solve_bolt_preload"
]
