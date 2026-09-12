import re
import uuid
from typing import List, Optional, Tuple, Dict
from annotations.models import EngineeringSymbol, SymbolType
from annotations.config import HIGH_CONFIDENCE_PARSER, HEURISTIC_PARSER_CONFIDENCE

# Mapping of regex pattern, SymbolType, confidence, and symbol label
SYMBOL_PATTERNS = [
    # Diameter symbols
    (r"[Ø⌀]", SymbolType.DIAMETER, HIGH_CONFIDENCE_PARSER, "diameter_symbol"),
    (r"\b(?:dia|dia\.|diameter)\b", SymbolType.DIAMETER, 0.90, "diameter_text"),
    
    # Radius symbols
    (r"\b(?:rad|rad\.|radius)\b", SymbolType.RADIUS, 0.90, "radius_text"),
    (r"(?<![a-zA-Z0-9])R(?=[0-9]|\s+[0-9])", SymbolType.RADIUS, HIGH_CONFIDENCE_PARSER, "radius_prefix"),
    
    # Tolerance / Plus-Minus
    (r"±", SymbolType.PLUS_MINUS, HIGH_CONFIDENCE_PARSER, "plus_minus_symbol"),
    (r"\+/-|\+-", SymbolType.PLUS_MINUS, 0.90, "plus_minus_ascii"),
    (r"(?<!\w)[+\-](?=\s*[0-9])", SymbolType.PLUS_MINUS, 0.80, "sign_prefix"),
    
    # Degree / Angle
    (r"°", SymbolType.DEGREE, HIGH_CONFIDENCE_PARSER, "degree_symbol"),
    (r"\b(?:deg|degree|degrees)\b", SymbolType.DEGREE, 0.90, "degree_text"),
    
    # Preparatory GD&T symbols (extensible for future slices)
    (r"⏥", SymbolType.FLATNESS, HIGH_CONFIDENCE_PARSER, "flatness_symbol"),
    (r"∥", SymbolType.PARALLELISM, HIGH_CONFIDENCE_PARSER, "parallelism_symbol"),
    (r"⊥", SymbolType.PERPENDICULARITY, HIGH_CONFIDENCE_PARSER, "perpendicularity_symbol"),
    (r"⌖", SymbolType.POSITION, HIGH_CONFIDENCE_PARSER, "position_symbol"),
    (r"\bRa\b", SymbolType.SURFACE_ROUGHNESS, 0.85, "surface_roughness_ra"),
]


def detect_symbols(
    raw_text: str,
    bounding_box: Optional[Tuple[float, float, float, float]] = None,
    source_text_id: Optional[str] = None
) -> List[EngineeringSymbol]:
    """
    Deterministically detect engineering and geometric symbols from OCR text.
    
    Args:
        raw_text: Raw OCR detected string.
        bounding_box: Bounding box of the source OCR text token.
        source_text_id: Identifier of the source OCR result.

    Returns:
        List of detected EngineeringSymbol objects.
    """
    if not raw_text or not raw_text.strip():
        return []

    symbols: List[EngineeringSymbol] = []
    seen_types = set()

    for pattern, sym_type, conf, label in SYMBOL_PATTERNS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match and sym_type not in seen_types:
            seen_types.add(sym_type)
            symbols.append(
                EngineeringSymbol(
                    id=f"sym_{uuid.uuid4().hex[:8]}",
                    symbol_type=sym_type,
                    raw_symbol=match.group(0),
                    bounding_box=bounding_box,
                    confidence=conf,
                    source_text_id=source_text_id
                )
            )

    return symbols
