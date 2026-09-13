"""
Data models for the Parametric Mechanical Design Engine (Slice 12).
Defines design variables, shaft design requirements, candidate records,
and deterministic design synthesis results.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from solvers.models import CalculationCertificate, AssessmentStatus
from design.models import (
    EngineeringSpecification,
    MissingInformation,
    RequirementConflict,
    DerivedEngineeringValue
)


class DesignStatus(str, Enum):
    """Overall feasibility and assessment status of the mechanical design synthesis."""
    READY = "READY"
    BLOCKED = "BLOCKED"
    PASS = "PASS"
    FAIL = "FAIL"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class DesignObjective(str, Enum):
    """Optimization objective for design candidate ranking."""
    MINIMIZE_SHAFT_DIAMETER = "MINIMIZE_SHAFT_DIAMETER"
    MINIMIZE_WEIGHT = "MINIMIZE_WEIGHT"
    MINIMIZE_COST = "MINIMIZE_COST"


class DesignVariable(BaseModel):
    """
    Parametric dimension or engineering variable explored during candidate generation.
    Tracks bounds, search step, and whether default search ranges were assumed.
    """
    name: str
    value: Optional[float] = None
    unit: str = "mm"
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    step: Optional[float] = None
    source: str = "user_input"
    is_assumed: bool = False
    rationale: Optional[str] = None


class ShaftDesignRequirements(BaseModel):
    """
    Structured mechanical requirements specifically for shaft sizing and detailing.
    Can be populated directly by API callers or derived from an EngineeringSpecification.
    """
    power: Optional[float] = None
    power_unit: str = "kW"
    speed_rpm: Optional[float] = None
    torque: Optional[float] = None
    torque_unit: str = "N*m"
    material: Optional[str] = None
    material_grade: Optional[str] = None
    allowable_shear_stress: Optional[float] = None
    allowable_shear_stress_unit: str = "MPa"
    allowable_equivalent_stress: Optional[float] = None
    yield_strength: Optional[float] = None
    yield_strength_unit: str = "MPa"
    design_factor: Optional[float] = None
    minimum_factor_of_safety: Optional[float] = None
    diameter_min: Optional[float] = None
    diameter_max: Optional[float] = None
    diameter_step: Optional[float] = None
    shaft_length: Optional[float] = None
    bending_moment: Optional[float] = None
    design_standard: Optional[str] = None
    manufacturing_constraints: List[str] = Field(default_factory=list)


class DesignCandidate(BaseModel):
    """
    Evaluated discrete mechanical design candidate.
    Captures exact dimensions, stress results, safety factor, and solver calculation certificates.
    """
    candidate_id: str
    machine_element: str = "shaft"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    analyses: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    assessment: AssessmentStatus
    factor_of_safety: Optional[float] = None
    calculated_stress_mpa: Optional[float] = None
    allowable_stress_mpa: Optional[float] = None
    calculation_certificates: List[CalculationCertificate] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class DesignResult(BaseModel):
    """
    Final synthesis produced by the Parametric Mechanical Design Engine.
    Exposes selected optimal candidate, alternatives, governing analysis,
    gaps, assumptions, and audit report.
    """
    design_id: str
    specification_id: Optional[str] = None
    problem_statement: Optional[str] = None
    machine_element: str = "shaft"
    selected_candidate: Optional[DesignCandidate] = None
    alternative_candidates: List[DesignCandidate] = Field(default_factory=list)
    design_variables: List[DesignVariable] = Field(default_factory=list)
    governing_analysis: Optional[str] = None
    objective: DesignObjective = DesignObjective.MINIMIZE_SHAFT_DIAMETER
    constraints: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[MissingInformation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    conflicts: List[RequirementConflict] = Field(default_factory=list)
    human_review_required: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    design_status: DesignStatus
    derived_values: List[DerivedEngineeringValue] = Field(default_factory=list)
    report: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DesignRequest(BaseModel):
    """Input payload for the POST /design endpoint."""
    problem_statement: Optional[str] = None
    specification: Optional[EngineeringSpecification] = None
    engineering_inputs: Optional[Dict[str, Any]] = None
    design_constraints: Optional[Dict[str, Any]] = None
    objective: Optional[str] = None


class DesignResponse(BaseModel):
    """Output payload from the POST /design endpoint."""
    result: DesignResult
    report: str
