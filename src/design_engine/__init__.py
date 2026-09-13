"""
Parametric Mechanical Design Engine package (Slice 12).
Synthesizes, evaluates, and ranks deterministic machine element designs.
"""

from design_engine.models import (
    DesignStatus,
    DesignObjective,
    DesignVariable,
    ShaftDesignRequirements,
    DesignCandidate,
    DesignResult,
    DesignRequest,
    DesignResponse
)
from design_engine.config import (
    DEFAULT_DIAMETER_MIN_MM,
    DEFAULT_DIAMETER_MAX_MM,
    DEFAULT_DIAMETER_STEP_MM,
    TORQUE_CONFLICT_TOLERANCE_PCT,
    DISTORTION_ENERGY_SHEAR_FACTOR,
    TRESCA_SHEAR_FACTOR
)
from design_engine.variables import create_shaft_diameter_variable
from design_engine.candidates import CandidateGenerator, ShaftDiameterCandidateGenerator
from design_engine.shaft import (
    resolve_shaft_torque,
    resolve_allowable_stress,
    calculate_required_diameter
)
from design_engine.evaluator import CandidateEvaluator
from design_engine.ranker import CandidateRanker
from design_engine.designer import (
    ShaftDesigner,
    design_from_specification,
    design_from_problem_statement
)
from design_engine.report import generate_design_report

__all__ = [
    "DesignStatus",
    "DesignObjective",
    "DesignVariable",
    "ShaftDesignRequirements",
    "DesignCandidate",
    "DesignResult",
    "DesignRequest",
    "DesignResponse",
    "DEFAULT_DIAMETER_MIN_MM",
    "DEFAULT_DIAMETER_MAX_MM",
    "DEFAULT_DIAMETER_STEP_MM",
    "TORQUE_CONFLICT_TOLERANCE_PCT",
    "DISTORTION_ENERGY_SHEAR_FACTOR",
    "TRESCA_SHEAR_FACTOR",
    "create_shaft_diameter_variable",
    "CandidateGenerator",
    "ShaftDiameterCandidateGenerator",
    "resolve_shaft_torque",
    "resolve_allowable_stress",
    "calculate_required_diameter",
    "CandidateEvaluator",
    "CandidateRanker",
    "ShaftDesigner",
    "design_from_specification",
    "design_from_problem_statement",
    "generate_design_report"
]
