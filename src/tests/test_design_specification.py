"""
Comprehensive unit and integration test suite for Slice 11:
Engineering Specification & Design Problem Interpreter.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

from design import (
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
    DerivedEngineeringValue,
    DesignSpecificationExtractor,
    MockDesignSpecificationProvider,
    DerivationEngine,
    PowerSpeedToTorqueRule,
    normalize_power,
    normalize_rotational_speed,
    extract_specification,
    plan_analyses_for_specification,
    generate_design_specification_report
)
from analysis.models import AnalysisType, AnalysisStatus


# ==============================================================================
# 1. Model Tests
# ==============================================================================

def test_model_valid_specification():
    """Verify clean instantiation of EngineeringSpecification with structured sub-models."""
    spec = EngineeringSpecification(
        specification_id="spec-test-001",
        problem_statement="Design a transmission shaft for 5 kW at 1500 RPM.",
        machine_element="shaft",
        operating_conditions=[
            OperatingCondition(parameter="power", value=5.0, unit="kW", normalized_value=5000.0, normalized_unit="W"),
            OperatingCondition(parameter="speed", value=1500.0, unit="RPM", normalized_value=1500.0, normalized_unit="RPM")
        ],
        geometry_requirements=[
            EngineeringQuantity(value=25.0, unit="mm", normalized_value=0.025, normalized_unit="m", evidence_id="diameter")
        ],
        material_requirements=MaterialRequirement(material_name="steel", material_grade="AISI 1045"),
        load_requirements=[
            LoadRequirement(load_type="torque", magnitude=EngineeringQuantity(value=31.83, unit="N*m"))
        ],
        design_constraints=[
            DesignConstraint(constraint_type="min_safety_factor", value=2.0, priority=ConstraintPriority.HIGH)
        ]
    )

    assert spec.specification_id == "spec-test-001"
    assert spec.machine_element == "shaft"
    assert len(spec.operating_conditions) == 2
    assert spec.material_requirements.material_grade == "AISI 1045"
    assert spec.requires_human_review is False


def test_model_optional_fields():
    """Verify minimal specification with only problem statement and defaults."""
    spec = EngineeringSpecification(
        specification_id="spec-min-001",
        problem_statement="Generic machine element inquiry."
    )
    assert spec.machine_element is None
    assert spec.material_requirements is None
    assert len(spec.operating_conditions) == 0
    assert len(spec.derived_values) == 0
    assert len(spec.missing_information) == 0
    assert len(spec.conflicts) == 0


def test_model_conflicts_and_human_review():
    """Verify conflict structure triggers requires_human_review flag."""
    conflict = RequirementConflict(
        conflict_id="conf-01",
        field="speed",
        description="Conflicting operational speeds specified.",
        affected_requirements=["speed_low", "speed_high"],
        requires_human_review=True
    )
    spec = EngineeringSpecification(
        specification_id="spec-conf-001",
        problem_statement="Problem with contradictory requirements.",
        conflicts=[conflict],
        requires_human_review=True
    )
    assert len(spec.conflicts) == 1
    assert spec.requires_human_review is True


# ==============================================================================
# 2. Normalization Tests
# ==============================================================================

def test_normalize_power_units():
    """Verify deterministic conversion of kW, W, and hp to Watts."""
    w, unit, factor = normalize_power(5.0, "kW")
    assert w == 5000.0
    assert unit == "W"
    assert factor == 1000.0

    w_w, _, _ = normalize_power(250.0, "W")
    assert w_w == 250.0

    w_hp, _, _ = normalize_power(10.0, "hp")
    assert w_hp == pytest.approx(7456.998, rel=1e-3)

    with pytest.raises(ValueError, match="Unsupported power unit"):
        normalize_power(10.0, "parsec")


def test_normalize_rotational_speed_units():
    """Verify deterministic conversion of RPM and rad/s."""
    rpm, u_rpm, rad_s, u_rad = normalize_rotational_speed(1500.0, "RPM")
    assert rpm == 1500.0
    assert u_rpm == "RPM"
    assert rad_s == pytest.approx(157.0796, rel=1e-4)
    assert u_rad == "rad/s"

    # Input given directly in rad/s
    rpm_from_rad, _, rad_s2, _ = normalize_rotational_speed(157.0796, "rad/s")
    assert rpm_from_rad == pytest.approx(1500.0, rel=1e-3)
    assert rad_s2 == pytest.approx(157.0796, rel=1e-3)

    with pytest.raises(ValueError, match="Unsupported rotational speed unit"):
        normalize_rotational_speed(100.0, "gallons")


# ==============================================================================
# 3. Deterministic Derivation Tests
# ==============================================================================

def test_derivation_power_speed_to_torque_benchmark():
    """Verify 5 kW at 1500 RPM deterministically calculates T = 31.83 N*m."""
    rule = PowerSpeedToTorqueRule()
    context = {"power": 5.0, "power_unit": "kW", "speed": 1500.0, "speed_unit": "RPM"}

    assert rule.can_derive(context) is True
    res = rule.derive(context)

    assert res is not None
    assert res.name == "torque"
    assert res.output_unit == "N*m"
    # T = 5000 / (2 * pi * 1500 / 60) = 5000 / 157.0796327 = 31.8309886 N*m
    assert res.output_value == pytest.approx(31.831, rel=1e-3)
    assert "T = P / omega" in res.formula
    assert len(res.calculation_steps) == 3
    assert res.provenance == "derived_calculation"
    assert len(res.assumptions) >= 1


def test_derivation_missing_or_invalid_inputs():
    """Derivation safely aborts or rejects missing/non-positive inputs."""
    rule = PowerSpeedToTorqueRule()

    # Missing speed
    assert rule.can_derive({"power": 5.0}) is False

    # Missing power
    assert rule.can_derive({"speed": 1500.0}) is False

    # Non-positive power
    with pytest.raises(ValueError, match="strictly positive"):
        rule.derive({"power": -5.0, "speed": 1500.0})

    # Non-positive speed
    with pytest.raises(ValueError, match="strictly positive"):
        rule.derive({"power": 5.0, "speed": 0.0})


# ==============================================================================
# 4. Natural Language Extraction Tests
# ==============================================================================

def test_extract_shaft_problem():
    """Primary benchmark: 'Design a steel shaft to transmit 5 kW at 1500 RPM.'"""
    statement = "Design a steel shaft to transmit 5 kW at 1500 RPM."
    spec = extract_specification(statement)

    assert spec.machine_element == "shaft"
    assert spec.material_requirements is not None
    assert spec.material_requirements.material_name == "steel"
    assert spec.material_requirements.material_grade is None  # Not fabricated!

    # Verify operating conditions extracted
    p_op = next((op for op in spec.operating_conditions if op.parameter == "power"), None)
    assert p_op is not None
    assert p_op.value == 5.0
    assert p_op.unit == "kW"
    assert p_op.normalized_value == 5000.0

    s_op = next((op for op in spec.operating_conditions if op.parameter == "rotational_speed"), None)
    assert s_op is not None
    assert s_op.value == 1500.0
    assert s_op.unit == "RPM"

    # Verify deterministic torque derivation
    t_dv = next((dv for dv in spec.derived_values if dv.name == "torque"), None)
    assert t_dv is not None
    assert t_dv.output_value == pytest.approx(31.831, rel=1e-3)
    assert t_dv.output_unit == "N*m"

    # Verify missing information identified
    missing_fields = [m.field for m in spec.missing_information]
    assert "shaft_diameter" in missing_fields
    assert "shaft_length" in missing_fields
    assert "support_arrangement" in missing_fields
    assert "material_grade" in missing_fields

    # Verify diameter blocks analysis, length does not
    dia_m = next(m for m in spec.missing_information if m.field == "shaft_diameter")
    assert dia_m.blocks_analysis is True
    assert dia_m.importance == MissingImportance.REQUIRED_FOR_ANALYSIS

    len_m = next(m for m in spec.missing_information if m.field == "shaft_length")
    assert len_m.blocks_analysis is False


def test_extract_bolted_joint_problem():
    """Verify extraction for bolted joint connection."""
    statement = "Check bolted connection with M16 bolts under 40 kN tensile load."
    spec = extract_specification(statement)

    assert spec.machine_element == "bolted_joint"

    # M16 recognized as bolt diameter 16 mm
    assert any(g.value == 16.0 and g.unit == "mm" for g in spec.geometry_requirements)

    # 40 kN tensile load recognized
    assert any(l.load_type == "axial_tension" and l.magnitude.value == 40.0 and l.magnitude.unit == "KN" for l in spec.load_requirements)

    # Missing info checks
    missing_fields = [m.field for m in spec.missing_information]
    assert "bolt_grade" in missing_fields


def test_extract_beam_problem():
    """Verify extraction for beam problem."""
    statement = "Analyze a steel I-beam with 10 kN central point load over 3 m span."
    spec = extract_specification(statement)

    assert spec.machine_element == "beam"
    assert any(g.value == 3.0 and g.unit == "m" for g in spec.geometry_requirements)


def test_extract_unknown_machine_element():
    """Unrecognized machine element must be safely classified as unknown."""
    statement = "Optimize vibration damping for widget X7."
    spec = extract_specification(statement)

    assert spec.machine_element == "unknown"


def test_extract_malformed_provider_data():
    """Malformed provider outputs fail safely without crashing."""
    mock_provider = MockDesignSpecificationProvider(canned_data={
        "machine_element": "shaft",
        "power": "invalid_number_here"
    })
    extractor = DesignSpecificationExtractor(provider=mock_provider)

    with pytest.raises(Exception):
        extractor.extract("Some statement")


# ==============================================================================
# 5. Provenance & Assumption Tracking Tests
# ==============================================================================

def test_provenance_and_no_fabricated_grades():
    """Generic material name must not fabricate a specific numerical grade."""
    spec = extract_specification("Design a steel shaft to transmit 5 kW at 1500 RPM.")

    assert spec.material_requirements.material_name == "steel"
    assert spec.material_requirements.material_grade is None

    # Assumption recorded
    assert any("generic 'steel'" in a for a in spec.assumptions)

    # Derived torque has explicit provenance
    torque_load = next(l for l in spec.load_requirements if l.load_type == "torque")
    assert torque_load.source == "derived_calculation"
    assert torque_load.magnitude.source == "derived_calculation"


# ==============================================================================
# 6. Analysis Planner Bridge Integration Tests
# ==============================================================================

def test_planner_integration_shaft_problem():
    """
    5 kW @ 1500 RPM shaft problem derives torque -> activates shaft torsion.
    Absence of bending information leaves shaft bending absent/blocked.
    """
    spec = extract_specification("Design a steel shaft to transmit 5 kW at 1500 RPM.")
    plan = plan_analyses_for_specification(spec)

    assert plan is not None
    # Shaft torsion must be scheduled
    torsion_item = next((it for it in plan.items if it.analysis_type == AnalysisType.TORSION), None)
    assert torsion_item is not None

    # Status must be MISSING_INPUTS because shaft diameter was not specified
    assert torsion_item.status == AnalysisStatus.MISSING_INPUTS
    assert "shaft_diameter" in torsion_item.missing_calculation_inputs

    # Shaft bending must NOT be automatically scheduled because no bending loads exist
    bending_item = next((it for it in plan.items if it.analysis_type == AnalysisType.BENDING), None)
    assert bending_item is None


def test_planner_integration_shaft_with_supplied_diameter():
    """Supplied diameter marks shaft torsion calculation as READY."""
    spec = extract_specification(
        "Design a steel shaft to transmit 5 kW at 1500 RPM.",
        structured_inputs={"shaft_diameter": 25.0}
    )
    plan = plan_analyses_for_specification(spec)

    torsion_item = next(it for it in plan.items if it.analysis_type == AnalysisType.TORSION)
    assert torsion_item.status == AnalysisStatus.READY
    assert AnalysisType.TORSION in plan.ready_analyses


def test_planner_integration_explicit_requested_analyses():
    """Explicitly requested analyses in planning request are honored."""
    from analysis.models import AnalysisPlanningRequest

    spec = extract_specification("Design a steel shaft to transmit 5 kW at 1500 RPM.")
    req = AnalysisPlanningRequest(requested_analyses=[AnalysisType.FATIGUE])
    plan = plan_analyses_for_specification(spec, request=req)

    assert any(it.analysis_type == AnalysisType.FATIGUE for it in plan.items)


# ==============================================================================
# 7. Validation & Conflict Detection Tests
# ==============================================================================

def test_validation_contradictory_constraints():
    """Contradictory constraints (min_diameter > max_diameter) trigger conflict and review."""
    mock_provider = MockDesignSpecificationProvider(canned_data={
        "machine_element": "shaft",
        "constraints": [
            {"constraint_type": "min_diameter", "value": 50.0, "priority": "high"},
            {"constraint_type": "max_diameter", "value": 30.0, "priority": "high"}
        ]
    })
    extractor = DesignSpecificationExtractor(provider=mock_provider)
    spec = extractor.extract("Design a shaft with min diameter 50 mm and max diameter 30 mm.")

    assert len(spec.conflicts) >= 1
    assert spec.requires_human_review is True
    assert "diameter_constraints" in spec.conflicts[0].field


# ==============================================================================
# 8. Report Generation Tests
# ==============================================================================

def test_report_generation():
    """Deterministic markdown report renders knowns, derivations, gaps, and review flags."""
    spec = extract_specification("Design a steel shaft to transmit 5 kW at 1500 RPM.")
    plan = plan_analyses_for_specification(spec)
    report = generate_design_specification_report(spec, plan)

    assert "# Engineering Specification Report" in report
    assert "SHAFT" in report
    assert "5 kW" in report
    assert "1500 RPM" in report
    assert "TORQUE" in report
    assert "31.83" in report
    assert "Missing Information" in report
    assert "shaft_diameter" in report


# ==============================================================================
# 9. API Endpoint Integration Tests
# ==============================================================================

def test_api_design_specification_endpoint():
    """Test POST /design/specification HTTP endpoint with FastAPI TestClient."""
    client = TestClient(app)

    payload = {
        "problem_statement": "Design a steel shaft to transmit 5 kW at 1500 RPM.",
        "engineering_inputs": {"shaft_diameter": 25.0}
    }

    resp = client.post("/design/specification", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "specification" in data
    assert "derived_values" in data
    assert "missing_information" in data
    assert "analysis_plan" in data
    assert "report" in data

    spec_data = data["specification"]
    assert spec_data["machine_element"] == "shaft"

    # Derived torque
    derived = data["derived_values"]
    assert len(derived) >= 1
    assert derived[0]["name"] == "torque"
    assert derived[0]["output_value"] == pytest.approx(31.831, rel=1e-3)

    # Analysis plan
    plan_data = data["analysis_plan"]
    assert "ready_analyses" in plan_data
    assert "torsion" in plan_data["ready_analyses"]
