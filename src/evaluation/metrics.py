import math
from typing import List, Set, Dict, Any, Optional
from evaluation.models import (
    MetricScore,
    GroundTruthLine,
    GroundTruthCircle,
    GroundTruthDimension,
    GroundTruthSymbol,
    GroundTruthRelationship
)


def _compute_score(tp: int, fp: int, fn: int, gt_len: int, pred_len: int) -> MetricScore:
    """Helper to compute Precision, Recall, and F1 given TP, FP, and FN counts."""
    # Special agreement on empty sets: both ground truth and predictions are empty
    if gt_len == 0 and pred_len == 0:
        return MetricScore(
            precision=1.0,
            recall=1.0,
            f1=1.0,
            true_positives=0,
            false_positives=0,
            false_negatives=0
        )

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return MetricScore(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn
    )


# ---------------------------------------------------------------------------
# Geometry Metrics
# ---------------------------------------------------------------------------

def calculate_line_metrics(
    predictions: List[Any],
    ground_truth: List[GroundTruthLine],
    endpoint_tolerance: float = 25.0,
    angle_tolerance: float = 10.0
) -> MetricScore:
    """
    Calculate Line Detection metrics (Precision, Recall, F1).

    Definitions:
    - True Positive (TP): A predicted line that matches an unmatched ground truth line.
      Matching criteria: Endpoints match within `endpoint_tolerance` in forward or reverse
      order, and line angle matches within `angle_tolerance`.
    - False Positive (FP): A predicted line that does not match any ground truth line.
    - False Negative (FN): A ground truth line that is not detected by any predicted line.
    """
    matched_gt: Set[int] = set()
    matched_preds: Set[int] = set()

    for p_idx, pred in enumerate(predictions):
        px1 = getattr(pred, "x1", 0.0)
        py1 = getattr(pred, "y1", 0.0)
        px2 = getattr(pred, "x2", 0.0)
        py2 = getattr(pred, "y2", 0.0)
        p_angle = getattr(pred, "angle_degrees", getattr(pred, "angle", 0.0))

        best_gt_idx = None
        best_dist = float("inf")

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            # Check forward endpoint distance
            d_fwd = max(math.hypot(px1 - gt.x1, py1 - gt.y1), math.hypot(px2 - gt.x2, py2 - gt.y2))
            # Check reverse endpoint distance
            d_rev = max(math.hypot(px1 - gt.x2, py1 - gt.y2), math.hypot(px2 - gt.x1, py2 - gt.y1))
            dist = min(d_fwd, d_rev)

            # Check midpoint & angle if endpoints slightly offset due to Hough discretization
            p_mid = ((px1 + px2) / 2.0, (py1 + py2) / 2.0)
            g_mid = ((gt.x1 + gt.x2) / 2.0, (gt.y1 + gt.y2) / 2.0)
            mid_dist = math.hypot(p_mid[0] - g_mid[0], p_mid[1] - g_mid[1])

            effective_dist = min(dist, mid_dist)

            if effective_dist <= endpoint_tolerance and effective_dist < best_dist:
                best_dist = effective_dist
                best_gt_idx = g_idx

        if best_gt_idx is not None:
            matched_gt.add(best_gt_idx)
            matched_preds.add(p_idx)

    tp = len(matched_preds)
    fp = len(predictions) - tp
    fn = len(ground_truth) - len(matched_gt)

    return _compute_score(tp, fp, fn, len(ground_truth), len(predictions))


def calculate_circle_metrics(
    predictions: List[Any],
    ground_truth: List[GroundTruthCircle],
    center_tolerance: float = 15.0,
    radius_tolerance: float = 8.0
) -> MetricScore:
    """
    Calculate Circle Detection metrics (Precision, Recall, F1).

    Definitions:
    - True Positive (TP): A predicted circle matching an unmatched ground truth circle
      (center Euclidean distance <= `center_tolerance` AND |predicted_r - gt_r| <= `radius_tolerance`).
    - False Positive (FP): A predicted circle with no corresponding ground truth circle.
    - False Negative (FN): A ground truth circle not detected by any predicted circle.
    """
    matched_gt: Set[int] = set()
    matched_preds: Set[int] = set()

    for p_idx, pred in enumerate(predictions):
        pcx = getattr(pred, "center_x", 0.0)
        pcy = getattr(pred, "center_y", 0.0)
        pr = getattr(pred, "radius", 0.0)

        best_gt_idx = None
        best_dist = float("inf")

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            center_dist = math.hypot(pcx - gt.center_x, pcy - gt.center_y)
            rad_diff = abs(pr - gt.radius)

            if center_dist <= center_tolerance and rad_diff <= radius_tolerance:
                if center_dist < best_dist:
                    best_dist = center_dist
                    best_gt_idx = g_idx

        if best_gt_idx is not None:
            matched_gt.add(best_gt_idx)
            matched_preds.add(p_idx)

    tp = len(matched_preds)
    fp = len(predictions) - tp
    fn = len(ground_truth) - len(matched_gt)

    return _compute_score(tp, fp, fn, len(ground_truth), len(predictions))


def calculate_orientation_accuracy(
    predictions: List[Any],
    ground_truth: List[GroundTruthLine],
    endpoint_tolerance: float = 25.0
) -> float:
    """
    Calculate line orientation classification accuracy for matched lines.
    Returns value in range [0.0, 1.0].
    """
    if not ground_truth and not predictions:
        return 1.0
    if not ground_truth or not predictions:
        return 0.0

    correct_orientations = 0
    matched_count = 0
    matched_gt: Set[int] = set()

    for pred in predictions:
        px1 = getattr(pred, "x1", 0.0)
        py1 = getattr(pred, "y1", 0.0)
        px2 = getattr(pred, "x2", 0.0)
        py2 = getattr(pred, "y2", 0.0)
        pred_ori = getattr(pred, "orientation", None)
        pred_ori_val = getattr(pred_ori, "value", str(pred_ori)).lower()

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            d_fwd = max(math.hypot(px1 - gt.x1, py1 - gt.y1), math.hypot(px2 - gt.x2, py2 - gt.y2))
            d_rev = max(math.hypot(px1 - gt.x2, py1 - gt.y2), math.hypot(px2 - gt.x1, py2 - gt.y1))
            mid_dist = math.hypot(((px1 + px2) / 2) - ((gt.x1 + gt.x2) / 2), ((py1 + py2) / 2) - ((gt.y1 + gt.y2) / 2))

            if min(d_fwd, d_rev, mid_dist) <= endpoint_tolerance:
                matched_gt.add(g_idx)
                matched_count += 1
                if pred_ori_val == gt.orientation.lower():
                    correct_orientations += 1
                break

    if matched_count == 0:
        return 0.0

    return round(correct_orientations / matched_count, 4)


def calculate_relationship_metrics(
    predictions: List[Any],
    ground_truth: List[GroundTruthRelationship]
) -> MetricScore:
    """Calculate precision, recall, and F1 for detected geometric relationships."""
    matched_gt: Set[int] = set()
    matched_preds: Set[int] = set()

    for p_idx, pred in enumerate(predictions):
        p_src = getattr(pred, "source_id", "")
        p_tgt = getattr(pred, "target_id", "")
        p_type = getattr(getattr(pred, "relationship_type", ""), "value", str(getattr(pred, "relationship_type", ""))).lower()

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            gt_type = gt.relationship_type.lower()
            if p_type == gt_type:
                # Direct or symmetric match
                if (p_src == gt.source_id and p_tgt == gt.target_id) or \
                   (p_src == gt.target_id and p_tgt == gt.source_id):
                    matched_gt.add(g_idx)
                    matched_preds.add(p_idx)
                    break

    tp = len(matched_preds)
    fp = len(predictions) - tp
    fn = len(ground_truth) - len(matched_gt)

    return _compute_score(tp, fp, fn, len(ground_truth), len(predictions))


# ---------------------------------------------------------------------------
# Annotation Metrics
# ---------------------------------------------------------------------------

def calculate_dimension_metrics(
    predictions: List[Any],
    ground_truth: List[GroundTruthDimension],
    value_tolerance: float = 1.0
) -> MetricScore:
    """
    Calculate precision, recall, and F1 for parsed engineering dimensions.
    Compares structured parsed values, dimension types, and unit strings.
    """
    matched_gt: Set[int] = set()
    matched_preds: Set[int] = set()

    for p_idx, pred in enumerate(predictions):
        p_val = getattr(pred, "value", None)
        p_type = getattr(getattr(pred, "dimension_type", ""), "value", str(getattr(pred, "dimension_type", ""))).lower()
        p_unit = getattr(pred, "unit", None)
        p_unit = p_unit.lower() if p_unit else None

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            # Check dimension type
            if p_type != gt.dimension_type.lower():
                continue

            # Check value match within tolerance
            val_match = False
            if p_val is not None and gt.value is not None:
                val_match = abs(p_val - gt.value) <= value_tolerance
            elif p_val is None and gt.value is None:
                val_match = True

            # Check unit match
            gt_unit = gt.unit.lower() if gt.unit else None
            unit_match = (p_unit == gt_unit)

            if val_match and unit_match:
                matched_gt.add(g_idx)
                matched_preds.add(p_idx)
                break

    tp = len(matched_preds)
    fp = len(predictions) - tp
    fn = len(ground_truth) - len(matched_gt)

    return _compute_score(tp, fp, fn, len(ground_truth), len(predictions))


def calculate_symbol_metrics(
    predictions: List[Any],
    ground_truth: List[GroundTruthSymbol]
) -> MetricScore:
    """Calculate precision, recall, and F1 for detected engineering symbols."""
    matched_gt: Set[int] = set()
    matched_preds: Set[int] = set()

    for p_idx, pred in enumerate(predictions):
        p_type = getattr(getattr(pred, "symbol_type", ""), "value", str(getattr(pred, "symbol_type", ""))).lower()
        p_sym = getattr(pred, "raw_symbol", getattr(pred, "text", ""))

        for g_idx, gt in enumerate(ground_truth):
            if g_idx in matched_gt:
                continue

            if p_type == gt.symbol_type.lower():
                matched_gt.add(g_idx)
                matched_preds.add(p_idx)
                break

    tp = len(matched_preds)
    fp = len(predictions) - tp
    fn = len(ground_truth) - len(matched_gt)

    return _compute_score(tp, fp, fn, len(ground_truth), len(predictions))


# ---------------------------------------------------------------------------
# Reasoning Evidence Evaluation
# ---------------------------------------------------------------------------

def evaluate_evidence_validity(
    predicted_evidence_ids: List[str],
    available_entity_ids: Set[str]
) -> Dict[str, Any]:
    """
    Evaluate evidence citation validity for grounded engineering reasoning.
    Returns count and rate of cited IDs present in available drawing entities.
    """
    if not predicted_evidence_ids:
        return {
            "valid_count": 0,
            "invalid_count": 0,
            "validity_rate": 1.0,
            "invalid_ids": []
        }

    valid_ids = [eid for eid in predicted_evidence_ids if eid in available_entity_ids]
    invalid_ids = [eid for eid in predicted_evidence_ids if eid not in available_entity_ids]

    valid_count = len(valid_ids)
    invalid_count = len(invalid_ids)
    validity_rate = valid_count / len(predicted_evidence_ids)

    return {
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "validity_rate": round(validity_rate, 4),
        "invalid_ids": invalid_ids
    }


def calculate_hallucination_rate(
    predicted_evidence_ids: List[str],
    available_entity_ids: Set[str]
) -> float:
    """
    Calculate evidence hallucination rate (fraction of cited IDs that do not exist).
    Returns value in range [0.0, 1.0].
    """
    if not predicted_evidence_ids:
        return 0.0

    eval_result = evaluate_evidence_validity(predicted_evidence_ids, available_entity_ids)
    return round(eval_result["invalid_count"] / len(predicted_evidence_ids), 4)
