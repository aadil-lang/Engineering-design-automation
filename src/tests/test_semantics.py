"""
Comprehensive tests for Slice 6: Mechanical Engineering Semantic Interpretation.
Tests deterministic feature recognition, explainability, conservative classifications,
API integration, and reasoning context consumption.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from core.models import (
    ImageMetadata,
    Line,
    Circle,
    Contour,
    LineFeature,
    CircleFeature,
    LineOrientation,
    GeometricRelationship,
    RelationshipType,
    BoundingInformation,
    EngineeringFeatures,
    AnalyzeResponse
)
from annotations.models import (
    Dimension,
    DimensionType,
    GeometryAssociation,
    AssociationType,
    AnnotationsResult
)
from semantics.models import (
    MechanicalFeatureType,
    MechanicalFeature,
    MechanicalSemanticsResult
)
from semantics.feature_rules import (
    evaluate_circle_semantics,
    detect_hole_patterns,
    detect_relational_features,
    detect_rectangular_plates,
    detect_slots,
    detect_shafts_and_stepped,
    detect_symmetry
)
from semantics.extractor import (
    MechanicalSemanticExtractor,
    extract_mechanical_semantics
)
from reasoning.context import (
    build_drawing_context,
    select_context_for_question
)
from reasoning.models import QuestionType


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Circle & Hole Classification Tests
# ---------------------------------------------------------------------------

def test_circle_to_circular_feature_without_evidence():
    """A detected circle without likely_hole and without diameter dimension is a circular_feature."""
    cf = CircleFeature(
        id="circle_0",
        center_x=100.0,
        center_y=100.0,
        radius=25.0,
        diameter=50.0,
        likely_hole=False
    )
    feature = evaluate_circle_semantics(cf, associations=[], dimensions_by_id={})

    assert feature.feature_type == MechanicalFeatureType.CIRCULAR_FEATURE
    assert feature.confidence == 0.60
    assert feature.attributes["diameter"] == 50.0
    assert feature.attributes["center"] == (100.0, 100.0)
    assert feature.attributes["classification_tier"] == "circular_feature"
    assert len(feature.evidence) >= 1
    assert "circular feature" in feature.reasoning_basis.lower()
    assert len(feature.uncertainties) > 0


def test_circle_likely_hole_to_hole_candidate():
    """A circle marked likely_hole without diameter callout is classified as a hole candidate."""
    cf = CircleFeature(
        id="circle_cand",
        center_x=150.0,
        center_y=150.0,
        radius=10.0,
        diameter=20.0,
        likely_hole=True
    )
    feature = evaluate_circle_semantics(cf, associations=[], dimensions_by_id={})

    assert feature.feature_type == MechanicalFeatureType.HOLE
    assert feature.confidence == 0.75
    assert feature.attributes["classification_tier"] == "candidate_hole"
    assert "candidate" in feature.reasoning_basis.lower()
    assert any("lacks" in u.lower() for u in feature.uncertainties)


def test_circle_with_diameter_dimension_to_strong_hole():
    """A circle marked likely_hole with an associated diameter dimension is classified as a strong hole."""
    cf = CircleFeature(
        id="circle_strong",
        center_x=200.0,
        center_y=200.0,
        radius=15.0,
        diameter=30.0,
        likely_hole=True
    )
    dim = Dimension(
        id="dim_diam_1",
        raw_text="Ø30",
        value=30.0,
        unit="mm",
        dimension_type=DimensionType.DIAMETER,
        confidence=0.95
    )
    assoc = GeometryAssociation(
        dimension_id="dim_diam_1",
        feature_id="circle_strong",
        association_type=AssociationType.CIRCLE_DIAMETER,
        distance=8.5,
        confidence=0.9
    )

    feature = evaluate_circle_semantics(
        cf,
        associations=[assoc],
        dimensions_by_id={dim.id: dim}
    )

    assert feature.feature_type == MechanicalFeatureType.HOLE
    assert feature.confidence == 0.92
    assert feature.attributes["classification_tier"] == "strong_hole"
    assert feature.attributes["dimension_value"] == 30.0
    assert len(feature.evidence) == 3  # circle, dimension, association
    # Verify reasoning basis matches prompt requirement
    assert "likely hole candidate" in feature.reasoning_basis
    assert "diameter dimension" in feature.reasoning_basis


def test_conservative_non_hole_classification():
    """Conservative test: An external or ambiguous circle must NOT be promoted to a hole."""
    cf = CircleFeature(
        id="circle_boss",
        center_x=300.0,
        center_y=100.0,
        radius=40.0,
        diameter=80.0,
        likely_hole=False
    )
    feature = evaluate_circle_semantics(cf, associations=[], dimensions_by_id={})
    assert feature.feature_type != MechanicalFeatureType.HOLE
    assert feature.feature_type == MechanicalFeatureType.CIRCULAR_FEATURE


# ---------------------------------------------------------------------------
# 2. Hole Pattern Tests
# ---------------------------------------------------------------------------

def test_linear_horizontal_hole_pattern():
    """Identifies horizontally aligned holes with consistent spacing as a linear hole pattern."""
    holes = [
        MechanicalFeature(
            id="hole_1",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (100.0, 200.0), "diameter": 12.0}
        ),
        MechanicalFeature(
            id="hole_2",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (150.0, 200.0), "diameter": 12.0}
        ),
        MechanicalFeature(
            id="hole_3",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (200.0, 200.0), "diameter": 12.0}
        )
    ]
    patterns = detect_hole_patterns(holes)

    assert len(patterns) == 1
    p = patterns[0]
    assert p.feature_type == MechanicalFeatureType.HOLE_PATTERN
    assert p.attributes["pattern_type"] == "linear_horizontal"
    assert p.attributes["count"] == 3
    assert p.attributes["spacing"] == 50.0
    assert len(p.attributes["member_ids"]) == 3
    assert p.confidence == 0.88
    assert "horizontally aligned" in p.reasoning_basis


def test_linear_vertical_hole_pattern():
    """Identifies vertically aligned holes as a linear hole pattern."""
    holes = [
        MechanicalFeature(
            id="hole_v1",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (250.0, 80.0), "diameter": 16.0}
        ),
        MechanicalFeature(
            id="hole_v2",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (250.0, 140.0), "diameter": 16.0}
        )
    ]
    patterns = detect_hole_patterns(holes)

    assert len(patterns) == 1
    assert patterns[0].attributes["pattern_type"] == "linear_vertical"
    assert patterns[0].attributes["count"] == 2
    assert patterns[0].attributes["spacing"] == 60.0


def test_circular_radial_hole_pattern():
    """Identifies holes arranged along a common pitch circle as a circular radial pattern."""
    # 4 holes on a circle of radius 50 centered at (200, 200)
    holes = [
        MechanicalFeature(
            id="h_rad_0",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (250.0, 200.0), "diameter": 10.0}
        ),
        MechanicalFeature(
            id="h_rad_1",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (200.0, 250.0), "diameter": 10.0}
        ),
        MechanicalFeature(
            id="h_rad_2",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (150.0, 200.0), "diameter": 10.0}
        ),
        MechanicalFeature(
            id="h_rad_3",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (200.0, 150.0), "diameter": 10.0}
        )
    ]
    patterns = detect_hole_patterns(holes)

    assert len(patterns) == 1
    assert patterns[0].attributes["pattern_type"] == "circular_radial"
    assert patterns[0].attributes["count"] == 4
    assert abs(patterns[0].attributes["pitch_circle_diameter"] - 100.0) < 2.0


def test_repeated_holes_cluster_conservative_pattern():
    """Multiple similar holes without strict alignment are classified conservatively as repeated patterns."""
    holes = [
        MechanicalFeature(
            id="h_arb_1",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (50.0, 60.0), "diameter": 14.0}
        ),
        MechanicalFeature(
            id="h_arb_2",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (120.0, 190.0), "diameter": 14.0}
        ),
        MechanicalFeature(
            id="h_arb_3",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=0.9,
            reasoning_basis="Test hole",
            attributes={"center": (270.0, 85.0), "diameter": 14.0}
        )
    ]
    patterns = detect_hole_patterns(holes)

    assert len(patterns) == 1
    assert patterns[0].attributes["pattern_type"] == "repeated_hole_pattern"
    assert "possible repeated circular-feature pattern" in patterns[0].reasoning_basis


# ---------------------------------------------------------------------------
# 3. Parallel & Perpendicular Semantics Tests
# ---------------------------------------------------------------------------

def test_parallel_feature_recognition():
    """Translates geometric parallel relationships into explicit parallel_features."""
    rel = GeometricRelationship(
        source_id="line_1",
        target_id="line_2",
        relationship_type=RelationshipType.PARALLEL,
        metadata={"angle_diff": 0.5}
    )
    features = detect_relational_features([rel])

    assert len(features) == 1
    feat = features[0]
    assert feat.feature_type == MechanicalFeatureType.PARALLEL_FEATURE
    assert feat.confidence == 0.85
    assert feat.attributes["source_line_id"] == "line_1"
    assert feat.attributes["target_line_id"] == "line_2"
    assert "parallel within the configured angular tolerance" in feat.reasoning_basis
    assert len(feat.evidence) == 3


def test_perpendicular_feature_recognition():
    """Translates geometric perpendicular relationships into explicit perpendicular_features."""
    rel = GeometricRelationship(
        source_id="line_a",
        target_id="line_b",
        relationship_type=RelationshipType.PERPENDICULAR,
        metadata={"angle_diff": 89.8}
    )
    features = detect_relational_features([rel])

    assert len(features) == 1
    feat = features[0]
    assert feat.feature_type == MechanicalFeatureType.PERPENDICULAR_FEATURE
    assert feat.confidence == 0.85
    assert feat.attributes["source_line_id"] == "line_a"
    assert feat.attributes["target_line_id"] == "line_b"
    assert "perpendicular within the configured angular tolerance" in feat.reasoning_basis


# ---------------------------------------------------------------------------
# 4. Rectangular Plate Recognition Tests
# ---------------------------------------------------------------------------

def test_rectangular_plate_recognition():
    """Four connected orthogonal boundary edges are recognized as a rectangular_plate candidate."""
    lines = [
        LineFeature(id="l_top", x1=50.0, y1=50.0, x2=250.0, y2=50.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL),
        LineFeature(id="l_bottom", x1=50.0, y1=150.0, x2=250.0, y2=150.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL),
        LineFeature(id="l_left", x1=50.0, y1=50.0, x2=50.0, y2=150.0, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL),
        LineFeature(id="l_right", x1=250.0, y1=50.0, x2=250.0, y2=150.0, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    ]
    plates = detect_rectangular_plates(lines)

    assert len(plates) == 1
    p = plates[0]
    assert p.feature_type == MechanicalFeatureType.RECTANGULAR_PLATE
    assert p.attributes["width"] == 200.0
    assert p.attributes["height"] == 100.0
    assert p.attributes["aspect_ratio"] == 2.0
    assert "rectangular plate candidate" in p.reasoning_basis
    assert any("does not confirm physical manufacturing intent" in u for u in p.uncertainties)


def test_rectangular_plate_conservative_rejection():
    """Fewer than 4 orthogonal lines or open shapes are not classified as plates."""
    lines = [
        LineFeature(id="l1", x1=50.0, y1=50.0, x2=250.0, y2=50.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL),
        LineFeature(id="l2", x1=50.0, y1=150.0, x2=250.0, y2=150.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL),
        LineFeature(id="l3", x1=50.0, y1=50.0, x2=50.0, y2=150.0, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    ]
    plates = detect_rectangular_plates(lines)
    assert len(plates) == 0


# ---------------------------------------------------------------------------
# 5. Slot Recognition Tests
# ---------------------------------------------------------------------------

def test_slot_recognition_positive():
    """Elongated parallel boundaries flanked by rounded ends are recognized as a slot."""
    l1 = LineFeature(id="slot_top", x1=100.0, y1=80.0, x2=200.0, y2=80.0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="slot_bottom", x1=100.0, y1=110.0, x2=200.0, y2=110.0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel = GeometricRelationship(source_id=l1.id, target_id=l2.id, relationship_type=RelationshipType.PARALLEL)

    # End semicircles/circles with radius matching slot width / 2 = 15.0
    c_end = CircleFeature(id="c_end", center_x=100.0, center_y=95.0, radius=15.0, diameter=30.0, likely_hole=False)

    slots = detect_slots([l1, l2], [rel], [c_end])
    assert len(slots) == 1
    s = slots[0]
    assert s.feature_type == MechanicalFeatureType.SLOT
    assert s.attributes["length"] == 100.0
    assert abs(s.attributes["width"] - 30.0) < 1.0
    assert s.attributes["aspect_ratio"] >= 1.8
    assert "slot profile" in s.reasoning_basis.lower()


def test_slot_recognition_conservative_rejection():
    """Parallel lines without rounded ends or with low aspect ratio must NOT be classified as slots."""
    l1 = LineFeature(id="l1", x1=100.0, y1=80.0, x2=130.0, y2=80.0, length=30.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="l2", x1=100.0, y1=110.0, x2=130.0, y2=110.0, length=30.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel = GeometricRelationship(source_id=l1.id, target_id=l2.id, relationship_type=RelationshipType.PARALLEL)

    # Aspect ratio = 30 / 30 = 1.0 < 1.8 threshold, no end circles
    slots = detect_slots([l1, l2], [rel], [])
    assert len(slots) == 0


# ---------------------------------------------------------------------------
# 6. Shaft & Stepped Feature Tests
# ---------------------------------------------------------------------------

def test_shaft_recognition_positive():
    """Elongated parallel lines associated with a diameter dimension are recognized as a shaft."""
    l1 = LineFeature(id="s_top", x1=50.0, y1=100.0, x2=250.0, y2=100.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="s_bottom", x1=50.0, y1=140.0, x2=250.0, y2=140.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel = GeometricRelationship(source_id=l1.id, target_id=l2.id, relationship_type=RelationshipType.PARALLEL)

    dim = Dimension(id="dim_shaft", raw_text="Ø40", value=40.0, dimension_type=DimensionType.DIAMETER, confidence=0.9)
    assoc = GeometryAssociation(dimension_id="dim_shaft", feature_id=l1.id, association_type=AssociationType.LINE_DIMENSION, distance=10.0, confidence=0.9)
    ann = AnnotationsResult(dimensions=[dim], associations=[assoc])

    features = detect_shafts_and_stepped([l1, l2], [rel], ann)
    shafts = [f for f in features if f.feature_type == MechanicalFeatureType.SHAFT]

    assert len(shafts) == 1
    s = shafts[0]
    assert s.attributes["length"] == 200.0
    assert abs(s.attributes["diameter"] - 40.0) < 1.0
    assert "cylindrical shaft section" in s.reasoning_basis


def test_shaft_conservative_rejection_without_diameter_dim():
    """Parallel lines without a diameter dimension must NOT be classified as a shaft."""
    l1 = LineFeature(id="s_top", x1=50.0, y1=100.0, x2=250.0, y2=100.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="s_bottom", x1=50.0, y1=140.0, x2=250.0, y2=140.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel = GeometricRelationship(source_id=l1.id, target_id=l2.id, relationship_type=RelationshipType.PARALLEL)

    features = detect_shafts_and_stepped([l1, l2], [rel], None)
    shafts = [f for f in features if f.feature_type == MechanicalFeatureType.SHAFT]
    assert len(shafts) == 0


def test_stepped_feature_recognition():
    """Coaxial shaft segments with distinct diameters along a common axis are recognized as a stepped feature."""
    # Step 1: Ø50, Length 100
    s1_top = LineFeature(id="s1_t", x1=50.0, y1=100.0, x2=150.0, y2=100.0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    s1_bot = LineFeature(id="s1_b", x1=50.0, y1=150.0, x2=150.0, y2=150.0, length=100.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel1 = GeometricRelationship(source_id="s1_t", target_id="s1_b", relationship_type=RelationshipType.PARALLEL)

    # Step 2: Ø30, Length 120 (centered on same Y axis mid = 125)
    s2_top = LineFeature(id="s2_t", x1=150.0, y1=110.0, x2=270.0, y2=110.0, length=120.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    s2_bot = LineFeature(id="s2_b", x1=150.0, y1=140.0, x2=270.0, y2=140.0, length=120.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    rel2 = GeometricRelationship(source_id="s2_t", target_id="s2_b", relationship_type=RelationshipType.PARALLEL)

    dim1 = Dimension(id="d1", raw_text="Ø50", value=50.0, dimension_type=DimensionType.DIAMETER, confidence=0.9)
    dim2 = Dimension(id="d2", raw_text="Ø30", value=30.0, dimension_type=DimensionType.DIAMETER, confidence=0.9)
    a1 = GeometryAssociation(dimension_id="d1", feature_id="s1_t", association_type=AssociationType.LINE_DIMENSION, distance=5.0, confidence=0.9)
    a2 = GeometryAssociation(dimension_id="d2", feature_id="s2_t", association_type=AssociationType.LINE_DIMENSION, distance=5.0, confidence=0.9)

    ann = AnnotationsResult(dimensions=[dim1, dim2], associations=[a1, a2])

    features = detect_shafts_and_stepped([s1_top, s1_bot, s2_top, s2_bot], [rel1, rel2], ann)
    stepped = [f for f in features if f.feature_type == MechanicalFeatureType.STEPPED_FEATURE]

    assert len(stepped) == 1
    assert stepped[0].attributes["step_count"] == 2
    assert "coaxial segments with stepped widths/diameters" in stepped[0].reasoning_basis


# ---------------------------------------------------------------------------
# 7. Symmetry Tests
# ---------------------------------------------------------------------------

def test_symmetry_vertical_axis():
    """Identifies bilateral symmetry across the vertical centerline."""
    binfo = BoundingInformation(bounding_box=(0.0, 0.0, 400.0, 300.0), width=400.0, height=300.0)  # cx = 200, cy = 150

    # Symmetric circles mirrored across x = 200: (120, 150) and (280, 150)
    c1 = CircleFeature(id="c_l", center_x=120.0, center_y=150.0, radius=20.0, diameter=40.0, likely_hole=True)
    c2 = CircleFeature(id="c_r", center_x=280.0, center_y=150.0, radius=20.0, diameter=40.0, likely_hole=True)

    # Symmetric vertical lines: x=100 and x=300
    l1 = LineFeature(id="vl_1", x1=100.0, y1=50.0, x2=100.0, y2=250.0, length=200.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    l2 = LineFeature(id="vl_2", x1=300.0, y1=50.0, x2=300.0, y2=250.0, length=200.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)

    sym = detect_symmetry([l1, l2], [c1, c2], binfo)
    assert len(sym) >= 1
    vert_sym = [s for s in sym if s.attributes["axis"] == "vertical"]
    assert len(vert_sym) == 1
    assert vert_sym[0].attributes["centerline_x"] == 200.0
    assert "vertical axis within spatial tolerance" in vert_sym[0].reasoning_basis


def test_symmetry_horizontal_axis():
    """Identifies bilateral symmetry across the horizontal centerline."""
    binfo = BoundingInformation(bounding_box=(0.0, 0.0, 400.0, 300.0), width=400.0, height=300.0)  # cy = 150

    c1 = CircleFeature(id="c_top", center_x=200.0, center_y=80.0, radius=15.0, diameter=30.0, likely_hole=True)
    c2 = CircleFeature(id="c_bot", center_x=200.0, center_y=220.0, radius=15.0, diameter=30.0, likely_hole=True)

    l1 = LineFeature(id="hl_1", x1=50.0, y1=60.0, x2=350.0, y2=60.0, length=300.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="hl_2", x1=50.0, y1=240.0, x2=350.0, y2=240.0, length=300.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)

    sym = detect_symmetry([l1, l2], [c1, c2], binfo)
    horiz_sym = [s for s in sym if s.attributes["axis"] == "horizontal"]
    assert len(horiz_sym) == 1
    assert horiz_sym[0].attributes["centerline_y"] == 150.0


# ---------------------------------------------------------------------------
# 8. Full Extractor & Explainability Tests
# ---------------------------------------------------------------------------

def test_full_semantic_extractor_and_explainability():
    """Verifies that the extractor orchestrates all rules and outputs full explainability fields."""
    cf1 = CircleFeature(id="c1", center_x=100.0, center_y=100.0, radius=10.0, diameter=20.0, likely_hole=True)
    cf2 = CircleFeature(id="c2", center_x=160.0, center_y=100.0, radius=10.0, diameter=20.0, likely_hole=True)
    l1 = LineFeature(id="l1", x1=50.0, y1=50.0, x2=250.0, y2=50.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l2 = LineFeature(id="l2", x1=50.0, y1=150.0, x2=250.0, y2=150.0, length=200.0, angle_degrees=0.0, orientation=LineOrientation.HORIZONTAL)
    l3 = LineFeature(id="l3", x1=50.0, y1=50.0, x2=50.0, y2=150.0, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    l4 = LineFeature(id="l4", x1=250.0, y1=50.0, x2=250.0, y2=150.0, length=100.0, angle_degrees=90.0, orientation=LineOrientation.VERTICAL)
    rel = GeometricRelationship(source_id="l1", target_id="l2", relationship_type=RelationshipType.PARALLEL)
    binfo = BoundingInformation(bounding_box=(50.0, 50.0, 200.0, 100.0), width=200.0, height=100.0)

    dim = Dimension(id="d_diam", raw_text="Ø20", value=20.0, dimension_type=DimensionType.DIAMETER, confidence=0.95)
    assoc = GeometryAssociation(dimension_id="d_diam", feature_id="c1", association_type=AssociationType.CIRCLE_DIAMETER, distance=5.0, confidence=0.9)

    ef = EngineeringFeatures(
        line_features=[l1, l2, l3, l4],
        circle_features=[cf1, cf2],
        relationships=[rel],
        bounding_information=binfo,
        summary={"total_lines": 4, "total_circles": 2}
    )
    ann = AnnotationsResult(dimensions=[dim], associations=[assoc])

    result = extract_mechanical_semantics(ef, ann)

    assert isinstance(result, MechanicalSemanticsResult)
    assert len(result.features) > 0
    assert result.summary["total_features"] == len(result.features)
    assert "holes_count" in result.summary
    assert "feature_counts" in result.summary

    # Verify explainability on every single feature
    for f in result.features:
        assert 0.0 <= f.confidence <= 1.0
        assert f.reasoning_basis is not None and len(f.reasoning_basis) > 5
        assert isinstance(f.evidence, list)
        assert len(f.evidence) >= 1
        for ev in f.evidence:
            assert ev.source_type
            assert ev.source_id
            assert ev.description
        assert isinstance(f.uncertainties, list)
        assert len(f.uncertainties) >= 1  # Mandatory engineering caveat


# ---------------------------------------------------------------------------
# 9. API Integration Tests
# ---------------------------------------------------------------------------

def test_api_analyze_contains_mechanical_semantics():
    """Tests that POST /analyze returns mechanical_semantics while preserving Slice 1-3 fields."""
    import io
    import cv2
    import numpy as np

    # Generate a dummy synthetic drawing in-memory
    img = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.circle(img, (200, 150), 30, (0, 0, 0), 2)
    cv2.rectangle(img, (50, 50), (350, 250), (0, 0, 0), 2)
    success, encoded = cv2.imencode(".png", img)
    assert success

    response = client.post(
        "/analyze",
        files={"file": ("test_drawing.png", io.BytesIO(encoded.tobytes()), "image/png")}
    )
    assert response.status_code == 200
    data = response.json()

    # Slice 1-3 backward compatibility
    assert "image" in data
    assert "lines" in data
    assert "circles" in data
    assert "contours" in data
    assert "engineering_features" in data
    assert "annotations" in data

    # Slice 6 integration
    assert "mechanical_semantics" in data
    ms = data["mechanical_semantics"]
    assert "features" in ms
    assert "summary" in ms
    assert "warnings" in ms


# ---------------------------------------------------------------------------
# 10. Reasoning Context Integration Tests
# ---------------------------------------------------------------------------

def test_reasoning_drawing_context_consumes_mechanical_semantics():
    """Verifies that DrawingContext and select_context_for_question consume mechanical semantics."""
    hole_feature = MechanicalFeature(
        id="hole_test",
        feature_type=MechanicalFeatureType.HOLE,
        confidence=0.92,
        evidence=[],
        reasoning_basis="Test hole reasoning",
        attributes={"diameter": 20.0}
    )
    parallel_feature = MechanicalFeature(
        id="parallel_test",
        feature_type=MechanicalFeatureType.PARALLEL_FEATURE,
        confidence=0.85,
        evidence=[],
        reasoning_basis="Test parallel reasoning",
        attributes={"source_line_id": "l1", "target_line_id": "l2"}
    )
    plate_feature = MechanicalFeature(
        id="plate_test",
        feature_type=MechanicalFeatureType.RECTANGULAR_PLATE,
        confidence=0.80,
        evidence=[],
        reasoning_basis="Test plate reasoning",
        attributes={"width": 200.0, "height": 100.0}
    )

    ms = MechanicalSemanticsResult(
        features=[hole_feature, parallel_feature, plate_feature],
        summary={"total_features": 3, "holes_count": 1},
        warnings=[]
    )

    resp = AnalyzeResponse(
        image=ImageMetadata(width=400, height=300),
        lines=[],
        circles=[],
        contours=[],
        mechanical_semantics=ms
    )

    context = build_drawing_context(resp)
    assert len(context.mechanical_features) == 3

    # Question Type: HOLE_ANALYSIS receives only hole features
    hole_ctx = select_context_for_question(context, QuestionType.HOLE_ANALYSIS)
    assert "mechanical_features" in hole_ctx
    assert len(hole_ctx["mechanical_features"]) == 1
    assert hole_ctx["mechanical_features"][0]["feature_type"] == "hole"

    # Question Type: RELATIONSHIP_ANALYSIS receives only relational features
    rel_ctx = select_context_for_question(context, QuestionType.RELATIONSHIP_ANALYSIS)
    assert "mechanical_features" in rel_ctx
    assert len(rel_ctx["mechanical_features"]) == 1
    assert rel_ctx["mechanical_features"][0]["feature_type"] == "parallel_feature"

    # Question Type: GEOMETRY_SUMMARY receives plate feature
    geom_ctx = select_context_for_question(context, QuestionType.GEOMETRY_SUMMARY)
    assert "mechanical_features" in geom_ctx
    geom_types = [f["feature_type"] for f in geom_ctx["mechanical_features"]]
    assert "rectangular_plate" in geom_types

    # Question Type: GENERAL_ENGINEERING_QUESTION receives all mechanical features
    gen_ctx = select_context_for_question(context, QuestionType.GENERAL_ENGINEERING_QUESTION)
    assert len(gen_ctx["mechanical_features"]) == 3
