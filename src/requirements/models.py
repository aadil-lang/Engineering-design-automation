"""
Data models for Engineering Requirement Specification, Deterministic Validation,
Analytical Solver Results, and End-to-End Design Pipeline (Slice 14).
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class RequirementValidationStatus(str, Enum):
    """Deterministic validation status for engineering requirements."""
    VALID = "VALID"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class PipelineStatus(str, Enum):
    """End-to-end engineering pipeline execution status."""
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    FAILED = "FAILED"


class FieldProvenance(BaseModel):
    """
    Provenance metadata for an individual extracted requirement parameter.
    Tracks exact source text span, extracted value, and explicit presence in the input prompt.
    """
    field_name: str
    value: Optional[Any] = None
    source_text: Optional[str] = None
    is_explicit: bool = True
    confidence: float = 1.0


class EngineeringSpec(BaseModel):
    """
    Structured engineering requirement specification.
    Preserves exact user-supplied values versus missing values without arbitrary defaults.
    """
    component: Optional[str] = "shaft"
    material: Optional[str] = None
    power_kw: Optional[float] = None
    rpm: Optional[float] = None
    factor_of_safety: Optional[float] = None
    length_mm: Optional[float] = None
    yield_strength_mpa: Optional[float] = None

    # Metadata & Provenance (no engineering inferences)
    raw_text: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    material_resolution: Optional[Dict[str, Any]] = None
    extra_parameters: Dict[str, Any] = Field(default_factory=dict)


class RequirementValidationResult(BaseModel):
    """
    Structured result of deterministic requirement validation.
    Surfaces schema validity, missing required parameters, and validation errors.
    """
    is_valid: bool
    status: RequirementValidationStatus
    spec: EngineeringSpec
    missing_information: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EngineeringResult(BaseModel):
    """
    Deterministic calculation certificate and sizing result produced from a validated EngineeringSpec.
    Clearly distinguishes user-supplied requirement inputs from derived engineering outputs.
    """
    is_valid: bool
    status: RequirementValidationStatus
    spec: EngineeringSpec

    # Input requirements (preserved without unverified alteration)
    component: Optional[str] = None
    material: Optional[str] = None
    power_kw: Optional[float] = None
    rpm: Optional[float] = None
    factor_of_safety: Optional[float] = None
    length_mm: Optional[float] = None
    yield_strength_mpa: Optional[float] = None

    # Calculated engineering outputs (None if validation blocked or invalid)
    torque_nm: Optional[float] = None
    allowable_stress_mpa: Optional[float] = None
    minimum_required_diameter_mm: Optional[float] = None
    selected_diameter_mm: Optional[float] = None
    design_stress_mpa: Optional[float] = None
    achieved_factor_of_safety: Optional[float] = None
    is_safe: Optional[bool] = None

    # Nominal Diameter Selection Policy & Provenance (Slice 14.5)
    diameter_selection_policy: Optional[str] = None
    diameter_series_used: List[float] = Field(default_factory=list)
    diameter_selection_reason: Optional[str] = None

    # Audit Trail, Traceability & Reports
    calculation_steps: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EndToEndDesignResult(BaseModel):
    """
    Unified result of the end-to-end deterministic engineering pipeline (Slice 14.4 & 14.5).
    Aggregates requirement extraction, field provenance, analytical solver verification,
    nominal diameter selection policy audit, parametric 3D CAD models, 2D technical drawings,
    dimensional cross-validation, and the engineering handoff package.
    """
    status: PipelineStatus
    spec: Optional[EngineeringSpec] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    material_resolution: Optional[Dict[str, Any]] = None
    solver_result: Optional[EngineeringResult] = None
    cad_result: Optional[Any] = None
    cad_status: Optional[str] = None
    drawing_document: Optional[Any] = None
    cross_validation: Dict[str, Any] = Field(default_factory=dict)
    handoff: Optional[Any] = None
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    report: Optional[str] = None
