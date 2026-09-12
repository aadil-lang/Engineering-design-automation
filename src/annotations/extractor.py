from typing import List, Optional, Dict, Any, TYPE_CHECKING
from collections import Counter
import numpy as np

from annotations.models import (
    AnnotationsResult,
    OCRResult,
    Dimension,
    EngineeringSymbol,
    GeometryAssociation
)
from annotations.config import MIN_OCR_CONFIDENCE
from annotations.preprocess import preprocess_for_ocr
from annotations.ocr import OCREngine, get_ocr_engine
from annotations.parser import parse_dimension_text
from annotations.symbols import detect_symbols
from annotations.association import associate_dimensions_with_geometry

if TYPE_CHECKING:
    from core.models import EngineeringFeatures


def extract_annotations_from_ocr(
    ocr_results: List[OCRResult],
    engineering_features: Optional[Any] = None
) -> AnnotationsResult:
    """
    Transform raw OCR results into structured engineering annotations, dimensions,
    symbols, and candidate spatial associations with geometric features.
    """
    dimensions: List[Dimension] = []
    symbols: List[EngineeringSymbol] = []

    for item in ocr_results:
        if item.confidence < MIN_OCR_CONFIDENCE:
            continue

        # 1. Deterministic Symbol Detection
        detected_syms = detect_symbols(
            raw_text=item.text,
            bounding_box=item.bounding_box,
            source_text_id=item.id
        )
        symbols.extend(detected_syms)

        # 2. Deterministic Dimension Parsing
        parsed_dim = parse_dimension_text(
            raw_text=item.text,
            bounding_box=item.bounding_box,
            source_text_id=item.id
        )
        if parsed_dim is not None:
            dimensions.append(parsed_dim)

    # 3. Spatial Geometry Association
    associations: List[GeometryAssociation] = associate_dimensions_with_geometry(
        dimensions=dimensions,
        engineering_features=engineering_features
    )

    # 4. Summary Statistics
    dim_types = Counter(d.dimension_type.value for d in dimensions)
    sym_types = Counter(s.symbol_type.value for s in symbols)
    associated_dims = len(set(a.dimension_id for a in associations))

    summary: Dict[str, Any] = {
        "total_ocr_detections": len(ocr_results),
        "total_dimensions": len(dimensions),
        "dimensions_by_type": dict(dim_types),
        "total_symbols": len(symbols),
        "symbols_by_type": dict(sym_types),
        "total_associations": len(associations),
        "associated_dimensions": associated_dims
    }

    return AnnotationsResult(
        ocr_results=ocr_results,
        dimensions=dimensions,
        symbols=symbols,
        associations=associations,
        summary=summary
    )


def extract_annotations(
    image: np.ndarray,
    engineering_features: Optional[Any] = None,
    ocr_engine: Optional[OCREngine] = None
) -> AnnotationsResult:
    """
    Main entry point for Slice 3 pipeline:
    Image -> OCR Preprocessing -> OCR Engine -> Dimension/Symbol Parser -> Geometry Association.
    """
    if ocr_engine is None:
        ocr_engine = get_ocr_engine()

    # Preprocess image specifically for OCR
    preprocessed_img = preprocess_for_ocr(image)

    # Run OCR recognition
    ocr_results = ocr_engine.recognize(preprocessed_img)

    # Extract structured annotations
    return extract_annotations_from_ocr(
        ocr_results=ocr_results,
        engineering_features=engineering_features
    )
