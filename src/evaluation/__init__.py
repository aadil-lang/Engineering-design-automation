"""Evaluation and Benchmarking Foundation (Slice 5A & 5B)."""

from evaluation.models import (
    GroundTruthLine,
    GroundTruthCircle,
    GroundTruthDimension,
    GroundTruthSymbol,
    GroundTruthRelationship,
    GroundTruth,
    EvaluationCase,
    MetricScore,
    EvaluationResult,
    EvaluationSummaryReport
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
    generate_markdown_report,
    report_to_json,
    print_evaluation_summary,
    derive_error_analysis,
    compare_benchmark_reports
)

__all__ = [
    "GroundTruthLine",
    "GroundTruthCircle",
    "GroundTruthDimension",
    "GroundTruthSymbol",
    "GroundTruthRelationship",
    "GroundTruth",
    "EvaluationCase",
    "MetricScore",
    "EvaluationResult",
    "EvaluationSummaryReport",
    "case_horizontal_line",
    "case_vertical_line",
    "case_diagonal_lines",
    "case_parallel_lines",
    "case_perpendicular_lines",
    "case_hole",
    "case_multiple_holes",
    "case_mixed_geometry",
    "get_all_synthetic_cases",
    "calculate_line_metrics",
    "calculate_circle_metrics",
    "calculate_orientation_accuracy",
    "calculate_relationship_metrics",
    "calculate_dimension_metrics",
    "calculate_symbol_metrics",
    "evaluate_evidence_validity",
    "calculate_hallucination_rate",
    "EvaluationRunner",
    "generate_evaluation_report",
    "generate_markdown_report",
    "report_to_json",
    "print_evaluation_summary",
    "derive_error_analysis",
    "compare_benchmark_reports"
]
