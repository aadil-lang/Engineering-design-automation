from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MechanicalFeatureType(str, Enum):
    HOLE = "hole"
    HOLE_PATTERN = "hole_pattern"
    CIRCULAR_FEATURE = "circular_feature"
    SHAFT = "shaft"
    SLOT = "slot"
    RECTANGULAR_PLATE = "rectangular_plate"
    STEPPED_FEATURE = "stepped_feature"
    SYMMETRIC_FEATURE = "symmetric_feature"
    PARALLEL_FEATURE = "parallel_feature"
    PERPENDICULAR_FEATURE = "perpendicular_feature"
    UNKNOWN = "unknown"


class SemanticEvidenceItem(BaseModel):
    source_type: str  # e.g., "circle", "dimension", "association", "line", "relationship"
    source_id: str
    description: str


class MechanicalFeature(BaseModel):
    id: str
    feature_type: MechanicalFeatureType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[SemanticEvidenceItem] = Field(default_factory=list)
    reasoning_basis: str
    uncertainties: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class MechanicalSemanticsResult(BaseModel):
    features: List[MechanicalFeature] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
