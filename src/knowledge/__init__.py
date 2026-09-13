"""
Engineering Knowledge & Rules module (Slice 7 & Material Knowledge Base v1).
Provides deterministic engineering knowledge, rule applicability evaluation,
explicit missing-information tracking, and authoritative material property resolution.
"""

from knowledge.models import (
    KnowledgeSourceType,
    EngineeringKnowledgeItem,
    EngineeringRule,
    EngineeringRuleMatch,
    MissingInformationItem,
    EngineeringKnowledgeResult
)
from knowledge.materials.schema import MaterialRecord, MaterialResolutionResult
from knowledge.materials.registry import MaterialRegistry, get_material_registry
from knowledge.materials.repository import (
    MaterialRepository,
    normalize_designation,
    get_default_material_repository
)

__all__ = [
    "KnowledgeSourceType",
    "EngineeringKnowledgeItem",
    "EngineeringRule",
    "EngineeringRuleMatch",
    "MissingInformationItem",
    "EngineeringKnowledgeResult",
    "BuiltInEngineeringKnowledgeBase",
    "EngineeringApplicabilityEngine",
    "BuiltInKnowledgeRetriever",
    "evaluate_engineering_knowledge",
    "MaterialRecord",
    "MaterialResolutionResult",
    "MaterialRegistry",
    "get_material_registry",
    "MaterialRepository",
    "normalize_designation",
    "get_default_material_repository",
]


def evaluate_engineering_knowledge(
    mechanical_semantics=None,
    annotations=None,
    engineering_inputs=None
) -> EngineeringKnowledgeResult:
    """Convenience function evaluating engineering knowledge against drawing semantics and inputs."""
    from knowledge.applicability import EngineeringApplicabilityEngine
    engine = EngineeringApplicabilityEngine()
    return engine.evaluate(
        mechanical_semantics=mechanical_semantics,
        annotations=annotations,
        engineering_inputs=engineering_inputs
    )


def __getattr__(name: str):
    if name == "BuiltInEngineeringKnowledgeBase":
        from knowledge.knowledge_base import BuiltInEngineeringKnowledgeBase
        return BuiltInEngineeringKnowledgeBase
    if name == "EngineeringApplicabilityEngine":
        from knowledge.applicability import EngineeringApplicabilityEngine
        return EngineeringApplicabilityEngine
    if name == "BuiltInKnowledgeRetriever":
        from knowledge.retriever import BuiltInKnowledgeRetriever
        return BuiltInKnowledgeRetriever
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
