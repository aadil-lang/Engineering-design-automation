from pydantic import BaseModel, Field
from typing import List

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

class AnalyzeResponse(BaseModel):
    image: ImageMetadata
    lines: List[Line]
    circles: List[Circle]
    contours: List[Contour]
