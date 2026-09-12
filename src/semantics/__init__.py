"""
Mechanical Engineering Semantic Interpretation module (Slice 6).
Provides deterministic, explainable extraction of high-level mechanical features.
"""

from semantics.models import (
    MechanicalFeatureType,
    SemanticEvidenceItem,
    MechanicalFeature,
    MechanicalSemanticsResult
)

__all__ = [
    "MechanicalFeatureType",
    "SemanticEvidenceItem",
    "MechanicalFeature",
    "MechanicalSemanticsResult",
    "MechanicalSemanticRecognizer",
    "MechanicalSemanticExtractor",
    "extract_mechanical_semantics",
]


def __getattr__(name: str):
    if name == "MechanicalSemanticRecognizer":
        from semantics.recognizer import MechanicalSemanticRecognizer
        return MechanicalSemanticRecognizer
    if name in ("MechanicalSemanticExtractor", "extract_mechanical_semantics"):
        from semantics.extractor import (
            MechanicalSemanticExtractor,
            extract_mechanical_semantics
        )
        if name == "MechanicalSemanticExtractor":
            return MechanicalSemanticExtractor
        return extract_mechanical_semantics
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
