"""
Deterministic Engineering Requirement Validator (Slice 14.1).
Enforces physical and schema constraints on EngineeringSpec instances.
Performs strictly zero engineering calculations (no diameter, torque, stress, or strength inference).
"""

import math
from typing import List
from requirements.models import (
    EngineeringSpec,
    RequirementValidationStatus,
    RequirementValidationResult
)


class RequirementValidator:
    """
    Deterministic validator for EngineeringSpec instances.
    Evaluates completeness for downstream engineering sizing/CAD generation
    and strictly validates physical/numeric constraints.
    """

    SUPPORTED_COMPONENTS = {"shaft", "solid_shaft", "circular_shaft"}

    def validate(self, spec: EngineeringSpec) -> RequirementValidationResult:
        """
        Validates an EngineeringSpec instance deterministically.
        Returns RequirementValidationResult without mutating or inferring any engineering values.
        """
        errors: List[str] = []
        missing_information: List[str] = []
        warnings: List[str] = []

        # 1. Component validation
        if spec.component is None:
            missing_information.append("component")
        elif not isinstance(spec.component, str) or not spec.component.strip():
            errors.append("Component name cannot be empty or whitespace.")
        elif spec.component.strip().lower() not in self.SUPPORTED_COMPONENTS:
            errors.append(
                f"Unsupported component type: '{spec.component}'. "
                f"Supported components: {sorted(list(self.SUPPORTED_COMPONENTS))}."
            )

        # 2. Material validation
        if spec.material is None:
            missing_information.append("material")
        elif not isinstance(spec.material, str) or not spec.material.strip():
            errors.append("Material cannot be empty or whitespace.")

        # 3. Power (kW) validation
        if spec.power_kw is None:
            missing_information.append("power_kw")
        else:
            if not isinstance(spec.power_kw, (int, float)) or math.isnan(spec.power_kw) or math.isinf(spec.power_kw):
                errors.append(f"Power (power_kw) must be a finite number; received {spec.power_kw}.")
            elif spec.power_kw < 0:
                errors.append(f"Power (power_kw) cannot be negative; received {spec.power_kw} kW.")
            elif spec.power_kw == 0:
                errors.append("Power (power_kw) must be strictly positive (> 0); received 0 kW.")

        # 4. Rotational speed (RPM) validation
        if spec.rpm is None:
            missing_information.append("rpm")
        else:
            if not isinstance(spec.rpm, (int, float)) or math.isnan(spec.rpm) or math.isinf(spec.rpm):
                errors.append(f"Rotational speed (rpm) must be a finite number; received {spec.rpm}.")
            elif spec.rpm <= 0:
                errors.append(f"Rotational speed (rpm) must be strictly positive (> 0); received {spec.rpm} RPM.")

        # 5. Factor of Safety validation
        if spec.factor_of_safety is None:
            missing_information.append("factor_of_safety")
        else:
            if not isinstance(spec.factor_of_safety, (int, float)) or math.isnan(spec.factor_of_safety) or math.isinf(spec.factor_of_safety):
                errors.append(f"Factor of safety must be a finite number; received {spec.factor_of_safety}.")
            elif spec.factor_of_safety <= 0:
                errors.append(f"Factor of safety must be strictly positive (> 0); received {spec.factor_of_safety}.")

        # 6. Length (mm) validation
        if spec.length_mm is None:
            missing_information.append("length_mm")
        else:
            if not isinstance(spec.length_mm, (int, float)) or math.isnan(spec.length_mm) or math.isinf(spec.length_mm):
                errors.append(f"Shaft length (length_mm) must be a finite number; received {spec.length_mm}.")
            elif spec.length_mm <= 0:
                errors.append(f"Shaft length (length_mm) must be strictly positive (> 0); received {spec.length_mm} mm.")

        # Determine validation status
        if errors:
            status = RequirementValidationStatus.INVALID
            is_valid = False
        elif missing_information:
            status = RequirementValidationStatus.BLOCKED
            is_valid = False
        else:
            status = RequirementValidationStatus.VALID
            is_valid = True

        return RequirementValidationResult(
            is_valid=is_valid,
            status=status,
            spec=spec,
            missing_information=missing_information,
            errors=errors,
            warnings=warnings
        )


def validate_engineering_spec(spec: EngineeringSpec) -> RequirementValidationResult:
    """Convenience function for deterministic requirement validation."""
    return RequirementValidator().validate(spec)
