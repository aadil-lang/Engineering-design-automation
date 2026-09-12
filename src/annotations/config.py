"""Centralized configuration and tolerances for OCR, dimensions, symbols, and spatial geometry association."""

# OCR Preprocessing & Engine configuration
OCR_UPSCALE_FACTOR: float = 2.0
OCR_DENOISE_KERNEL_SIZE: int = 3
OCR_ADAPTIVE_BLOCK_SIZE: int = 15
OCR_ADAPTIVE_C: int = 4
MIN_OCR_CONFIDENCE: float = 0.30

# Dimension Parsing Confidence scores
HIGH_CONFIDENCE_PARSER: float = 0.95
DEFAULT_LINEAR_CONFIDENCE: float = 0.90
HEURISTIC_PARSER_CONFIDENCE: float = 0.75  # e.g., "D20" heuristic diameter

# Spatial Association Tolerances (in pixels)
MAX_ASSOCIATION_DISTANCE: float = 60.0
LINE_ASSOCIATION_DISTANCE: float = 50.0
CIRCLE_ASSOCIATION_DISTANCE: float = 80.0
MIN_ASSOCIATION_CONFIDENCE: float = 0.20
