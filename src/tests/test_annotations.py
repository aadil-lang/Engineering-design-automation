import numpy as np
import pytest
from core.models import (
    LineFeature,
    CircleFeature,
    LineOrientation,
    EngineeringFeatures,
    BoundingInformation
)
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
from annotations.parser import parse_dimension_text
from annotations.symbols import detect_symbols
from annotations.association import associate_dimensions_with_geometry
from annotations.preprocess import preprocess_for_ocr
from annotations.ocr import MockOCREngine, FallbackOCREngine
from annotations.extractor import extract_annotations_from_ocr, extract_annotations


# 1. Model Serialization Tests

def test_ocr_result_serialization():
    res = OCRResult(
        id="ocr_1",
        text="Ø25.0",
        confidence=0.98,
        bounding_box=(10.0, 20.0, 50.0, 15.0)
    )
    dumped = res.model_dump()
    assert dumped["id"] == "ocr_1"
    assert dumped["text"] == "Ø25.0"
    assert dumped["confidence"] == 0.98
    assert dumped["bounding_box"] == (10.0, 20.0, 50.0, 15.0)

    reconstructed = OCRResult.model_validate(dumped)
    assert reconstructed == res


def test_dimension_model_serialization():
    dim = Dimension(
        id="dim_1",
        raw_text="50 ±0.02 mm",
        value=50.0,
        unit="mm",
        dimension_type=DimensionType.LINEAR,
        tolerance=Tolerance(symmetric=0.02, raw_text="±0.02"),
        confidence=0.95,
        bounding_box=(100.0, 150.0, 60.0, 20.0),
        source_text_id="ocr_1"
    )
    data = dim.model_dump()
    assert data["value"] == 50.0
    assert data["unit"] == "mm"
    assert data["tolerance"]["symmetric"] == 0.02
    assert Dimension.model_validate(data) == dim


# 2. Plain Dimensions

def test_dimension_plain_integer():
    dim = parse_dimension_text("50")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 50.0
    assert dim.unit is None
    assert dim.tolerance is None
    assert dim.confidence >= 0.90


def test_dimension_plain_float():
    dim = parse_dimension_text("25.5")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 25.5
    assert dim.unit is None


def test_dimension_plain_hundred():
    dim = parse_dimension_text("100")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 100.0


# 3. Diameter Parsing

def test_dimension_diameter_unicode_slash():
    dim = parse_dimension_text("Ø20")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0
    assert dim.unit is None
    assert dim.confidence >= 0.95


def test_dimension_diameter_unicode_circle():
    dim = parse_dimension_text("⌀20")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0


def test_dimension_diameter_prefix_dia():
    dim = parse_dimension_text("Dia 20")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0


def test_dimension_diameter_prefix_uppercase_dia():
    dim = parse_dimension_text("DIA 20")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0


def test_dimension_diameter_heuristic_d():
    dim = parse_dimension_text("D20")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0
    # Heuristic confidence should be lower than explicit symbol
    assert dim.confidence == 0.75


# 4. Radius Parsing

def test_dimension_radius():
    dim = parse_dimension_text("R10")
    assert dim is not None
    assert dim.dimension_type == DimensionType.RADIUS
    assert dim.value == 10.0
    assert dim.unit is None


def test_dimension_radius_with_space():
    dim = parse_dimension_text("R 10")
    assert dim is not None
    assert dim.dimension_type == DimensionType.RADIUS
    assert dim.value == 10.0


def test_dimension_radius_rad_prefix():
    dim = parse_dimension_text("Rad 15")
    assert dim is not None
    assert dim.dimension_type == DimensionType.RADIUS
    assert dim.value == 15.0


# 5. Angular Dimensions

def test_dimension_angular_degree_symbol():
    dim = parse_dimension_text("45°")
    assert dim is not None
    assert dim.dimension_type == DimensionType.ANGULAR
    assert dim.value == 45.0
    assert dim.unit == "deg"


def test_dimension_angular_deg_text():
    dim = parse_dimension_text("45 deg")
    assert dim is not None
    assert dim.dimension_type == DimensionType.ANGULAR
    assert dim.value == 45.0
    assert dim.unit == "deg"


def test_dimension_angular_degree_word():
    dim = parse_dimension_text("45 degree")
    assert dim is not None
    assert dim.dimension_type == DimensionType.ANGULAR
    assert dim.value == 45.0
    assert dim.unit == "deg"


# 6. Tolerances

def test_dimension_tolerance_symmetric_unicode():
    dim = parse_dimension_text("50 ±0.02")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 50.0
    assert dim.tolerance is not None
    assert dim.tolerance.symmetric == 0.02
    assert "±0.02" in dim.tolerance.raw_text


def test_dimension_tolerance_symmetric_ascii():
    dim = parse_dimension_text("50 +/- 0.02")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 50.0
    assert dim.tolerance is not None
    assert dim.tolerance.symmetric == 0.02


def test_dimension_tolerance_bilateral():
    dim = parse_dimension_text("50 +0.02/-0.01")
    assert dim is not None
    assert dim.dimension_type == DimensionType.LINEAR
    assert dim.value == 50.0
    assert dim.tolerance is not None
    assert dim.tolerance.upper == 0.02
    assert dim.tolerance.lower == -0.01


def test_dimension_diameter_with_tolerance():
    dim = parse_dimension_text("Ø20 ±0.05")
    assert dim is not None
    assert dim.dimension_type == DimensionType.DIAMETER
    assert dim.value == 20.0
    assert dim.tolerance is not None
    assert dim.tolerance.symmetric == 0.05


# 7. Units & Malformed strings

def test_dimension_unit_extraction_mm():
    dim = parse_dimension_text("20 mm")
    assert dim is not None
    assert dim.value == 20.0
    assert dim.unit == "mm"


def test_dimension_unit_extraction_inch():
    dim = parse_dimension_text("100.5 inch")
    assert dim is not None
    assert dim.value == 100.5
    assert dim.unit == "inch"


def test_dimension_unit_extraction_cm():
    dim = parse_dimension_text("15 cm")
    assert dim is not None
    assert dim.value == 15.0
    assert dim.unit == "cm"


def test_dimension_no_unit_remains_null():
    dim = parse_dimension_text("50")
    assert dim is not None
    assert dim.unit is None


def test_dimension_malformed_text():
    assert parse_dimension_text("PART NO 12345 ABC") is None
    assert parse_dimension_text("STEEL") is None
    assert parse_dimension_text("") is None
    assert parse_dimension_text("   ") is None


# 8. Symbol Recognition

def test_symbol_recognition_diameter():
    syms = detect_symbols("Ø20 and ⌀30")
    types = [s.symbol_type for s in syms]
    assert SymbolType.DIAMETER in types


def test_symbol_recognition_radius():
    syms = detect_symbols("R10 fillet")
    types = [s.symbol_type for s in syms]
    assert SymbolType.RADIUS in types


def test_symbol_recognition_plus_minus():
    syms = detect_symbols("50 ±0.05")
    types = [s.symbol_type for s in syms]
    assert SymbolType.PLUS_MINUS in types


def test_symbol_recognition_degree():
    syms = detect_symbols("chamfer 45°")
    types = [s.symbol_type for s in syms]
    assert SymbolType.DEGREE in types


def test_symbol_recognition_future_gdt():
    syms = detect_symbols("flatness ⏥ parallelism ∥ perpendicularity ⊥")
    types = [s.symbol_type for s in syms]
    assert SymbolType.FLATNESS in types
    assert SymbolType.PARALLELISM in types
    assert SymbolType.PERPENDICULARITY in types


# 9. Spatial Geometry Association

def test_association_dimension_near_line():
    line = LineFeature(
        id="line_1",
        x1=50.0,
        y1=100.0,
        x2=200.0,
        y2=100.0,
        length=150.0,
        angle_degrees=0.0,
        orientation=LineOrientation.HORIZONTAL
    )
    dim = Dimension(
        id="dim_1",
        raw_text="150",
        value=150.0,
        dimension_type=DimensionType.LINEAR,
        confidence=0.9,
        bounding_box=(110.0, 110.0, 40.0, 15.0)  # center at (130, 117.5), distance to line y=100 is 17.5px
    )
    features = EngineeringFeatures(
        line_features=[line],
        circle_features=[],
        relationships=[],
        bounding_information=BoundingInformation(bounding_box=(0, 0, 300, 300), width=300, height=300),
        summary={}
    )

    associations = associate_dimensions_with_geometry([dim], features)
    assert len(associations) == 1
    assoc = associations[0]
    assert assoc.dimension_id == "dim_1"
    assert assoc.feature_id == "line_1"
    assert assoc.association_type == AssociationType.LINE_DIMENSION
    assert assoc.distance == 17.5
    assert assoc.confidence > 0.6


def test_association_diameter_near_circle():
    circle = CircleFeature(
        id="circle_1",
        center_x=100.0,
        center_y=100.0,
        radius=25.0,
        diameter=50.0,
        likely_hole=True
    )
    dim = Dimension(
        id="dim_dia",
        raw_text="Ø50",
        value=50.0,
        dimension_type=DimensionType.DIAMETER,
        confidence=0.95,
        bounding_box=(90.0, 120.0, 30.0, 12.0)  # center (105, 126), dist to (100, 100) is sqrt(25+676) = 26.5
    )
    features = EngineeringFeatures(
        line_features=[],
        circle_features=[circle],
        relationships=[],
        bounding_information=BoundingInformation(bounding_box=(0, 0, 300, 300), width=300, height=300),
        summary={}
    )

    associations = associate_dimensions_with_geometry([dim], features)
    assert len(associations) == 1
    assoc = associations[0]
    assert assoc.dimension_id == "dim_dia"
    assert assoc.feature_id == "circle_1"
    assert assoc.association_type == AssociationType.CIRCLE_DIAMETER
    assert assoc.metadata is not None
    assert assoc.metadata.get("nominal_diameter_match") is True


def test_association_radius_near_circle():
    circle = CircleFeature(
        id="circle_fillet",
        center_x=80.0,
        center_y=80.0,
        radius=10.0,
        diameter=20.0,
        likely_hole=False
    )
    dim = Dimension(
        id="dim_r",
        raw_text="R10",
        value=10.0,
        dimension_type=DimensionType.RADIUS,
        confidence=0.95,
        bounding_box=(75.0, 85.0, 20.0, 10.0)  # center (85, 90)
    )
    features = EngineeringFeatures(
        line_features=[],
        circle_features=[circle],
        relationships=[],
        bounding_information=BoundingInformation(bounding_box=(0, 0, 300, 300), width=300, height=300),
        summary={}
    )

    associations = associate_dimensions_with_geometry([dim], features)
    assert len(associations) == 1
    assoc = associations[0]
    assert assoc.association_type == AssociationType.CIRCLE_RADIUS


def test_association_distant_unrelated_geometry():
    line = LineFeature(
        id="line_far",
        x1=10.0,
        y1=10.0,
        x2=50.0,
        y2=10.0,
        length=40.0,
        angle_degrees=0.0,
        orientation=LineOrientation.HORIZONTAL
    )
    dim = Dimension(
        id="dim_far",
        raw_text="50",
        value=50.0,
        dimension_type=DimensionType.LINEAR,
        confidence=0.9,
        bounding_box=(800.0, 800.0, 30.0, 10.0)
    )
    features = EngineeringFeatures(
        line_features=[line],
        circle_features=[],
        relationships=[],
        bounding_information=BoundingInformation(bounding_box=(0, 0, 1000, 1000), width=1000, height=1000),
        summary={}
    )

    associations = associate_dimensions_with_geometry([dim], features)
    assert len(associations) == 0


# 10. Preprocessing & OCR Abstraction Tests

def test_ocr_preprocessing_grayscale_output():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[40:60, 40:60] = 255  # white square
    preprocessed = preprocess_for_ocr(img, upscale_factor=1.5)
    assert len(preprocessed.shape) == 2
    assert preprocessed.shape[0] == 150
    assert preprocessed.shape[1] == 150


def test_mock_ocr_engine_returns_canned_results():
    canned = [
        OCRResult(id="1", text="Ø20", confidence=0.95, bounding_box=(10.0, 10.0, 30.0, 15.0))
    ]
    mock_engine = MockOCREngine(canned_results=canned)
    img = np.zeros((100, 100), dtype=np.uint8)
    results = mock_engine.recognize(img)
    assert len(results) == 1
    assert results[0].text == "Ø20"


def test_fallback_ocr_engine_empty_and_safe():
    fallback = FallbackOCREngine()
    assert fallback.is_available() is True
    img = np.zeros((100, 100), dtype=np.uint8)
    results = fallback.recognize(img)
    assert results == []


# 11. End-to-end Annotation Extractor

def test_extract_annotations_from_ocr_pipeline():
    ocr_items = [
        OCRResult(id="t1", text="50 ±0.02 mm", confidence=0.95, bounding_box=(100.0, 50.0, 60.0, 15.0)),
        OCRResult(id="t2", text="Ø20", confidence=0.90, bounding_box=(200.0, 200.0, 30.0, 15.0)),
        OCRResult(id="t3", text="TITLE BLOCK", confidence=0.85, bounding_box=(500.0, 500.0, 80.0, 20.0)),
    ]

    circle = CircleFeature(
        id="c1",
        center_x=205.0,
        center_y=205.0,
        radius=10.0,
        diameter=20.0,
        likely_hole=True
    )
    features = EngineeringFeatures(
        line_features=[],
        circle_features=[circle],
        relationships=[],
        bounding_information=BoundingInformation(bounding_box=(0, 0, 600, 600), width=600, height=600),
        summary={}
    )

    result = extract_annotations_from_ocr(ocr_items, features)
    assert isinstance(result, AnnotationsResult)
    assert len(result.ocr_results) == 3
    assert len(result.dimensions) == 2  # "50 ±0.02 mm" and "Ø20"
    assert len(result.symbols) >= 2     # "±" and "Ø"
    assert len(result.associations) == 1
    assert result.associations[0].association_type == AssociationType.CIRCLE_DIAMETER
    assert result.summary["total_dimensions"] == 2
    assert result.summary["associated_dimensions"] == 1


def test_extract_annotations_with_mock_engine():
    img = np.zeros((100, 100), dtype=np.uint8)
    mock_ocr = MockOCREngine([
        OCRResult(id="m1", text="45°", confidence=0.95, bounding_box=(20.0, 20.0, 25.0, 12.0))
    ])
    result = extract_annotations(img, ocr_engine=mock_ocr)
    assert len(result.dimensions) == 1
    assert result.dimensions[0].dimension_type == DimensionType.ANGULAR
    assert result.dimensions[0].value == 45.0
