import re
import uuid
from typing import Optional, Tuple
from annotations.models import Dimension, DimensionType, Tolerance
from annotations.config import (
    HIGH_CONFIDENCE_PARSER,
    DEFAULT_LINEAR_CONFIDENCE,
    HEURISTIC_PARSER_CONFIDENCE
)

# Regex pattern for recognized engineering unit suffixes
UNIT_PATTERN = re.compile(r"(?:\s*(mm|cm|in|inch|inches))\b", re.IGNORECASE)

# Regex for symmetric tolerance: ±0.02, +/- 0.02, +- 0.02
SYMMETRIC_TOL_PATTERN = re.compile(r"(?:±|\+/[-–]|\+[-–])\s*([0-9]+(?:\.[0-9]+)?)")

# Regex for bilateral tolerance: +0.02/-0.01 or +0.02 -0.01
BILATERAL_TOL_PATTERN = re.compile(
    r"\+\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*[-–]\s*([0-9]+(?:\.[0-9]+)?)"
)

# Prefix and notation patterns
DIAMETER_UNICODE_PATTERN = re.compile(r"^[Ø⌀]\s*([0-9]+(?:\.[0-9]+)?)$")
DIAMETER_TEXT_PATTERN = re.compile(r"^(?:dia|dia\.|diameter)\s*([0-9]+(?:\.[0-9]+)?)$", re.IGNORECASE)
DIAMETER_HEURISTIC_PATTERN = re.compile(r"^d\s*([0-9]+(?:\.[0-9]+)?)$", re.IGNORECASE)

RADIUS_PATTERN = re.compile(r"^(?:r|rad|rad\.|radius)\s*([0-9]+(?:\.[0-9]+)?)$", re.IGNORECASE)
ANGULAR_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(?:°|deg|degree|degrees)$", re.IGNORECASE)
PLAIN_NUMBER_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)$")


def parse_dimension_text(
    raw_text: str,
    bounding_box: Optional[Tuple[float, float, float, float]] = None,
    source_text_id: Optional[str] = None
) -> Optional[Dimension]:
    """
    Deterministically parse raw OCR text into an engineering Dimension model.

    Supports:
    - Plain linear dimensions: "50", "25.5", "100"
    - Diameters: "Ø20", "⌀20", "Dia 20", "D20" (heuristic)
    - Radii: "R10", "R 10"
    - Angles: "45°", "45 deg", "45 degree"
    - Tolerances: "50 ±0.02", "50 +/- 0.02", "50 +0.02/-0.01"
    - Unit suffixes: "20 mm", "50.5 inch", "10 cm", "2.5 in"

    Returns:
        Dimension object if dimension information was parsed, or None if the text
        does not contain engineering dimension notation.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned_text = raw_text.strip()
    working_text = cleaned_text

    # 1. Extract Unit Suffix (do not invent unit if absent)
    unit: Optional[str] = None
    unit_match = UNIT_PATTERN.search(working_text)
    if unit_match:
        unit = unit_match.group(1).lower()
        # Remove the unit portion from working_text
        working_text = working_text[:unit_match.start()] + working_text[unit_match.end():]
        working_text = working_text.strip()

    # 2. Extract Tolerance Notation
    tolerance: Optional[Tolerance] = None
    
    # Check bilateral tolerance (+0.02/-0.01)
    bi_match = BILATERAL_TOL_PATTERN.search(working_text)
    if bi_match:
        upper_val = float(bi_match.group(1))
        lower_val = -float(bi_match.group(2))
        raw_tol = bi_match.group(0)
        tolerance = Tolerance(upper=upper_val, lower=lower_val, raw_text=raw_tol)
        working_text = working_text[:bi_match.start()] + working_text[bi_match.end():]
        working_text = working_text.strip()
    else:
        # Check symmetric tolerance (±0.02 or +/- 0.02)
        sym_match = SYMMETRIC_TOL_PATTERN.search(working_text)
        if sym_match:
            sym_val = float(sym_match.group(1))
            raw_tol = sym_match.group(0)
            tolerance = Tolerance(symmetric=sym_val, raw_text=raw_tol)
            working_text = working_text[:sym_match.start()] + working_text[sym_match.end():]
            working_text = working_text.strip()

    # 3. Check for pure angular text before prefix stripping
    ang_match = ANGULAR_PATTERN.match(working_text)
    if ang_match:
        val = float(ang_match.group(1))
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit or "deg",
            dimension_type=DimensionType.ANGULAR,
            tolerance=tolerance,
            confidence=HIGH_CONFIDENCE_PARSER,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # 4. Check Diameter: Unicode symbol (Ø / ⌀)
    dia_u_match = DIAMETER_UNICODE_PATTERN.match(working_text)
    if dia_u_match:
        val = float(dia_u_match.group(1))
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit,
            dimension_type=DimensionType.DIAMETER,
            tolerance=tolerance,
            confidence=HIGH_CONFIDENCE_PARSER,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # Check Diameter: Text prefix ("Dia 20", "DIA 20")
    dia_t_match = DIAMETER_TEXT_PATTERN.match(working_text)
    if dia_t_match:
        val = float(dia_t_match.group(1))
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit,
            dimension_type=DimensionType.DIAMETER,
            tolerance=tolerance,
            confidence=HIGH_CONFIDENCE_PARSER,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # Check Diameter: Heuristic prefix ("D20")
    dia_h_match = DIAMETER_HEURISTIC_PATTERN.match(working_text)
    if dia_h_match:
        val = float(dia_h_match.group(1))
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit,
            dimension_type=DimensionType.DIAMETER,
            tolerance=tolerance,
            confidence=HEURISTIC_PARSER_CONFIDENCE,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # 5. Check Radius: "R10", "R 10", "Rad 10"
    rad_match = RADIUS_PATTERN.match(working_text)
    if rad_match:
        val = float(rad_match.group(1))
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit,
            dimension_type=DimensionType.RADIUS,
            tolerance=tolerance,
            confidence=HIGH_CONFIDENCE_PARSER,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # 6. Check Plain Linear Dimension: "50", "25.5", "100"
    num_match = PLAIN_NUMBER_PATTERN.match(working_text)
    if num_match:
        val = float(num_match.group(1))
        dim_type = DimensionType.LINEAR
        conf = DEFAULT_LINEAR_CONFIDENCE
        if tolerance is not None:
            # If tolerance is present, still linear type with tolerance
            conf = HIGH_CONFIDENCE_PARSER
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=val,
            unit=unit,
            dimension_type=dim_type,
            tolerance=tolerance,
            confidence=conf,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    # 7. Standalone Tolerance without nominal value (e.g. "±0.02")
    if tolerance is not None and not working_text:
        return Dimension(
            id=f"dim_{uuid.uuid4().hex[:8]}",
            raw_text=cleaned_text,
            value=None,
            unit=unit,
            dimension_type=DimensionType.TOLERANCE,
            tolerance=tolerance,
            confidence=DEFAULT_LINEAR_CONFIDENCE,
            bounding_box=bounding_box,
            source_text_id=source_text_id
        )

    return None
