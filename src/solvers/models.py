"""
Pydantic data models for deterministic mechanical solvers, machine elements, and calculation certificates.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class MachineElementType(str, Enum):
    """Canonical classification of machine elements supported by the analysis platform."""
    SHAFT = "shaft"
    BOLTED_JOINT = "bolted_joint"
    BEAM = "beam"
    GEAR = "gear"
    BEARING = "bearing"
    SPRING = "spring"
    GENERAL = "general"


class AnalysisCapability(BaseModel):
    """
    Metadata describing an individual machine-element analysis capability and its designated solver.
    Allows discovery of available engineering evaluations by machine element type.
    """
    analysis_type: str
    machine_element: MachineElementType
    solver_id: str
    required_inputs: List[str]
    optional_inputs: List[str] = Field(default_factory=list)
    units: Dict[str, str] = Field(default_factory=dict)
    prerequisites: List[str] = Field(default_factory=list)
    applicability_criteria: str
    is_solver_available: bool = True
    can_assess: bool = True
    limitations: List[str] = Field(default_factory=list)


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


class ProvenanceSource(str, Enum):
    """Audit taxonomy classifying origin of parameters and engineering values."""
    USER_PROVIDED = "engineering_inputs"
    DRAWING_DIMENSION = "drawing_dimension"
    MECHANICAL_SEMANTICS = "mechanical_semantics"
    USER_SELECTED = "user_selected"
    ASSUMED_DEFAULT = "assumed_default"
    DERIVED_APPROXIMATION = "derived_approximation"
    NOMINAL_GEOMETRIC_APPROXIMATION = "nominal_geometric_approximation"


class EngineeringAssumption(BaseModel):
    """
    Auditable record of an engineering assumption, fallback default, or approximation applied.
    Enforces strict distinction between user-provided inputs and assumed values.
    """
    parameter: str
    value: Any
    unit: Optional[str] = None
    category: str = "assumed_default"  # "assumed_default", "derived_approximation", "nominal_geometric_approximation"
    rationale: str
    is_user_provided: bool = False


class InputProvenance(BaseModel):
    """Audit record capturing the origin of an engineering input parameter."""
    value: Any
    unit: Optional[str] = None
    source: str = "engineering_inputs"  # e.g., "engineering_inputs", "drawing_dimension", "mechanical_semantics", "assumed_default", "derived_approximation"
    source_id: Optional[str] = None
    is_assumed: bool = False
    assumption_rationale: Optional[str] = None


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
    machine_element: Optional[MachineElementType] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    normalized_inputs: Dict[str, float] = Field(default_factory=dict)
    conversions: List[UnitConversion] = Field(default_factory=list)
    calculations: List[CalculationStep] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    assessments: List[AssessmentResult] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    tracked_assumptions: List[EngineeringAssumption] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provenance: Dict[str, InputProvenance] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
