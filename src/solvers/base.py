"""
Abstract base class and shared utilities for deterministic mechanical solvers.
"""

from abc import ABC, abstractmethod
import uuid
from typing import Dict, List, Optional, Any
from solvers.models import (
    CalculationCertificate,
    CertificateStatus,
    AssessmentResult,
    AssessmentStatus,
    InputProvenance,
    MachineElementType,
    AnalysisCapability,
    EngineeringAssumption
)


class MechanicalSolver(ABC):
    """
    Abstract base class for all closed-form deterministic engineering solvers.
    Enforces strict input validation, transparent unit conversion, audit step generation,
    engineering assessments, and explicit physical assumptions and limitations.
    """

    @property
    @abstractmethod
    def solver_id(self) -> str:
        """Unique identifier of the deterministic solver (e.g., 'py_mech_torsion_v1')."""
        pass

    @property
    @abstractmethod
    def solver_version(self) -> str:
        """Version string of the solver."""
        pass

    @property
    @abstractmethod
    def analysis_type(self) -> str:
        """The canonical analysis type this solver executes (e.g., 'shaft_torsion')."""
        pass

    @property
    @abstractmethod
    def machine_element(self) -> MachineElementType:
        """The primary machine element category (e.g., SHAFT, BOLTED_JOINT, BEAM)."""
        pass

    @property
    @abstractmethod
    def required_inputs(self) -> List[str]:
        """List of required input parameter names."""
        pass

    @property
    @abstractmethod
    def optional_inputs(self) -> List[str]:
        """List of optional input parameter names."""
        pass

    @property
    @abstractmethod
    def default_assumptions(self) -> List[str]:
        """Standard physical assumptions underpinning this closed-form formulation."""
        pass

    @property
    @abstractmethod
    def default_limitations(self) -> List[str]:
        """Boundary conditions, stress concentrations, or geometric limitations."""
        pass

    def get_capability(self) -> AnalysisCapability:
        """Returns standard metadata describing this solver's capabilities and boundaries."""
        return AnalysisCapability(
            analysis_type=self.analysis_type,
            machine_element=self.machine_element,
            solver_id=self.solver_id,
            required_inputs=self.required_inputs,
            optional_inputs=self.optional_inputs,
            applicability_criteria=f"Applicable to {self.machine_element.value} machine elements.",
            is_solver_available=True,
            can_assess=True,
            limitations=self.default_limitations
        )

    @abstractmethod
    def solve(
        self,
        inputs: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        """
        Executes deterministic mechanical calculations on validated inputs.
        Returns a CalculationCertificate with mathematical steps, results, and assessments.
        """
        pass

    def _build_provenance_map(
        self,
        inputs: Dict[str, Any],
        raw_provenance: Optional[Dict[str, Any]] = None,
        assumed_provenance: Optional[Dict[str, InputProvenance]] = None
    ) -> Dict[str, InputProvenance]:
        """
        Constructs typed InputProvenance objects for audit records.
        Strictly distinguishes user-provided data from assumed defaults or derived approximations.
        """
        prov_map: Dict[str, InputProvenance] = {}
        raw_prov = raw_provenance or {}
        assumed_prov = assumed_provenance or {}

        # 1. Process inputs
        for k, v in inputs.items():
            if k in raw_prov:
                entry = raw_prov[k]
                if isinstance(entry, InputProvenance):
                    prov_map[k] = entry
                elif isinstance(entry, dict):
                    prov_map[k] = InputProvenance(
                        value=entry.get("value", v),
                        unit=entry.get("unit"),
                        source=entry.get("source", "engineering_inputs"),
                        source_id=entry.get("source_id"),
                        is_assumed=entry.get("is_assumed", False),
                        assumption_rationale=entry.get("assumption_rationale")
                    )
                else:
                    prov_map[k] = InputProvenance(
                        value=v,
                        source=str(entry),
                        is_assumed=False
                    )
            elif k in assumed_prov:
                prov_map[k] = assumed_prov[k]
            else:
                prov_map[k] = InputProvenance(
                    value=v,
                    source="engineering_inputs",
                    is_assumed=False
                )

        # 2. Add any assumed parameters not explicitly in inputs (e.g., derived areas, default factors)
        for k, entry in assumed_prov.items():
            if k not in prov_map:
                prov_map[k] = entry

        return prov_map

    def _generate_certificate_id(self) -> str:
        """Generates a unique deterministic certificate identifier."""
        return f"cert-{self.solver_id}-{uuid.uuid4().hex[:8]}"

    def _create_stress_assessment(
        self,
        assessment_type: str,
        calculated_stress_pa: float,
        allowable_stress_pa: Optional[float] = None,
        design_factor: Optional[float] = None,
        stress_name: str = "stress"
    ) -> AssessmentResult:
        """
        Evaluates calculated stress against allowable limits with conservative engineering language.
        Rules:
        - If calculated <= allowable / design_factor: PASS
        - If calculated > allowable / design_factor: FAIL
        - If allowable is None: NOT_ASSESSED
        Never states 'the component is safe'.
        """
        calc_mpa = calculated_stress_pa / 1e6

        if allowable_stress_pa is None:
            return AssessmentResult(
                assessment_type=assessment_type,
                status=AssessmentStatus.NOT_ASSESSED,
                calculated_value=calc_mpa,
                calculated_unit="MPa",
                summary=f"No allowable {stress_name} supplied; engineering pass/fail assessment cannot be completed."
            )

        allow_mpa = allowable_stress_pa / 1e6
        effective_allowable = allow_mpa / (design_factor if design_factor and design_factor > 0 else 1.0)

        fos = (allow_mpa / calc_mpa) if calc_mpa > 1e-9 else float("inf")
        margin = (effective_allowable - calc_mpa) / effective_allowable if effective_allowable > 0 else 0.0

        if calc_mpa <= effective_allowable:
            status = AssessmentStatus.PASS
            df_clause = f" (factored by design factor {design_factor:.2f})" if design_factor else ""
            summary = (
                f"Calculated {stress_name} ({calc_mpa:.2f} MPa) is below the supplied allowable "
                f"{stress_name} ({allow_mpa:.2f} MPa{df_clause}) with a Factor of Safety of {fos:.2f}."
            )
        else:
            status = AssessmentStatus.FAIL
            df_clause = f" (factored by design factor {design_factor:.2f})" if design_factor else ""
            summary = (
                f"Calculated {stress_name} ({calc_mpa:.2f} MPa) exceeds the supplied allowable "
                f"{stress_name} ({allow_mpa:.2f} MPa{df_clause}); Factor of Safety is {fos:.2f}."
            )

        return AssessmentResult(
            assessment_type=assessment_type,
            status=status,
            allowable_value=allow_mpa,
            allowable_unit="MPa",
            calculated_value=calc_mpa,
            calculated_unit="MPa",
            factor_of_safety=round(fos, 3) if fos != float("inf") else None,
            margin_of_safety=round(margin, 3),
            design_factor=design_factor,
            summary=summary
        )
