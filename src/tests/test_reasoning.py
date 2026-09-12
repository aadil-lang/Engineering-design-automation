import json
import pytest
from fastapi.testclient import TestClient
from api.main import app

from core.models import (
    AnalyzeResponse,
    ImageMetadata,
    Line,
    Circle,
    Contour,
    LineFeature,
    CircleFeature,
    LineOrientation,
    GeometricRelationship,
    RelationshipType,
    BoundingInformation,
    EngineeringFeatures
)
from annotations.models import (
    AnnotationsResult,
    OCRResult,
    Dimension,
    DimensionType,
    Tolerance,
    EngineeringSymbol,
    SymbolType,
    GeometryAssociation,
    AssociationType
)
from reasoning.models import (
    QuestionType,
    ReasoningRequest,
    ReasoningResponse,
    FactItem,
    InferenceItem,
    UncertaintyItem,
    ConfidenceScore
)
from reasoning.context import (
    DrawingContext,
    build_drawing_context,
    select_context_for_question,
    drawing_context_to_json
)
from reasoning.router import route_question
from reasoning.prompts import build_reasoning_prompt, GROUNDED_SYSTEM_PROMPT
from reasoning.provider import MockLLMProvider
from reasoning.validation import validate_reasoning_response, extract_valid_entity_ids
from reasoning.reasoner import reason_about_drawing

client = TestClient(app)


@pytest.fixture
def sample_analysis_response() -> AnalyzeResponse:
    """Fixture providing a rich AnalyzeResponse encompassing Slices 1, 2, and 3."""
    line1 = LineFeature(
        id="line_0",
        x1=10.0,
        y1=50.0,
        x2=100.0,
        y2=50.0,
        length=90.0,
        angle_degrees=0.0,
        orientation=LineOrientation.HORIZONTAL
    )
    line2 = LineFeature(
        id="line_1",
        x1=10.0,
        y1=50.0,
        x2=10.0,
        y2=150.0,
        length=100.0,
        angle_degrees=90.0,
        orientation=LineOrientation.VERTICAL
    )
    circle = CircleFeature(
        id="circle_0",
        center_x=50.0,
        center_y=100.0,
        radius=10.0,
        diameter=20.0,
        likely_hole=True,
        confidence=0.85
    )
    rel = GeometricRelationship(
        source_id="line_0",
        target_id="line_1",
        relationship_type=RelationshipType.PERPENDICULAR
    )
    bbox = BoundingInformation(
        bounding_box=(10.0, 50.0, 90.0, 100.0),
        width=90.0,
        height=100.0
    )
    eng_features = EngineeringFeatures(
        line_features=[line1, line2],
        circle_features=[circle],
        relationships=[rel],
        bounding_information=bbox,
        summary={"total_lines": 2, "total_circles": 1}
    )

    ocr = OCRResult(
        id="ocr_1",
        text="Ø20",
        confidence=0.95,
        bounding_box=(45.0, 85.0, 25.0, 12.0)
    )
    dim = Dimension(
        id="dim_1",
        raw_text="Ø20",
        value=20.0,
        dimension_type=DimensionType.DIAMETER,
        confidence=0.95,
        bounding_box=(45.0, 85.0, 25.0, 12.0),
        source_text_id="ocr_1"
    )
    sym = EngineeringSymbol(
        id="sym_1",
        symbol_type=SymbolType.DIAMETER,
        raw_symbol="Ø",
        confidence=0.95,
        source_text_id="ocr_1"
    )
    assoc = GeometryAssociation(
        dimension_id="dim_1",
        feature_id="circle_0",
        association_type=AssociationType.CIRCLE_DIAMETER,
        distance=15.0,
        confidence=0.90,
        metadata={"nominal_diameter_match": True}
    )
    annotations = AnnotationsResult(
        ocr_results=[ocr],
        dimensions=[dim],
        symbols=[sym],
        associations=[assoc],
        summary={"total_dimensions": 1}
    )

    return AnalyzeResponse(
        image=ImageMetadata(width=200, height=200),
        lines=[Line(x1=10, y1=50, x2=100, y2=50, length=90, angle=0)],
        circles=[Circle(center_x=50, center_y=100, radius=10)],
        contours=[],
        engineering_features=eng_features,
        annotations=annotations
    )


# 1. Context Creation & Serialization Tests

def test_drawing_context_creation_and_serialization(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    assert context.image["width"] == 200
    assert len(context.line_features) == 2
    assert len(context.circle_features) == 1
    assert len(context.dimensions) == 1
    assert len(context.associations) == 1

    json_str = drawing_context_to_json(context)
    assert "circle_0" in json_str
    assert "dim_1" in json_str
    # Verify deterministic JSON formatting
    data = json.loads(json_str)
    assert data["image"]["height"] == 200


def test_context_selection_hole_analysis(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    filtered = select_context_for_question(context, QuestionType.HOLE_ANALYSIS)
    assert "circle_features" in filtered
    assert "dimensions" in filtered
    assert "associations" in filtered
    # Unrelated lines should not be prioritized in hole analysis
    assert "line_features" not in filtered


def test_context_selection_dimension_summary(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    filtered = select_context_for_question(context, QuestionType.DIMENSION_SUMMARY)
    assert "dimensions" in filtered
    assert "symbols" in filtered
    assert "circle_features" not in filtered


def test_context_selection_relationship_analysis(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    filtered = select_context_for_question(context, QuestionType.RELATIONSHIP_ANALYSIS)
    assert "line_features" in filtered
    assert "relationships" in filtered
    assert "dimensions" not in filtered


# 2. Question Routing Tests

def test_router_hole_analysis():
    assert route_question("What are the hole diameters?") == QuestionType.HOLE_ANALYSIS
    assert route_question("How many drilled bore holes exist?") == QuestionType.HOLE_ANALYSIS


def test_router_dimension_summary():
    assert route_question("What dimensions are shown on this drawing?") == QuestionType.DIMENSION_SUMMARY
    assert route_question("List all tolerances and nominal values") == QuestionType.DIMENSION_SUMMARY


def test_router_relationship_analysis():
    assert route_question("Which lines are parallel or perpendicular?") == QuestionType.RELATIONSHIP_ANALYSIS
    assert route_question("Are any line features connected?") == QuestionType.RELATIONSHIP_ANALYSIS


def test_router_geometry_summary():
    assert route_question("What is the bounding box of the geometric shape?") == QuestionType.GEOMETRY_SUMMARY
    assert route_question("Summarize the line and circle contours") == QuestionType.GEOMETRY_SUMMARY


def test_router_annotation_summary():
    assert route_question("What text annotations were detected by OCR?") == QuestionType.ANNOTATION_SUMMARY
    assert route_question("List all engineering symbols") == QuestionType.ANNOTATION_SUMMARY


def test_router_general_fallback():
    assert route_question("Is this part ready for CNC milling?") == QuestionType.GENERAL_ENGINEERING_QUESTION
    assert route_question("") == QuestionType.GENERAL_ENGINEERING_QUESTION


# 3. Prompt Construction Tests

def test_prompt_construction(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    sys_prompt, user_prompt = build_reasoning_prompt(
        "What are the hole diameters?",
        context,
        QuestionType.HOLE_ANALYSIS
    )
    assert "GROUNDED EVIDENCE" in sys_prompt
    assert "circle_0" in user_prompt
    assert "dim_1" in user_prompt
    assert "Question Category: hole_analysis" in user_prompt


# 4. Mock LLM Provider Tests

def test_mock_llm_provider_hole_analysis(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    sys_p, user_p = build_reasoning_prompt("What are the hole diameters?", context, QuestionType.HOLE_ANALYSIS)
    provider = MockLLMProvider()
    response_str = provider.generate(sys_p, user_p)
    data = json.loads(response_str)
    assert "hole" in data["answer"].lower()
    assert "circle_0" in data["evidence"]
    assert data["confidence"]["score"] > 0.8


def test_mock_llm_provider_canned_override():
    provider = MockLLMProvider()
    canned = json.dumps({
        "answer": "Test answer",
        "facts": [],
        "inferences": [],
        "uncertainties": [],
        "evidence": [],
        "confidence": {"score": 0.9, "source": "test"}
    })
    provider.set_response(canned)
    assert provider.generate("sys", "user") == canned


# 5. Response Validation Tests

def test_validation_valid_response(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    raw = json.dumps({
        "answer": "There is one hole circle_0 with diameter 20.",
        "facts": [{"statement": "Detected circle_0 diameter is 20.", "evidence": ["circle_0"]}],
        "inferences": [{"statement": "dim_1 applies to circle_0.", "evidence": ["dim_1", "circle_0"]}],
        "uncertainties": [],
        "evidence": ["circle_0", "dim_1"],
        "confidence": {"score": 0.95, "source": "model_heuristic"}
    })
    validated = validate_reasoning_response(raw, context)
    assert validated.metadata["validation_status"] == "passed"
    assert len(validated.facts) == 1
    assert len(validated.inferences) == 1
    assert len(validated.uncertainties) == 0
    assert validated.confidence.source == "validated_grounded_evidence"


def test_validation_nonexistent_evidence_id_demoted(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    # circle_99 and dim_99 DO NOT exist in context
    raw = json.dumps({
        "answer": "Found hole circle_99 with diameter 30.",
        "facts": [{"statement": "Circle circle_99 exists with diameter 30.", "evidence": ["circle_99"]}],
        "inferences": [],
        "uncertainties": [],
        "evidence": ["circle_99"],
        "confidence": {"score": 0.9, "source": "model_heuristic"}
    })
    validated = validate_reasoning_response(raw, context)
    assert validated.metadata["validation_status"] == "unsupported_ids_flagged"
    assert "circle_99" in validated.metadata["unsupported_ids"]
    # Fact citing nonexistent ID must be demoted to uncertainty!
    assert len(validated.facts) == 0
    assert len(validated.uncertainties) == 1
    assert "UNVERIFIED ID circle_99" in validated.uncertainties[0].statement
    # Confidence must be penalized
    assert validated.confidence.score < 0.9
    assert validated.confidence.source == "penalized_unsupported_evidence"


def test_validation_markdown_fence_cleaning(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    raw = """```json
    {
        "answer": "Cleaned response.",
        "facts": [],
        "inferences": [],
        "uncertainties": [],
        "evidence": [],
        "confidence": 0.85
    }
    ```"""
    validated = validate_reasoning_response(raw, context)
    assert validated.answer == "Cleaned response."
    assert validated.confidence.score == 0.85


def test_validation_malformed_json_raises(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    with pytest.raises(ValueError, match="Malformed LLM JSON output"):
        validate_reasoning_response("NOT JSON AT ALL", context)


def test_validation_confidence_clamping(sample_analysis_response):
    context = build_drawing_context(sample_analysis_response)
    raw = json.dumps({
        "answer": "Test answer.",
        "facts": [],
        "inferences": [],
        "uncertainties": [],
        "evidence": [],
        "confidence": 1.5  # invalid > 1.0
    })
    validated = validate_reasoning_response(raw, context)
    assert validated.confidence.score == 1.0


# 6. End-to-end Grounded Reasoning Tests

def test_grounded_reasoning_hole_diameter(sample_analysis_response):
    req = ReasoningRequest(
        question="What is the likely hole diameter?",
        drawing=sample_analysis_response
    )
    res = reason_about_drawing(req)
    assert isinstance(res, ReasoningResponse)
    assert "circle_0" in res.evidence
    assert res.metadata["question_type"] == "hole_analysis"
    assert res.metadata["validation_status"] == "passed"


def test_grounded_reasoning_contradictory_evidence():
    """Test where circle diameter is 20 but annotation states Ø25 (contradiction)."""
    circle = CircleFeature(
        id="circle_0",
        center_x=50.0,
        center_y=100.0,
        radius=10.0,
        diameter=20.0,
        likely_hole=True
    )
    dim = Dimension(
        id="dim_conflict",
        raw_text="Ø25",
        value=25.0,  # Conflict: 25 vs 20
        dimension_type=DimensionType.DIAMETER,
        confidence=0.95,
        bounding_box=(45.0, 85.0, 25.0, 12.0)
    )
    assoc = GeometryAssociation(
        dimension_id="dim_conflict",
        feature_id="circle_0",
        association_type=AssociationType.CIRCLE_DIAMETER,
        distance=15.0,
        confidence=0.70
    )
    analysis = AnalyzeResponse(
        image=ImageMetadata(width=200, height=200),
        lines=[],
        circles=[],
        contours=[],
        engineering_features=EngineeringFeatures(
            line_features=[],
            circle_features=[circle],
            relationships=[],
            bounding_information=BoundingInformation(bounding_box=(0, 0, 200, 200), width=200, height=200),
            summary={}
        ),
        annotations=AnnotationsResult(
            ocr_results=[],
            dimensions=[dim],
            symbols=[],
            associations=[assoc],
            summary={}
        )
    )

    req = ReasoningRequest(question="What are the hole diameters?", drawing=analysis)
    res = reason_about_drawing(req)
    # Must NOT claim certainty; conflict must be exposed in uncertainties!
    assert len(res.uncertainties) > 0
    assert any("conflict" in u.statement.lower() or "differs" in u.statement.lower() for u in res.uncertainties)


def test_reasoning_observability_metadata(sample_analysis_response):
    req = ReasoningRequest(question="Summarize lines and circles", drawing=sample_analysis_response)
    res = reason_about_drawing(req)
    meta = res.metadata
    assert "question_type" in meta
    assert "provider" in meta
    assert "context_counts" in meta
    assert meta["context_counts"]["circles"] == 1
    assert meta["context_counts"]["lines"] == 2
    assert "estimated_prompt_tokens" in meta


# 7. API Route Tests

def test_api_post_reason_success(sample_analysis_response):
    payload = {
        "question": "What are the hole diameters?",
        "drawing": sample_analysis_response.model_dump()
    }
    resp = client.post("/reason", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "facts" in data
    assert "inferences" in data
    assert "uncertainties" in data
    assert "evidence" in data
    assert "confidence" in data
    assert "circle_0" in data["evidence"]


def test_api_post_analyze_and_reason_convenience(synthetic_image_bytes):
    files = {"file": ("part.png", synthetic_image_bytes, "image/png")}
    data = {"question": "What geometric features are in this drawing?"}
    resp = client.post("/analyze-and-reason", files=files, data=data)
    assert resp.status_code == 200
    res_data = resp.json()
    assert "analysis" in res_data
    assert "reasoning" in res_data
    assert "image" in res_data["analysis"]
    assert "answer" in res_data["reasoning"]
