"""
Knowledge base interface and built-in engineering knowledge repository.
"""

from typing import List, Optional, Dict, Protocol
from knowledge.models import EngineeringKnowledgeItem, EngineeringRule
from knowledge.rules import BUILT_IN_RULES, BUILT_IN_KNOWLEDGE_ITEMS


class EngineeringKnowledgeBase(Protocol):
    """Protocol definition for pluggable engineering knowledge bases."""

    def get_all_items(self) -> List[EngineeringKnowledgeItem]:
        ...

    def get_item(self, item_id: str) -> Optional[EngineeringKnowledgeItem]:
        ...

    def get_items_by_domain(self, domain: str) -> List[EngineeringKnowledgeItem]:
        ...

    def get_items_for_feature(self, feature_type: str) -> List[EngineeringKnowledgeItem]:
        ...

    def get_rules(self) -> List[EngineeringRule]:
        ...

    def get_rule(self, rule_id: str) -> Optional[EngineeringRule]:
        ...


class BuiltInEngineeringKnowledgeBase:
    """
    Deterministic in-memory knowledge base containing foundational engineering
    principles, domain requirements, and analysis applicability rules.
    """

    def __init__(
        self,
        items: Optional[List[EngineeringKnowledgeItem]] = None,
        rules: Optional[List[EngineeringRule]] = None
    ):
        self._items: List[EngineeringKnowledgeItem] = list(items if items is not None else BUILT_IN_KNOWLEDGE_ITEMS)
        self._rules: List[EngineeringRule] = list(rules if rules is not None else BUILT_IN_RULES)

        self._items_by_id: Dict[str, EngineeringKnowledgeItem] = {
            item.id: item for item in self._items
        }
        self._rules_by_id: Dict[str, EngineeringRule] = {
            rule.id: rule for rule in self._rules
        }

    def get_all_items(self) -> List[EngineeringKnowledgeItem]:
        """Returns all knowledge items."""
        return list(self._items)

    def get_item(self, item_id: str) -> Optional[EngineeringKnowledgeItem]:
        """Retrieves a knowledge item by its unique ID."""
        return self._items_by_id.get(item_id)

    def get_items_by_domain(self, domain: str) -> List[EngineeringKnowledgeItem]:
        """Retrieves knowledge items matching the given domain."""
        target = domain.strip().lower()
        return [item for item in self._items if item.domain.lower() == target]

    def get_items_for_feature(self, feature_type: str) -> List[EngineeringKnowledgeItem]:
        """Retrieves knowledge items applicable to the specified mechanical feature type."""
        target = feature_type.strip().lower()
        return [
            item for item in self._items
            if any(f.lower() == target for f in item.related_features)
        ]

    def get_rules(self) -> List[EngineeringRule]:
        """Returns all registered engineering rules."""
        return list(self._rules)

    def get_rule(self, rule_id: str) -> Optional[EngineeringRule]:
        """Retrieves an engineering rule by its ID."""
        return self._rules_by_id.get(rule_id)
