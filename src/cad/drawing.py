"""
Structured 2D Engineering Drawing Domain Models.
Defines the intermediate engineering drawing representation before rendering to SVG/DXF/PDF.
Every dimension retains explicit provenance back to CAD and design parameters.
"""

from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class DrawingLine(BaseModel):
    """2D vector line element with engineering layer classification and line style."""
    start: Tuple[float, float]
    end: Tuple[float, float]
    style: str = "solid"  # "solid", "centerline", "dimension", "extension", "hidden"
    layer: str = "geometry"
    source_edge_id: Optional[str] = None


class DrawingArc(BaseModel):
    """2D circular arc or full circle element (e.g. for shaft end view or radial fillets)."""
    center: Tuple[float, float]
    radius: float
    start_angle_deg: float = 0.0
    end_angle_deg: float = 360.0
    style: str = "solid"
    layer: str = "geometry"
    source_edge_id: Optional[str] = None


class DrawingDimension(BaseModel):
    """
    Standard engineering dimension entity with witness/extension lines, arrows,
    and bidirectional traceability back to the governing CAD/design parameter.
    """
    dimension_id: str
    dimension_type: str  # "diameter", "linear_length", "radial"
    value: float
    unit: str = "mm"
    source_parameter: str  # e.g., "shaft.diameter", "shaft.length"
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    text_position: Tuple[float, float]
    annotation_text: str  # e.g., "Ø12", "300"
    tolerance: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class DrawingView(BaseModel):
    """
    Standard orthographic projection view derived from the 3D BRep.
    Contains projected visible silhouette geometry, centerlines, and dimension entities.
    """
    view_id: str
    view_type: str  # "front_orthographic", "end_view", "isometric_detail"
    scale: float = 1.0
    origin: Tuple[float, float] = (0.0, 0.0)
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    lines: List[DrawingLine] = Field(default_factory=list)
    arcs: List[DrawingArc] = Field(default_factory=list)
    centerlines: List[DrawingLine] = Field(default_factory=list)
    dimensions: List[DrawingDimension] = Field(default_factory=list)
    annotations: List[str] = Field(default_factory=list)


class TitleBlock(BaseModel):
    """Engineering drawing title block metadata according to standard drafting practice."""
    title: str
    drawing_number: str
    revision: str = "A"
    material: Optional[str] = None
    units: str = "mm"
    scale: str = "1:1"
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    source_design_id: Optional[str] = None
    designer: str = "MechaAI Engineering Intelligence"
    approver: str = "Human Review Required"
    organization: str = "MECHAI ENGINEERING"


class DrawingDocument(BaseModel):
    """
    Root container for an intermediate 2D Engineering Drawing.
    Serves as the deterministic precursor to SVG, DXF, and PDF renderers.
    """
    drawing_id: str
    part_name: str
    source_design_id: Optional[str] = None
    source_specification_id: Optional[str] = None
    title_block: TitleBlock
    views: List[DrawingView] = Field(default_factory=list)
    dimensions: List[DrawingDimension] = Field(default_factory=list)
    units: str = "mm"
    sheet_width: float = 840.0   # Standard A3 landscape aspect
    sheet_height: float = 594.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
