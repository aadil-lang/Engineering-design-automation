"""Annotations, Dimensions, OCR, and Engineering Symbols module (Slice 3)."""

from annotations.models import (
    OCRResult,
    Dimension,
    DimensionType,
    Tolerance,
    EngineeringSymbol,
    SymbolType,
    GeometryAssociation,
    AssociationType,
    AnnotationsResult
)
from annotations.config import (
    OCR_UPSCALE_FACTOR,
    MIN_OCR_CONFIDENCE,
    MAX_ASSOCIATION_DISTANCE,
    LINE_ASSOCIATION_DISTANCE,
    CIRCLE_ASSOCIATION_DISTANCE
)
from annotations.preprocess import preprocess_for_ocr
from annotations.ocr import (
    OCREngine,
    MockOCREngine,
    FallbackOCREngine,
    TesseractOCREngine,
    get_ocr_engine
)
from annotations.parser import parse_dimension_text
from annotations.symbols import detect_symbols
from annotations.association import associate_dimensions_with_geometry
from annotations.extractor import extract_annotations, extract_annotations_from_ocr

__all__ = [
    "OCRResult",
    "Dimension",
    "DimensionType",
    "Tolerance",
    "EngineeringSymbol",
    "SymbolType",
    "GeometryAssociation",
    "AssociationType",
    "AnnotationsResult",
    "preprocess_for_ocr",
    "OCREngine",
    "MockOCREngine",
    "FallbackOCREngine",
    "TesseractOCREngine",
    "get_ocr_engine",
    "parse_dimension_text",
    "detect_symbols",
    "associate_dimensions_with_geometry",
    "extract_annotations",
    "extract_annotations_from_ocr",
    "OCR_UPSCALE_FACTOR",
    "MIN_OCR_CONFIDENCE",
    "MAX_ASSOCIATION_DISTANCE",
    "LINE_ASSOCIATION_DISTANCE",
    "CIRCLE_ASSOCIATION_DISTANCE"
]
