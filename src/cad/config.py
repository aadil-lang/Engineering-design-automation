"""
Configuration parameters, directory locations, and tiered engineering tolerances
for Parametric CAD and 2D Engineering Drawing Generation.
"""

from typing import Dict, Any

# Output directories for generated CAD and drawing artifacts
DEFAULT_CAD_ARTIFACT_DIR: str = "artifacts/cad"
DEFAULT_DRAWING_ARTIFACT_DIR: str = "artifacts/drawings"

# Default measurement units
DEFAULT_LENGTH_UNIT: str = "mm"

# Tiered Engineering Tolerances (separated by domain)
# 1. Parameter tolerance: checking user input conformity and consistency
PARAMETER_TOLERANCE_MM: float = 1e-3

# 2. Geometry tolerance: 3D BRep geometric closure, bounding-box, and volume accuracy
GEOMETRY_TOLERANCE_MM: float = 1e-6
GEOMETRY_VOLUME_REL_TOLERANCE: float = 1e-4  # 0.01% volume relative error threshold

# 3. Drawing tolerance: 2D projection, dimension line alignment, and display formatting
DRAWING_TOLERANCE_MM: float = 1e-2

# Standard CAD metadata defaults
DEFAULT_CAD_ORGANIZATION: str = "MechaAI Engineering Intelligence Platform"
DEFAULT_CAD_AUTHOR: str = "Automated Parametric CAD Engine"
DEFAULT_CAD_SCHEMA: str = "CONFIG_CONTROL_DESIGN"  # ISO 10303-21 STEP schema

# Standard Drawing Title Block template
DEFAULT_TITLE_BLOCK: Dict[str, Any] = {
    "organization": "MECHAI ENGINEERING",
    "projection_type": "THIRD_ANGLE",
    "drawing_status": "PRELIMINARY_DESIGN",
    "revision": "A",
    "designer": "AI Design Engineer",
    "approver": "Human Engineering Review Required"
}
