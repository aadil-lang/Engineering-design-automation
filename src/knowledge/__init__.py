"""
Engineering Knowledge & Rules module (Slice 7).
Provides deterministic engineering knowledge, rule applicability evaluation,
and explicit missing-information tracking.
"""

from knowledge.models import (
    KnowledgeSourceType,
    EngineeringKnowledgeItem,
    EngineeringRule,
    EngineeringRuleMatch,
    MissingInformationItem,
    EngineeringKnowledgeResult
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
