"""
Comprehensive test suite for Slice 14.1: Engineering Requirement Schema + Deterministic Validation.
Validates structured schema integrity, deterministic missing-information reporting,
rejection of invalid/unphysical inputs, and strict anti-inference boundaries.
"""

import math
import pytest
from requirements import (
    RequirementValidationStatus,
    EngineeringSpec,
    RequirementValidationResult,
    RequirementValidator,
    validate_engineering_spec
)


# ==============================================================================
# 1. Valid Specifications & Benchmarks
# ==============================================================================

def test_complete_shaft_specification_passes():
    """1. Complete shaft specification passes validation with VALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is True
    assert res.status == RequirementValidationStatus.VALID
    assert res.missing_information == []
    assert res.errors == []
    assert res.spec == spec


def test_slice_13_benchmark_representation():
    """
    2. The Slice 13 benchmark can be represented exactly:
       solid circular steel shaft, 5 kW, 1500 RPM, FoS 2, length 300 mm.
    """
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0,
        raw_text="Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2."
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is True
    assert res.status == RequirementValidationStatus.VALID
    assert res.spec.material == "steel"
    assert res.spec.power_kw == 5.0
    assert res.spec.rpm == 1500.0
    assert res.spec.factor_of_safety == 2.0
    assert res.spec.length_mm == 300.0


# ==============================================================================
# 2. Missing Information (BLOCKED Status)
# ==============================================================================

def test_missing_length_blocked():
    """3. Missing length -> BLOCKED status with 'length_mm' in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=None
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.BLOCKED
    assert "length_mm" in res.missing_information
    assert res.errors == []


def test_missing_material_blocked():
    """4. Missing material -> BLOCKED status with 'material' in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material=None,
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.BLOCKED
    assert "material" in res.missing_information


def test_missing_power_blocked():
    """5. Missing power -> BLOCKED status with 'power_kw' in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=None,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.BLOCKED
    assert "power_kw" in res.missing_information


def test_missing_rpm_blocked():
    """6. Missing RPM -> BLOCKED status with 'rpm' in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=None,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.BLOCKED
    assert "rpm" in res.missing_information


def test_missing_factor_of_safety_blocked():
    """7. Missing factor of safety -> BLOCKED status with 'factor_of_safety' in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=None,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.BLOCKED
    assert "factor_of_safety" in res.missing_information


def test_multiple_missing_fields_blocked():
    """Multiple missing fields are all reported in missing_information."""
    spec = EngineeringSpec(
        component="shaft",
        material=None,
        power_kw=5.0,
        rpm=None,
        factor_of_safety=None,
        length_mm=None
    )
    res = validate_engineering_spec(spec)
    assert res.status == RequirementValidationStatus.BLOCKED
    assert set(res.missing_information) == {"material", "rpm", "factor_of_safety", "length_mm"}


# ==============================================================================
# 3. Invalid Values Rejection (INVALID Status)
# ==============================================================================

def test_negative_power_rejected():
    """8. Negative power rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=-5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("power" in err.lower() for err in res.errors)


def test_zero_power_rejected():
    """Zero power rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=0.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("power" in err.lower() for err in res.errors)


def test_zero_rpm_rejected():
    """9. Zero RPM rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=0.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("rpm" in err.lower() or "speed" in err.lower() for err in res.errors)


def test_negative_rpm_rejected():
    """10. Negative RPM rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=-1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("rpm" in err.lower() or "speed" in err.lower() for err in res.errors)


def test_zero_factor_of_safety_rejected():
    """11. Zero factor of safety rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=0.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("factor of safety" in err.lower() for err in res.errors)


def test_negative_factor_of_safety_rejected():
    """12. Negative factor of safety rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=-2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("factor of safety" in err.lower() for err in res.errors)


def test_zero_length_rejected():
    """13. Zero length rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=0.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("length" in err.lower() for err in res.errors)


def test_negative_length_rejected():
    """14. Negative length rejected with INVALID status."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=-300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("length" in err.lower() for err in res.errors)


def test_empty_material_rejected():
    """15. Empty material (empty string or whitespace) rejected with INVALID status."""
    spec_empty = EngineeringSpec(
        component="shaft",
        material="",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res_empty = validate_engineering_spec(spec_empty)
    assert res_empty.is_valid is False
    assert res_empty.status == RequirementValidationStatus.INVALID
    assert any("material" in err.lower() for err in res_empty.errors)

    spec_ws = EngineeringSpec(
        component="shaft",
        material="   ",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res_ws = validate_engineering_spec(spec_ws)
    assert res_ws.is_valid is False
    assert res_ws.status == RequirementValidationStatus.INVALID


def test_empty_component_rejected():
    """16. Empty component (empty string or whitespace) rejected with INVALID status."""
    spec_empty = EngineeringSpec(
        component="",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec_empty)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("component" in err.lower() for err in res.errors)


def test_unsupported_component_rejected():
    """Unsupported machine element is rejected cleanly."""
    spec = EngineeringSpec(
        component="hydraulic_piston",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert res.is_valid is False
    assert res.status == RequirementValidationStatus.INVALID
    assert any("unsupported component" in err.lower() for err in res.errors)


def test_non_finite_numeric_values_rejected():
    """17. Non-finite numeric values (NaN, Inf, -Inf) rejected."""
    for bad_val in (float("nan"), float("inf"), float("-inf")):
        spec_power = EngineeringSpec(
            component="shaft",
            material="steel",
            power_kw=bad_val,
            rpm=1500.0,
            factor_of_safety=2.0,
            length_mm=300.0
        )
        res_power = validate_engineering_spec(spec_power)
        assert res_power.is_valid is False
        assert res_power.status == RequirementValidationStatus.INVALID

        spec_rpm = EngineeringSpec(
            component="shaft",
            material="steel",
            power_kw=5.0,
            rpm=bad_val,
            factor_of_safety=2.0,
            length_mm=300.0
        )
        res_rpm = validate_engineering_spec(spec_rpm)
        assert res_rpm.is_valid is False
        assert res_rpm.status == RequirementValidationStatus.INVALID


# ==============================================================================
# 4. Anti-Inference Boundaries
# ==============================================================================

def test_anti_inference_missing_length_remains_none():
    """18. Missing length remains None and is not inferred."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=None
    )
    res = validate_engineering_spec(spec)
    assert res.spec.length_mm is None


def test_anti_inference_no_default_length():
    """19. Validator does not create a default length or mutate the specification."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=None
    )
    res = validate_engineering_spec(spec)
    assert res.spec.length_mm is None
    assert getattr(res.spec, "inferred_length", None) is None


def test_anti_inference_no_default_material_strength():
    """20. Validator does not create a default material strength or yield stress."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert getattr(res.spec, "yield_strength_mpa", None) is None
    assert getattr(res.spec, "allowable_stress_mpa", None) is None


def test_anti_inference_no_diameter_calculation():
    """21. Validator does not calculate or introduce a shaft diameter."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res = validate_engineering_spec(spec)
    assert getattr(res.spec, "diameter", None) is None
    assert getattr(res.spec, "shaft_diameter_mm", None) is None
    assert getattr(res.spec, "torque_nm", None) is None


# ==============================================================================
# 5. Ergonomics & Schema Serialization
# ==============================================================================

def test_validator_class_and_function_equivalence():
    """RequirementValidator instance matches validate_engineering_spec output."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    res1 = RequirementValidator().validate(spec)
    res2 = validate_engineering_spec(spec)
    assert res1.model_dump() == res2.model_dump()


def test_pydantic_serialization_and_deserialization():
    """EngineeringSpec and RequirementValidationResult serialize cleanly to JSON/dict."""
    spec = EngineeringSpec(
        component="shaft",
        material="steel",
        power_kw=5.0,
        rpm=1500.0,
        factor_of_safety=2.0,
        length_mm=300.0
    )
    data = spec.model_dump()
    assert data["power_kw"] == 5.0
    assert data["rpm"] == 1500.0

    restored = EngineeringSpec(**data)
    assert restored == spec

    res = validate_engineering_spec(spec)
    res_data = res.model_dump()
    assert res_data["status"] == "VALID"
    assert res_data["is_valid"] is True
