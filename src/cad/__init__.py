"""
Parametric CAD and 2D Engineering Drawing Module (Slice 13).
Produces deterministic 3D BRep solids, ISO-10303-21 STEP exchange files,
and standards-compliant 2D technical drawings from validated mechanical designs.
"""

from cad.models import (
    CADStatus,
    CADSpecification,
    CADArtifact,
    BRepValidationResult,
    CADGenerationRequest,
    CADGenerationResponse,
    EngineeringHandoff
)
from cad.config import (
    DEFAULT_CAD_ARTIFACT_DIR,
    DEFAULT_DRAWING_ARTIFACT_DIR,
    PARAMETER_TOLERANCE_MM,
    GEOMETRY_TOLERANCE_MM,
    DRAWING_TOLERANCE_MM
)
from cad.interfaces import CADBackend
from cad.brep import BRepSolidCylinder
from cad.backend import OpenCascadeBackend
from cad.drawing import (
    DrawingDocument,
    DrawingView,
    DrawingDimension,
    DrawingLine,
    DrawingArc,
    TitleBlock
)
from cad.exporters import SVGRenderer, DrawingExporter
from cad.shaft import build_shaft_cad_specification
from cad.handoff import create_engineering_handoff_package
from cad.generator import CADGenerator
from cad.report import generate_cad_report

__all__ = [
    "CADStatus",
    "CADSpecification",
    "CADArtifact",
    "BRepValidationResult",
    "CADGenerationRequest",
    "CADGenerationResponse",
    "EngineeringHandoff",
    "DEFAULT_CAD_ARTIFACT_DIR",
    "DEFAULT_DRAWING_ARTIFACT_DIR",
    "PARAMETER_TOLERANCE_MM",
    "GEOMETRY_TOLERANCE_MM",
    "DRAWING_TOLERANCE_MM",
    "CADBackend",
    "BRepSolidCylinder",
    "OpenCascadeBackend",
    "DrawingDocument",
    "DrawingView",
    "DrawingDimension",
    "DrawingLine",
    "DrawingArc",
    "TitleBlock",
    "SVGRenderer",
    "DrawingExporter",
    "build_shaft_cad_specification",
    "create_engineering_handoff_package",
    "CADGenerator",
    "generate_cad_report"
]
