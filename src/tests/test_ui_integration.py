"""
Integration and Presentation Test Suite for Slice 15: Engineering Design Review Interface.
Verifies static asset delivery (/ui, /ui/style.css, /ui/app.js), static artifact serving (/artifacts/...),
and API contract compliance for all review states (SUCCESS, BLOCKED, INVALID, REQUIRES_REVIEW).
"""

import os
import pytest
from fastapi.testclient import TestClient
from api.main import app
from requirements.models import PipelineStatus
from requirements.pipeline import EndToEndPipeline
from cad.generator import CADGenerator
from cad.models import CADStatus


# ==============================================================================
# 1. UI Static Asset Delivery Tests
# ==============================================================================

def test_ui_index_html_served():
    """Verifies that GET /ui returns HTTP 200 with the design review console HTML."""
    client = TestClient(app)
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "MechaAI" in response.text
    assert "Design Review Console" in response.text
    assert "problemStatement" in response.text
    assert "yieldStrength" in response.text
    assert "shaftLength" in response.text
    assert "Preliminary Engineering Design Output" in response.text


def test_ui_css_and_js_served():
    """Verifies that style.css and app.js are served correctly."""
    client = TestClient(app)
    css_res = client.get("/ui/style.css")
    assert css_res.status_code == 200

    js_res = client.get("/ui/app.js")
    assert js_res.status_code == 200
    assert "handleRunDesign" in js_res.text


def test_design_review_redirect():
    """Verifies that /design-review redirects to /ui."""
    client = TestClient(app)
    res = client.get("/design-review", follow_redirects=False)
    assert res.status_code in (307, 302, 301, 308)
    assert res.headers["location"] == "/ui"


# ==============================================================================
# 2. Pipeline API Integration & Status Contract Tests
# ==============================================================================

def test_api_benchmark_successful_payload():
    """
    Test Case 1: Full benchmark execution through API contract.
    Asserts exact values, units, nominal diameter policy, artifacts, and cross-validation agreement.
    """
    client = TestClient(app)
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.",
        "engineering_inputs": {
            "yield_strength_mpa": 355.0,
            "length_mm": 300.0
        }
    }
    res = client.post("/design/pipeline", json=payload)
    assert res.status_code == 200
    data = res.json()

    # 1. Status
    assert data["status"] == "SUCCESS"

    # 2. Spec & Provenance
    assert data["spec"]["power_kw"] == 5.0
    assert data["spec"]["rpm"] == 1500.0
    assert data["spec"]["yield_strength_mpa"] == 355.0
    assert data["spec"]["length_mm"] == 300.0
    assert "yield_strength_mpa" in data["provenance"]

    # 3. Solver Derivations & Policy
    sol = data["solver_result"]
    assert sol["is_valid"] is True
    assert sol["torque_nm"] == pytest.approx(31.831, rel=1e-3)
    assert sol["allowable_stress_mpa"] == pytest.approx(102.48, rel=1e-2)
    assert sol["minimum_required_diameter_mm"] == pytest.approx(11.65, rel=1e-2)
    assert sol["selected_diameter_mm"] == 12.0
    assert sol["diameter_selection_policy"] == "metric_nominal_shaft_series_r20_custom"
    assert sol["achieved_factor_of_safety"] == pytest.approx(2.18, rel=1e-2)
    assert sol["is_safe"] is True

    # 4. Artifacts & Cross Validation
    assert "step" in data["artifacts"]
    assert "svg" in data["artifacts"]
    assert data["cross_validation"]["all_match"] is True

    # 5. Handoff Traceability
    assert data["handoff"]["traceability_matrix"]["parameters"]["shaft_diameter"]["cad_value"] == 12.0
    assert data["handoff"]["traceability_matrix"]["parameters"]["shaft_diameter"]["drawing_dimension"] == 12.0


def test_api_missing_yield_strength_blocked_state():
    """
    Test Case 2: Missing yield strength halts with BLOCKED status and no CAD artifacts.
    """
    client = TestClient(app)
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2 and length 300 mm.",
        "engineering_inputs": {}
    }
    res = client.post("/design/pipeline", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "BLOCKED"
    assert "yield_strength_mpa" in data["missing_information"]
    assert data["solver_result"]["selected_diameter_mm"] is None
    assert data["cad_result"] is None
    assert data["artifacts"] == {}


def test_api_missing_length_blocked_state():
    """
    Test Case 3: Missing shaft length halts with BLOCKED status and no CAD artifacts.
    """
    client = TestClient(app)
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2.",
        "engineering_inputs": {
            "yield_strength_mpa": 355.0
        }
    }
    res = client.post("/design/pipeline", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "BLOCKED"
    assert "length_mm" in data["missing_information"]
    assert data["cad_result"] is None


def test_api_invalid_yield_strength_state():
    """
    Test Case 4: Non-positive yield strength halts with INVALID status and error messages.
    """
    client = TestClient(app)
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2.",
        "engineering_inputs": {
            "yield_strength_mpa": -355.0,
            "length_mm": 300.0
        }
    }
    res = client.post("/design/pipeline", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "INVALID"
    assert len(data["errors"]) > 0
    assert any("yield_strength_mpa" in err for err in data["errors"])
    assert data["cad_result"] is None


# ==============================================================================
# 3. Artifact Serving Route Tests
# ==============================================================================

def test_static_artifact_serving():
    """
    Test Case 8: Verifies that artifacts generated in artifacts/ can be downloaded via /artifacts/...
    """
    client = TestClient(app)
    
    # Run benchmark to ensure artifacts are written to artifacts/
    payload = {
        "problem_statement": "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with FoS 2.",
        "engineering_inputs": {
            "yield_strength_mpa": 355.0,
            "length_mm": 300.0
        }
    }
    res = client.post("/design/pipeline", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Get SVG artifact
    svg_art = data["artifacts"].get("svg")
    assert svg_art is not None
    svg_path = svg_art["file_path"].replace("\\", "/")
    rel_path = svg_path[svg_path.find("artifacts/") + len("artifacts/"):]

    # Fetch through static route
    art_res = client.get(f"/artifacts/{rel_path}")
    assert art_res.status_code == 200
    assert len(art_res.content) > 0
