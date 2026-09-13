"""
Comprehensive unit and integration test suite for Material Knowledge Base v1.
Validates schemas, registry loading, deterministic normalization, lookup strategies,
precedence/override mechanics, error handling, pipeline integration, and legacy compatibility.
"""

import pytest
import json
import tempfile
from pydantic import ValidationError

from knowledge.materials.schema import MaterialRecord, MaterialResolutionResult
from knowledge.materials.registry import MaterialRegistry, get_material_registry
from knowledge.materials.repository import (
    MaterialRepository,
    normalize_designation,
    get_default_material_repository
)
from requirements.models import EngineeringSpec, PipelineStatus, RequirementValidationStatus
from requirements.pipeline import EndToEndPipeline, run_design_pipeline
from fastapi.testclient import TestClient
from api.main import app


# ==============================================================================
# 1. Schema & Validation Tests
# ==============================================================================

def test_valid_material_schema():
    """Validates that a correctly specified material record is accepted."""
    record = MaterialRecord(
        material_id="mat_test_steel",
        designation="TestSteel-355",
        standard="ISO 12345",
        category="structural_steel",
        yield_strength_mpa=355.0,
        ultimate_tensile_strength_mpa=510.0,
        elastic_modulus_gpa=210.0,
        poisson_ratio=0.30,
        density_kg_m3=7850.0,
        source="ISO 12345 Table 1",
        source_revision="2022",
        status="verified",
        aliases=["TestSteel", "TS355"]
    )
    assert record.material_id == "mat_test_steel"
    assert record.yield_strength_mpa == 355.0
    assert record.elastic_modulus_gpa == 210.0
    assert record.poisson_ratio == 0.30
    assert record.density_kg_m3 == 7850.0


def test_malformed_material_record_rejection():
    """Validates that physically invalid or non-positive values are strictly rejected."""
    # Negative yield strength
    with pytest.raises(ValidationError):
        MaterialRecord(
            material_id="mat_bad_1",
            designation="BadSteel",
            standard="ISO 12345",
            category="steel",
            yield_strength_mpa=-355.0,
            elastic_modulus_gpa=210.0,
            poisson_ratio=0.30,
            density_kg_m3=7850.0,
            source="Test",
            source_revision="2022"
        )

    # Invalid Poisson's ratio (must be 0.0 < nu < 0.5)
    with pytest.raises(ValidationError):
        MaterialRecord(
            material_id="mat_bad_2",
            designation="BadSteel",
            standard="ISO 12345",
            category="steel",
            yield_strength_mpa=355.0,
            elastic_modulus_gpa=210.0,
            poisson_ratio=0.55,  # Exceeds 0.5
            density_kg_m3=7850.0,
            source="Test",
            source_revision="2022"
        )

    # Zero density
    with pytest.raises(ValidationError):
        MaterialRecord(
            material_id="mat_bad_3",
            designation="BadSteel",
            standard="ISO 12345",
            category="steel",
            yield_strength_mpa=355.0,
            elastic_modulus_gpa=210.0,
            poisson_ratio=0.30,
            density_kg_m3=0.0,
            source="Test",
            source_revision="2022"
        )


def test_registry_rejects_malformed_json_file():
    """Validates that registry load raises clear errors on malformed dataset files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('[{"material_id": "mat_invalid", "designation": "Incomplete"}]')
        temp_path = f.name

    with pytest.raises(ValueError) as excinfo:
        MaterialRegistry(data_path=temp_path)
    assert "Malformed material record" in str(excinfo.value)


# ==============================================================================
# 2. Lookup & Normalization Tests
# ==============================================================================

def test_lookup_by_id():
    """Validates direct lookup by unique material_id."""
    repo = get_default_material_repository()
    rec = repo.get_by_id("mat_s355j2")
    assert rec is not None
    assert rec.designation == "S355J2"
    assert rec.yield_strength_mpa == 355.0
    assert rec.standard == "EN 10025-2:2019"

    rec_al = repo.get_by_id("mat_al_6061_t6")
    assert rec_al is not None
    assert rec_al.designation == "6061-T6"
    assert rec_al.yield_strength_mpa == 276.0


def test_lookup_by_designation():
    """Validates case-insensitive designation and alias lookups."""
    repo = get_default_material_repository()

    # Exact and alias lookups
    assert repo.get_by_designation("S355") is not None
    assert repo.get_by_designation("s355j2") is not None
    assert repo.get_by_designation("AISI 1045") is not None
    assert repo.get_by_designation("c45") is not None
    assert repo.get_by_designation("6061-T6") is not None
    assert repo.get_by_designation("AISI 304") is not None


def test_case_and_whitespace_normalization():
    """Validates robust deterministic normalization across punctuation and casing."""
    assert normalize_designation("  S-355 JR  ") == "s355jr"
    assert normalize_designation("AISI_1045") == "aisi1045"
    assert normalize_designation("6061 - T6") == "6061t6"
    assert normalize_designation("Steel (S355)") == "steels355"

    repo = get_default_material_repository()
    assert repo.find("  s-355 jr  ") is not None
    assert repo.find("AISI 1045") is not None
    assert repo.find("aisi-1045") is not None
    assert repo.find("6061-t6") is not None


# ==============================================================================
# 3. Resolution Hierarchy & Override Tests
# ==============================================================================

def test_unknown_material_resolution():
    """Validates that unknown materials return explicit unresolved results without inventing properties."""
    repo = get_default_material_repository()
    res = repo.resolve(requested_material="Titanium Beta-C")
    assert not res.resolved
    assert res.yield_strength_mpa is None
    assert res.status == "Unresolved"
    assert len(res.errors) > 0
    assert "not found in Material Knowledge Base" in res.errors[0]


def test_generic_steel_without_yield_strength_blocked():
    """Validates that generic 'steel' without a specific grade or Sy is unresolved and not fabricated."""
    repo = get_default_material_repository()
    res = repo.resolve(requested_material="steel")
    assert not res.resolved
    assert res.yield_strength_mpa is None
    assert res.status == "Unresolved"
    assert "generic" in res.errors[0].lower()


def test_explicit_yield_strength_overriding_kb_value():
    """
    Validates requirement:
    If user supplies material = S355 and explicit yield_strength = 280 MPa:
    The explicit 280 MPa requirement takes precedence, and the discrepancy is traceable.
    """
    repo = get_default_material_repository()
    res = repo.resolve(requested_material="S355", explicit_yield_strength_mpa=280.0)
    assert res.resolved
    assert res.yield_strength_mpa == 280.0
    assert res.is_explicit_override is True
    assert res.status == "Explicit override"
    assert res.yield_strength_source == "Explicit user requirement"
    assert res.knowledge_base_yield_strength_mpa == 355.0
    assert len(res.warnings) > 0
    assert "280.0 MPa" in res.warnings[0]
    assert "355.0 MPa" in res.warnings[0]


def test_kb_value_used_when_no_explicit_yield_strength():
    """Validates that when no explicit Sy is supplied, KB supplies standard value with Verified status."""
    repo = get_default_material_repository()
    res = repo.resolve(requested_material="S355", explicit_yield_strength_mpa=None)
    assert res.resolved
    assert res.yield_strength_mpa == 355.0
    assert res.is_explicit_override is False
    assert res.status == "Verified"
    assert res.yield_strength_source == "Knowledge Base"
    assert res.standard == "EN 10025-2:2019"


def test_no_silent_s355_fallback():
    """Validates that missing material or generic steel does not silently fall back to S355."""
    repo = get_default_material_repository()
    res_none = repo.resolve(requested_material=None, explicit_yield_strength_mpa=None)
    assert not res_none.resolved
    assert res_none.yield_strength_mpa is None

    res_steel = repo.resolve(requested_material="steel", explicit_yield_strength_mpa=None)
    assert not res_steel.resolved
    assert res_steel.yield_strength_mpa is None


# ==============================================================================
# 4. Canonical Pipeline Integration Tests
# ==============================================================================

def test_canonical_pipeline_resolves_kb_material():
    """
    Validates end-to-end pipeline:
    Prompt with named material 'S355' and no explicit Sy resolves 355 MPa from KB and completes successfully.
    """
    statement = "Design a solid circular shaft made of S355 to transmit 5 kW at 1500 RPM with a factor of safety of 2."
    extra_inputs = {"length_mm": 300.0}

    result = run_design_pipeline(
        problem_statement=statement,
        extra_inputs=extra_inputs
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.solver_result is not None
    assert result.solver_result.is_valid is True
    assert result.solver_result.yield_strength_mpa == 355.0
    assert result.material_resolution is not None
    assert result.material_resolution["resolved"] is True
    assert result.material_resolution["yield_strength_source"] == "Knowledge Base"
    assert result.material_resolution["status"] == "Verified"
    assert "Material Traceability & Knowledge Base Resolution" in result.report
    assert "EN 10025-2:2019" in result.report


def test_canonical_pipeline_explicit_yield_override():
    """
    Validates end-to-end pipeline:
    Prompt specifies S355, but extra_inputs specifies yield_strength_mpa = 280.0.
    Pipeline uses 280.0 MPa, records 'Explicit override', and completes successfully.
    """
    statement = "Design a solid circular shaft made of S355 to transmit 5 kW at 1500 RPM with a factor of safety of 2."
    extra_inputs = {"length_mm": 300.0, "yield_strength_mpa": 280.0}

    result = run_design_pipeline(
        problem_statement=statement,
        extra_inputs=extra_inputs
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.solver_result.yield_strength_mpa == 280.0
    assert result.material_resolution["is_explicit_override"] is True
    assert result.material_resolution["yield_strength_source"] == "Explicit user requirement"
    assert result.material_resolution["knowledge_base_yield_strength_mpa"] == 355.0
    assert "Explicit override" in result.report


def test_canonical_pipeline_generic_steel_without_sy_blocks():
    """
    Validates that generic 'steel' with no explicit Sy stops at validation with BLOCKED status.
    """
    statement = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2."
    extra_inputs = {"length_mm": 300.0}

    result = run_design_pipeline(
        problem_statement=statement,
        extra_inputs=extra_inputs
    )

    assert result.status == PipelineStatus.BLOCKED
    assert "yield_strength_mpa" in result.missing_information
    assert result.cad_result is None


def test_solver_receives_resolved_properties():
    """
    Validates that the solver receives the exact resolved material properties for AISI 1045 (Sy = 310 MPa).
    """
    statement = "Design a solid circular shaft made of AISI 1045 to transmit 10 kW at 1000 RPM with FoS 2.5."
    extra_inputs = {"length_mm": 400.0}

    result = run_design_pipeline(
        problem_statement=statement,
        extra_inputs=extra_inputs
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.solver_result.yield_strength_mpa == 310.0
    assert result.solver_result.factor_of_safety == 2.5
    # S_sy = 0.57735 * 310 = 178.98 MPa, tau_allow = 178.98 / 2.5 = 71.59 MPa
    assert abs(result.solver_result.allowable_stress_mpa - 71.59) < 0.2


# ==============================================================================
# 5. Legacy /design Route Compatibility Tests
# ==============================================================================

def test_legacy_design_path_remains_unchanged():
    """
    Validates that the legacy POST /design endpoint remains functioning without modification.
    """
    client = TestClient(app)
    payload = {
        "problem_statement": "Design a steel shaft to transmit 5 kW at 1500 RPM.",
        "engineering_inputs": {
            "yield_strength": 355.0,
            "design_factor": 2.0,
            "length": 300.0,
            "material": "STEEL"
        }
    }
    response = client.post("/design", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "report" in data
    assert data["result"]["selected_candidate"] is not None
    assert data["result"]["machine_element"] == "shaft"
    assert data["result"]["design_status"] == "PASS"
