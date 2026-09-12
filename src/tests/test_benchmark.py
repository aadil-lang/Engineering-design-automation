import os
import json
import subprocess
import pytest
from evaluation.runner import EvaluationRunner
from evaluation.synthetic import get_all_synthetic_cases
from evaluation.report import (
    generate_evaluation_report,
    generate_markdown_report,
    report_to_json,
    print_evaluation_summary,
    derive_error_analysis,
    compare_benchmark_reports
)
from evaluation.run_benchmark import run_benchmark


# ---------------------------------------------------------------------------
# 1. Benchmark Execution & Metrics Tests
# ---------------------------------------------------------------------------

def test_benchmark_execution_all_cases():
    runner = EvaluationRunner()
    cases = get_all_synthetic_cases()
    results = runner.run_all()

    assert len(results) == 8
    assert len(results) == len(cases)

    for r in results:
        assert r.case_id.startswith("case_")
        assert "lines" in r.metrics
        assert "circles" in r.metrics
        assert "relationships" in r.metrics
        assert "dimensions" in r.metrics
        assert "symbols" in r.metrics


def test_aggregate_report_generation():
    runner = EvaluationRunner()
    results = runner.run_all()
    report = generate_evaluation_report(results)

    assert report.total_cases == 8
    geo = report.aggregate_metrics["geometry"]
    assert "lines" in geo
    assert "circles" in geo
    assert geo["lines"]["mean_recall"] == 1.0  # All lines detected
    assert geo["mean_orientation_accuracy"] == 1.0


# ---------------------------------------------------------------------------
# 2. Markdown Report Tests & N/A Handling
# ---------------------------------------------------------------------------

def test_markdown_report_formatting():
    runner = EvaluationRunner()
    results = runner.run_all()
    report = generate_evaluation_report(results)
    md = generate_markdown_report(report)

    # Required sections
    assert "# Mechanical Engineering Drawing Intelligence Evaluation" in md
    assert "## Dataset" in md
    assert "## Aggregate Results" in md
    assert "## Per-Case Results" in md
    assert "## Error Analysis" in md
    assert "## Limitations" in md

    # Check N/A handling in per-case table
    # case_horizontal_line has 0 circles, so Circle F1 should be N/A
    lines = md.split("\n")
    horiz_line = [l for l in lines if "case_horizontal_line" in l]
    assert len(horiz_line) == 1
    assert "N/A" in horiz_line[0]


def test_error_analysis_derivation():
    runner = EvaluationRunner()
    results = runner.run_all()
    errors = derive_error_analysis(results)

    assert len(errors) >= 2
    # Should identify line fragmentation
    assert any("Line Fragmentation" in e for e in errors)
    # Should identify circle corner false positives
    assert any("Corner Sensitivity" in e for e in errors)


# ---------------------------------------------------------------------------
# 3. JSON Report & Determinism Tests
# ---------------------------------------------------------------------------

def test_json_report_structure():
    runner = EvaluationRunner()
    results = runner.run_all()
    report = generate_evaluation_report(results)
    json_str = report_to_json(report, run_id="test_run_1")

    data = json.loads(json_str)
    assert data["run_id"] == "test_run_1"
    assert data["total_cases"] == 8
    assert "matching_tolerances" in data
    assert "aggregate_metrics" in data
    assert len(data["case_results"]) == 8
    assert "error_analysis" in data
    assert "limitations" in data


# ---------------------------------------------------------------------------
# 4. Regression Comparison Tests
# ---------------------------------------------------------------------------

def test_regression_comparison_no_regression():
    curr = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.68},
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            },
            "annotations": {"mean_dimension_f1": 0.0}
        }
    }
    baseline = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.68},
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            },
            "annotations": {"mean_dimension_f1": 0.0}
        }
    }
    comp = compare_benchmark_reports(curr, baseline, tolerance=0.05)
    assert comp["has_regressions"] is False
    assert len(comp["regressions"]) == 0


def test_regression_comparison_detected_regression():
    curr = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.50},  # dropped from 0.68
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            }
        }
    }
    baseline = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.68},
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            }
        }
    }
    comp = compare_benchmark_reports(curr, baseline, tolerance=0.05)
    assert comp["has_regressions"] is True
    assert any("Line F1 regressed" in r for r in comp["regressions"])


def test_regression_comparison_detected_improvement():
    curr = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.85},  # improved from 0.68
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            }
        }
    }
    baseline = {
        "aggregate_metrics": {
            "geometry": {
                "lines": {"mean_f1": 0.68},
                "circles": {"mean_f1": 0.77},
                "mean_relationship_f1": 0.18
            }
        }
    }
    comp = compare_benchmark_reports(curr, baseline, tolerance=0.05)
    assert comp["has_regressions"] is False
    assert any("Line F1 improved" in i for i in comp["improvements"])


# ---------------------------------------------------------------------------
# 5. Run Benchmark File Generation & CLI Tests
# ---------------------------------------------------------------------------

def test_run_benchmark_file_generation(tmp_path):
    out_dir = str(tmp_path / "eval_out")
    status = run_benchmark(output_dir=out_dir)
    assert status == 0

    json_file = os.path.join(out_dir, "benchmark_report.json")
    md_file = os.path.join(out_dir, "benchmark_report.md")

    assert os.path.exists(json_file)
    assert os.path.exists(md_file)

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["total_cases"] == 8

    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Mechanical Engineering Drawing Intelligence Evaluation" in content


def test_print_evaluation_summary_output():
    runner = EvaluationRunner()
    report = generate_evaluation_report(runner.run_all())
    text = print_evaluation_summary(report)

    assert "Evaluation completed" in text
    assert "Cases: 8" in text
    assert "Line F1:" in text
    assert "Circle F1:" in text
