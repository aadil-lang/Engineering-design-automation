"""
Solver Runner orchestrating the execution of planned mechanical analyses across machine elements.
"""

from typing import Dict, List, Optional, Any
from analysis.models import AnalysisPlan, AnalysisPlanItem, AnalysisStatus
from semantics.models import MechanicalFeature
from solvers.models import (
    CalculationCertificate,
    InputProvenance
)
from solvers.registry import SolverRegistry, get_solver_registry
from solvers.validation import SolverValidationError


class SolverRunner:
    """
    Orchestrates execution of deterministic mechanical solvers across multiple machine elements
    (Shafts, Bolted Joints, Beams, etc.).
    Validates plan item execution eligibility, resolves inputs and provenance from
    operating inputs and recognized drawing features, and produces CalculationCertificates.
    """

    def __init__(self, registry: Optional[SolverRegistry] = None):
        self.registry = registry or get_solver_registry()

    def execute_plan(
        self,
        plan: AnalysisPlan,
        features: Optional[List[MechanicalFeature]] = None,
        operating_inputs: Optional[Dict[str, Any]] = None
    ) -> List[CalculationCertificate]:
        """
        Executes all eligible (READY or USER_REQUESTED_READY) items in an AnalysisPlan.
        Skips disabled or blocked items. Returns generated calculation certificates.
        """
        certificates: List[CalculationCertificate] = []
        op_inputs = dict(operating_inputs or {})

        for item in plan.items:
            if not self.is_eligible_for_execution(item):
                continue

            try:
                cert = self.execute_item(item, features=features, operating_inputs=op_inputs)
                certificates.append(cert)
            except Exception as e:
                # Re-raise deterministic validation/calculation errors
                raise e

        return certificates

    def is_eligible_for_execution(self, item: AnalysisPlanItem) -> bool:
        """Determines if an AnalysisPlanItem is in a calculable state and has an available solver."""
        if item.status not in (AnalysisStatus.READY,):
            return False
        if item.user_disabled:
            return False
        if item.missing_calculation_inputs:
            return False
        target_solver = item.solver_id or item.analysis_type
        if not self.registry.is_available(target_solver):
            return False
        return True

    def execute_item(
        self,
        item: AnalysisPlanItem,
        features: Optional[List[MechanicalFeature]] = None,
        operating_inputs: Optional[Dict[str, Any]] = None
    ) -> CalculationCertificate:
        """
        Executes a single AnalysisPlanItem through its designated deterministic solver.
        Raises SolverValidationError if item is not eligible, inputs are missing, or solver is unavailable.
        """
        type_str = item.analysis_type.value if hasattr(item.analysis_type, "value") else str(item.analysis_type)
        status_str = item.status.value if hasattr(item.status, "value") else str(item.status)

        # 1. Enforce eligibility
        if item.user_disabled or item.status in (AnalysisStatus.USER_DISABLED, AnalysisStatus.BLOCKED, AnalysisStatus.NOT_APPLICABLE):
            raise SolverValidationError(
                f"Analysis item '{type_str}' cannot be executed because its status is '{status_str}'."
            )

        if item.missing_calculation_inputs:
            raise SolverValidationError(
                f"Analysis item '{type_str}' is missing calculation input(s): {item.missing_calculation_inputs}"
            )

        # 2. Resolve solver
        target_solver_key = item.solver_id or item.analysis_type
        solver = self.registry.get_solver(target_solver_key)
        if solver is None:
            raise SolverValidationError(
                f"No deterministic solver available for '{target_solver_key}'."
            )

        # 3. Resolve input parameters and provenance
        resolved_inputs, provenance_map = self._resolve_inputs_and_provenance(
            item=item,
            features=features or [],
            operating_inputs=operating_inputs or {}
        )

        # 4. Execute solver
        certificate = solver.solve(inputs=resolved_inputs, provenance=provenance_map)
        return certificate

    def _resolve_inputs_and_provenance(
        self,
        item: AnalysisPlanItem,
        features: List[MechanicalFeature],
        operating_inputs: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, InputProvenance]]:
        """
        Collects parameter values from:
        1. Feature attributes (if item references a feature_id or id)
        2. operating_inputs / available_inputs
        Handles both shaft and bolted joint machine elements.
        """
        inputs: Dict[str, Any] = {}
        prov: Dict[str, InputProvenance] = {}

        # 1. Check feature attributes
        target_feat: Optional[MechanicalFeature] = None
        if item.feature_ids:
            fid = item.feature_ids[0]
            target_feat = next(
                (f for f in features if getattr(f, "id", None) == fid or getattr(f, "feature_id", None) == fid),
                None
            )
        elif features:
            target_feat = features[0]

        if target_feat and target_feat.attributes:
            feat_id = getattr(target_feat, "id", getattr(target_feat, "feature_id", "feat-0"))
            attrs = target_feat.attributes

            # Shaft Diameter & Length
            diam = attrs.get("nominal_diameter") or attrs.get("diameter") or attrs.get("shaft_diameter")
            if diam is not None:
                inputs["shaft_diameter"] = float(diam)
                prov["shaft_diameter"] = InputProvenance(
                    value=float(diam),
                    unit="mm",
                    source="mechanical_semantics",
                    source_id=feat_id
                )

            length = attrs.get("length") or attrs.get("shaft_length")
            if length is not None:
                inputs["shaft_length"] = float(length)
                prov["shaft_length"] = InputProvenance(
                    value=float(length),
                    unit="mm",
                    source="mechanical_semantics",
                    source_id=feat_id
                )

            # Bolted Joint Attributes
            bolt_d = attrs.get("bolt_diameter") or attrs.get("hole_diameter") or attrs.get("fastener_diameter")
            if bolt_d is not None:
                inputs["bolt_diameter"] = float(bolt_d)
                prov["bolt_diameter"] = InputProvenance(
                    value=float(bolt_d),
                    unit="mm",
                    source="mechanical_semantics",
                    source_id=feat_id
                )

            bolt_cnt = attrs.get("bolt_count") or attrs.get("hole_count")
            if bolt_cnt is not None:
                inputs["bolt_count"] = int(bolt_cnt)
                prov["bolt_count"] = InputProvenance(
                    value=int(bolt_cnt),
                    source="mechanical_semantics",
                    source_id=feat_id
                )

        # 2. Merge operating inputs
        for k, v in operating_inputs.items():
            inputs[k] = v
            prov[k] = InputProvenance(
                value=v,
                source="engineering_inputs"
            )

        # Aliases for Shaft
        if "diameter" in inputs and "shaft_diameter" not in inputs:
            inputs["shaft_diameter"] = inputs["diameter"]
            if "diameter" in prov:
                prov["shaft_diameter"] = prov["diameter"]

        if "moment" in inputs and "bending_moment" not in inputs:
            inputs["bending_moment"] = inputs["moment"]
            if "moment" in prov:
                prov["bending_moment"] = prov["moment"]

        # Aliases for Bolted Joint
        if "diameter" in inputs and "bolt_diameter" not in inputs and "shaft_diameter" not in inputs:
            inputs["bolt_diameter"] = inputs["diameter"]
            if "diameter" in prov:
                prov["bolt_diameter"] = prov["diameter"]

        if "bolt_nominal_diameter" in inputs and "bolt_diameter" not in inputs:
            inputs["bolt_diameter"] = inputs["bolt_nominal_diameter"]
            if "bolt_nominal_diameter" in prov:
                prov["bolt_diameter"] = prov["bolt_nominal_diameter"]

        return inputs, prov
