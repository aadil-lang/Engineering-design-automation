"""
Deterministic Analysis Planner formulating structured mechanical execution plans.
Maps Slice 7 Engineering Rules and user requirements to candidate deterministic solvers.
"""

import uuid
from typing import Dict, List, Optional, Set, Any
from core.models import MechanicalSemanticsResult
from knowledge.models import EngineeringKnowledgeResult, EngineeringRuleMatch
from semantics.models import MechanicalFeature, MechanicalFeatureType
from analysis.models import (
    AnalysisType,
    AnalysisStatus,
    AnalysisPlan,
    AnalysisPlanItem,
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
    Formulates a deterministic engineering analysis plan and execution schedule.
    Evaluates semantic drawing features, rule applicability matches, and user overrides.
    """

    def __init__(self, registry: Optional[AnalysisSolverRegistry] = None):
        self.registry = registry or AnalysisSolverRegistry()

    def create_plan(
        self,
        mechanical_semantics: Optional[MechanicalSemanticsResult] = None,
        engineering_knowledge: Optional[EngineeringKnowledgeResult] = None,
        engineering_inputs: Optional[Dict[str, Any]] = None,
        request: Optional[AnalysisPlanningRequest] = None
    ) -> AnalysisPlan:
        """Generates a complete, auditable AnalysisPlan."""
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        req = request or AnalysisPlanningRequest()
        inputs = dict(engineering_inputs or req.engineering_inputs or {})

        features = mechanical_semantics.features if mechanical_semantics else []
        features_by_id = {f.id: f for f in features}

        # Index Slice 7 rule matches
        rule_matches: Dict[str, EngineeringRuleMatch] = {}
        if engineering_knowledge and engineering_knowledge.applicable_rules:
            for rm in engineering_knowledge.applicable_rules:
                rule_matches[rm.rule_id] = rm

        items: List[AnalysisPlanItem] = []
        processed_types: Set[AnalysisType] = set()
        warnings: List[str] = [
            "Analysis plan formulated; deterministic mechanical calculations are executed when opt-in enabled.",
            "This plan is an engineering execution schedule and does NOT certify mechanical safety."
        ]

        # 1. Process Automatically Recommended Analyses from Knowledge Rules
        if req.recommend_analyses:
            for rule_id, match in rule_matches.items():
                analysis_type = RULE_TO_ANALYSIS_TYPE.get(rule_id)
                if not analysis_type or analysis_type in processed_types:
                    continue

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

            # 1b. Check explicit machine element classification in engineering inputs
            elem_spec = str(inputs.get("machine_element", "")).lower()
            if elem_spec in ("bolted_joint", "bolt", "fastener"):
                if "tensile_load" in inputs and "shear_load" in inputs:
                    if AnalysisType.BOLT_COMBINED_STRESS not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.BOLT_COMBINED_STRESS, features)
                        items.append(self._build_plan_item(AnalysisType.BOLT_COMBINED_STRESS, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.BOLT_COMBINED_STRESS)
                elif "tensile_load" in inputs:
                    if AnalysisType.BOLT_TENSION not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.BOLT_TENSION, features)
                        items.append(self._build_plan_item(AnalysisType.BOLT_TENSION, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.BOLT_TENSION)
                elif "shear_load" in inputs:
                    if AnalysisType.BOLT_SHEAR not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.BOLT_SHEAR, features)
                        items.append(self._build_plan_item(AnalysisType.BOLT_SHEAR, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.BOLT_SHEAR)

                if "preload_factor" in inputs or "proof_stress" in inputs:
                    if AnalysisType.BOLT_PRELOAD not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.BOLT_PRELOAD, features)
                        items.append(self._build_plan_item(AnalysisType.BOLT_PRELOAD, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.BOLT_PRELOAD)
            elif elem_spec in ("shaft", "axle", "rotor", "spindle"):
                if "torque" in inputs and "bending_moment" in inputs:
                    if AnalysisType.COMBINED_STRESS not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.COMBINED_STRESS, features)
                        items.append(self._build_plan_item(AnalysisType.COMBINED_STRESS, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.COMBINED_STRESS)
                elif "torque" in inputs:
                    if AnalysisType.TORSION not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.TORSION, features)
                        items.append(self._build_plan_item(AnalysisType.TORSION, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.TORSION)
                elif "bending_moment" in inputs:
                    if AnalysisType.BENDING not in processed_types:
                        p_feat = self._find_candidate_feature(AnalysisType.BENDING, features)
                        items.append(self._build_plan_item(AnalysisType.BENDING, None, p_feat, inputs, req, from_rule=False))
                        processed_types.add(AnalysisType.BENDING)

        # 2. Process Explicitly Requested Analyses not yet processed
        for requested_type in req.requested_analyses:
            if requested_type in processed_types:
                # Mark existing as user_selected
                for it in items:
                    if it.analysis_type == requested_type:
                        it.user_selected = True
                continue

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

        # 3. Process Disabled Analyses Overrides
        for disabled_type in req.disabled_analyses:
            already_item = next((it for it in items if it.analysis_type == disabled_type), None)
            if already_item:
                already_item.status = AnalysisStatus.USER_DISABLED
                already_item.user_disabled = True
                already_item.rationale = f"Analysis '{disabled_type.value}' was explicitly disabled by user override."
                already_item.limitations.append("Disabled by user request; excluded from planned execution.")
            else:
                items.append(
                    AnalysisPlanItem(
                        analysis_type=disabled_type,
                        status=AnalysisStatus.USER_DISABLED,
                        priority="low",
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
        blocked_analyses = [it.analysis_type for it in items if it.status in (AnalysisStatus.BLOCKED, AnalysisStatus.MISSING_INPUTS)]
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
            f"Execution target is planned deterministic solver '{solver_id}'.",
            "Analysis plan does NOT perform numerical stress evaluation or certify safety."
        ]
        if rule_match and rule_match.limitations:
            limitations.extend(rule_match.limitations)

        assumptions = []
        if analysis_type == AnalysisType.HOLE_PATTERN_LOAD:
            assumptions.append("Equal load sharing among pattern fastener holes is assumed unless pitch-stiffness variation is modeled.")
        if analysis_type == AnalysisType.TORSION:
            assumptions.append("Uniform circular shaft cross-section; Saint-Venant torsional shear distribution assumed.")
        if analysis_type in (AnalysisType.BOLT_TENSION, AnalysisType.BOLT_SHEAR, AnalysisType.BOLT_COMBINED_STRESS, AnalysisType.BOLT_PRELOAD):
            assumptions.append("Bolted joint analytical calculation; prying and gasket relaxation not modeled.")

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
        if analysis_type in (AnalysisType.BOLT_TENSION, AnalysisType.BOLT_SHEAR, AnalysisType.BOLT_COMBINED_STRESS, AnalysisType.BOLT_PRELOAD):
            hp = next((f for f in features if f.feature_type == MechanicalFeatureType.HOLE_PATTERN), None)
            if hp:
                return hp
            return next((f for f in features if f.feature_type == MechanicalFeatureType.HOLE), None)
        return None

    def _check_prerequisites(self, items: List[AnalysisPlanItem]) -> None:
        """Verifies that prerequisite analyses are satisfied."""
        status_by_type = {it.analysis_type: it.status for it in items}

        for it in items:
            prereqs = self.registry.get_prerequisites(it.analysis_type)
            for p in prereqs:
                p_status = status_by_type.get(p)
                if p_status in (AnalysisStatus.USER_DISABLED, AnalysisStatus.BLOCKED):
                    it.status = AnalysisStatus.BLOCKED
                    it.rationale = f"Prerequisite analysis '{p.value}' is {p_status.value}; '{it.analysis_type.value}' is blocked."
