"""
Design Problem Interpreter & Engineering Specification Module (Slice 11).
Translates natural language mechanical engineering problems into structured,
auditable Engineering Specifications with deterministic closed-form derivations.
"""

from typing import Optional, Dict, Any
from design.models import (
    EngineeringSpecification,
    EngineeringQuantity,
    LoadRequirement,
    MaterialRequirement,
    OperatingCondition,
    DesignConstraint,
    ConstraintPriority,
    MissingInformation,
    MissingImportance,
    RequirementConflict,
    DerivedEngineeringValue
)
from design.extractor import DesignSpecificationExtractor
from design.provider import (
    DesignSpecificationProvider,
    MockDesignSpecificationProvider,
    GeminiDesignSpecificationProvider,
    get_design_provider
)
from design.derivation import (
    DerivationRule,
    PowerSpeedToTorqueRule,
    DerivationEngine
)
from design.normalization import (
    normalize_power,
    normalize_rotational_speed,
    normalize_quantity_data
)
from design.missing import detect_missing_information
from design.validation import validate_specification
from design.planner_bridge import (
    specification_to_planner_inputs,
    plan_analyses_for_specification
)
from design.report import generate_design_specification_report


def extract_specification(
    problem_statement: str,
    structured_inputs: Optional[Dict[str, Any]] = None,
    provider: Optional[DesignSpecificationProvider] = None
) -> EngineeringSpecification:
    """
    Convenience interface extracting a structured EngineeringSpecification from natural language.
    Executes NLP requirement parsing, deterministic unit normalization, closed-form derivations,
    and missing information analysis.
    """
    extractor = DesignSpecificationExtractor(provider=provider)
    return extractor.extract(problem_statement, structured_inputs=structured_inputs)


__all__ = [
    "EngineeringSpecification",
    "EngineeringQuantity",
    "LoadRequirement",
    "MaterialRequirement",
    "OperatingCondition",
    "DesignConstraint",
    "ConstraintPriority",
    "MissingInformation",
    "MissingImportance",
    "RequirementConflict",
    "DerivedEngineeringValue",
    "DesignSpecificationExtractor",
    "DesignSpecificationProvider",
    "MockDesignSpecificationProvider",
    "GeminiDesignSpecificationProvider",
    "get_design_provider",
    "DerivationRule",
    "PowerSpeedToTorqueRule",
    "DerivationEngine",
    "normalize_power",
    "normalize_rotational_speed",
    "normalize_quantity_data",
    "detect_missing_information",
    "validate_specification",
    "specification_to_planner_inputs",
    "plan_analyses_for_specification",
    "generate_design_specification_report",
    "extract_specification"
]
