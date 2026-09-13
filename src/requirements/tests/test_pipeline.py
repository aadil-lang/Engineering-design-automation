"""
Comprehensive test suite for Slice 14.4: End-to-End Engineering Design Pipeline.
Verifies the complete pipeline flow:
NL Requirement -> Extraction -> Validation -> Closed-Form Mechanical Solver
-> Parametric 3D BRep CAD -> 2D Technical Drawing -> Dimensional Cross-Validation
-> Engineering Handoff Packaging.

Covers all 8 required verification categories:
1. Full Success Benchmark (5 kW, 1500 RPM, FoS=2, Sy=355 MPa, L=300 mm -> d=12 mm, STEP, SVG, Verified)
2. Missing Yield Strength Blocking (Generic "steel" without Sy -> BLOCKED, No CAD)
3. Missing Length Blocking (Missing L -> BLOCKED, No CAD)
4. Invalid Engineering Inputs (Negative/Zero Sy, L, P, N -> INVALID, No CAD)
5. Parameter-Level Provenance & Lineage Traceability
6. Architectural Integrity: Zero LLM Engineering Arithmetic (Solver derivation only)
7. CAD/Drawing Dimensional Mismatch -> REQUIRES_REVIEW Status
8. API Route Verification & Full System Regression
"""

import math
import pytest
from fastapi.testclient import TestClient

from requirements.models import (
    EngineeringSpec,
    FieldProvenance,
    RequirementValidationStatus,
    PipelineStatus,
    EndToEndDesignResult
)
from requirements.pipeline import EndToEndPipeline, run_design_pipeline
from cad.models import CADSpecification, CADStatus, CADArtifact
from cad.generator import CADGenerator
from cad.drawing import DrawingDocument, DrawingDimension
from api.main import app


# ==============================================================================
# 1. Full Success Benchmark Test
# ==============================================================================

def test_full_success_benchmark_pipeline(tmp_path):
    """
    Test 1: Full End-to-End Success Pipeline with the established benchmark.
    NL: 'Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.'
    Structured inputs: yield_strength_mpa=355.0, length_mm=300.0
    Expected:
      - Torque ≈ 31.83 N*m
      - Req Diameter ≈ 11.65 mm
      - Selected Diameter = 12.0 mm
      - Design Stress ≈ 93.82 MPa
      - Achieved FoS ≈ 2.18
      - Length = 300.0 mm
      - Valid STEP, SVG, BRep volume, 100% CAD <-> Drawing match
      - Status: SUCCESS
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2."
    extra_inputs = {
        "yield_strength_mpa": 355.0,
        "length_mm": 300.0
    }

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    # 1. Overall Status
    assert res.status == PipelineStatus.SUCCESS

    # 2. Extracted & Supplied Requirements
    assert res.spec is not None
    assert res.spec.component == "shaft"
    assert res.spec.material == "steel"
    assert res.spec.power_kw == 5.0
    assert res.spec.rpm == 1500.0
    assert res.spec.factor_of_safety == 2.0
    assert res.spec.yield_strength_mpa == 355.0
    assert res.spec.length_mm == 300.0

    # 3. Solver Outputs & Derivations
    assert res.solver_result is not None
    assert res.solver_result.is_valid is True
    assert res.solver_result.status == RequirementValidationStatus.VALID
    assert res.solver_result.torque_nm == pytest.approx(31.831, rel=1e-3)
    assert res.solver_result.minimum_required_diameter_mm == pytest.approx(11.65, rel=1e-2)
    assert res.solver_result.selected_diameter_mm == 12.0
    assert res.solver_result.design_stress_mpa == pytest.approx(93.82, rel=1e-2)
    assert res.solver_result.achieved_factor_of_safety == pytest.approx(2.18, rel=1e-2)
    assert res.solver_result.is_safe is True
    assert len(res.solver_result.calculation_steps) >= 6

    # 4. CAD & Drawing Artifacts
    assert res.cad_result is not None
    assert res.cad_status == "GENERATED"
    assert res.cad_result.status == CADStatus.GENERATED
    assert "step" in res.artifacts
    assert "svg" in res.artifacts
    assert res.cad_result.validation.is_valid is True
    assert res.cad_result.validation.bounding_box["dx"] == 300.0
    assert res.cad_result.validation.bounding_box["dy"] == 12.0

    # 5. Dimensional Cross-Validation
    assert res.cross_validation["all_match"] is True
    assert res.cross_validation["diameter_matches"]["match"] is True
    assert res.cross_validation["length_matches"]["match"] is True

    # 6. Engineering Handoff
    assert res.handoff is not None
    assert res.handoff.handoff_id.startswith("handoff-")
    assert res.handoff.machine_element == "shaft"
    assert res.handoff.traceability_matrix["parameters"]["shaft_diameter"]["cad_value"] == 12.0
    assert res.handoff.traceability_matrix["parameters"]["shaft_diameter"]["drawing_dimension"] == 12.0
    assert res.handoff.traceability_matrix["parameters"]["shaft_length"]["cad_value"] == 300.0
    assert res.handoff.traceability_matrix["parameters"]["shaft_length"]["drawing_dimension"] == 300.0
    assert res.handoff.traceability_matrix["solver_metrics"]["torque_nm"] == pytest.approx(31.831, rel=1e-3)

    # 7. Audit Report & Disclaimers
    assert "Disclaimer" in res.report
    assert "does not grant certified manufacturing approval" in res.report
    assert "Parameter Provenance" in res.report
    assert "Deterministic Mechanical Calculation Certificate" in res.report


# ==============================================================================
# 2. Missing Yield Strength Blocking Tests
# ==============================================================================

def test_missing_yield_strength_blocks_pipeline_before_cad(tmp_path):
    """
    Test 2: Natural-language prompt without explicit yield strength -> BLOCKED.
    Verifies that generic 'steel' does not imply 355 MPa, solver does not compute,
    and no CAD artifacts are created.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm."
    # No yield strength supplied
    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=None,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.BLOCKED
    assert res.solver_result.is_valid is False
    assert res.solver_result.status == RequirementValidationStatus.BLOCKED
    assert "yield_strength_mpa" in res.missing_information
    assert res.solver_result.selected_diameter_mm is None
    assert res.solver_result.torque_nm is None
    assert res.cad_result is None
    assert res.artifacts == {}
    assert res.handoff is None
    assert "yield_strength_mpa" in res.report


# ==============================================================================
# 3. Missing Length Blocking Tests
# ==============================================================================

def test_missing_length_blocks_pipeline_before_cad(tmp_path):
    """
    Test 3: Prompt with Sy supplied but length missing -> BLOCKED.
    Verifies no CAD generation occurs without explicit length.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2."
    extra_inputs = {"yield_strength_mpa": 355.0}

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.BLOCKED
    assert res.solver_result.is_valid is False
    assert "length_mm" in res.missing_information
    assert res.cad_result is None
    assert res.artifacts == {}


# ==============================================================================
# 4. Invalid Engineering Inputs Tests
# ==============================================================================

def test_negative_yield_strength_halts_as_invalid(tmp_path):
    """
    Test 4A: Negative yield strength -> INVALID, no calculations or CAD.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2."
    extra_inputs = {"yield_strength_mpa": -355.0, "length_mm": 300.0}

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.INVALID
    assert res.solver_result.is_valid is False
    assert len(res.errors) > 0
    assert any("yield_strength_mpa" in err for err in res.errors)
    assert res.cad_result is None


def test_zero_power_halts_as_invalid(tmp_path):
    """
    Test 4B: Zero or negative power in prompt/inputs -> INVALID.
    """
    problem = "Design a shaft with 0 kW at 1500 RPM and length 300 mm."
    extra_inputs = {"yield_strength_mpa": 355.0}

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.INVALID
    assert res.solver_result.is_valid is False
    assert len(res.errors) > 0
    assert res.cad_result is None


# ==============================================================================
# 5. Provenance Traceability Tests
# ==============================================================================

def test_field_level_provenance_preserved_throughout_pipeline(tmp_path):
    """
    Test 5: Validates field-level provenance metadata is preserved from extraction
    and structured input overlay through to CAD specification and report.
    """
    problem = "Design a solid circular steel shaft to transmit 10 kW at 1000 RPM with a minimum factor of safety of 1.5."
    extra_inputs = {
        "yield_strength_mpa": 250.0,
        "length_mm": 450.0
    }

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.SUCCESS
    assert "power_kw" in res.provenance
    assert "rpm" in res.provenance
    assert "yield_strength_mpa" in res.provenance
    assert "length_mm" in res.provenance

    # Verify provenance origin labels
    sy_prov = res.provenance["yield_strength_mpa"]
    len_prov = res.provenance["length_mm"]
    assert sy_prov["source_text"] == "structured_input"
    assert len_prov["source_text"] == "structured_input"
    assert sy_prov["is_explicit"] is True

    # Check CAD specification provenance
    assert res.cad_result.cad_specification.provenance["yield_strength_mpa"]["value"] == 250.0


# ==============================================================================
# 6. No Calculation by LLM Tests
# ==============================================================================

def test_llm_cannot_calculate_or_override_deterministic_solver(tmp_path):
    """
    Test 6: Verifies that even if the prompt or LLM payload contains hallucinated
    diameters or stresses, the pipeline derives geometry strictly from ShaftEngineeringSolver.
    """
    # Prompt contains distracting/misleading numbers
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2. We guess the diameter is 50 mm and torque is 999 Nm."
    extra_inputs = {
        "yield_strength_mpa": 355.0,
        "length_mm": 300.0,
        "hallucinated_diameter": 50.0
    }

    res = run_design_pipeline(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.SUCCESS
    # Calculated diameter must be 12.0 mm (from 5kW @ 1500RPM with Sy=355, FoS=2), NEVER 50 mm!
    assert res.solver_result.selected_diameter_mm == 12.0
    assert res.solver_result.torque_nm == pytest.approx(31.831, rel=1e-3)
    assert res.cad_result.cad_specification.diameter == 12.0
    assert res.cad_result.validation.bounding_box["dy"] == 12.0


# ==============================================================================
# 7. CAD/Drawing Mismatch Triggers REQUIRES_REVIEW Tests
# ==============================================================================

class PerturbedDrawingGenerator(CADGenerator):
    """Subclass of CADGenerator that simulates a dimensional mismatch in the 2D drawing."""
    def generate(self, spec, output_dir=None):
        resp = super().generate(spec, output_dir=output_dir)
        # Perturb a drawing dimension to simulate CAD/Drawing divergence
        if resp.drawing_document and resp.drawing_document.dimensions:
            for dim in resp.drawing_document.dimensions:
                if dim.dimension_type == "diameter":
                    dim.value = dim.value + 5.0  # e.g. 17.0 mm instead of 12.0 mm
            # Re-run cross validation
            resp.dimensional_cross_validation = self._cross_validate_dimensions(spec, resp.drawing_document)
            resp.status = CADStatus.REQUIRES_REVIEW
        return resp


def test_cad_drawing_mismatch_triggers_requires_review(tmp_path):
    """
    Test 7: If drawing dimensions disagree with CAD solid model dimensions,
    the pipeline status becomes REQUIRES_REVIEW rather than SUCCESS.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2."
    extra_inputs = {"yield_strength_mpa": 355.0, "length_mm": 300.0}

    pipeline = EndToEndPipeline(cad_generator=PerturbedDrawingGenerator())
    res = pipeline.run(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.REQUIRES_REVIEW
    assert res.cross_validation["all_match"] is False
    assert res.cross_validation["diameter_matches"]["match"] is False
    assert any("requires engineering review" in w for w in res.warnings)


# ==============================================================================
# 8. API Route Integration Tests
# ==============================================================================

def test_api_design_pipeline_endpoint():
    """
    Test 8: Validates the POST /design/pipeline API endpoint via FastAPI TestClient.
    """
    client = TestClient(app)

    # 1. Full Success Payload
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.",
        "engineering_inputs": {
            "yield_strength_mpa": 355.0,
            "length_mm": 300.0
        }
    }
    response = client.post("/design/pipeline", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["solver_result"]["selected_diameter_mm"] == 12.0
    assert data["solver_result"]["torque_nm"] == pytest.approx(31.831, rel=1e-3)
    assert "step" in data["artifacts"]
    assert "svg" in data["artifacts"]
    assert data["cross_validation"]["all_match"] is True

    # 2. Blocked Missing Yield Strength Payload
    blocked_payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2.",
        "engineering_inputs": {
            "length_mm": 300.0
        }
    }
    b_response = client.post("/design/pipeline", json=blocked_payload)
    assert b_response.status_code == 200
    b_data = b_response.json()
    assert b_data["status"] == "BLOCKED"
    assert "yield_strength_mpa" in b_data["missing_information"]
    assert b_data["solver_result"]["selected_diameter_mm"] is None


# ==============================================================================
# 9. Empty Requirement & CAD Failure Path Tests
# ==============================================================================

def test_empty_prompt_and_no_structured_inputs_blocks_cleanly(tmp_path):
    """
    Test 9: prompt='' with no structured inputs stops cleanly at validation
    with BLOCKED status and does not invoke the solver or CAD generation.
    """
    res = run_design_pipeline(
        problem_statement="",
        extra_inputs=None,
        output_dir=str(tmp_path)
    )
    assert res.status in (PipelineStatus.BLOCKED, PipelineStatus.INVALID)
    assert res.solver_result is None or res.solver_result.is_valid is False
    assert res.cad_result is None
    assert res.artifacts == {}
    assert res.handoff is None


class FailingCADGenerator(CADGenerator):
    """CADGenerator subclass that simulates a backend kernel or export failure."""
    def generate(self, spec, output_dir=None):
        raise RuntimeError("Simulated OpenCascade kernel crash or disk write failure during STEP export.")


def test_cad_kernel_failure_returns_pipeline_failed_status(tmp_path):
    """
    Test 10: Simulated CAD kernel failure returns PipelineStatus.FAILED
    and ensures no downstream artifact is reported as successfully generated.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2."
    extra_inputs = {"yield_strength_mpa": 355.0, "length_mm": 300.0}

    pipeline = EndToEndPipeline(cad_generator=FailingCADGenerator())
    res = pipeline.run(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert res.status == PipelineStatus.FAILED
    assert res.cad_result is None
    assert res.artifacts == {}
    assert res.handoff is None
    assert len(res.errors) > 0
    assert any("Simulated OpenCascade kernel crash" in err for err in res.errors)
