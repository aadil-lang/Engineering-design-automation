"""
Deterministic execution planner for engineering analysis.
Transforms mechanical semantics and applicability rules into a structured, auditable AnalysisPlan.
"""

import uuid
from typing import List, Dict, Any, Optional, Set
from semantics.models import MechanicalSemanticsResult, MechanicalFeatureType, MechanicalFeature
from knowledge.models import EngineeringKnowledgeResult, EngineeringRuleMatch
from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlanItem,
    AnalysisPlan,
    AnalysisPlanningRequest
)
from analysis.config import (
    DEFAULT_PLANNER_VERSION,
    DEFAULT_PRIORITIES,
    PRIORITY_MEDIUM
)
from analysis.inputs import resolve_analysis_inputs
from analysis.applicability import AnalysisSolverRegistry


# Mapping from Slice 7 rule IDs to AnalysisType
RULE_TO_ANALYSIS_TYPE: Dict[str, AnalysisType] = {
    "shaft_torsion_applicability": AnalysisType.TORSION,
    "shaft_bending_applicability": AnalysisType.BENDING,
    "shaft_combined_stress_applicability": AnalysisType.COMBINED_STRESS,
    "fatigue_analysis_applicability": AnalysisType.FATIGUE,
    "buckling_analysis_applicability": AnalysisType.BUCKLING,
    "deflection_analysis_applicability": AnalysisType.DEFLECTION,
    "hole_pattern_engineering_requirements": AnalysisType.HOLE_PATTERN_LOAD
}


class AnalysisPlanner:
    """
    Formulates a deterministic analysis execution plan based on mechanical semantics,
    knowledge applicability rules, engineering inputs, and user preferences.
    Does NOT perform numerical calculations.
    """

    def __init__(self, solver_registry: Optional[AnalysisSolverRegistry] = None):
        self.registry = solver_registry or AnalysisSolverRegistry()

    def create_plan(
        self,
        mechanical_semantics: Optional[MechanicalSemanticsResult] = None,
        engineering_knowledge: Optional[EngineeringKnowledgeResult] = None,
        engineering_inputs: Optional[Dict[str, Any]] = None,
        request: Optional[AnalysisPlanningRequest] = None
    ) -> AnalysisPlan:
        """
        Generates an AnalysisPlan respecting knowledge rules and user controls.
        User controls (requested / disabled) take precedence over automatic recommendations.
        """
        req = request or AnalysisPlanningRequest()
        inputs = dict(req.engineering_inputs or (engineering_inputs or {}))
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        features = mechanical_semantics.features if mechanical_semantics else []
        features_by_id = {f.id: f for f in features}

        # Index Slice 7 rule matches by rule_id
        rule_matches: Dict[str, EngineeringRuleMatch] = {}
        if engineering_knowledge and engineering_knowledge.applicable_rules:
            for rm in engineering_knowledge.applicable_rules:
                rule_matches[rm.rule_id] = rm

        items: List[AnalysisPlanItem] = []
        processed_types: Set[AnalysisType] = set()
        warnings: List[str] = [
            "Analysis plan formulated; deterministic mechanical calculations are pending solver implementation (Slice 9+).",
            "This plan is an engineering execution schedule and does NOT certify mechanical safety."
        ]

        # 1. Process Automatically Recommended Analyses from Knowledge Rules
        if req.recommend_analyses:
            for rule_id, match in rule_matches.items():
                analysis_type = RULE_TO_ANALYSIS_TYPE.get(rule_id)
                if not analysis_type or analysis_type in processed_types:
                    continue

                # Associate primary feature (from evidence_ids or candidate lookup)
                primary_feature: Optional[MechanicalFeature] = None
                for ev_id in match.evidence_ids:
                    if ev_id in features_by_id:
                        primary_feature = features_by_id[ev_id]
                        break
                if primary_feature is None:
                    primary_feature = self._find_candidate_feature(analysis_type, features)

                item = self._build_plan_item(
                    analysis_type=analysis_type,
                    rule_match=match,
                    primary_feature=primary_feature,
                    engineering_inputs=inputs,
                    request=req,
                    from_rule=True
                )
                items.append(item)
                processed_types.add(analysis_type)

        # 2. Process Explicitly Requested Analyses not yet processed
        for requested_type in req.requested_analyses:
            if requested_type in processed_types:
                # Mark existing as user_selected
                for it in items:
                    if it.analysis_type == requested_type:
                        it.user_selected = True
                continue

            # User explicitly requested an analysis not automatically triggered by knowledge rules
            primary_feat = self._find_candidate_feature(requested_type, features)
            item = self._build_plan_item(
                analysis_type=requested_type,
                rule_match=None,
                primary_feature=primary_feat,
                engineering_inputs=inputs,
                request=req,
                from_rule=False
            )
            item.user_selected = True
            items.append(item)
            processed_types.add(requested_type)

        # 3. Apply Explicit User Disabled Overrides
        for disabled_type in req.disabled_analyses:
            # Check if already in items
            found = False
            for it in items:
                if it.analysis_type == disabled_type:
                    it.status = AnalysisStatus.USER_DISABLED
                    it.user_disabled = True
                    it.rationale = f"Analysis '{disabled_type.value}' was explicitly disabled by user override."
                    found = True
            if not found:
                items.append(
                    AnalysisPlanItem(
                        analysis_type=disabled_type,
                        status=AnalysisStatus.USER_DISABLED,
                        priority=DEFAULT_PRIORITIES.get(disabled_type, PRIORITY_MEDIUM),
                        rationale=f"Analysis '{disabled_type.value}' was explicitly disabled by user override.",
                        user_disabled=True,
                        limitations=["Disabled by user request; excluded from planned execution."]
                    )
                )
                processed_types.add(disabled_type)

        # 4. Check Prerequisites for Combined / Multiaxial Analyses
        self._check_prerequisites(items)

        # 5. Compile Summary Sets
        ready_analyses = [it.analysis_type for it in items if it.status == AnalysisStatus.READY]
        blocked_analyses = [it.analysis_type for it in items if it.status == AnalysisStatus.BLOCKED]
        recommended_analyses = [
            it.analysis_type for it in items
            if it.status in (AnalysisStatus.READY, AnalysisStatus.RECOMMENDED, AnalysisStatus.MISSING_INPUTS)
            and not it.user_disabled
        ]

        all_missing_inputs: Set[str] = set()
        for it in items:
            if it.status not in (AnalysisStatus.USER_DISABLED, AnalysisStatus.NOT_APPLICABLE):
                all_missing_inputs.update(it.missing_inputs)

        return AnalysisPlan(
            plan_id=plan_id,
            items=items,
            recommended_analyses=recommended_analyses,
            ready_analyses=ready_analyses,
            blocked_analyses=blocked_analyses,
            missing_inputs=sorted(all_missing_inputs),
            warnings=warnings,
            planner_version=DEFAULT_PLANNER_VERSION
        )

    def _build_plan_item(
        self,
        analysis_type: AnalysisType,
        rule_match: Optional[EngineeringRuleMatch],
        primary_feature: Optional[MechanicalFeature],
        engineering_inputs: Dict[str, Any],
        request: AnalysisPlanningRequest,
        from_rule: bool
    ) -> AnalysisPlanItem:
        """Constructs an individual AnalysisPlanItem evaluating calculation and assessment inputs."""
        solver_id = self.registry.get_solver_id(analysis_type)
        priority = DEFAULT_PRIORITIES.get(analysis_type, PRIORITY_MEDIUM)

        # Resolve available, missing calculation, and missing assessment inputs
        resolved = resolve_analysis_inputs(
            analysis_type=analysis_type,
            engineering_inputs=engineering_inputs,
            feature=primary_feature
        )

        calc_missing = resolved["missing_calculation_inputs"]
        assess_missing = resolved["missing_assessment_inputs"]
        missing_all = resolved["missing_inputs"]
        available_all = resolved["available_inputs"]
        required_all = resolved["required_inputs"]

        feature_ids = [primary_feature.id] if primary_feature else []
        evidence_ids = list(rule_match.evidence_ids) if (rule_match and rule_match.evidence_ids) else list(feature_ids)

        # Handle user disable check
        is_user_disabled = analysis_type in request.disabled_analyses
        is_user_selected = analysis_type in request.requested_analyses

        if is_user_disabled:
            status = AnalysisStatus.USER_DISABLED
            rationale = f"Analysis '{analysis_type.value}' is disabled by user override."
        elif len(calc_missing) > 0:
            status = AnalysisStatus.MISSING_INPUTS
            missing_str = ", ".join(calc_missing)
            if rule_match:
                rationale = f"{rule_match.rationale} Cannot execute calculation: missing required calculation input(s): {missing_str}."
            else:
                rationale = f"Analysis '{analysis_type.value}' requested but cannot execute: missing required calculation input(s): {missing_str}."
        else:
            # Calculation inputs are satisfied
            status = AnalysisStatus.READY
            if rule_match:
                base_rationale = rule_match.rationale
            else:
                feat_desc = f"feature '{primary_feature.id}'" if primary_feature else "supplied geometry"
                base_rationale = f"Required calculation inputs for {analysis_type.value} on {feat_desc} are available."

            if len(assess_missing) > 0:
                rationale = (
                    f"{base_rationale} Raw mechanical calculation is READY for deterministic solver '{solver_id}'. "
                    f"Safety factor assessment requires: {', '.join(assess_missing)}."
                )
            else:
                rationale = (
                    f"{base_rationale} Calculation and assessment inputs are available; "
                    f"analysis is READY for deterministic solver '{solver_id}'."
                )

        prereqs = [p.value for p in self.registry.get_prerequisites(analysis_type)]

        limitations = [
            f"Execution target is planned deterministic solver '{solver_id}' (Slice 9+).",
            "Analysis plan does NOT perform numerical stress evaluation or certify safety."
        ]
        if rule_match and rule_match.limitations:
            limitations.extend(rule_match.limitations)

        assumptions = []
        if analysis_type == AnalysisType.HOLE_PATTERN_LOAD:
            assumptions.append("Equal load sharing among pattern fastener holes is assumed unless pitch-stiffness variation is modeled.")
        if analysis_type == AnalysisType.TORSION:
            assumptions.append("Uniform circular shaft cross-section; Saint-Venant torsional shear distribution assumed.")

        confidence = rule_match.confidence if rule_match else 0.90

        return AnalysisPlanItem(
            analysis_type=analysis_type,
            status=status,
            priority=priority,
            rationale=rationale,
            feature_ids=feature_ids,
            evidence_ids=evidence_ids,
            required_inputs=required_all,
            available_inputs=available_all,
            missing_inputs=missing_all,
            calculation_inputs=resolved["calculation_inputs"],
            assessment_inputs=resolved["assessment_inputs"],
            missing_calculation_inputs=calc_missing,
            missing_assessment_inputs=assess_missing,
            solver_id=solver_id,
            prerequisites=prereqs,
            assumptions=assumptions,
            limitations=limitations,
            confidence=confidence,
            user_selected=is_user_selected,
            user_disabled=is_user_disabled
        )

    def _find_candidate_feature(
        self,
        analysis_type: AnalysisType,
        features: List[MechanicalFeature]
    ) -> Optional[MechanicalFeature]:
        """Finds the most relevant semantic feature for a requested analysis type."""
        if analysis_type in (AnalysisType.TORSION, AnalysisType.BENDING, AnalysisType.COMBINED_STRESS, AnalysisType.BUCKLING):
            return next((f for f in features if f.feature_type == MechanicalFeatureType.SHAFT), None)
        if analysis_type == AnalysisType.HOLE_PATTERN_LOAD:
            return next((f for f in features if f.feature_type == MechanicalFeatureType.HOLE_PATTERN), None)
        if analysis_type == AnalysisType.BEARING_STRESS:
            return next((f for f in features if f.feature_type in (MechanicalFeatureType.HOLE, MechanicalFeatureType.SHAFT)), None)
        if analysis_type == AnalysisType.DEFLECTION:
            return next((f for f in features if f.feature_type in (MechanicalFeatureType.SHAFT, MechanicalFeatureType.RECTANGULAR_PLATE)), None)
        return None

    def _check_prerequisites(self, items: List[AnalysisPlanItem]) -> None:
        """Verifies that prerequisite analyses are satisfied."""
        status_by_type = {it.analysis_type: it.status for it in items}

        for it in items:
            prereqs = self.registry.get_prerequisites(it.analysis_type)
            for p in prereqs:
                p_status = status_by_type.get(p)
                # If prerequisite is user-disabled or blocked, mark dependent analysis as blocked
                if p_status in (AnalysisStatus.USER_DISABLED, AnalysisStatus.BLOCKED):
                    it.status = AnalysisStatus.BLOCKED
                    it.rationale = f"Prerequisite analysis '{p.value}' is {p_status.value}; '{it.analysis_type.value}' is blocked."
