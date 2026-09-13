"""
Comprehensive test suite for Slice 14.2: LLM Requirement Extraction + Provenance.
Tests explicit requirement extraction, parameter-level provenance, unstated parameter preservation,
unit normalization, anti-inference compliance, and mock LLM provider integration.
"""

import json
import pytest
from reasoning.provider import MockLLMProvider
from requirements import (
    RequirementExtractor,
    extract_requirements,
    validate_engineering_spec,
    RequirementValidationStatus,
    EngineeringSpec
)


# ==============================================================================
# 1. Full Benchmark Extraction & Provenance Tests
# ==============================================================================

def test_slice_13_benchmark_full_extraction():
    """
    Extracts full Slice 13 benchmark problem statement:
    'Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm.'
    Verifies all values and per-field provenance.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm."
    spec = extract_requirements(problem)

    assert spec.component == "shaft"
    assert spec.material == "steel"
    assert spec.power_kw == 5.0
    assert spec.rpm == 1500.0
    assert spec.factor_of_safety == 2.0
    assert spec.length_mm == 300.0
    assert spec.raw_text == problem

    # Verify provenance
    prov = spec.provenance.get("fields", {})
    assert "power_kw" in prov
    assert "5 kW" in prov["power_kw"]["source_text"] or "5" in str(prov["power_kw"]["value"])
    assert prov["power_kw"]["is_explicit"] is True

    assert "rpm" in prov
    assert "1500" in prov["rpm"]["source_text"]

    assert "factor_of_safety" in prov
    assert "2" in prov["factor_of_safety"]["source_text"]

    assert "length_mm" in prov
    assert "300" in prov["length_mm"]["source_text"]

    assert "material" in prov
    assert "steel" in prov["material"]["source_text"].lower()

    # Downstream validation passes
    val = validate_engineering_spec(spec)
    assert val.is_valid is True
    assert val.status == RequirementValidationStatus.VALID


# ==============================================================================
# 2. Unstated Parameter Preservation (Anti-Inference & BLOCKED downstream)
# ==============================================================================

def test_unstated_length_remains_none_and_provenance_marked():
    """
    Problem statement omitting length:
    'Design a steel shaft transmitting 5 kW at 1500 RPM with a factor of safety of 2.'
    Extractor must NOT invent length_mm; downstream validator blocks.
    """
    problem = "Design a steel shaft transmitting 5 kW at 1500 RPM with a factor of safety of 2."
    spec = extract_requirements(problem)

    assert spec.component == "shaft"
    assert spec.material == "steel"
    assert spec.power_kw == 5.0
    assert spec.rpm == 1500.0
    assert spec.factor_of_safety == 2.0
    assert spec.length_mm is None

    # Provenance for length_mm reflects unstated status
    prov = spec.provenance.get("fields", {})
    assert prov["length_mm"]["value"] is None
    assert prov["length_mm"]["is_explicit"] is False

    # Downstream validation blocks on missing length_mm
    val = validate_engineering_spec(spec)
    assert val.is_valid is False
    assert val.status == RequirementValidationStatus.BLOCKED
    assert "length_mm" in val.missing_information


def test_unstated_material_and_fos_remains_none():
    """
    Problem statement omitting material and factor of safety:
    'Design a shaft to transmit 10 kW at 3000 RPM with length 500 mm.'
    """
    problem = "Design a shaft to transmit 10 kW at 3000 RPM with length 500 mm."
    spec = extract_requirements(problem)

    assert spec.component == "shaft"
    assert spec.material is None
    assert spec.power_kw == 10.0
    assert spec.rpm == 3000.0
    assert spec.factor_of_safety is None
    assert spec.length_mm == 500.0

    val = validate_engineering_spec(spec)
    assert val.status == RequirementValidationStatus.BLOCKED
    assert "material" in val.missing_information
    assert "factor_of_safety" in val.missing_information


# ==============================================================================
# 3. Anti-Inference Compliance Tests
# ==============================================================================

def test_extractor_never_calculates_diameter():
    """Extractor does not calculate or include shaft diameter."""
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2 and length 300 mm."
    spec = extract_requirements(problem)

    assert getattr(spec, "diameter", None) is None
    assert getattr(spec, "shaft_diameter_mm", None) is None
    assert "diameter" not in spec.provenance.get("fields", {})


def test_extractor_never_calculates_torque():
    """Extractor does not compute torque from power and speed."""
    problem = "Design a steel shaft transmitting 5 kW at 1500 RPM."
    spec = extract_requirements(problem)

    assert getattr(spec, "torque_nm", None) is None
    assert getattr(spec, "torque", None) is None


def test_extractor_never_infers_material_yield_strength():
    """Extractor preserves generic steel without fabricating 355 MPa or AISI 1045."""
    problem = "Design a steel shaft to transmit 5 kW at 1500 RPM with length 300 mm and FoS 2."
    spec = extract_requirements(problem)

    assert spec.material == "steel"
    assert getattr(spec, "yield_strength_mpa", None) is None
    assert getattr(spec, "material_grade", None) is None


# ==============================================================================
# 4. Unit Normalization Tests
# ==============================================================================

def test_unit_normalization_watts_to_kw():
    """Converts 5000 W to 5.0 kW."""
    problem = "Design a steel shaft to transmit 5000 W at 1500 RPM with length 300 mm and factor of safety 2."
    spec = extract_requirements(problem)
    assert spec.power_kw == 5.0
    assert "5000 W" in spec.provenance["fields"]["power_kw"]["source_text"]


def test_unit_normalization_meters_to_mm():
    """Converts 0.3 m to 300.0 mm."""
    problem = "Design a steel shaft to transmit 5 kW at 1500 RPM with length 0.3 m and FoS 2."
    spec = extract_requirements(problem)
    assert spec.length_mm == 300.0
    assert "0.3 m" in spec.provenance["fields"]["length_mm"]["source_text"]


# ==============================================================================
# 5. Invalid Input Value Extraction & Downstream Rejection
# ==============================================================================

def test_negative_power_extracted_and_downstream_invalid():
    """Negative power is faithfully extracted and rejected by the validator."""
    problem = "Design a shaft with -5 kW at 1500 RPM, length 300 mm, FoS 2, steel."
    spec = extract_requirements(problem)
    assert spec.power_kw == -5.0

    val = validate_engineering_spec(spec)
    assert val.is_valid is False
    assert val.status == RequirementValidationStatus.INVALID


def test_zero_rpm_extracted_and_downstream_invalid():
    """Zero RPM is extracted and rejected downstream."""
    problem = "Design a steel shaft with 5 kW at 0 RPM, length 300 mm, FoS 2."
    spec = extract_requirements(problem)
    assert spec.rpm == 0.0

    val = validate_engineering_spec(spec)
    assert val.is_valid is False
    assert val.status == RequirementValidationStatus.INVALID


# ==============================================================================
# 6. Mock LLM Provider & Canned JSON Integration Tests
# ==============================================================================

def test_mock_llm_provider_canned_json_response():
    """Verifies extractor parses LLM markdown code-fence JSON output."""
    canned_payload = {
        "component": "shaft",
        "material": "steel",
        "power_kw": 7.5,
        "rpm": 1800.0,
        "factor_of_safety": 2.5,
        "length_mm": 450.0,
        "provenance": {
          "power_kw": {"source_text": "7.5 kW", "value": 7.5, "is_explicit": True},
          "rpm": {"source_text": "1800 RPM", "value": 1800.0, "is_explicit": True},
          "factor_of_safety": {"source_text": "factor of safety 2.5", "value": 2.5, "is_explicit": True},
          "length_mm": {"source_text": "length 450 mm", "value": 450.0, "is_explicit": True},
          "material": {"source_text": "steel", "value": "steel", "is_explicit": True},
          "component": {"source_text": "shaft", "value": "shaft", "is_explicit": True}
        }
    }
    raw_canned = f"```json\n{json.dumps(canned_payload)}\n```"
    mock_prov = MockLLMProvider(canned_response=raw_canned)
    extractor = RequirementExtractor(provider=mock_prov)

    spec = extractor.extract("Design a shaft transmitting 7.5 kW at 1800 RPM with FoS 2.5 and length 450 mm in steel.")
    assert spec.power_kw == 7.5
    assert spec.rpm == 1800.0
    assert spec.factor_of_safety == 2.5
    assert spec.length_mm == 450.0
    assert spec.material == "steel"

    val = validate_engineering_spec(spec)
    assert val.is_valid is True
    assert val.status == RequirementValidationStatus.VALID


def test_mock_llm_malformed_json_triggers_clean_fallback():
    """Malformed LLM JSON falls back to deterministic grounded extraction without crashing."""
    mock_prov = MockLLMProvider(canned_response="Malformed { non-json output }}}")
    extractor = RequirementExtractor(provider=mock_prov)

    spec = extractor.extract("Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm.")
    assert spec.power_kw == 5.0
    assert spec.rpm == 1500.0
    assert spec.factor_of_safety == 2.0
    assert spec.length_mm == 300.0
    assert spec.material == "steel"
