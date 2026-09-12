"""
Centralized configuration thresholds for mechanical engineering semantic interpretation.

IMPORTANT ENGINEERING PRINCIPLE:
The thresholds and rules defined below are heuristic engineering rules based on 2D
geometric features and annotations. They represent engineering evidence interpretations,
NOT guaranteed manufacturing intent or physical inspection verification.
"""

# Hole & Circular Feature Heuristic Thresholds
HOLE_STRONG_CONFIDENCE: float = 0.92
HOLE_CANDIDATE_CONFIDENCE: float = 0.75
CIRCULAR_FEATURE_CONFIDENCE: float = 0.60
HOLE_MIN_CONFIDENCE: float = 0.50
CIRCLE_TO_HOLE_ASSOCIATION_REQUIRED: bool = False

# Hole Pattern Recognition Thresholds
PATTERN_MIN_HOLES: int = 2
PATTERN_SPACING_TOLERANCE: float = 15.0      # Spatial variance in alignment and spacing (pixels)
PATTERN_DIAMETER_TOLERANCE: float = 5.0     # Maximum diameter variance to group holes (pixels)
PATTERN_LINEAR_CONFIDENCE: float = 0.88
PATTERN_CIRCULAR_CONFIDENCE: float = 0.85
PATTERN_REPEATED_CONFIDENCE: float = 0.70

# Parallel & Perpendicular Feature Semantics
PARALLEL_ANGLE_TOLERANCE: float = 5.0        # Degrees
PERPENDICULAR_ANGLE_TOLERANCE: float = 5.0    # Degrees
PARALLEL_FEATURE_CONFIDENCE: float = 0.85
PERPENDICULAR_FEATURE_CONFIDENCE: float = 0.85

# Rectangular Plate Recognition Thresholds
RECTANGLE_CORNER_TOLERANCE: float = 25.0    # Max gap between corner endpoints (pixels)
RECTANGLE_ASPECT_RATIO_TOLERANCE: float = 0.15
RECTANGULAR_PLATE_CONFIDENCE: float = 0.80

# Slot Recognition Thresholds
SLOT_ASPECT_RATIO_THRESHOLD: float = 1.8    # Minimum length-to-width ratio for slots
SLOT_PARALLEL_TOLERANCE: float = 8.0        # Max angle difference between slot parallel boundaries (deg)
SLOT_CONFIDENCE: float = 0.80

# Shaft & Stepped Feature Thresholds
SHAFT_MIN_ASPECT_RATIO: float = 2.0         # Minimum length-to-diameter ratio for a shaft segment
SHAFT_CONFIDENCE: float = 0.75
STEPPED_MIN_STEPS: int = 2
STEPPED_AXIS_ALIGNMENT_TOLERANCE: float = 15.0  # Centerline offset tolerance (pixels)
STEPPED_FEATURE_CONFIDENCE: float = 0.70

# Symmetry Recognition Thresholds
SYMMETRY_COORDINATE_TOLERANCE: float = 15.0  # Pixel tolerance for bilateral reflection symmetry
SYMMETRY_CONFIDENCE: float = 0.80
