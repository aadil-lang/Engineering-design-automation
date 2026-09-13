"""
Engineering Requirements, LLM Extraction, and Deterministic Solver Integration (Slice 14).
Provides end-to-end structured requirement extraction, validation, closed-form mechanical calculation,
and explicit nominal diameter selection policies.
"""

from requirements.models import (
    RequirementValidationStatus,
    PipelineStatus,
    FieldProvenance,
    EngineeringSpec,
    RequirementValidationResult,
    EngineeringResult,
    EndToEndDesignResult
)
from requirements.validator import (
    RequirementValidator,
    validate_engineering_spec
)
from requirements.extractor import (
    RequirementExtractor,
    extract_requirements
)
from requirements.diameter_policy import (
    DEFAULT_NOMINAL_SHAFT_SERIES,
    NominalDiameterSelectionResult,
    NominalDiameterSelectionPolicy,
    select_nominal_diameter
)
from requirements.solver import (
    ShaftEngineeringSolver,
    solve_shaft,
    solve_engineering_spec
)
from requirements.pipeline import (
    EndToEndPipeline,
    run_design_pipeline
)

__all__ = [
    "RequirementValidationStatus",
    "PipelineStatus",
    "FieldProvenance",
    "EngineeringSpec",
    "RequirementValidationResult",
    "EngineeringResult",
    "EndToEndDesignResult",
    "RequirementValidator",
    "validate_engineering_spec",
    "RequirementExtractor",
    "extract_requirements",
    "DEFAULT_NOMINAL_SHAFT_SERIES",
    "NominalDiameterSelectionResult",
    "NominalDiameterSelectionPolicy",
    "select_nominal_diameter",
    "ShaftEngineeringSolver",
    "solve_shaft",
    "solve_engineering_spec",
    "EndToEndPipeline",
    "run_design_pipeline"
]
