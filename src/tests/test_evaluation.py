import json
import numpy as np
import pytest
from evaluation.models import (
    GroundTruthLine,
    GroundTruthCircle,
    GroundTruthDimension,
    GroundTruthSymbol,
    GroundTruthRelationship,
    GroundTruth,
    EvaluationCase,
    EvaluationResult
)
from evaluation.synthetic import (
    case_horizontal_line,
    case_vertical_line,
    case_diagonal_lines,
    case_parallel_lines,
    case_perpendicular_lines,
    case_hole,
    case_multiple_holes,
    case_mixed_geometry,
    get_all_synthetic_cases
)
from evaluation.metrics import (
    calculate_line_metrics,
    calculate_circle_metrics,
    calculate_orientation_accuracy,
    calculate_relationship_metrics,
    calculate_dimension_metrics,
    calculate_symbol_metrics,
    evaluate_evidence_validity,
    calculate_hallucination_rate
)
from evaluation.runner import EvaluationRunner
from evaluation.report import (
    generate_evaluation_report,
    report_to_json,
    print_evaluation_summary
)


# ---------------------------------------------------------------------------
# 1. Synthetic Case Generation Tests
# ---------------------------------------------------------------------------

def test_synthetic_case_generation():
    cases = get_all_synthetic_cases()
    assert len(cases) == 8
    for case in cases:
        assert isinstance(case, EvaluationCase)
        assert isinstance(case.image, np.ndarray)
        assert case.image.shape == (400, 400, 3)
        assert case.image.dtype == np.uint8
        assert isinstance(case.ground_truth, GroundTruth)


def test_synthetic_case_determinism():
    c1 = case_horizontal_line()
    c2 = case_horizontal_line()
    assert np.array_equal(c1.image, c2.image)
    assert c1.ground_truth == c2.ground_truth


def test_synthetic_ground_truth_properties():
    hole_case = case_hole()
    assert len(hole_case.ground_truth.circles) == 1
    assert hole_case.ground_truth.circles[0].radius == 25.0
    assert len(hole_case.ground_truth.lines) == 4

    multi_hole_case = case_multiple_holes()
    assert len(multi_hole_case.ground_truth.circles) == 3

    perp_case = case_perpendicular_lines()
    assert len(perp_case.ground_truth.relationships) >= 1
    assert perp_case.ground_truth.relationships[0].relationship_type == "perpendicular"


# ---------------------------------------------------------------------------
# 2. Line Metrics Tests
# ---------------------------------------------------------------------------

class DummyLine:
    def __init__(self, x1, y1, x2, y2, angle=0.0, orientation="horizontal"):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.angle_degrees = angle
        self.orientation = orientation


def test_line_metrics_perfect_match():
    gt = [GroundTruthLine(id="l1", x1=50, y1=200, x2=350, y2=200, orientation="horizontal")]
    preds = [DummyLine(50, 200, 350, 200, angle=0.0, orientation="horizontal")]

    score = calculate_line_metrics(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0
    assert score.true_positives == 1
    assert score.false_positives == 0
    assert score.false_negatives == 0


def test_line_metrics_reverse_endpoints_match():
    # Endpoints reversed (350, 200) -> (50, 200)
    gt = [GroundTruthLine(id="l1", x1=50, y1=200, x2=350, y2=200, orientation="horizontal")]
    preds = [DummyLine(350, 200, 50, 200, angle=180.0, orientation="horizontal")]

    score = calculate_line_metrics(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_line_metrics_partial_match():
    gt = [
        GroundTruthLine(id="l1", x1=50, y1=100, x2=350, y2=100, orientation="horizontal"),
        GroundTruthLine(id="l2", x1=50, y1=200, x2=350, y2=200, orientation="horizontal")
    ]
    # 1 true positive, 1 false positive
    preds = [
        DummyLine(50, 100, 350, 100, angle=0.0),
        DummyLine(50, 300, 350, 300, angle=0.0)
    ]

    score = calculate_line_metrics(preds, gt)
    assert score.true_positives == 1
    assert score.false_positives == 1
    assert score.false_negatives == 1
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1 == 0.5


def test_line_metrics_empty_cases():
    # Empty predictions & empty ground truth -> Perfect agreement
    score = calculate_line_metrics([], [])
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0

    # Empty predictions with ground truth present
    gt = [GroundTruthLine(id="l1", x1=50, y1=200, x2=350, y2=200, orientation="horizontal")]
    score = calculate_line_metrics([], gt)
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.false_negatives == 1

    # Empty ground truth with predictions present
    preds = [DummyLine(50, 200, 350, 200)]
    score = calculate_line_metrics(preds, [])
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.false_positives == 1


# ---------------------------------------------------------------------------
# 3. Circle Metrics Tests
# ---------------------------------------------------------------------------

class DummyCircle:
    def __init__(self, cx, cy, r):
        self.center_x = cx
        self.center_y = cy
        self.radius = r


def test_circle_metrics_perfect_match():
    gt = [GroundTruthCircle(id="c1", center_x=200, center_y=200, radius=25)]
    preds = [DummyCircle(200, 200, 25)]

    score = calculate_circle_metrics(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_circle_metrics_tolerance_mismatch():
    gt = [GroundTruthCircle(id="c1", center_x=200, center_y=200, radius=25)]
    # Center distance is 50px away (> 15px tolerance)
    preds = [DummyCircle(250, 200, 25)]

    score = calculate_circle_metrics(preds, gt)
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.true_positives == 0
    assert score.false_positives == 1
    assert score.false_negatives == 1


def test_circle_metrics_empty():
    score = calculate_circle_metrics([], [])
    assert score.precision == 1.0
    assert score.recall == 1.0


# ---------------------------------------------------------------------------
# 4. Orientation Accuracy Tests
# ---------------------------------------------------------------------------

def test_orientation_accuracy():
    gt = [
        GroundTruthLine(id="l1", x1=50, y1=100, x2=350, y2=100, orientation="horizontal"),
        GroundTruthLine(id="l2", x1=200, y1=50, x2=200, y2=350, orientation="vertical")
    ]
    # One correct orientation ("horizontal"), one wrong ("diagonal" instead of "vertical")
    preds = [
        DummyLine(50, 100, 350, 100, orientation="horizontal"),
        DummyLine(200, 50, 200, 350, orientation="diagonal")
    ]

    acc = calculate_orientation_accuracy(preds, gt)
    assert acc == 0.5


# ---------------------------------------------------------------------------
# 5. Relationship Metrics Tests
# ---------------------------------------------------------------------------

class DummyRelationship:
    def __init__(self, src, tgt, rel_type):
        self.source_id = src
        self.target_id = tgt
        self.relationship_type = rel_type


def test_relationship_metrics():
    gt = [
        GroundTruthRelationship(source_id="line_0", target_id="line_1", relationship_type="parallel")
    ]
    # Symmetric match: line_1 -> line_0 is equivalent to line_0 -> line_1
    preds = [
        DummyRelationship("line_1", "line_0", "parallel")
    ]
    score = calculate_relationship_metrics(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


# ---------------------------------------------------------------------------
# 6. Annotation Metrics Tests
# ---------------------------------------------------------------------------

class DummyDimension:
    def __init__(self, val, dim_type, unit=None):
        self.value = val
        self.dimension_type = dim_type
        self.unit = unit


class DummySymbol:
    def __init__(self, sym_type, text=""):
        self.symbol_type = sym_type
        self.text = text


def test_dimension_metrics():
    gt = [
        GroundTruthDimension(id="d1", raw_text="Ø20", value=20.0, dimension_type="diameter", unit=None)
    ]
    # Value match within tolerance
    preds = [
        DummyDimension(20.2, "diameter", None)
    ]
    score = calculate_dimension_metrics(preds, gt, value_tolerance=0.5)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0

    # Wrong dimension type
    preds_wrong = [DummyDimension(20.0, "linear", None)]
    score_wrong = calculate_dimension_metrics(preds_wrong, gt)
    assert score_wrong.f1 == 0.0


def test_symbol_metrics():
    gt = [GroundTruthSymbol(id="s1", symbol_type="diameter", text="Ø")]
    preds = [DummySymbol("diameter", "Ø")]

    score = calculate_symbol_metrics(preds, gt)
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


# ---------------------------------------------------------------------------
# 7. Reasoning Evidence Evaluation Tests
# ---------------------------------------------------------------------------

def test_evidence_validity():
    available = {"line_0", "line_1", "circle_0", "dim_1"}
    cited = ["line_0", "circle_0", "nonexistent_99"]

    eval_res = evaluate_evidence_validity(cited, available)
    assert eval_res["valid_count"] == 2
    assert eval_res["invalid_count"] == 1
    assert eval_res["validity_rate"] == round(2 / 3, 4)
    assert "nonexistent_99" in eval_res["invalid_ids"]


def test_hallucination_rate():
    available = {"circle_0"}
    assert calculate_hallucination_rate(["circle_0"], available) == 0.0
    assert calculate_hallucination_rate(["ghost_1"], available) == 1.0
    assert calculate_hallucination_rate([], available) == 0.0


# ---------------------------------------------------------------------------
# 8. Evaluation Runner & Report Generation Tests
# ---------------------------------------------------------------------------

def test_evaluation_runner_single_case():
    case = case_horizontal_line()
    runner = EvaluationRunner(cases=[case])
    res = runner.evaluate_case(case)

    assert isinstance(res, EvaluationResult)
    assert res.case_id == "case_horizontal_line"
    assert "lines" in res.metrics
    assert res.metrics["lines"]["recall"] > 0.0  # Horizontal line should be detected


def test_evaluation_runner_all_cases():
    cases = get_all_synthetic_cases()
    runner = EvaluationRunner(cases=cases)
    results = runner.run_all()

    assert len(results) == len(cases)
    for res in results:
        assert isinstance(res, EvaluationResult)
        assert "lines" in res.metrics
        assert "circles" in res.metrics


def test_completely_incorrect_predictions():
    # Completely wrong line predictions far from ground truth
    gt = [GroundTruthLine(id="l1", x1=10, y1=10, x2=50, y2=10, orientation="horizontal")]
    preds = [DummyLine(300, 300, 350, 300, angle=0.0)]

    score = calculate_line_metrics(preds, gt)
    assert score.true_positives == 0
    assert score.false_positives == 1
    assert score.false_negatives == 1
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.f1 == 0.0


def test_evaluation_report_generation():
    case1 = case_horizontal_line()
    case2 = case_hole()
    runner = EvaluationRunner(cases=[case1, case2])
    results = runner.run_all()

    report = generate_evaluation_report(results)
    assert report.total_cases == 2
    assert "geometry" in report.aggregate_metrics
    assert "lines" in report.aggregate_metrics["geometry"]
    assert "circles" in report.aggregate_metrics["geometry"]

    json_str = report_to_json(report)
    parsed = json.loads(json_str)
    assert parsed["total_cases"] == 2

    text_summary = print_evaluation_summary(report)
    assert "Evaluation completed" in text_summary
    assert "Cases: 2" in text_summary
