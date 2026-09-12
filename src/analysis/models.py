from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AnalysisType(str, Enum):
    TORSION = "torsion"
    BENDING = "bending"
    COMBINED_STRESS = "combined_stress"
    DEFLECTION = "deflection"
    FATIGUE = "fatigue"
    BUCKLING = "buckling"
    BEARING_STRESS = "bearing_stress"
    HOLE_PATTERN_LOAD = "hole_pattern_load"
    VON_MISES = "von_mises"
    THERMAL_EXPANSION = "thermal_expansion"


class AnalysisStatus(str, Enum):
    RECOMMENDED = "recommended"
    READY = "ready"
    MISSING_INPUTS = "missing_inputs"
    NOT_APPLICABLE = "not_applicable"
    USER_DISABLED = "user_disabled"
    BLOCKED = "blocked"


class AnalysisPlanningRequest(BaseModel):
    recommend_analyses: bool = True
    requested_analyses: List[AnalysisType] = Field(default_factory=list)
    disabled_analyses: List[AnalysisType] = Field(default_factory=list)
    engineering_inputs: Dict[str, Any] = Field(default_factory=dict)
    feature_selection: Optional[List[str]] = None
    human_requested: bool = False


class AnalysisPlanItem(BaseModel):
    analysis_type: AnalysisType
    status: AnalysisStatus
    priority: str = "medium"  # "critical", "high", "medium", "low"
    rationale: str
    feature_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    available_inputs: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    calculation_inputs: List[str] = Field(default_factory=list)
    assessment_inputs: List[str] = Field(default_factory=list)
    missing_calculation_inputs: List[str] = Field(default_factory=list)
    missing_assessment_inputs: List[str] = Field(default_factory=list)
    solver_id: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    user_selected: bool = False
    user_disabled: bool = False


class AnalysisPlan(BaseModel):
    plan_id: str
    items: List[AnalysisPlanItem] = Field(default_factory=list)
    recommended_analyses: List[AnalysisType] = Field(default_factory=list)
    ready_analyses: List[AnalysisType] = Field(default_factory=list)
    blocked_analyses: List[AnalysisType] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    planner_version: str = "1.0.0"
