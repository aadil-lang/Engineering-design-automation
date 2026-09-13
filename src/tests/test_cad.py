"""
Comprehensive test suite for Slice 13: Practical Parametric CAD + Engineering Drawing Generation.
Covers BRep solid modeling, ISO-10303-21 STEP export, 2D drawing derivation,
SVG rendering, dimensional cross-validation, engineering handoff, and acceptance benchmarks.
"""

import os
import math
import pytest
from fastapi.testclient import TestClient
from api.main import app

from cad import (
    CADStatus,
    CADSpecification,
    CADArtifact,
    BRepValidationResult,
    CADBackend,
    BRepSolidCylinder,
    OpenCascadeBackend,
    DrawingDocument,
    SVGRenderer,
    DrawingExporter,
    build_shaft_cad_specification,
    create_engineering_handoff_package,
    CADGenerator
)
from design_engine import (
    ShaftDesignRequirements,
    ShaftDesigner,
    design_from_problem_statement
)


# ==============================================================================
# 1. CAD Specification & Input Validation Tests
# ==============================================================================

def test_shaft_cad_specification_creation():
    """Verify CADSpecification creation and structured attribute population."""
    spec = CADSpecification(
        part_name="SHAFT_12X300",
        machine_element="shaft",
        diameter=12.0,
        length=300.0,
        material="steel",
        units="mm",
        source_design_id="design-test-01"
    )
    assert spec.part_name == "SHAFT_12X300"
    assert spec.diameter == 12.0
    assert spec.length == 300.0
    assert spec.material == "steel"
    assert spec.units == "mm"


def test_missing_diameter_blocks_generation():
    """Missing or None diameter in specification raises ValueError."""
    backend = OpenCascadeBackend()
    spec = CADSpecification(part_name="SHAFT_NODIA", length=300.0, diameter=None)
    with pytest.raises(ValueError, match="strictly positive diameter"):
        backend.generate_part(spec)


def test_missing_length_blocks_generation():
    """Missing length in DesignResult does not invent a length; returns BLOCKED."""
    # Create DesignResult without length
    designer = ShaftDesigner()
    req = ShaftDesignRequirements(
        power=5.0,
        speed_rpm=1500.0,
        yield_strength=355.0,
        design_factor=2.0
        # length omitted
    )
    res = designer.design(req)

    # Attempt CAD spec build without length
    spec, status, missing = build_shaft_cad_specification(res)
    assert status == CADStatus.BLOCKED
    assert spec is None
    assert any(m.field == "shaft_length" for m in missing)


def test_invalid_diameter_and_length_rejected():
    """Non-positive dimensions raise ValueError."""
    with pytest.raises(ValueError, match="strictly positive"):
        BRepSolidCylinder(diameter_mm=-5.0, length_mm=300.0)

    with pytest.raises(ValueError, match="strictly positive"):
        BRepSolidCylinder(diameter_mm=12.0, length_mm=0.0)


def test_generic_steel_remains_generic():
    """Generic steel material is preserved without fabricating alloy grades."""
    designer = ShaftDesigner()
    req = ShaftDesignRequirements(
        power=5.0,
        speed_rpm=1500.0,
        yield_strength=355.0,
        design_factor=2.0,
        material="steel"
    )
    res = designer.design(req)
    spec, status, _ = build_shaft_cad_specification(res, extra_inputs={"length": 300.0})

    assert status == CADStatus.READY
    assert spec.material == "steel"
    assert spec.material_grade is None


# ==============================================================================
# 2. 3D BRep Solid Geometry & Topological Validation
# ==============================================================================

def test_solid_shaft_12x300_generated():
    """Generates 12 mm x 300 mm cylinder and validates analytical volume and bbox."""
    solid = BRepSolidCylinder(diameter_mm=12.0, length_mm=300.0)
    val = solid.validate()

    assert val.is_valid is True
    # V = pi * r^2 * L = pi * 6^2 * 300 = 33929.20 mm^3
    expected_vol = math.pi * (6.0 ** 2) * 300.0
    assert solid.theoretical_volume_mm3 == pytest.approx(expected_vol, rel=1e-4)
    assert val.calculated_volume == pytest.approx(expected_vol, rel=1e-4)

    # Check bounding box
    bbox = solid.bounding_box
    assert bbox["dx"] == 300.0
    assert bbox["dy"] == 12.0
    assert bbox["dz"] == 12.0
    assert val.dimensional_checks["length_matches_bbox"] is True


def test_parametric_regeneration():
    """Modifying diameter or length regenerates distinct solid geometry."""
    solid1 = BRepSolidCylinder(diameter_mm=12.0, length_mm=300.0)
    solid2 = BRepSolidCylinder(diameter_mm=15.0, length_mm=350.0)

    assert solid1.bounding_box["dy"] == 12.0
    assert solid2.bounding_box["dy"] == 15.0
    assert solid1.bounding_box["dx"] == 300.0
    assert solid2.bounding_box["dx"] == 350.0
    assert solid2.theoretical_volume_mm3 > solid1.theoretical_volume_mm3


# ==============================================================================
# 3. STEP Export & Exchange Verification
# ==============================================================================

def test_step_export_succeeds(tmp_path):
    """Exports valid ISO-10303-21 STEP exchange file to disk."""
    backend = OpenCascadeBackend()
    solid = BRepSolidCylinder(diameter_mm=12.0, length_mm=300.0)
    step_path = str(tmp_path / "shaft_12x300.stp")

    artifact = backend.export_step(
        solid=solid,
        file_path=step_path,
        metadata={"part_name": "SHAFT_12X300", "source_design_id": "des-test-99"}
    )

    assert artifact.format == "step"
    assert artifact.status == CADStatus.GENERATED
    assert os.path.exists(step_path)
    assert artifact.file_size_bytes > 0


def test_step_artifact_valid_and_non_empty(tmp_path):
    """Verifies STEP file syntax conforms to ISO-10303-21 with valid header and data."""
    backend = OpenCascadeBackend()
    solid = BRepSolidCylinder(diameter_mm=12.0, length_mm=300.0)
    step_path = str(tmp_path / "shaft_check.stp")

    backend.export_step(solid, step_path, {"part_name": "SHAFT_CHECK", "source_design_id": "des-check"})

    with open(step_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "ISO-10303-21;" in content
    assert "HEADER;" in content
    assert "FILE_SCHEMA" in content
    assert "DATA;" in content
    assert "CYLINDRICAL_SURFACE" in content or "BRep" in content
    assert "END-ISO-10303-21;" in content
    assert "des-check" in content


# ==============================================================================
# 4. 2D Drawing Derivation from 3D BRep
# ==============================================================================

def test_drawing_document_derived_from_brep():
    """Derives structured DrawingDocument from 3D BRep solid with orthographic views."""
    backend = OpenCascadeBackend()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0, material="steel")
    solid = backend.generate_part(spec)
    doc = backend.derive_drawing_geometry(solid, spec)

    assert doc.part_name == "SHAFT_12X300"
    assert len(doc.views) == 2
    view_types = [v.view_type for v in doc.views]
    assert "front_orthographic" in view_types
    assert "end_view" in view_types

    assert doc.title_block.material == "steel"
    assert doc.title_block.title == "SHAFT_12X300"


def test_drawing_dimensions_equal_cad_parameters():
    """Verifies that derived drawing dimensions identically equal 3D CAD dimensions."""
    backend = OpenCascadeBackend()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0)
    solid = backend.generate_part(spec)
    doc = backend.derive_drawing_geometry(solid, spec)

    dia_dim = next(d for d in doc.dimensions if d.source_parameter == "shaft.diameter")
    len_dim = next(d for d in doc.dimensions if d.source_parameter == "shaft.length")

    assert dia_dim.value == 12.0
    assert len_dim.value == 300.0


def test_centerline_generated():
    """Centerlines are generated for both front elevation and circular end view."""
    backend = OpenCascadeBackend()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0)
    solid = backend.generate_part(spec)
    doc = backend.derive_drawing_geometry(solid, spec)

    front_view = next(v for v in doc.views if v.view_type == "front_orthographic")
    end_view = next(v for v in doc.views if v.view_type == "end_view")

    assert len(front_view.centerlines) >= 1
    assert len(end_view.centerlines) >= 2  # Horizontal and vertical cross-centerlines


# ==============================================================================
# 5. Engineering SVG Rendering Tests
# ==============================================================================

def test_svg_generated_with_technical_layout(tmp_path):
    """Renders DrawingDocument into standards-compliant technical drawing SVG."""
    backend = OpenCascadeBackend()
    exporter = DrawingExporter()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0, material="steel")
    solid = backend.generate_part(spec)
    doc = backend.derive_drawing_geometry(solid, spec)

    svg_path = str(tmp_path / "drawing_test.svg")
    art = exporter.export_svg(doc, svg_path)

    assert art.format == "svg"
    assert os.path.exists(svg_path)
    assert art.file_size_bytes > 0

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    assert "<svg" in svg_content
    assert "</svg>" in svg_content
    assert "title_block" in svg_content
    assert "SHAFT_12X300" in svg_content


def test_svg_contains_visual_dimension_callouts_and_semantic_data(tmp_path):
    """Verifies visual dimension text (Ø12, 300) and semantic data-* attributes."""
    backend = OpenCascadeBackend()
    exporter = DrawingExporter()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0)
    solid = backend.generate_part(spec)
    doc = backend.derive_drawing_geometry(solid, spec)

    svg_path = str(tmp_path / "svg_meta.svg")
    exporter.export_svg(doc, svg_path)

    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    # Visual dimension callouts
    assert "Ø12" in svg_content
    assert "300" in svg_content

    # Semantic engineering attributes
    assert 'data-feature-type="shaft"' in svg_content
    assert 'data-source-parameter="shaft.diameter"' in svg_content
    assert 'data-source-parameter="shaft.length"' in svg_content
    assert 'data-value="12.0"' in svg_content or 'data-value="12"' in svg_content
    assert 'data-value="300.0"' in svg_content or 'data-value="300"' in svg_content


# ==============================================================================
# 6. Dimensional Cross-Validation Tests
# ==============================================================================

def test_cad_drawing_mismatch_detection(tmp_path):
    """Detects and flags dimensional discrepancies between CAD specification and drawing."""
    gen = CADGenerator()
    spec = CADSpecification(part_name="SHAFT_12X300", diameter=12.0, length=300.0)
    solid = gen.backend.generate_part(spec)
    doc = gen.backend.derive_drawing_geometry(solid, spec)

    # Mutate drawing dimension to create a simulated tampering mismatch
    for dim in doc.dimensions:
        if dim.source_parameter == "shaft.diameter":
            dim.value = 15.0  # Mismatch!

    cross = gen._cross_validate_dimensions(spec, doc)
    assert cross["all_match"] is False
    assert cross["diameter_matches"]["match"] is False
    assert cross["diameter_matches"]["delta_mm"] == pytest.approx(3.0)


# ==============================================================================
# 7. Traceability & Engineering Handoff Tests
# ==============================================================================

def test_engineering_handoff_traceability(tmp_path):
    """Verifies EngineeringHandoff links specification, CAD, drawing, and validation."""
    gen = CADGenerator()
    spec = CADSpecification(
        part_name="SHAFT_12X300",
        diameter=12.0,
        length=300.0,
        source_design_id="design-handoff-01"
    )
    resp = gen.generate(spec, output_dir=str(tmp_path))

    handoff = create_engineering_handoff_package(
        cad_specification=spec,
        cad_artifacts=resp.artifacts,
        drawing_document=resp.drawing_document,
        validation_result=resp.validation
    )

    assert handoff.handoff_id.startswith("handoff-")
    assert handoff.machine_element == "shaft"
    assert "shaft_diameter" in handoff.traceability_matrix["parameters"]
    assert handoff.validation_summary["brep_valid"] is True
    assert handoff.validation_summary["step_artifact_present"] is True
    assert handoff.validation_summary["svg_artifact_present"] is True


def test_unsupported_machine_element_blocked(tmp_path):
    """Unsupported elements return BLOCKED status cleanly."""
    gen = CADGenerator()
    spec = CADSpecification(
        part_name="SPUR_GEAR_01",
        machine_element="gear",
        diameter=50.0,
        length=20.0
    )
    resp = gen.generate(spec, output_dir=str(tmp_path))
    assert resp.status == CADStatus.BLOCKED
    assert any("not currently supported" in w for w in resp.warnings)


# ==============================================================================
# 8. Primary Acceptance Benchmark Case
# ==============================================================================

def test_acceptance_case_5kw_1500rpm_shaft(tmp_path):
    """
    Problem: 'Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.'
    Inputs: yield_strength = 355 MPa, design_factor = 2, length = 300 mm.
    1. Slice 12 selects diameter = 12 mm.
    2. CAD generator produces 12 x 300 mm solid geometry.
    3. Exports STEP file.
    4. Derives 2D drawing.
    5. Exports SVG.
    6. Verifies dimensions, centerline, generic steel, and cross-validation agreement.
    """
    problem = "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2."
    extra_inputs = {
        "yield_strength": 355.0,
        "design_factor": 2.0,
        "length": 300.0
    }

    gen = CADGenerator()
    resp = gen.generate_from_problem_statement(
        problem_statement=problem,
        extra_inputs=extra_inputs,
        output_dir=str(tmp_path)
    )

    assert resp.status == CADStatus.GENERATED
    assert resp.cad_specification.diameter == 12.0
    assert resp.cad_specification.length == 300.0
    assert resp.cad_specification.material == "steel"

    # Verify STEP artifact
    step_art = resp.artifacts.get("step")
    assert step_art is not None
    assert os.path.exists(step_art.file_path)
    assert step_art.file_size_bytes > 0

    # Verify SVG artifact
    svg_art = resp.artifacts.get("svg")
    assert svg_art is not None
    assert os.path.exists(svg_art.file_path)
    assert svg_art.file_size_bytes > 0

    # Verify drawing document dimensions
    doc = resp.drawing_document
    dia_dim = next(d for d in doc.dimensions if d.source_parameter == "shaft.diameter")
    len_dim = next(d for d in doc.dimensions if d.source_parameter == "shaft.length")
    assert dia_dim.value == 12.0
    assert len_dim.value == 300.0

    # Verify cross-validation
    assert resp.dimensional_cross_validation["all_match"] is True

    # Verify BRep validation
    assert resp.validation.is_valid is True
    assert resp.validation.bounding_box["dx"] == 300.0
    assert resp.validation.bounding_box["dy"] == 12.0

    # Verify report generated
    assert "# Parametric CAD & Engineering Drawing Report" in resp.report
    assert "SHAFT" in resp.report


# ==============================================================================
# 9. API Endpoint Integration Tests
# ==============================================================================

def test_api_post_design_cad_endpoint():
    """Test POST /design/cad endpoint with FastAPI TestClient."""
    client = TestClient(app)

    payload = {
        "problem_statement": "Design a steel shaft to transmit 5 kW at 1500 RPM.",
        "engineering_inputs": {
            "yield_strength": 355.0,
            "design_factor": 2.0,
            "length": 300.0
        }
    }

    resp = client.post("/design/cad", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "GENERATED"
    assert "cad_specification" in data
    assert data["cad_specification"]["diameter"] == 12.0
    assert data["cad_specification"]["length"] == 300.0
    assert "artifacts" in data
    assert "step" in data["artifacts"]
    assert "svg" in data["artifacts"]
    assert data["dimensional_cross_validation"]["all_match"] is True
    assert "report" in data
