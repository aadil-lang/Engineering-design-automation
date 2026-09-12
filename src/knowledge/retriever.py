"""
Retriever abstraction and deterministic built-in knowledge retriever.
"""

from typing import List, Optional, Protocol, Set
from knowledge.models import EngineeringKnowledgeItem
from knowledge.knowledge_base import BuiltInEngineeringKnowledgeBase


class EngineeringKnowledgeRetriever(Protocol):
    """Protocol for pluggable engineering knowledge retrieval."""

    def retrieve(
        self,
        query: Optional[str] = None,
        feature_types: Optional[List[str]] = None,
        domains: Optional[List[str]] = None,
        top_k: int = 10
    ) -> List[EngineeringKnowledgeItem]:
        ...


class BuiltInKnowledgeRetriever:
    """
    Deterministic rule- and keyword-based retriever operating over the in-memory
    BuiltInEngineeringKnowledgeBase. Serves as the drop-in baseline for future
    embedding- or vector-based retrievers.
    """

    def __init__(self, knowledge_base: Optional[BuiltInEngineeringKnowledgeBase] = None):
        self.kb = knowledge_base or BuiltInEngineeringKnowledgeBase()

    def retrieve(
        self,
        query: Optional[str] = None,
        feature_types: Optional[List[str]] = None,
        domains: Optional[List[str]] = None,
        top_k: int = 10
    ) -> List[EngineeringKnowledgeItem]:
        """
        Retrieves knowledge items using deterministic domain, feature-type, and
        keyword matching.
        """
        candidates = self.kb.get_all_items()

        # 1. Filter by domains if specified
        if domains:
            target_domains = {d.strip().lower() for d in domains}
            candidates = [c for c in candidates if c.domain.lower() in target_domains]

        # 2. Filter / score by feature_types if specified
        feature_set: Set[str] = set()
        if feature_types:
            feature_set = {ft.strip().lower() for ft in feature_types}

        scored_candidates = []
        for item in candidates:
            score = 0.0

            # Feature match score
            item_features = {f.lower() for f in item.related_features}
            common_features = item_features.intersection(feature_set)
            if feature_set:
                if common_features:
                    score += len(common_features) * 2.0
            else:
                score += 1.0

            # Query keyword score
            if query:
                tokens = [t.lower() for t in query.replace("_", " ").split() if len(t) > 2]
                search_text = f"{item.title} {item.statement} {' '.join(item.tags)}".lower()
                matches = sum(1 for t in tokens if t in search_text)
                score += matches * 1.5

            if score > 0.0 or (not query and not feature_types):
                scored_candidates.append((score, item))

        # Sort descending by score, tie-break by item.id for deterministic output
        scored_candidates.sort(key=lambda x: (x[0], x[1].id), reverse=True)
        return [item for _, item in scored_candidates[:top_k]]
