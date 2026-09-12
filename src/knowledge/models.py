from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class KnowledgeSourceType(str, Enum):
    BUILT_IN_RULE = "built_in_rule"
    ENGINEERING_STANDARD = "engineering_standard"
    HANDBOOK = "handbook"
    MATERIAL_DATABASE = "material_database"
    COMPANY_KNOWLEDGE = "company_knowledge"
    PROJECT_DOCUMENT = "project_document"
    RETRIEVED_DOCUMENT = "retrieved_document"


class EngineeringKnowledgeItem(BaseModel):
    id: str
    title: str
    domain: str
    statement: str
    applicability: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    related_features: List[str] = Field(default_factory=list)
    source_type: KnowledgeSourceType = KnowledgeSourceType.BUILT_IN_RULE
    source_reference: Optional[str] = "internal-engineering-rule"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class EngineeringRule(BaseModel):
    id: str
    title: str
    domain: str
    feature_types: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    rationale: str
    limitations: List[str] = Field(default_factory=list)
    source_type: KnowledgeSourceType = KnowledgeSourceType.BUILT_IN_RULE
    source_reference: Optional[str] = "internal-engineering-rule"


class MissingInformationItem(BaseModel):
    field: str
    description: str
    feature_id: Optional[str] = None
    rule_id: Optional[str] = None


class EngineeringRuleMatch(BaseModel):
    rule_id: str
    applicability: bool
    rationale: str
    required_inputs: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)


class EngineeringKnowledgeResult(BaseModel):
    items: List[EngineeringKnowledgeItem] = Field(default_factory=list)
    applicable_rules: List[EngineeringRuleMatch] = Field(default_factory=list)
    missing_information: List[MissingInformationItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
