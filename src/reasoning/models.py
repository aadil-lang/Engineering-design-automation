from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from core.models import AnalyzeResponse


class QuestionType(str, Enum):
    HOLE_ANALYSIS = "hole_analysis"
    DIMENSION_SUMMARY = "dimension_summary"
    GEOMETRY_SUMMARY = "geometry_summary"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    ANNOTATION_SUMMARY = "annotation_summary"
    GENERAL_ENGINEERING_QUESTION = "general_engineering_question"


class EvidenceSourceType(str, Enum):
    LINE = "line"
    CIRCLE = "circle"
    CONTOUR = "contour"
    DIMENSION = "dimension"
    SYMBOL = "symbol"
    RELATIONSHIP = "relationship"
    ASSOCIATION = "association"


class EvidenceReference(BaseModel):
    source_type: EvidenceSourceType
    source_id: str
    statement: str


class FactItem(BaseModel):
    statement: str
    evidence: List[str] = Field(default_factory=list)


class InferenceItem(BaseModel):
    statement: str
    evidence: List[str] = Field(default_factory=list)


class UncertaintyItem(BaseModel):
    statement: str
    evidence: Optional[List[str]] = Field(default_factory=list)


class ConfidenceScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    source: str = "model_heuristic"


class ReasoningRequest(BaseModel):
    question: str
    drawing: AnalyzeResponse


class ReasoningResponse(BaseModel):
    answer: str
    facts: List[FactItem] = Field(default_factory=list)
    inferences: List[InferenceItem] = Field(default_factory=list)
    uncertainties: List[UncertaintyItem] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: ConfidenceScore
    metadata: Optional[Dict[str, Any]] = None


class AnalyzeAndReasonResponse(BaseModel):
    analysis: AnalyzeResponse
    reasoning: ReasoningResponse
