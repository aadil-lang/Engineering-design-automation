"""
High-level extractor for mechanical engineering semantics.
"""

from typing import Optional, Dict, Any
from core.models import EngineeringFeatures
from annotations.models import AnnotationsResult
from semantics.models import MechanicalSemanticsResult, MechanicalFeatureType
from semantics.recognizer import MechanicalSemanticRecognizer


class MechanicalSemanticExtractor:
    """
    Service transforming low-level CV geometry, engineering features, and annotations
    into a structured MechanicalSemanticsResult.
    """

    def __init__(self):
        self.recognizer = MechanicalSemanticRecognizer()

    def extract(
        self,
        engineering_features: Optional[EngineeringFeatures],
        annotations: Optional[AnnotationsResult] = None
    ) -> MechanicalSemanticsResult:
        """
        Extracts mechanical semantic interpretations deterministically.
        """
        features, warnings = self.recognizer.recognize_all(
            engineering_features=engineering_features,
            annotations=annotations
        )

        # Build feature count summary
        counts_by_type: Dict[str, int] = {ft.value: 0 for ft in MechanicalFeatureType}
        for f in features:
            type_val = f.feature_type.value if hasattr(f.feature_type, "value") else str(f.feature_type)
            counts_by_type[type_val] = counts_by_type.get(type_val, 0) + 1

        summary: Dict[str, Any] = {
            "total_features": len(features),
            "feature_counts": counts_by_type,
            "holes_count": counts_by_type.get("hole", 0),
            "hole_patterns_count": counts_by_type.get("hole_pattern", 0),
            "circular_features_count": counts_by_type.get("circular_feature", 0),
            "rectangular_plates_count": counts_by_type.get("rectangular_plate", 0),
            "slots_count": counts_by_type.get("slot", 0),
            "shafts_count": counts_by_type.get("shaft", 0),
            "stepped_features_count": counts_by_type.get("stepped_feature", 0),
            "symmetric_features_count": counts_by_type.get("symmetric_feature", 0),
            "parallel_features_count": counts_by_type.get("parallel_feature", 0),
            "perpendicular_features_count": counts_by_type.get("perpendicular_feature", 0)
        }

        return MechanicalSemanticsResult(
            features=features,
            summary=summary,
            warnings=warnings
        )


def extract_mechanical_semantics(
    engineering_features: Optional[EngineeringFeatures],
    annotations: Optional[AnnotationsResult] = None
) -> MechanicalSemanticsResult:
    """
    Functional entry point for extracting mechanical engineering semantics.
    """
    extractor = MechanicalSemanticExtractor()
    return extractor.extract(engineering_features, annotations)
