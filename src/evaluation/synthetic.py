import cv2
import numpy as np
from typing import List
from evaluation.models import (
    EvaluationCase,
    GroundTruth,
    GroundTruthLine,
    GroundTruthCircle,
    GroundTruthDimension,
    GroundTruthSymbol,
    GroundTruthRelationship
)


def _create_white_canvas(width: int = 400, height: int = 400) -> np.ndarray:
    """Create a pristine white 3-channel canvas for drawing."""
    return np.ones((height, width, 3), dtype=np.uint8) * 255


def case_horizontal_line() -> EvaluationCase:
    """Case 1: Single horizontal line."""
    img = _create_white_canvas(400, 400)
    cv2.line(img, (50, 200), (350, 200), (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(
                id="line_0",
                x1=50.0,
                y1=200.0,
                x2=350.0,
                y2=200.0,
                orientation="horizontal"
            )
        ]
    )
    return EvaluationCase(
        case_id="case_horizontal_line",
        description="Single horizontal line spanning from x=50 to x=350 at y=200",
        image=img,
        ground_truth=gt
    )


def case_vertical_line() -> EvaluationCase:
    """Case 2: Single vertical line."""
    img = _create_white_canvas(400, 400)
    cv2.line(img, (200, 50), (200, 350), (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(
                id="line_0",
                x1=200.0,
                y1=50.0,
                x2=200.0,
                y2=350.0,
                orientation="vertical"
            )
        ]
    )
    return EvaluationCase(
        case_id="case_vertical_line",
        description="Single vertical line spanning from y=50 to y=350 at x=200",
        image=img,
        ground_truth=gt
    )


def case_diagonal_lines() -> EvaluationCase:
    """Case 3: Multiple diagonal lines."""
    img = _create_white_canvas(400, 400)
    cv2.line(img, (50, 50), (350, 350), (0, 0, 0), thickness=2)
    cv2.line(img, (50, 350), (350, 50), (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(id="line_0", x1=50.0, y1=50.0, x2=350.0, y2=350.0, orientation="diagonal"),
            GroundTruthLine(id="line_1", x1=50.0, y1=350.0, x2=350.0, y2=50.0, orientation="diagonal")
        ]
    )
    return EvaluationCase(
        case_id="case_diagonal_lines",
        description="Two diagonal lines intersecting in an X pattern",
        image=img,
        ground_truth=gt
    )


def case_parallel_lines() -> EvaluationCase:
    """Case 4: Two parallel horizontal lines."""
    img = _create_white_canvas(400, 400)
    cv2.line(img, (50, 150), (350, 150), (0, 0, 0), thickness=2)
    cv2.line(img, (50, 250), (350, 250), (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(id="line_0", x1=50.0, y1=150.0, x2=350.0, y2=150.0, orientation="horizontal"),
            GroundTruthLine(id="line_1", x1=50.0, y1=250.0, x2=350.0, y2=250.0, orientation="horizontal")
        ],
        relationships=[
            GroundTruthRelationship(source_id="line_0", target_id="line_1", relationship_type="parallel")
        ]
    )
    return EvaluationCase(
        case_id="case_parallel_lines",
        description="Two horizontal parallel lines separated by 100 pixels",
        image=img,
        ground_truth=gt
    )


def case_perpendicular_lines() -> EvaluationCase:
    """Case 5: Horizontal and vertical lines intersecting perpendicularly."""
    img = _create_white_canvas(400, 400)
    # Horizontal line
    cv2.line(img, (50, 200), (350, 200), (0, 0, 0), thickness=2)
    # Vertical line connected at (200, 200)
    cv2.line(img, (200, 50), (200, 200), (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(id="line_0", x1=50.0, y1=200.0, x2=350.0, y2=200.0, orientation="horizontal"),
            GroundTruthLine(id="line_1", x1=200.0, y1=50.0, x2=200.0, y2=200.0, orientation="vertical")
        ],
        relationships=[
            GroundTruthRelationship(source_id="line_0", target_id="line_1", relationship_type="perpendicular"),
            GroundTruthRelationship(source_id="line_0", target_id="line_1", relationship_type="connected")
        ]
    )
    return EvaluationCase(
        case_id="case_perpendicular_lines",
        description="T-junction with horizontal line and connected vertical line",
        image=img,
        ground_truth=gt
    )


def case_hole() -> EvaluationCase:
    """Case 6: Rectangular outer boundary with one centered circular hole."""
    img = _create_white_canvas(400, 400)
    # Outer rectangle: (50, 50) to (350, 350)
    cv2.rectangle(img, (50, 50), (350, 350), (0, 0, 0), thickness=2)
    # Circular hole: center (200, 200), radius 25
    cv2.circle(img, (200, 200), 25, (0, 0, 0), thickness=2)

    gt = GroundTruth(
        lines=[
            GroundTruthLine(id="line_top", x1=50.0, y1=50.0, x2=350.0, y2=50.0, orientation="horizontal"),
            GroundTruthLine(id="line_bottom", x1=50.0, y1=350.0, x2=350.0, y2=350.0, orientation="horizontal"),
            GroundTruthLine(id="line_left", x1=50.0, y1=50.0, x2=50.0, y2=350.0, orientation="vertical"),
            GroundTruthLine(id="line_right", x1=350.0, y1=50.0, x2=350.0, y2=350.0, orientation="vertical")
        ],
        circles=[
            GroundTruthCircle(id="circle_0", center_x=200.0, center_y=200.0, radius=25.0)
        ]
    )
    return EvaluationCase(
        case_id="case_hole",
        description="Rectangular plate with a single central circular hole",
        image=img,
        ground_truth=gt
    )


def case_multiple_holes() -> EvaluationCase:
    """Case 7: Multiple circular holes representing hole candidates."""
    img = _create_white_canvas(400, 400)
    # Draw three distinct holes along horizontal axis
    cv2.circle(img, (100, 200), 15, (0, 0, 0), thickness=2)
    cv2.circle(img, (200, 200), 20, (0, 0, 0), thickness=2)
    cv2.circle(img, (300, 200), 25, (0, 0, 0), thickness=2)

    gt = GroundTruth(
        circles=[
            GroundTruthCircle(id="circle_0", center_x=100.0, center_y=200.0, radius=15.0),
            GroundTruthCircle(id="circle_1", center_x=200.0, center_y=200.0, radius=20.0),
            GroundTruthCircle(id="circle_2", center_x=300.0, center_y=200.0, radius=25.0)
        ]
    )
    return EvaluationCase(
        case_id="case_multiple_holes",
        description="Three circular holes with radii 15, 20, and 25 px",
        image=img,
        ground_truth=gt
    )


def case_mixed_geometry() -> EvaluationCase:
    """Case 8: Mixed geometry with lines, a circle, and annotations."""
    img = _create_white_canvas(400, 400)
    # Plate rectangle
    cv2.rectangle(img, (50, 50), (350, 300), (0, 0, 0), thickness=2)
    # Center hole
    cv2.circle(img, (200, 175), 20, (0, 0, 0), thickness=2)

    # Text callout for dimension
    cv2.putText(
        img,
        "D40",
        (185, 230),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2
    )

    gt = GroundTruth(
        lines=[
            GroundTruthLine(id="line_top", x1=50.0, y1=50.0, x2=350.0, y2=50.0, orientation="horizontal"),
            GroundTruthLine(id="line_bottom", x1=50.0, y1=300.0, x2=350.0, y2=300.0, orientation="horizontal"),
            GroundTruthLine(id="line_left", x1=50.0, y1=50.0, x2=50.0, y2=300.0, orientation="vertical"),
            GroundTruthLine(id="line_right", x1=350.0, y1=50.0, x2=350.0, y2=300.0, orientation="vertical")
        ],
        circles=[
            GroundTruthCircle(id="circle_0", center_x=200.0, center_y=175.0, radius=20.0)
        ],
        dimensions=[
            GroundTruthDimension(
                id="dim_0",
                raw_text="D40",
                value=40.0,
                dimension_type="diameter",
                unit=None
            )
        ]
    )
    return EvaluationCase(
        case_id="case_mixed_geometry",
        description="Rectangular plate with central hole and D40 dimension callout",
        image=img,
        ground_truth=gt
    )


def get_all_synthetic_cases() -> List[EvaluationCase]:
    """Retrieve all standard synthetic benchmark cases."""
    return [
        case_horizontal_line(),
        case_vertical_line(),
        case_diagonal_lines(),
        case_parallel_lines(),
        case_perpendicular_lines(),
        case_hole(),
        case_multiple_holes(),
        case_mixed_geometry()
    ]
