"""
Deterministic applicability engine evaluating engineering rules against mechanical semantics
and supplied engineering inputs.
"""

from typing import List, Dict, Any, Optional, Set
from semantics.models import MechanicalSemanticsResult, MechanicalFeatureType
from annotations.models import AnnotationsResult
from knowledge.models import (
    EngineeringKnowledgeResult,
    EngineeringRuleMatch,
    EngineeringKnowledgeItem,
    MissingInformationItem
)
from knowledge.knowledge_base import BuiltInEngineeringKnowledgeBase
from knowledge.config import (
    BUCKLING_SLENDERNESS_MIN,
    RULE_CONFIDENCE_EXPLICIT,
    RULE_CONFIDENCE_POTENTIAL
)


class EngineeringApplicabilityEngine:
    """
    Evaluates mechanical semantics and supplied engineering context against
    deterministic engineering rules to determine relevant analyses and missing information.
    Does NOT perform mechanical stress or numerical calculations.
    """

    def __init__(self, knowledge_base: Optional[BuiltInEngineeringKnowledgeBase] = None):
        self.kb = knowledge_base or BuiltInEngineeringKnowledgeBase()

    def evaluate(
        self,
        mechanical_semantics: Optional[MechanicalSemanticsResult] = None,
        annotations: Optional[AnnotationsResult] = None,
        engineering_inputs: Optional[Dict[str, Any]] = None
    ) -> EngineeringKnowledgeResult:
        """
        Determines applicable engineering rules, surfaces missing inputs,
        and retrieves relevant knowledge items.
        """
        inputs = engineering_inputs or {}
        features = mechanical_semantics.features if mechanical_semantics else []
        warnings: List[str] = []

        if not features:
            warnings.append("No mechanical semantic features provided; knowledge evaluation limited to input parameters.")

        applicable_rules: List[EngineeringRuleMatch] = []
        missing_info: List[MissingInformationItem] = []
        relevant_feature_types: Set[str] = set()

        # Categorize detected features
        shafts = [f for f in features if f.feature_type == MechanicalFeatureType.SHAFT]
        holes = [f for f in features if f.feature_type == MechanicalFeatureType.HOLE]
        patterns = [f for f in features if f.feature_type == MechanicalFeatureType.HOLE_PATTERN]
        plates = [f for f in features if f.feature_type == MechanicalFeatureType.RECTANGULAR_PLATE]

        for f in features:
            type_str = f.feature_type.value if hasattr(f.feature_type, "value") else str(f.feature_type)
            relevant_feature_types.add(type_str)

        # -------------------------------------------------------------------
        # Rule A: Shaft Torsion
        # -------------------------------------------------------------------
        rule_torsion = self.kb.get_rule("shaft_torsion_applicability")
        if rule_torsion and shafts:
            for s in shafts:
                has_torque = "torque" in inputs or "T" in inputs
                diam = s.attributes.get("diameter") or inputs.get("shaft_diameter")
                allowable = inputs.get("material_allowable_stress") or inputs.get("allowable_stress")

                missing = []
                if not has_torque:
                    missing.append("torque")
                if diam is None:
                    missing.append("shaft_diameter")
                if allowable is None:
                    missing.append("material_allowable_stress")

                evidence_ids = [s.id]
                if has_torque:
                    evidence_ids.append("input:torque")

                is_applicable = True
                if has_torque:
                    rationale = f"Shaft feature '{s.id}' is present and torque is supplied ({inputs.get('torque', inputs.get('T'))}); torsional shear stress analysis is relevant."
                    conf = RULE_CONFIDENCE_EXPLICIT
                else:
                    rationale = f"Shaft feature '{s.id}' is present; torsional stress analysis may be applicable if torque is transmitted. Torque is currently missing."
                    conf = RULE_CONFIDENCE_POTENTIAL

                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_torsion.id,
                        applicability=is_applicable,
                        rationale=rationale,
                        required_inputs=rule_torsion.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=evidence_ids,
                        confidence=conf,
                        limitations=rule_torsion.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing input '{m}' required for shaft torsional assessment on '{s.id}'.",
                            feature_id=s.id,
                            rule_id=rule_torsion.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule B: Shaft Bending
        # -------------------------------------------------------------------
        rule_bending = self.kb.get_rule("shaft_bending_applicability")
        if rule_bending and shafts:
            has_bending_load = any(k in inputs for k in ("transverse_load", "bending_moment", "radial_load"))
            # Conservative: If shaft exists but no bending load is supplied, do NOT assume bending
            if has_bending_load:
                for s in shafts:
                    diam = s.attributes.get("diameter") or inputs.get("shaft_diameter")
                    length = s.attributes.get("length") or inputs.get("shaft_length")
                    supports = inputs.get("support_conditions")
                    allowable = inputs.get("material_allowable_stress")

                    missing = []
                    if diam is None:
                        missing.append("shaft_diameter")
                    if length is None:
                        missing.append("shaft_length")
                    if not supports:
                        missing.append("support_conditions")
                    if allowable is None:
                        missing.append("material_allowable_stress")

                    applicable_rules.append(
                        EngineeringRuleMatch(
                            rule_id=rule_bending.id,
                            applicability=True,
                            rationale=f"Shaft feature '{s.id}' is present with transverse/bending loading supplied; bending stress analysis is applicable.",
                            required_inputs=rule_bending.required_inputs,
                            missing_inputs=missing,
                            evidence_ids=[s.id, "input:bending_load"],
                            confidence=RULE_CONFIDENCE_EXPLICIT,
                            limitations=rule_bending.limitations
                        )
                    )
                    for m in missing:
                        missing_info.append(
                            MissingInformationItem(
                                field=m,
                                description=f"Missing input '{m}' required for shaft bending analysis on '{s.id}'.",
                                feature_id=s.id,
                                rule_id=rule_bending.id
                            )
                        )

        # -------------------------------------------------------------------
        # Rule C: Combined Shaft Loading
        # -------------------------------------------------------------------
        rule_combined = self.kb.get_rule("shaft_combined_stress_applicability")
        if rule_combined and shafts:
            has_torque = "torque" in inputs or "T" in inputs
            has_bending_load = any(k in inputs for k in ("transverse_load", "bending_moment", "radial_load"))
            if has_torque and has_bending_load:
                for s in shafts:
                    missing = []
                    if "yield_strength" not in inputs:
                        missing.append("yield_strength")
                    if "shaft_diameter" not in inputs and "diameter" not in s.attributes:
                        missing.append("shaft_diameter")

                    applicable_rules.append(
                        EngineeringRuleMatch(
                            rule_id=rule_combined.id,
                            applicability=True,
                            rationale=f"Shaft '{s.id}' is subjected to both torsional and bending loads simultaneously; combined multiaxial stress evaluation (von Mises) is applicable.",
                            required_inputs=rule_combined.required_inputs,
                            missing_inputs=missing,
                            evidence_ids=[s.id, "input:torque", "input:bending_load"],
                            confidence=RULE_CONFIDENCE_EXPLICIT,
                            limitations=rule_combined.limitations
                        )
                    )
                    for m in missing:
                        missing_info.append(
                            MissingInformationItem(
                                field=m,
                                description=f"Missing input '{m}' required for combined stress analysis on '{s.id}'.",
                                feature_id=s.id,
                                rule_id=rule_combined.id
                            )
                        )

        # -------------------------------------------------------------------
        # Rule D: Fatigue
        # -------------------------------------------------------------------
        rule_fatigue = self.kb.get_rule("fatigue_analysis_applicability")
        if rule_fatigue:
            has_cyclic = any(
                inputs.get(k) is True or (isinstance(inputs.get(k), (int, float)) and inputs.get(k) > 0)
                for k in ("cyclic_loading", "repeated_loading", "alternating_load", "fatigue_cycles")
            )
            # Conservative: Only applicable if cyclic loading is explicitly indicated
            if has_cyclic:
                missing = [
                    req for req in ("stress_amplitude", "mean_stress", "endurance_limit", "surface_finish_factor")
                    if req not in inputs
                ]
                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_fatigue.id,
                        applicability=True,
                        rationale="Cyclic or repeated loading is explicitly indicated in inputs; fatigue life analysis is applicable.",
                        required_inputs=rule_fatigue.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=["input:cyclic_loading"],
                        confidence=RULE_CONFIDENCE_EXPLICIT,
                        limitations=rule_fatigue.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing parameter '{m}' required for fatigue evaluation.",
                            rule_id=rule_fatigue.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule E: Buckling
        # -------------------------------------------------------------------
        rule_buckling = self.kb.get_rule("buckling_analysis_applicability")
        if rule_buckling and shafts:
            has_compression = any(k in inputs for k in ("compressive_load", "axial_compression", "P_comp"))
            # Conservative: Only applicable if member is slender AND compressive load is known
            if has_compression:
                for s in shafts:
                    length = s.attributes.get("length", 0.0)
                    diam = s.attributes.get("diameter", 1.0)
                    slenderness = length / diam if diam > 0 else 0.0

                    if slenderness >= BUCKLING_SLENDERNESS_MIN or "compressive_load" in inputs:
                        missing = [
                            req for req in ("effective_length", "column_cross_section", "elastic_modulus")
                            if req not in inputs
                        ]
                        applicable_rules.append(
                            EngineeringRuleMatch(
                                rule_id=rule_buckling.id,
                                applicability=True,
                                rationale=f"Shaft '{s.id}' is subjected to axial compressive loading; column buckling analysis is applicable.",
                                required_inputs=rule_buckling.required_inputs,
                                missing_inputs=missing,
                                evidence_ids=[s.id, "input:compressive_load"],
                                confidence=RULE_CONFIDENCE_EXPLICIT,
                                limitations=rule_buckling.limitations
                            )
                        )
                        for m in missing:
                            missing_info.append(
                                MissingInformationItem(
                                    field=m,
                                    description=f"Missing input '{m}' required for buckling assessment on '{s.id}'.",
                                    feature_id=s.id,
                                    rule_id=rule_buckling.id
                                )
                            )

        # -------------------------------------------------------------------
        # Rule F: Deflection
        # -------------------------------------------------------------------
        rule_deflection = self.kb.get_rule("deflection_analysis_applicability")
        if rule_deflection and (shafts or plates):
            has_any_load = any(
                k in inputs for k in ("applied_load", "transverse_load", "torque", "applied_pressure_or_load", "force")
            )
            if has_any_load:
                missing = [
                    req for req in ("support_conditions", "elastic_modulus")
                    if req not in inputs
                ]
                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_deflection.id,
                        applicability=True,
                        rationale="Applied loading is present on structural geometry; elastic deflection and stiffness verification are relevant.",
                        required_inputs=rule_deflection.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=["input:applied_load"],
                        confidence=RULE_CONFIDENCE_EXPLICIT,
                        limitations=rule_deflection.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing parameter '{m}' required for structural deflection assessment.",
                            rule_id=rule_deflection.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule G: Hole Requirements
        # -------------------------------------------------------------------
        rule_hole = self.kb.get_rule("hole_engineering_requirements")
        if rule_hole and holes:
            for h in holes:
                missing = []
                if "positional_tolerance" not in inputs:
                    missing.append("positional_tolerance")
                if "hole_depth_or_through" not in inputs and "depth" not in h.attributes:
                    missing.append("hole_depth_or_through")

                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_hole.id,
                        applicability=True,
                        rationale=f"Hole feature '{h.id}' detected; hole diameter, positional tolerancing, and through/blind depth specification are required engineering inputs.",
                        required_inputs=rule_hole.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=[h.id],
                        confidence=RULE_CONFIDENCE_EXPLICIT,
                        limitations=rule_hole.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing engineering callout '{m}' for hole '{h.id}'.",
                            feature_id=h.id,
                            rule_id=rule_hole.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule H: Hole Pattern Requirements
        # -------------------------------------------------------------------
        rule_pattern = self.kb.get_rule("hole_pattern_engineering_requirements")
        if rule_pattern and patterns:
            for p in patterns:
                missing = []
                if "composite_positional_tolerance" not in inputs:
                    missing.append("composite_positional_tolerance")
                if "pattern_position" not in inputs:
                    missing.append("pattern_position")

                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_pattern.id,
                        applicability=True,
                        rationale=f"Hole pattern '{p.id}' detected; spacing/pitch verification, pattern reference position, and composite positional tolerancing are relevant.",
                        required_inputs=rule_pattern.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=[p.id],
                        confidence=RULE_CONFIDENCE_EXPLICIT,
                        limitations=rule_pattern.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing pattern callout '{m}' for pattern '{p.id}'.",
                            feature_id=p.id,
                            rule_id=rule_pattern.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule I: Rectangular Plate Analysis
        # -------------------------------------------------------------------
        rule_plate = self.kb.get_rule("rectangular_plate_analysis_applicability")
        if rule_plate and plates:
            for pl in plates:
                missing = []
                if "plate_thickness" not in inputs and "thickness" not in pl.attributes:
                    missing.append("plate_thickness")
                if "material" not in inputs:
                    missing.append("material")
                if "applied_pressure_or_load" not in inputs and "loading" not in inputs:
                    missing.append("applied_pressure_or_load")
                if "boundary_conditions" not in inputs:
                    missing.append("boundary_conditions")

                applicable_rules.append(
                    EngineeringRuleMatch(
                        rule_id=rule_plate.id,
                        applicability=True,
                        rationale=f"Rectangular plate candidate '{pl.id}' detected; plate thickness, material specification, out-of-plane loading, and boundary conditions are required.",
                        required_inputs=rule_plate.required_inputs,
                        missing_inputs=missing,
                        evidence_ids=[pl.id],
                        confidence=RULE_CONFIDENCE_EXPLICIT,
                        limitations=rule_plate.limitations
                    )
                )
                for m in missing:
                    missing_info.append(
                        MissingInformationItem(
                            field=m,
                            description=f"Missing input '{m}' required for rectangular plate '{pl.id}' analysis.",
                            feature_id=pl.id,
                            rule_id=rule_plate.id
                        )
                    )

        # -------------------------------------------------------------------
        # Rule J: Material Specification Requirement
        # -------------------------------------------------------------------
        rule_material = self.kb.get_rule("material_specification_requirement")
        if rule_material and (applicable_rules or features):
            missing = [
                req for req in ("material_grade", "yield_strength", "ultimate_tensile_strength", "elastic_modulus")
                if req not in inputs
            ]
            applicable_rules.append(
                EngineeringRuleMatch(
                    rule_id=rule_material.id,
                    applicability=True,
                    rationale="Mechanical analysis and stress evaluations require verified material grade and mechanical properties; values must never be fabricated.",
                    required_inputs=rule_material.required_inputs,
                    missing_inputs=missing,
                    evidence_ids=["engineering_materials_requirement"],
                    confidence=RULE_CONFIDENCE_EXPLICIT,
                    limitations=rule_material.limitations
                )
            )
            for m in missing:
                missing_info.append(
                    MissingInformationItem(
                        field=m,
                        description=f"Certified material property '{m}' is missing; cannot perform stress certification without it.",
                        rule_id=rule_material.id
                    )
                )

        # Retrieve relevant knowledge items for the identified feature types and rules
        items: List[EngineeringKnowledgeItem] = []
        seen_item_ids: Set[str] = set()

        for ft in relevant_feature_types:
            for item in self.kb.get_items_for_feature(ft):
                if item.id not in seen_item_ids:
                    items.append(item)
                    seen_item_ids.add(item.id)

        # If material rule is active, include materials knowledge item
        mat_item = self.kb.get_item("know_material_properties_requirement")
        if mat_item and mat_item.id not in seen_item_ids:
            items.append(mat_item)
            seen_item_ids.add(mat_item.id)

        return EngineeringKnowledgeResult(
            items=items,
            applicable_rules=applicable_rules,
            missing_information=missing_info,
            warnings=warnings
        )
