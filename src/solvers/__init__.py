"""
Mechanical Engineering Deterministic Solver Package.
Provides closed-form mechanical engineering solvers for shaft torsion, bending, and combined stress.
"""

from typing import Optional, Dict, Any
from solvers.models import (
    CalculationCertificate,
    CalculationStep,
    AssessmentResult,
    CertificateStatus,
    AssessmentStatus,
    UnitConversion,
    InputProvenance
)
from solvers.base import MechanicalSolver
from solvers.torsion import ShaftTorsionSolver
from solvers.bending import ShaftBendingSolver
from solvers.combined_stress import ShaftCombinedStressSolver
from solvers.registry import SolverRegistry, get_solver_registry
from solvers.runner import SolverRunner
from solvers.report import generate_calculation_report
from solvers.validation import SolverValidationError


def solve_torsion(
    torque: Any,
    shaft_diameter: Any,
    allowable_shear_stress: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    shear_modulus: Optional[Any] = None,
    shaft_length: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic shaft torsion solver."""
    inputs: Dict[str, Any] = {
        "torque": torque,
        "shaft_diameter": shaft_diameter
    }
    if allowable_shear_stress is not None:
        inputs["allowable_shear_stress"] = allowable_shear_stress
    if design_factor is not None:
        inputs["design_factor"] = design_factor
    if shear_modulus is not None:
        inputs["shear_modulus"] = shear_modulus
    if shaft_length is not None:
        inputs["shaft_length"] = shaft_length

    solver = ShaftTorsionSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_bending(
    bending_moment: Any,
    shaft_diameter: Any,
    allowable_bending_stress: Optional[Any] = None,
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
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = ShaftBendingSolver()
    return solver.solve(inputs, provenance=provenance)


def solve_combined_stress(
    torque: Any,
    bending_moment: Any,
    shaft_diameter: Any,
    allowable_equivalent_stress: Optional[Any] = None,
    yield_strength: Optional[Any] = None,
    design_factor: Optional[Any] = None,
    provenance: Optional[Dict[str, Any]] = None
) -> CalculationCertificate:
    """Convenience functional interface executing the deterministic combined shaft stress solver."""
    inputs: Dict[str, Any] = {
        "torque": torque,
        "bending_moment": bending_moment,
        "shaft_diameter": shaft_diameter
    }
    if allowable_equivalent_stress is not None:
        inputs["allowable_equivalent_stress"] = allowable_equivalent_stress
    if yield_strength is not None:
        inputs["yield_strength"] = yield_strength
    if design_factor is not None:
        inputs["design_factor"] = design_factor

    solver = ShaftCombinedStressSolver()
    return solver.solve(inputs, provenance=provenance)


__all__ = [
    "CalculationCertificate",
    "CalculationStep",
    "AssessmentResult",
    "CertificateStatus",
    "AssessmentStatus",
    "UnitConversion",
    "InputProvenance",
    "MechanicalSolver",
    "ShaftTorsionSolver",
    "ShaftBendingSolver",
    "ShaftCombinedStressSolver",
    "SolverRegistry",
    "get_solver_registry",
    "SolverRunner",
    "generate_calculation_report",
    "SolverValidationError",
    "solve_torsion",
    "solve_bending",
    "solve_combined_stress"
]
