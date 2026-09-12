import math
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING
from annotations.models import Dimension, DimensionType, GeometryAssociation, AssociationType
from annotations.config import (
    LINE_ASSOCIATION_DISTANCE,
    CIRCLE_ASSOCIATION_DISTANCE,
    MAX_ASSOCIATION_DISTANCE,
    MIN_ASSOCIATION_CONFIDENCE
)

if TYPE_CHECKING:
    from core.models import LineFeature, CircleFeature, EngineeringFeatures


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate the shortest distance from point (px, py) to segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    segment_len_sq = dx * dx + dy * dy

    if segment_len_sq == 0.0:
        return math.hypot(px - x1, py - y1)

    # Project point onto segment
    t = ((px - x1) * dx + (py - y1) * dy) / segment_len_sq
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.hypot(px - closest_x, py - closest_y)


def point_to_circle_distance(px: float, py: float, cx: float, cy: float, radius: float) -> Tuple[float, float]:
    """
    Calculate distances from point (px, py) to a circle:
    Returns (perimeter_distance, center_distance).
    """
    center_dist = math.hypot(px - cx, py - cy)
    perimeter_dist = abs(center_dist - radius)
    return perimeter_dist, center_dist


def associate_dimensions_with_geometry(
    dimensions: List[Dimension],
    engineering_features: Optional[Any] = None
) -> List[GeometryAssociation]:
    """
    Deterministically associate detected dimensions with nearby geometric features
    (lines, circles) from Slice 2.

    Candidate association heuristics:
    - Diameter dimension ("Ø20") close to a circle -> circle_diameter
    - Radius dimension ("R10") close to a circle -> circle_radius
    - Linear dimension ("50") close to a line -> line_dimension
    - Other proximity within threshold -> nearby_geometry

    Returns:
        List of candidate GeometryAssociation objects with distances and confidence scores.
    """
    if not engineering_features or not dimensions:
        return []

    lines = getattr(engineering_features, "line_features", None) or []
    circles = getattr(engineering_features, "circle_features", None) or []

    associations: List[GeometryAssociation] = []

    for dim in dimensions:
        if not dim.bounding_box:
            continue

        bx, by, bw, bh = dim.bounding_box
        center_x = bx + bw / 2.0
        center_y = by + bh / 2.0

        best_association: Optional[GeometryAssociation] = None

        # 1. Diameter Dimensions -> Prefer Circle Features
        if dim.dimension_type == DimensionType.DIAMETER and circles:
            best_circle = None
            min_dist = float("inf")
            for c in circles:
                p_dist, c_dist = point_to_circle_distance(center_x, center_y, c.center_x, c.center_y, c.radius)
                eff_dist = min(p_dist, c_dist)
                if eff_dist < min_dist:
                    min_dist = eff_dist
                    best_circle = c

            if best_circle and min_dist <= CIRCLE_ASSOCIATION_DISTANCE:
                conf = max(MIN_ASSOCIATION_CONFIDENCE, 1.0 - (min_dist / CIRCLE_ASSOCIATION_DISTANCE))
                metadata: Dict[str, Any] = {"matched_geometry": "circle", "circle_diameter": best_circle.diameter}
                if dim.value and abs(dim.value - best_circle.diameter) <= 2.0:
                    metadata["nominal_diameter_match"] = True
                    conf = min(1.0, conf + 0.1)

                best_association = GeometryAssociation(
                    dimension_id=dim.id,
                    feature_id=best_circle.id,
                    association_type=AssociationType.CIRCLE_DIAMETER,
                    distance=round(min_dist, 2),
                    confidence=round(conf, 3),
                    metadata=metadata
                )

        # 2. Radius Dimensions -> Prefer Circle Features
        elif dim.dimension_type == DimensionType.RADIUS and circles:
            best_circle = None
            min_dist = float("inf")
            for c in circles:
                p_dist, c_dist = point_to_circle_distance(center_x, center_y, c.center_x, c.center_y, c.radius)
                eff_dist = min(p_dist, c_dist)
                if eff_dist < min_dist:
                    min_dist = eff_dist
                    best_circle = c

            if best_circle and min_dist <= CIRCLE_ASSOCIATION_DISTANCE:
                conf = max(MIN_ASSOCIATION_CONFIDENCE, 1.0 - (min_dist / CIRCLE_ASSOCIATION_DISTANCE))
                metadata = {"matched_geometry": "circle", "circle_radius": best_circle.radius}
                if dim.value and abs(dim.value - best_circle.radius) <= 2.0:
                    metadata["nominal_radius_match"] = True
                    conf = min(1.0, conf + 0.1)

                best_association = GeometryAssociation(
                    dimension_id=dim.id,
                    feature_id=best_circle.id,
                    association_type=AssociationType.CIRCLE_RADIUS,
                    distance=round(min_dist, 2),
                    confidence=round(conf, 3),
                    metadata=metadata
                )

        # 3. Linear Dimensions -> Prefer Line Features
        elif dim.dimension_type == DimensionType.LINEAR and lines:
            best_line = None
            min_dist = float("inf")
            for line in lines:
                dist = point_to_segment_distance(center_x, center_y, line.x1, line.y1, line.x2, line.y2)
                if dist < min_dist:
                    min_dist = dist
                    best_line = line

            if best_line and min_dist <= LINE_ASSOCIATION_DISTANCE:
                conf = max(MIN_ASSOCIATION_CONFIDENCE, 1.0 - (min_dist / LINE_ASSOCIATION_DISTANCE))
                orientation_val = getattr(best_line.orientation, "value", str(best_line.orientation))
                metadata = {"matched_geometry": "line", "line_orientation": orientation_val, "line_length": best_line.length}
                best_association = GeometryAssociation(
                    dimension_id=dim.id,
                    feature_id=best_line.id,
                    association_type=AssociationType.LINE_DIMENSION,
                    distance=round(min_dist, 2),
                    confidence=round(conf, 3),
                    metadata=metadata
                )

        # 4. Fallback Generic Proximity: Find any geometry within MAX_ASSOCIATION_DISTANCE
        if not best_association:
            closest_feat_id = None
            min_dist = float("inf")
            matched_geo = None

            for line in lines:
                dist = point_to_segment_distance(center_x, center_y, line.x1, line.y1, line.x2, line.y2)
                if dist < min_dist:
                    min_dist = dist
                    closest_feat_id = line.id
                    matched_geo = "line"

            for c in circles:
                p_dist, c_dist = point_to_circle_distance(center_x, center_y, c.center_x, c.center_y, c.radius)
                eff_dist = min(p_dist, c_dist)
                if eff_dist < min_dist:
                    min_dist = eff_dist
                    closest_feat_id = c.id
                    matched_geo = "circle"

            if closest_feat_id and min_dist <= MAX_ASSOCIATION_DISTANCE:
                conf = max(MIN_ASSOCIATION_CONFIDENCE, 1.0 - (min_dist / MAX_ASSOCIATION_DISTANCE))
                best_association = GeometryAssociation(
                    dimension_id=dim.id,
                    feature_id=closest_feat_id,
                    association_type=AssociationType.NEARBY_GEOMETRY,
                    distance=round(min_dist, 2),
                    confidence=round(conf, 3),
                    metadata={"matched_geometry": matched_geo}
                )

        if best_association:
            associations.append(best_association)

    return associations
