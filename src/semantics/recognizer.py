"""
Semantic recognizer orchestrating deterministic mechanical feature identification.
"""

from typing import List, Dict, Tuple, Optional
from core.models import EngineeringFeatures
from annotations.models import AnnotationsResult, Dimension
from semantics.models import MechanicalFeature, MechanicalFeatureType
from semantics.feature_rules import (
    evaluate_circle_semantics,
    detect_hole_patterns,
    detect_relational_features,
    detect_rectangular_plates,
    detect_slots,
    detect_shafts_and_stepped,
    detect_symmetry
)


class MechanicalSemanticRecognizer:
    """
    Orchestrates deterministic rule-based identification of mechanical engineering
    features from low-level geometry, relationships, and annotations.
    """

    def recognize_all(
        self,
        engineering_features: Optional[EngineeringFeatures],
        annotations: Optional[AnnotationsResult]
    ) -> Tuple[List[MechanicalFeature], List[str]]:
        """
        Executes all semantic rules in deterministic order and returns identified
        mechanical features and any diagnostic warnings.
        """
        features: List[MechanicalFeature] = []
        warnings: List[str] = []

        if engineering_features is None:
            warnings.append("No engineering features provided; semantic interpretation cannot proceed.")
            return features, warnings

        # Build fast lookup for dimensions
        dims_by_id: Dict[str, Dimension] = {}
        assocs = []
        if annotations:
            dims_by_id = {d.id: d for d in annotations.dimensions}
            assocs = annotations.associations
        else:
            warnings.append("No annotations provided; hole classification is operating on geometric heuristics only.")

        # 1. Circle & Hole Recognition
        recognized_holes: List[MechanicalFeature] = []
        for cf in engineering_features.circle_features:
            feat = evaluate_circle_semantics(cf, assocs, dims_by_id)
            features.append(feat)
            if feat.feature_type == MechanicalFeatureType.HOLE:
                recognized_holes.append(feat)

        # 2. Hole Pattern Recognition
        if recognized_holes:
            pattern_features = detect_hole_patterns(recognized_holes)
            features.extend(pattern_features)

        # 3. Parallel and Perpendicular Semantics
        if engineering_features.relationships:
            rel_features = detect_relational_features(engineering_features.relationships)
            features.extend(rel_features)

        # 4. Rectangular Plate Recognition
        plate_features = detect_rectangular_plates(
            engineering_features.line_features,
            engineering_features.bounding_information
        )
        features.extend(plate_features)

        # 5. Slot Recognition
        slot_features = detect_slots(
            engineering_features.line_features,
            engineering_features.relationships,
            engineering_features.circle_features
        )
        features.extend(slot_features)

        # 6. Shaft and Stepped Feature Recognition
        shaft_features = detect_shafts_and_stepped(
            engineering_features.line_features,
            engineering_features.relationships,
            annotations
        )
        features.extend(shaft_features)

        # 7. Symmetry Recognition
        symmetry_features = detect_symmetry(
            engineering_features.line_features,
            engineering_features.circle_features,
            engineering_features.bounding_information
        )
        features.extend(symmetry_features)

        return features, warnings
