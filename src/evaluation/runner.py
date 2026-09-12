from typing import List, Optional, Dict, Any
import numpy as np

from core.models import AnalyzeResponse
from vision.detector import extract_features
from geometry.extractor import extract_engineering_features
from annotations.extractor import extract_annotations
from evaluation.models import EvaluationCase, EvaluationResult
from evaluation.synthetic import get_all_synthetic_cases
from evaluation.metrics import (
    calculate_line_metrics,
    calculate_circle_metrics,
    calculate_orientation_accuracy,
    calculate_relationship_metrics,
    calculate_dimension_metrics,
    calculate_symbol_metrics
)


class EvaluationRunner:
    """
    Automated evaluation harness executing the drawing analysis pipeline
    against benchmark evaluation cases and computing standardized accuracy metrics.
    """

    def __init__(self, cases: Optional[List[EvaluationCase]] = None):
        self.cases = cases if cases is not None else get_all_synthetic_cases()

    def run_pipeline(self, image: np.ndarray) -> AnalyzeResponse:
        """Execute the end-to-end Slice 1–3 pipeline on an input image."""
        cv_response = extract_features(image)

        eng_features = extract_engineering_features(
            cv_response.lines,
            cv_response.circles,
            cv_response.contours,
            cv_response.image
        )
        cv_response.engineering_features = eng_features

        annotations = extract_annotations(
            image=image,
            engineering_features=eng_features
        )
        cv_response.annotations = annotations

        return cv_response

    def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        """Run analysis on a single EvaluationCase and compute benchmark metrics."""
        analysis = self.run_pipeline(case.image)

        pred_lines = analysis.engineering_features.line_features if analysis.engineering_features else []
        pred_circles = analysis.engineering_features.circle_features if analysis.engineering_features else []
        pred_rels = analysis.engineering_features.relationships if analysis.engineering_features else []
        pred_dims = analysis.annotations.dimensions if analysis.annotations else []
        pred_syms = analysis.annotations.symbols if analysis.annotations else []

        # Calculate metrics
        line_metrics = calculate_line_metrics(pred_lines, case.ground_truth.lines)
        circle_metrics = calculate_circle_metrics(pred_circles, case.ground_truth.circles)
        orientation_acc = calculate_orientation_accuracy(pred_lines, case.ground_truth.lines)
        rel_metrics = calculate_relationship_metrics(pred_rels, case.ground_truth.relationships)
        dim_metrics = calculate_dimension_metrics(pred_dims, case.ground_truth.dimensions)
        sym_metrics = calculate_symbol_metrics(pred_syms, case.ground_truth.symbols)

        metrics: Dict[str, Any] = {
            "lines": line_metrics.model_dump(),
            "circles": circle_metrics.model_dump(),
            "orientation_accuracy": orientation_acc,
            "relationships": rel_metrics.model_dump(),
            "dimensions": dim_metrics.model_dump(),
            "symbols": sym_metrics.model_dump()
        }

        details: Dict[str, Any] = {
            "description": case.description,
            "counts": {
                "gt_lines": len(case.ground_truth.lines),
                "pred_lines": len(pred_lines),
                "gt_circles": len(case.ground_truth.circles),
                "pred_circles": len(pred_circles),
                "gt_dimensions": len(case.ground_truth.dimensions),
                "pred_dimensions": len(pred_dims),
                "gt_symbols": len(case.ground_truth.symbols),
                "pred_symbols": len(pred_syms)
            }
        }

        return EvaluationResult(
            case_id=case.case_id,
            metrics=metrics,
            details=details
        )

    def run_all(self) -> List[EvaluationResult]:
        """Execute evaluation across all configured test cases."""
        return [self.evaluate_case(c) for c in self.cases]
