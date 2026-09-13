"""
Candidate Evaluation for the Parametric Mechanical Design Engine.
Executes existing deterministic solvers on candidate designs to compute stress,
factors of safety, and engineering assessments.
"""

from typing import List, Dict, Any, Optional
from solvers.registry import get_solver_registry, SolverRegistry
from solvers.models import CalculationCertificate, AssessmentStatus
from design_engine.models import DesignCandidate


class CandidateEvaluator:
    """
    Evaluates candidate mechanical designs through the existing deterministic solver engine.
    Ensures zero code duplication for analytical governing formulas.
    """

    def __init__(self, registry: Optional[SolverRegistry] = None):
        self.registry = registry or get_solver_registry()

    def evaluate_shaft_candidate(
        self,
        candidate_data: Dict[str, Any],
        torque_nm: float,
        allowable_shear_mpa: Optional[float] = None,
        design_factor: Optional[float] = None,
        provenance: Optional[Dict[str, Any]] = None
    ) -> DesignCandidate:
        """
        Evaluates a single solid circular shaft candidate using py_mech_torsion_v1.
        """
        solver = self.registry.get_solver("py_mech_torsion_v1")
        if solver is None:
            raise RuntimeError("Deterministic solver 'py_mech_torsion_v1' not registered in SolverRegistry.")

        cand_id = candidate_data["candidate_id"]
        dia_mm = candidate_data["shaft_diameter"]

        solver_inputs: Dict[str, Any] = {
            "torque": torque_nm,
            "shaft_diameter": dia_mm
        }
        if allowable_shear_mpa is not None:
            solver_inputs["allowable_shear_stress"] = allowable_shear_mpa
        if design_factor is not None:
            solver_inputs["design_factor"] = design_factor

        prov_data = dict(provenance or {})
        prov_data["shaft_diameter"] = {
            "value": dia_mm,
            "unit": "mm",
            "source": "design_candidate_search",
            "is_assumed": False
        }

        cert: CalculationCertificate = solver.solve(solver_inputs, provenance=prov_data)

        # Extract results
        calc_stress_mpa = cert.results.get("shear_stress_mpa")
        fos = cert.results.get("factor_of_safety")
        assessment_status = AssessmentStatus.NOT_ASSESSED

        if cert.assessments:
            first_assessment = cert.assessments[0]
            assessment_status = first_assessment.status
            if fos is None:
                fos = first_assessment.factor_of_safety

        return DesignCandidate(
            candidate_id=cand_id,
            machine_element="shaft",
            parameters={"shaft_diameter": dia_mm, "shaft_diameter_mm": dia_mm},
            analyses=["shaft_torsion"],
            constraints={"allowable_shear_stress_mpa": allowable_shear_mpa, "design_factor": design_factor},
            assessment=assessment_status,
            factor_of_safety=round(fos, 2) if fos is not None else None,
            calculated_stress_mpa=round(calc_stress_mpa, 2) if calc_stress_mpa is not None else None,
            allowable_stress_mpa=allowable_shear_mpa,
            calculation_certificates=[cert],
            assumptions=cert.assumptions,
            provenance={k: p.model_dump() for k, p in cert.provenance.items()}
        )

    def evaluate_all_shafts(
        self,
        candidate_configs: List[Dict[str, Any]],
        torque_nm: float,
        allowable_shear_mpa: Optional[float] = None,
        design_factor: Optional[float] = None,
        provenance: Optional[Dict[str, Any]] = None
    ) -> List[DesignCandidate]:
        """Evaluates a batch of shaft diameter candidates."""
        evaluated: List[DesignCandidate] = []
        for cfg in candidate_configs:
            cand = self.evaluate_shaft_candidate(
                candidate_data=cfg,
                torque_nm=torque_nm,
                allowable_shear_mpa=allowable_shear_mpa,
                design_factor=design_factor,
                provenance=provenance
            )
            evaluated.append(cand)
        return evaluated
