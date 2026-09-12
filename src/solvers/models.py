"""
Pydantic data models for deterministic mechanical solvers and calculation certificates.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CertificateStatus(str, Enum):
    SUCCESS = "success"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_ERROR = "execution_error"


class AssessmentStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_ASSESSED = "not_assessed"
    INSUFFICIENT_DATA = "insufficient_data"


class UnitConversion(BaseModel):
    """Explicit record of input unit normalization to standard SI units."""
    parameter: str
    original_value: float
    original_unit: str
    normalized_value: float
    normalized_unit: str
    conversion_factor: float


class CalculationStep(BaseModel):
    """Discrete auditable mathematical step in an engineering calculation."""
    step_id: str
    description: str
    formula: str
    substituted_expression: str
    result: float
    unit: str
    display_result: Optional[str] = None


class AssessmentResult(BaseModel):
    """Deterministic engineering evaluation comparing calculated stress against allowable limits."""
    assessment_type: str
    status: AssessmentStatus
    allowable_value: Optional[float] = None
    allowable_unit: Optional[str] = None
    calculated_value: Optional[float] = None
    calculated_unit: Optional[str] = None
    factor_of_safety: Optional[float] = None
    margin_of_safety: Optional[float] = None
    design_factor: Optional[float] = None
    summary: str


class InputProvenance(BaseModel):
    """Audit record capturing the origin of an engineering input parameter."""
    value: Any
    unit: Optional[str] = None
    source: str = "engineering_inputs"  # e.g., "engineering_inputs", "drawing_dimension", "mechanical_semantics", "user_selected"
    source_id: Optional[str] = None


class CalculationCertificate(BaseModel):
    """
    Formal, deterministic engineering calculation certificate produced by a mechanical solver.
    Provides complete mathematical transparency, substituted formulas, unit conversions,
    engineering assessments, and explicit physical assumptions and limitations.
    """
    certificate_id: str
    solver_id: str
    solver_version: str
    analysis_type: str
    status: CertificateStatus
    inputs: Dict[str, Any] = Field(default_factory=dict)
    normalized_inputs: Dict[str, float] = Field(default_factory=dict)
    conversions: List[UnitConversion] = Field(default_factory=list)
    calculations: List[CalculationStep] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    assessments: List[AssessmentResult] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provenance: Dict[str, InputProvenance] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
