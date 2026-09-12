from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from annotations.models import (
    OCRResult,
    Dimension,
    DimensionType,
    Tolerance,
    EngineeringSymbol,
    SymbolType,
    GeometryAssociation,
    AssociationType,
    AnnotationsResult
)

class ImageMetadata(BaseModel):
    width: int
    height: int

class Line(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    angle: float

class Circle(BaseModel):
    center_x: float
    center_y: float
    radius: float

class Contour(BaseModel):
    area: float
    perimeter: float
    bounding_box: tuple[float, float, float, float]  # (x, y, w, h)

# Slice 2: Engineering Features Models

class LineOrientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    DIAGONAL = "diagonal"

class RelationshipType(str, Enum):
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    CONNECTED = "connected"

class LineFeature(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    angle_degrees: float
    orientation: LineOrientation

class CircleFeature(BaseModel):
    id: str
    center_x: float
    center_y: float
    radius: float
    diameter: float
    likely_hole: bool
    confidence: Optional[float] = None

class GeometricRelationship(BaseModel):
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    metadata: Optional[Dict[str, Any]] = None

class BoundingInformation(BaseModel):
    bounding_box: tuple[float, float, float, float]  # (x, y, w, h)
    width: float
    height: float

class EngineeringFeatures(BaseModel):
    line_features: List[LineFeature]
    circle_features: List[CircleFeature]
    relationships: List[GeometricRelationship]
    bounding_information: BoundingInformation
    summary: Dict[str, Any]

# API Response model encompassing Slice 1, Slice 2, and Slice 3

class AnalyzeResponse(BaseModel):
    image: ImageMetadata
    lines: List[Line]
    circles: List[Circle]
    contours: List[Contour]
    engineering_features: Optional[EngineeringFeatures] = None
    annotations: Optional[AnnotationsResult] = None
