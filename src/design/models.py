"""
Pydantic data models for the Engineering Specification and Design Problem Interpreter (Slice 11).
Defines structured, auditable representations of mechanical design problems and requirements.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field


class ConstraintPriority(str, Enum):
    """Priority level for engineering design constraints."""
    MANDATORY = "mandatory"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MissingImportance(str, Enum):
    """Significance level of missing engineering data."""
    REQUIRED_FOR_DESIGN = "REQUIRED_FOR_DESIGN"
    REQUIRED_FOR_ANALYSIS = "REQUIRED_FOR_ANALYSIS"
    OPTIONAL = "OPTIONAL"
    INFORMATIONAL = "INFORMATIONAL"


class EngineeringQuantity(BaseModel):
    """
    A numerical physical quantity with explicit unit, normalized SI value, and origin provenance.
    """
    value: float
    unit: str
    normalized_value: Optional[float] = None
    normalized_unit: Optional[str] = None
    source: str = "user_statement"  # "user_statement", "engineering_inputs", "derived_calculation", "assumed_default"
    evidence_id: Optional[str] = None
    is_assumed: bool = False
    assumption_rationale: Optional[str] = None


class LoadRequirement(BaseModel):
    """Explicit mechanical load or torque acting on the system."""
    load_type: str  # "torque", "bending_moment", "axial_tension", "axial_compression", "direct_shear", "radial_load"
    magnitude: Optional[EngineeringQuantity] = None
    direction: Optional[str] = None
    application_context: Optional[str] = None
    source: str = "user_statement"
    is_assumed: bool = False


class MaterialRequirement(BaseModel):
    """Material specifications, generic alloy names, or explicit grades."""
    material_name: Optional[str] = None  # Generic category, e.g. "steel", "aluminum", "brass"
    material_grade: Optional[str] = None  # Explicit grade if specified, e.g. "AISI 1045", "6061-T6", None if generic
    required_properties: Dict[str, EngineeringQuantity] = Field(default_factory=dict)
    source: str = "user_statement"
    is_assumed: bool = False


class OperatingCondition(BaseModel):
    """Operating parameter such as power, speed, or environment."""
    parameter: str  # "power", "rotational_speed", "temperature", "duty_cycle"
    value: Optional[float] = None
    unit: Optional[str] = None
    normalized_value: Optional[float] = None
    normalized_unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    source: str = "user_statement"


class DesignConstraint(BaseModel):
    """Bounding physical or performance constraint."""
    constraint_type: str  # "max_diameter", "min_safety_factor", "max_length", "max_weight"
    value: Optional[float] = None
    unit: Optional[str] = None
    priority: ConstraintPriority = ConstraintPriority.HIGH
    source: str = "user_statement"


class MissingInformation(BaseModel):
    """Unspecified engineering parameter needed for downstream sizing, detailing, or analysis."""
    field: str
    reason: str
    importance: MissingImportance = MissingImportance.REQUIRED_FOR_DESIGN
    blocks_analysis: bool = False
    suggested_input: Optional[str] = None


class RequirementConflict(BaseModel):
    """Contradiction or incompatibility between stated requirements."""
    conflict_id: str
    field: str
    description: str
    affected_requirements: List[str] = Field(default_factory=list)
    requires_human_review: bool = True


class DerivedEngineeringValue(BaseModel):
    """
    Deterministically calculated engineering parameter computed from stated operating conditions.
    Contains closed-form mathematical provenance with zero LLM arithmetic.
    """
    name: str  # e.g., "torque"
    formula: str  # e.g., "T = P / omega = P / (2 * pi * N / 60)"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    output_value: float
    output_unit: str
    calculation_steps: List[str] = Field(default_factory=list)
    provenance: str = "derived_calculation"
    assumptions: List[str] = Field(default_factory=list)


class EngineeringSpecification(BaseModel):
    """
    Structured, auditable mechanical engineering specification extracted from
    natural language problem statements and operating requirements.
    """
    specification_id: str
    problem_statement: str
    machine_element: Optional[str] = None  # "shaft", "bolted_joint", "beam", "gear", "bearing", "spring", "column", "pressure_vessel", "key_joint", "unknown"
    system_type: Optional[str] = None
    functional_requirements: List[str] = Field(default_factory=list)
    operating_conditions: List[OperatingCondition] = Field(default_factory=list)
    geometry_requirements: List[EngineeringQuantity] = Field(default_factory=list)
    material_requirements: Optional[MaterialRequirement] = None
    load_requirements: List[LoadRequirement] = Field(default_factory=list)
    performance_requirements: List[str] = Field(default_factory=list)
    environmental_conditions: List[str] = Field(default_factory=list)
    safety_requirements: List[DesignConstraint] = Field(default_factory=list)
    manufacturing_constraints: List[str] = Field(default_factory=list)
    standards_requirements: List[str] = Field(default_factory=list)
    analysis_requirements: List[str] = Field(default_factory=list)
    design_constraints: List[DesignConstraint] = Field(default_factory=list)
    derived_values: List[DerivedEngineeringValue] = Field(default_factory=list)
    missing_information: List[MissingInformation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    conflicts: List[RequirementConflict] = Field(default_factory=list)
    source_evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    requires_human_review: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DesignSpecificationRequest(BaseModel):
    """Input payload for the POST /design/specification endpoint."""
    problem_statement: str
    engineering_inputs: Optional[Dict[str, Any]] = None
    requested_analyses: Optional[List[str]] = None
    provider: Optional[str] = None


class DesignSpecificationResponse(BaseModel):
    """Output payload from the POST /design/specification endpoint."""
    specification: EngineeringSpecification
    derived_values: List[DerivedEngineeringValue]
    missing_information: List[MissingInformation]
    validation_issues: List[str]
    analysis_plan: Optional[Any] = None  # AnalysisPlan
    report: str
