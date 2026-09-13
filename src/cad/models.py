"""
Data models for Parametric CAD & 2D Engineering Drawing Generation (Slice 13).
Defines CAD specifications, artifact descriptors, BRep validation records,
generation requests/responses, and the unified EngineeringHandoff package.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CADStatus(str, Enum):
    """Synthesis and validation status for CAD solid models and drawings."""
    READY = "READY"
    BLOCKED = "BLOCKED"
    GENERATED = "GENERATED"
    FAILED = "FAILED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class CADSpecification(BaseModel):
    """
    Structured geometric specification governing parametric solid modeling.
    Consumed by CAD backends without inventing or fabricating dimensions.
    """
    machine_element: str = "shaft"
    part_name: str
    material: Optional[str] = None
    material_grade: Optional[str] = None
    length: Optional[float] = None
    diameter: Optional[float] = None
    units: str = "mm"
    features: List[Dict[str, Any]] = Field(default_factory=list)
    source_design_id: Optional[str] = None
    source_design_candidate_id: Optional[str] = None
    source_specification_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)


class CADArtifact(BaseModel):
    """
    Descriptor for a generated CAD or drawing file artifact (STEP, SVG, DXF, PDF).
    Maintains provenance and geometric versioning back to the source design.
    """
    artifact_id: str
    machine_element: str
    backend: str
    format: str  # "step", "svg", "dxf", "pdf"
    filename: str
    file_path: str
    file_size_bytes: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_design_id: Optional[str] = None
    source_geometry_version: str = "1.0"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    status: CADStatus = CADStatus.GENERATED


class BRepValidationResult(BaseModel):
    """
    Geometric verification record assessing BRep topological validity,
    bounding box boundaries, analytical volume, and surface area.
    """
    is_valid: bool
    bounding_box: Dict[str, float] = Field(default_factory=dict)
    calculated_volume: float
    theoretical_volume: float
    volume_error_rel: float
    calculated_surface_area: float
    theoretical_surface_area: float
    dimensional_checks: Dict[str, bool] = Field(default_factory=dict)
    validation_messages: List[str] = Field(default_factory=list)


class CADGenerationRequest(BaseModel):
    """Input payload for the POST /design/cad endpoint."""
    problem_statement: Optional[str] = None
    design_result: Optional[Any] = None  # DesignResult from Slice 12
    engineering_inputs: Optional[Dict[str, Any]] = None
    cad_parameters: Optional[Dict[str, Any]] = None
    backend: Optional[str] = None


class CADGenerationResponse(BaseModel):
    """Output payload from the POST /design/cad endpoint."""
    status: CADStatus
    cad_specification: CADSpecification
    artifacts: Dict[str, CADArtifact] = Field(default_factory=dict)
    drawing_document: Optional[Any] = None  # DrawingDocument
    validation: Optional[BRepValidationResult] = None
    dimensional_cross_validation: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    missing_information: List[Dict[str, Any]] = Field(default_factory=list)
    report: Optional[str] = None


class EngineeringHandoff(BaseModel):
    """
    Unified architectural package aggregating design requirements,
    analytical solver certificates, 3D CAD models, 2D drawings,
    and end-to-end parameter traceability.
    """
    handoff_id: str
    source_specification_id: Optional[str] = None
    source_design_id: Optional[str] = None
    machine_element: str
    cad_specification: CADSpecification
    cad_artifacts: Dict[str, CADArtifact] = Field(default_factory=dict)
    drawing_document: Optional[Any] = None
    traceability_matrix: Dict[str, Any] = Field(default_factory=dict)
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    handoff_status: str = "READY_FOR_REVIEW"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
