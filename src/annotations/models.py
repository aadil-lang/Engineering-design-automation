from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum


class OCRResult(BaseModel):
    id: str
    text: str
    confidence: float
    bounding_box: Tuple[float, float, float, float]  # (x, y, w, h)


class DimensionType(str, Enum):
    LINEAR = "linear"
    DIAMETER = "diameter"
    RADIUS = "radius"
    ANGULAR = "angular"
    TOLERANCE = "tolerance"
    UNKNOWN = "unknown"


class Tolerance(BaseModel):
    upper: Optional[float] = None
    lower: Optional[float] = None
    symmetric: Optional[float] = None
    raw_text: Optional[str] = None


class Dimension(BaseModel):
    id: str
    raw_text: str
    value: Optional[float] = None
    unit: Optional[str] = None
    dimension_type: DimensionType
    tolerance: Optional[Tolerance] = None
    confidence: float
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    source_text_id: Optional[str] = None


class SymbolType(str, Enum):
    DIAMETER = "diameter"
    RADIUS = "radius"
    PLUS_MINUS = "plus_minus"
    DEGREE = "degree"
    FLATNESS = "flatness"
    PARALLELISM = "parallelism"
    PERPENDICULARITY = "perpendicularity"
    POSITION = "position"
    SURFACE_ROUGHNESS = "surface_roughness"
    OTHER = "other"


class EngineeringSymbol(BaseModel):
    id: str
    symbol_type: SymbolType
    raw_symbol: str
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    confidence: float
    source_text_id: Optional[str] = None


class AssociationType(str, Enum):
    LINE_DIMENSION = "line_dimension"
    CIRCLE_DIAMETER = "circle_diameter"
    CIRCLE_RADIUS = "circle_radius"
    NEARBY_GEOMETRY = "nearby_geometry"
    UNKNOWN = "unknown"


class GeometryAssociation(BaseModel):
    dimension_id: str
    feature_id: str
    association_type: AssociationType
    distance: float
    confidence: float
    metadata: Optional[Dict[str, Any]] = None


class AnnotationsResult(BaseModel):
    ocr_results: List[OCRResult] = []
    dimensions: List[Dimension] = []
    symbols: List[EngineeringSymbol] = []
    associations: List[GeometryAssociation] = []
    summary: Dict[str, Any] = {}
