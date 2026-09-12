import math
from typing import List, Tuple
from core.models import Line, Circle, LineFeature, CircleFeature, LineOrientation
from geometry.config import HORIZONTAL_TOLERANCE_DEG, VERTICAL_TOLERANCE_DEG, MIN_HOLE_RADIUS, MAX_HOLE_RADIUS

def normalize_angle(angle_deg: float) -> float:
    """
    Normalize angle to [0, 180) degrees for consistency.
    Lines without directionality can be represented in the upper half-plane.
    """
    angle = angle_deg % 180.0
    if angle < 0:
        angle += 180.0
    return angle

def classify_orientation(angle_deg: float) -> LineOrientation:
    """
    Classify line orientation based on normalized angle and configured tolerances.
    """
    norm_angle = normalize_angle(angle_deg)
    
    # Check horizontal (around 0 or 180)
    if norm_angle <= HORIZONTAL_TOLERANCE_DEG or norm_angle >= (180.0 - HORIZONTAL_TOLERANCE_DEG):
        return LineOrientation.HORIZONTAL
        
    # Check vertical (around 90)
    if abs(norm_angle - 90.0) <= VERTICAL_TOLERANCE_DEG:
        return LineOrientation.VERTICAL
        
    return LineOrientation.DIAGONAL

def derive_line_features(lines: List[Line]) -> List[LineFeature]:
    """Convert basic OpenCV lines to engineering LineFeatures."""
    features = []
    for i, line in enumerate(lines):
        norm_angle = normalize_angle(line.angle)
        orientation = classify_orientation(norm_angle)
        
        feature = LineFeature(
            id=f"line_{i}",
            x1=line.x1,
            y1=line.y1,
            x2=line.x2,
            y2=line.y2,
            length=line.length,
            angle_degrees=norm_angle,
            orientation=orientation
        )
        features.append(feature)
    return features

def derive_circle_features(circles: List[Circle]) -> List[CircleFeature]:
    """Convert basic OpenCV circles to engineering CircleFeatures with hole heuristics."""
    features = []
    for i, circle in enumerate(circles):
        diameter = circle.radius * 2.0
        
        # Heuristic: simple size-based hole candidate detection
        likely_hole = False
        confidence = 0.0
        if MIN_HOLE_RADIUS <= circle.radius <= MAX_HOLE_RADIUS:
            likely_hole = True
            confidence = 0.8  # Arbitrary heuristic confidence for now
            
        feature = CircleFeature(
            id=f"circle_{i}",
            center_x=circle.center_x,
            center_y=circle.center_y,
            radius=circle.radius,
            diameter=diameter,
            likely_hole=likely_hole,
            confidence=confidence
        )
        features.append(feature)
    return features
