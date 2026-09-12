from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class GroundTruthLine(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    orientation: str  # "horizontal", "vertical", "diagonal"


class GroundTruthCircle(BaseModel):
    id: str
    center_x: float
    center_y: float
    radius: float


class GroundTruthDimension(BaseModel):
    id: str
    raw_text: str
    value: Optional[float] = None
    dimension_type: str  # "linear", "diameter", "radius", "angular", etc.
    unit: Optional[str] = None


class GroundTruthSymbol(BaseModel):
    id: str
    symbol_type: str  # "diameter", "radius", "plus_minus", "degree", etc.
    text: str


class GroundTruthRelationship(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str  # "parallel", "perpendicular", "connected"


class GroundTruth(BaseModel):
    lines: List[GroundTruthLine] = Field(default_factory=list)
    circles: List[GroundTruthCircle] = Field(default_factory=list)
    dimensions: List[GroundTruthDimension] = Field(default_factory=list)
    relationships: List[GroundTruthRelationship] = Field(default_factory=list)
    symbols: List[GroundTruthSymbol] = Field(default_factory=list)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    case_id: str
    description: str
    image: Any  # np.ndarray
    ground_truth: GroundTruth


class MetricScore(BaseModel):
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)


class EvaluationResult(BaseModel):
    case_id: str
    metrics: Dict[str, Any]
    details: Dict[str, Any] = Field(default_factory=dict)


class EvaluationSummaryReport(BaseModel):
    total_cases: int
    aggregate_metrics: Dict[str, Any]
    case_results: List[EvaluationResult]
