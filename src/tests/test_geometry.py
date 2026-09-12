import pytest
from core.models import Line, Circle, LineFeature, LineOrientation, ImageMetadata, Contour
from geometry.features import classify_orientation, normalize_angle, derive_line_features, derive_circle_features
from geometry.relationships import is_parallel, is_perpendicular, are_endpoints_connected, extract_relationships
from geometry.extractor import calculate_bounding_information, extract_engineering_features

def test_normalize_angle():
    assert normalize_angle(10.0) == 10.0
    assert normalize_angle(190.0) == 10.0
    assert normalize_angle(-10.0) == 170.0
    assert normalize_angle(360.0) == 0.0
    assert normalize_angle(-180.0) == 0.0

def test_classify_orientation():
    assert classify_orientation(0.0) == LineOrientation.HORIZONTAL
    assert classify_orientation(4.0) == LineOrientation.HORIZONTAL
    assert classify_orientation(176.0) == LineOrientation.HORIZONTAL
    
    assert classify_orientation(90.0) == LineOrientation.VERTICAL
    assert classify_orientation(86.0) == LineOrientation.VERTICAL
    assert classify_orientation(94.0) == LineOrientation.VERTICAL
    
    assert classify_orientation(45.0) == LineOrientation.DIAGONAL
    assert classify_orientation(135.0) == LineOrientation.DIAGONAL

def test_derive_line_features():
    lines = [
        Line(x1=0, y1=0, x2=100, y2=0, length=100.0, angle=0.0),
        Line(x1=0, y1=0, x2=0, y2=100, length=100.0, angle=90.0),
        Line(x1=0, y1=0, x2=100, y2=100, length=141.4, angle=45.0)
    ]
    features = derive_line_features(lines)
    assert len(features) == 3
    assert features[0].orientation == LineOrientation.HORIZONTAL
    assert features[1].orientation == LineOrientation.VERTICAL
    assert features[2].orientation == LineOrientation.DIAGONAL

def test_derive_circle_features():
    circles = [
        Circle(center_x=10, center_y=10, radius=1.0),   # Too small
        Circle(center_x=50, center_y=50, radius=10.0),  # Likely hole
        Circle(center_x=100, center_y=100, radius=100.0) # Too large
    ]
    features = derive_circle_features(circles)
    assert len(features) == 3
    assert not features[0].likely_hole
    assert features[1].likely_hole
    assert not features[2].likely_hole
    assert features[1].diameter == 20.0

def test_is_parallel():
    assert is_parallel(10.0, 12.0)
    assert is_parallel(2.0, 179.0) # 2.0 and -1.0 (179.0) differ by 3.0 degrees
    assert not is_parallel(10.0, 20.0)

def test_is_perpendicular():
    assert is_perpendicular(0.0, 90.0)
    assert is_perpendicular(5.0, 93.0)
    assert is_perpendicular(175.0, 85.0)
    assert not is_perpendicular(10.0, 110.0)

def test_are_endpoints_connected():
    l1 = LineFeature(id="1", x1=0, y1=0, x2=100, y2=0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="2", x1=98, y1=2, x2=100, y2=100, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    l3 = LineFeature(id="3", x1=200, y1=200, x2=300, y2=300, length=141.4, angle_degrees=45.0, orientation=LineOrientation.DIAGONAL)
    
    assert are_endpoints_connected(l1, l2) # Connected (distance = 2.82 < 10.0)
    assert not are_endpoints_connected(l1, l3)

def test_extract_relationships():
    lines = [
        LineFeature(id="1", x1=0, y1=0, x2=100, y2=0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL),
        LineFeature(id="2", x1=0, y1=0, x2=0, y2=100, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL),
        LineFeature(id="3", x1=0, y1=10, x2=100, y2=10, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    ]
    rels = extract_relationships(lines)
    
    types = [r.relationship_type for r in rels]
    assert "parallel" in types
    assert "perpendicular" in types
    assert "connected" in types
    
    assert len(rels) >= 3

def test_calculate_bounding_information():
    img_meta = ImageMetadata(width=500, height=500)
    contours = [
        Contour(area=100, perimeter=40, bounding_box=(10.0, 10.0, 50.0, 50.0)),
        Contour(area=100, perimeter=40, bounding_box=(200.0, 200.0, 50.0, 50.0))
    ]
    bounds = calculate_bounding_information(img_meta, contours)
    assert bounds.bounding_box == (10.0, 10.0, 240.0, 240.0)
    assert bounds.width == 240.0
    assert bounds.height == 240.0

def test_calculate_bounding_information_empty():
    img_meta = ImageMetadata(width=500, height=500)
    bounds = calculate_bounding_information(img_meta, [])
    assert bounds.bounding_box == (0.0, 0.0, 500.0, 500.0)

def test_zero_length_line():
    lines = [Line(x1=0, y1=0, x2=0, y2=0, length=0.0, angle=0.0)]
    features = derive_line_features(lines)
    assert len(features) == 1
    assert features[0].length == 0.0

def test_extract_engineering_features():
    img_meta = ImageMetadata(width=500, height=500)
    lines = [Line(x1=0, y1=0, x2=100, y2=0, length=100.0, angle=0.0)]
    circles = [Circle(center_x=50, center_y=50, radius=10.0)]
    contours = []
    
    res = extract_engineering_features(lines, circles, contours, img_meta)
    
    assert len(res.line_features) == 1
    assert len(res.circle_features) == 1
    assert res.summary["total_line_features"] == 1
    assert res.summary["hole_candidates"] == 1
