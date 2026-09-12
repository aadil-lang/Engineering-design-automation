"""
Deterministic engineering feature rules for mechanical semantics.

These pure functions implement rule-based engineering logic to identify mechanical features
from low-level geometric primitives, relationships, and annotations.
"""

import math
from typing import List, Dict, Any, Optional, Tuple, Set
from core.models import (
    LineFeature,
    CircleFeature,
    GeometricRelationship,
    RelationshipType,
    LineOrientation,
    BoundingInformation
)
from annotations.models import (
    Dimension,
    DimensionType,
    GeometryAssociation,
    AssociationType,
    AnnotationsResult
)
from semantics.models import (
    MechanicalFeature,
    MechanicalFeatureType,
    SemanticEvidenceItem
)
from semantics.config import (
    HOLE_STRONG_CONFIDENCE,
    HOLE_CANDIDATE_CONFIDENCE,
    CIRCULAR_FEATURE_CONFIDENCE,
    PATTERN_MIN_HOLES,
    PATTERN_SPACING_TOLERANCE,
    PATTERN_DIAMETER_TOLERANCE,
    PATTERN_LINEAR_CONFIDENCE,
    PATTERN_CIRCULAR_CONFIDENCE,
    PATTERN_REPEATED_CONFIDENCE,
    PARALLEL_FEATURE_CONFIDENCE,
    PERPENDICULAR_FEATURE_CONFIDENCE,
    RECTANGLE_CORNER_TOLERANCE,
    RECTANGULAR_PLATE_CONFIDENCE,
    SLOT_ASPECT_RATIO_THRESHOLD,
    SLOT_CONFIDENCE,
    SHAFT_MIN_ASPECT_RATIO,
    SHAFT_CONFIDENCE,
    STEPPED_MIN_STEPS,
    STEPPED_AXIS_ALIGNMENT_TOLERANCE,
    STEPPED_FEATURE_CONFIDENCE,
    SYMMETRY_COORDINATE_TOLERANCE,
    SYMMETRY_CONFIDENCE
)


def evaluate_circle_semantics(
    circle: CircleFeature,
    associations: List[GeometryAssociation],
    dimensions_by_id: Dict[str, Dimension]
) -> MechanicalFeature:
    """
    Evaluates a single detected circle to classify it as:
    1. Strong hole (likely_hole + diameter/radius dimension)
    2. Hole candidate (likely_hole only)
    3. Circular feature (neither or insufficient evidence)
    """
    # Find associated diameter or radius dimensions
    associated_dims: List[Tuple[GeometryAssociation, Dimension]] = []
    for assoc in associations:
        if assoc.feature_id == circle.id and assoc.dimension_id in dimensions_by_id:
            dim = dimensions_by_id[assoc.dimension_id]
            is_diam_or_rad = (
                assoc.association_type in (AssociationType.CIRCLE_DIAMETER, AssociationType.CIRCLE_RADIUS)
                or dim.dimension_type in (DimensionType.DIAMETER, DimensionType.RADIUS)
                or "Ø" in dim.raw_text
                or "ø" in dim.raw_text
                or dim.raw_text.upper().startswith("R")
            )
            if is_diam_or_rad:
                associated_dims.append((assoc, dim))

    # Case 1: Strong hole evidence
    if circle.likely_hole and associated_dims:
        evidence: List[SemanticEvidenceItem] = [
            SemanticEvidenceItem(
                source_type="circle",
                source_id=circle.id,
                description=f"Detected circular geometry at ({round(circle.center_x, 1)}, {round(circle.center_y, 1)}) with diameter {round(circle.diameter, 2)}"
            )
        ]
        dim_texts = []
        dim_values = []
        for assoc, dim in associated_dims:
            evidence.append(
                SemanticEvidenceItem(
                    source_type="dimension",
                    source_id=dim.id,
                    description=f"Associated diameter/radius dimension callout: {dim.raw_text}"
                )
            )
            evidence.append(
                SemanticEvidenceItem(
                    source_type="association",
                    source_id=f"assoc_{circle.id}_{dim.id}",
                    description=f"Spatial association ({assoc.association_type.value}) at distance {round(assoc.distance, 1)}px"
                )
            )
            dim_texts.append(dim.raw_text)
            if dim.value is not None:
                dim_values.append(dim.value)

        return MechanicalFeature(
            id=f"mech_hole_{circle.id}",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=HOLE_STRONG_CONFIDENCE,
            evidence=evidence,
            reasoning_basis=(
                "Circular geometry has been identified as a likely hole candidate "
                "and is associated with a diameter dimension."
            ),
            uncertainties=[
                "Manufacturing intent cannot be confirmed from geometry alone."
            ],
            attributes={
                "center": (round(circle.center_x, 2), round(circle.center_y, 2)),
                "radius": round(circle.radius, 2),
                "diameter": round(circle.diameter, 2),
                "dimension_callout": dim_texts[0] if dim_texts else None,
                "dimension_value": dim_values[0] if dim_values else None,
                "classification_tier": "strong_hole"
            }
        )

    # Case 2: Candidate hole evidence (geometry satisfies hole conditions, lacks dimension)
    if circle.likely_hole:
        evidence = [
            SemanticEvidenceItem(
                source_type="circle",
                source_id=circle.id,
                description=f"Detected internal circular boundary at ({round(circle.center_x, 1)}, {round(circle.center_y, 1)})"
            )
        ]
        return MechanicalFeature(
            id=f"mech_hole_cand_{circle.id}",
            feature_type=MechanicalFeatureType.HOLE,
            confidence=HOLE_CANDIDATE_CONFIDENCE,
            evidence=evidence,
            reasoning_basis=(
                "Circular geometry satisfies geometric candidate conditions for a hole "
                "(closed internal circular boundary), but lacks confirming dimension annotation."
            ),
            uncertainties=[
                "Candidate hole lacks associated diameter or radius dimension callout.",
                "Manufacturing intent cannot be confirmed from geometry alone."
            ],
            attributes={
                "center": (round(circle.center_x, 2), round(circle.center_y, 2)),
                "radius": round(circle.radius, 2),
                "diameter": round(circle.diameter, 2),
                "classification_tier": "candidate_hole"
            }
        )

    # Case 3: Insufficient hole evidence -> Circular Feature
    evidence = [
        SemanticEvidenceItem(
            source_type="circle",
            source_id=circle.id,
            description=f"Detected circular geometry at ({round(circle.center_x, 1)}, {round(circle.center_y, 1)}) with diameter {round(circle.diameter, 2)}"
        )
    ]
    # Check if any dimension is attached even if not marked likely_hole
    for assoc in associations:
        if assoc.feature_id == circle.id and assoc.dimension_id in dimensions_by_id:
            dim = dimensions_by_id[assoc.dimension_id]
            evidence.append(
                SemanticEvidenceItem(
                    source_type="dimension",
                    source_id=dim.id,
                    description=f"Nearby dimension: {dim.raw_text}"
                )
            )

    return MechanicalFeature(
        id=f"mech_circ_{circle.id}",
        feature_type=MechanicalFeatureType.CIRCULAR_FEATURE,
        confidence=CIRCULAR_FEATURE_CONFIDENCE,
        evidence=evidence,
        reasoning_basis=(
            "Detected circular geometry does not exhibit sufficient evidence to be classified as a hole; "
            "classified conservatively as a circular feature."
        ),
        uncertainties=[
            "Ambiguous mechanical role (could represent external boss, cylindrical pin, curved profile, or decorative element)."
        ],
        attributes={
            "center": (round(circle.center_x, 2), round(circle.center_y, 2)),
            "radius": round(circle.radius, 2),
            "diameter": round(circle.diameter, 2),
            "classification_tier": "circular_feature"
        }
    )


def detect_hole_patterns(holes: List[MechanicalFeature]) -> List[MechanicalFeature]:
    """
    Detects simple hole patterns among recognized holes:
    - Linear hole patterns (horizontal, vertical, or collinear)
    - Circular/radial hole patterns (bolt circles)
    - Repeated circular-feature patterns (conservative cluster)
    """
    if len(holes) < PATTERN_MIN_HOLES:
        return []

    patterns: List[MechanicalFeature] = []
    visited_ids: Set[str] = set()

    # Group holes with similar diameter
    groups: List[List[MechanicalFeature]] = []
    for hole in holes:
        h_diam = hole.attributes.get("diameter", 0.0)
        placed = False
        for grp in groups:
            grp_diam = grp[0].attributes.get("diameter", 0.0)
            if abs(h_diam - grp_diam) <= PATTERN_DIAMETER_TOLERANCE:
                grp.append(hole)
                placed = True
                break
        if not placed:
            groups.append([hole])

    pattern_counter = 0
    for grp in groups:
        if len(grp) < PATTERN_MIN_HOLES:
            continue

        member_ids = [h.id for h in grp]
        centers = [h.attributes.get("center", (0.0, 0.0)) for h in grp]
        diam = grp[0].attributes.get("diameter", 0.0)

        # 1. Check Horizontal Linear Alignment (constant Y)
        y_coords = [c[1] for c in centers]
        is_horiz = (max(y_coords) - min(y_coords)) <= PATTERN_SPACING_TOLERANCE

        # 2. Check Vertical Linear Alignment (constant X)
        x_coords = [c[0] for c in centers]
        is_vert = (max(x_coords) - min(x_coords)) <= PATTERN_SPACING_TOLERANCE

        evidence_items = [
            SemanticEvidenceItem(
                source_type="hole",
                source_id=h.id,
                description=f"Pattern member hole {h.id} at ({round(c[0], 1)}, {round(c[1], 1)})"
            )
            for h, c in zip(grp, centers)
        ]

        if is_horiz:
            # Sort by X
            sorted_by_x = sorted(zip(centers, grp), key=lambda item: item[0][0])
            spacings = [
                sorted_by_x[i+1][0][0] - sorted_by_x[i][0][0]
                for i in range(len(sorted_by_x) - 1)
            ]
            avg_spacing = sum(spacings) / len(spacings) if spacings else 0.0
            is_evenly_spaced = (max(spacings) - min(spacings)) <= PATTERN_SPACING_TOLERANCE if spacings else False

            patterns.append(
                MechanicalFeature(
                    id=f"mech_pattern_{pattern_counter}",
                    feature_type=MechanicalFeatureType.HOLE_PATTERN,
                    confidence=PATTERN_LINEAR_CONFIDENCE,
                    evidence=evidence_items,
                    reasoning_basis=(
                        f"Detected {len(grp)} holes of similar diameter ({round(diam, 1)}) "
                        f"horizontally aligned{' with consistent center spacing' if is_evenly_spaced else ''}."
                    ),
                    uncertainties=[
                        "Pattern inferred from 2D geometric alignment; drawing lacks explicit group manufacturing callout (e.g. 'Nx ØD')."
                    ],
                    attributes={
                        "pattern_type": "linear_horizontal",
                        "member_ids": member_ids,
                        "count": len(grp),
                        "spacing": round(avg_spacing, 2) if is_evenly_spaced else None,
                        "diameter": round(diam, 2)
                    }
                )
            )
            pattern_counter += 1
            visited_ids.update(member_ids)
            continue

        if is_vert:
            # Sort by Y
            sorted_by_y = sorted(zip(centers, grp), key=lambda item: item[0][1])
            spacings = [
                sorted_by_y[i+1][0][1] - sorted_by_y[i][0][1]
                for i in range(len(sorted_by_y) - 1)
            ]
            avg_spacing = sum(spacings) / len(spacings) if spacings else 0.0
            is_evenly_spaced = (max(spacings) - min(spacings)) <= PATTERN_SPACING_TOLERANCE if spacings else False

            patterns.append(
                MechanicalFeature(
                    id=f"mech_pattern_{pattern_counter}",
                    feature_type=MechanicalFeatureType.HOLE_PATTERN,
                    confidence=PATTERN_LINEAR_CONFIDENCE,
                    evidence=evidence_items,
                    reasoning_basis=(
                        f"Detected {len(grp)} holes of similar diameter ({round(diam, 1)}) "
                        f"vertically aligned{' with consistent center spacing' if is_evenly_spaced else ''}."
                    ),
                    uncertainties=[
                        "Pattern inferred from 2D geometric alignment; drawing lacks explicit group manufacturing callout."
                    ],
                    attributes={
                        "pattern_type": "linear_vertical",
                        "member_ids": member_ids,
                        "count": len(grp),
                        "spacing": round(avg_spacing, 2) if is_evenly_spaced else None,
                        "diameter": round(diam, 2)
                    }
                )
            )
            pattern_counter += 1
            visited_ids.update(member_ids)
            continue

        # 3. Check Radial / Bolt-Circle Pattern (>= 3 holes)
        if len(grp) >= 3:
            cx = sum(c[0] for c in centers) / len(centers)
            cy = sum(c[1] for c in centers) / len(centers)
            radii = [math.hypot(c[0] - cx, c[1] - cy) for c in centers]
            avg_r = sum(radii) / len(radii)
            r_variance = max(radii) - min(radii)

            if r_variance <= PATTERN_SPACING_TOLERANCE and avg_r > 10.0:
                patterns.append(
                    MechanicalFeature(
                        id=f"mech_pattern_{pattern_counter}",
                        feature_type=MechanicalFeatureType.HOLE_PATTERN,
                        confidence=PATTERN_CIRCULAR_CONFIDENCE,
                        evidence=evidence_items,
                        reasoning_basis=(
                            f"Detected {len(grp)} holes of similar diameter arranged radially "
                            f"along a common pitch circle of diameter {round(2 * avg_r, 1)}px."
                        ),
                        uncertainties=[
                            "Radial hole pattern inferred from geometric distribution; pitch circle diameter (PCD) callout unverified."
                        ],
                        attributes={
                            "pattern_type": "circular_radial",
                            "member_ids": member_ids,
                            "count": len(grp),
                            "pitch_circle_diameter": round(2 * avg_r, 2),
                            "diameter": round(diam, 2)
                        }
                    )
                )
                pattern_counter += 1
                visited_ids.update(member_ids)
                continue

            # 4. Conservative fallback for 3+ similar circles without alignment
            patterns.append(
                MechanicalFeature(
                    id=f"mech_pattern_{pattern_counter}",
                    feature_type=MechanicalFeatureType.HOLE_PATTERN,
                    confidence=PATTERN_REPEATED_CONFIDENCE,
                    evidence=evidence_items,
                    reasoning_basis=(
                        f"possible repeated circular-feature pattern: identified {len(grp)} "
                        f"circular features of similar diameter ({round(diam, 1)}) without linear or radial alignment."
                    ),
                    uncertainties=[
                        "Possible repeated circular-feature pattern; lacking spatial alignment or common pitch circle to confirm manufacturing hole pattern."
                    ],
                    attributes={
                        "pattern_type": "repeated_hole_pattern",
                        "member_ids": member_ids,
                        "count": len(grp),
                        "diameter": round(diam, 2)
                    }
                )
            )
            pattern_counter += 1
            visited_ids.update(member_ids)

    return patterns


def detect_relational_features(
    relationships: List[GeometricRelationship]
) -> List[MechanicalFeature]:
    """
    Translates geometric relationships (parallel, perpendicular) into explicit mechanical features.
    """
    rel_features: List[MechanicalFeature] = []
    idx = 0

    for rel in relationships:
        if rel.relationship_type == RelationshipType.PARALLEL:
            evidence = [
                SemanticEvidenceItem(
                    source_type="line",
                    source_id=rel.source_id,
                    description=f"First parallel line boundary ({rel.source_id})"
                ),
                SemanticEvidenceItem(
                    source_type="line",
                    source_id=rel.target_id,
                    description=f"Second parallel line boundary ({rel.target_id})"
                ),
                SemanticEvidenceItem(
                    source_type="relationship",
                    source_id=f"rel_{rel.source_id}_{rel.target_id}",
                    description="Geometric parallel relationship"
                )
            ]
            rel_features.append(
                MechanicalFeature(
                    id=f"mech_parallel_{idx}",
                    feature_type=MechanicalFeatureType.PARALLEL_FEATURE,
                    confidence=PARALLEL_FEATURE_CONFIDENCE,
                    evidence=evidence,
                    reasoning_basis=(
                        "Geometry engine identified the two line features as parallel "
                        "within the configured angular tolerance."
                    ),
                    uncertainties=[
                        "Parallelism derived from 2D vector angles; toleranced datum relationship unconfirmed."
                    ],
                    attributes={
                        "source_line_id": rel.source_id,
                        "target_line_id": rel.target_id,
                        "metadata": rel.metadata
                    }
                )
            )
            idx += 1

        elif rel.relationship_type == RelationshipType.PERPENDICULAR:
            evidence = [
                SemanticEvidenceItem(
                    source_type="line",
                    source_id=rel.source_id,
                    description=f"First perpendicular line boundary ({rel.source_id})"
                ),
                SemanticEvidenceItem(
                    source_type="line",
                    source_id=rel.target_id,
                    description=f"Second perpendicular line boundary ({rel.target_id})"
                ),
                SemanticEvidenceItem(
                    source_type="relationship",
                    source_id=f"rel_{rel.source_id}_{rel.target_id}",
                    description="Geometric perpendicular relationship"
                )
            ]
            rel_features.append(
                MechanicalFeature(
                    id=f"mech_perp_{idx}",
                    feature_type=MechanicalFeatureType.PERPENDICULAR_FEATURE,
                    confidence=PERPENDICULAR_FEATURE_CONFIDENCE,
                    evidence=evidence,
                    reasoning_basis=(
                        "Geometry engine identified the two line features as perpendicular "
                        "within the configured angular tolerance."
                    ),
                    uncertainties=[
                        "Perpendicularity derived from 2D vector angles; toleranced datum relationship unconfirmed."
                    ],
                    attributes={
                        "source_line_id": rel.source_id,
                        "target_line_id": rel.target_id,
                        "metadata": rel.metadata
                    }
                )
            )
            idx += 1

    return rel_features


def detect_rectangular_plates(
    line_features: List[LineFeature],
    bounding_info: Optional[BoundingInformation] = None
) -> List[MechanicalFeature]:
    """
    Conservative recognizer for rectangular plates:
    Requires four major boundary edges (~2 horizontal, ~2 vertical) forming an enclosed loop.
    """
    plates: List[MechanicalFeature] = []
    if len(line_features) < 4:
        return plates

    horizontals = [lf for lf in line_features if lf.orientation == LineOrientation.HORIZONTAL]
    verticals = [lf for lf in line_features if lf.orientation == LineOrientation.VERTICAL]

    if len(horizontals) < 2 or len(verticals) < 2:
        return plates

    # Sort horizontals by Y (top, bottom)
    horiz_sorted = sorted(horizontals, key=lambda l: (l.y1 + l.y2) / 2.0)
    top_line = horiz_sorted[0]
    bottom_line = horiz_sorted[-1]

    # Sort verticals by X (left, right)
    vert_sorted = sorted(verticals, key=lambda l: (l.x1 + l.x2) / 2.0)
    left_line = vert_sorted[0]
    right_line = vert_sorted[-1]

    # Check that they represent distinct opposite lines
    y_dist = abs((bottom_line.y1 + bottom_line.y2) / 2.0 - (top_line.y1 + top_line.y2) / 2.0)
    x_dist = abs((right_line.x1 + right_line.x2) / 2.0 - (left_line.x1 + left_line.x2) / 2.0)

    if y_dist < 20.0 or x_dist < 20.0:
        return plates

    # Verify corner proximity
    top_x_min = min(top_line.x1, top_line.x2)
    top_x_max = max(top_line.x1, top_line.x2)
    bottom_x_min = min(bottom_line.x1, bottom_line.x2)
    bottom_x_max = max(bottom_line.x1, bottom_line.x2)

    left_y_min = min(left_line.y1, left_line.y2)
    left_y_max = max(left_line.y1, left_line.y2)
    right_y_min = min(right_line.y1, right_line.y2)
    right_y_max = max(right_line.y1, right_line.y2)

    left_x = (left_line.x1 + left_line.x2) / 2.0
    right_x = (right_line.x1 + right_line.x2) / 2.0
    top_y = (top_line.y1 + top_line.y2) / 2.0
    bottom_y = (bottom_line.y1 + bottom_line.y2) / 2.0

    # Opposite edge alignment checks
    tol = RECTANGLE_CORNER_TOLERANCE
    corner_alignment_ok = (
        abs(top_x_min - left_x) <= tol
        and abs(top_x_max - right_x) <= tol
        and abs(bottom_x_min - left_x) <= tol
        and abs(bottom_x_max - right_x) <= tol
        and abs(left_y_min - top_y) <= tol
        and abs(left_y_max - bottom_y) <= tol
        and abs(right_y_min - top_y) <= tol
        and abs(right_y_max - bottom_y) <= tol
    )

    if not corner_alignment_ok:
        return plates

    width = round(x_dist, 2)
    height = round(y_dist, 2)
    aspect_ratio = round(width / height if height > 0 else 1.0, 2)

    evidence = [
        SemanticEvidenceItem(source_type="line", source_id=top_line.id, description=f"Top boundary edge ({top_line.id})"),
        SemanticEvidenceItem(source_type="line", source_id=bottom_line.id, description=f"Bottom boundary edge ({bottom_line.id})"),
        SemanticEvidenceItem(source_type="line", source_id=left_line.id, description=f"Left boundary edge ({left_line.id})"),
        SemanticEvidenceItem(source_type="line", source_id=right_line.id, description=f"Right boundary edge ({right_line.id})"),
    ]

    plates.append(
        MechanicalFeature(
            id="mech_plate_0",
            feature_type=MechanicalFeatureType.RECTANGULAR_PLATE,
            confidence=RECTANGULAR_PLATE_CONFIDENCE,
            evidence=evidence,
            reasoning_basis=(
                "Geometric boundary consists of four orthogonal edge segments forming a closed rectangular profile; "
                "interpreted conservatively as a rectangular plate candidate."
            ),
            uncertainties=[
                "Geometric interpretation only; does not confirm physical manufacturing intent, plate thickness, or 3D form.",
                "Plate stock or machined block material specification not established from 2D geometry alone."
            ],
            attributes={
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "boundary_line_ids": [top_line.id, bottom_line.id, left_line.id, right_line.id]
            }
        )
    )
    return plates


def detect_slots(
    line_features: List[LineFeature],
    relationships: List[GeometricRelationship],
    circle_features: List[CircleFeature]
) -> List[MechanicalFeature]:
    """
    Conservative slot recognizer:
    Identifies two approximately parallel elongated lines connected or bounded
    by rounded ends or circular geometry with aspect ratio >= SLOT_ASPECT_RATIO_THRESHOLD.
    """
    slots: List[MechanicalFeature] = []
    lines_by_id = {lf.id: lf for lf in line_features}

    # Find parallel pairs
    parallel_pairs: List[Tuple[LineFeature, LineFeature]] = []
    for rel in relationships:
        if rel.relationship_type == RelationshipType.PARALLEL:
            if rel.source_id in lines_by_id and rel.target_id in lines_by_id:
                parallel_pairs.append((lines_by_id[rel.source_id], lines_by_id[rel.target_id]))

    slot_counter = 0
    for l1, l2 in parallel_pairs:
        avg_len = (l1.length + l2.length) / 2.0
        # Determine separation distance
        mid1 = ((l1.x1 + l1.x2) / 2.0, (l1.y1 + l1.y2) / 2.0)
        mid2 = ((l2.x1 + l2.x2) / 2.0, (l2.y1 + l2.y2) / 2.0)
        dist = math.hypot(mid1[0] - mid2[0], mid1[1] - mid2[1])

        if dist < 4.0:
            continue

        aspect_ratio = avg_len / dist
        if aspect_ratio < SLOT_ASPECT_RATIO_THRESHOLD:
            continue

        # Look for rounded ends: circles or semicircles with diameter close to dist near the ends
        end_evidence: List[SemanticEvidenceItem] = []
        target_radius = dist / 2.0

        for cf in circle_features:
            # Check if circle radius matches slot width / 2
            if abs(cf.radius - target_radius) <= 6.0:
                # Check proximity to either end of the lines
                c_pos = (cf.center_x, cf.center_y)
                d_end1 = min(
                    math.hypot(c_pos[0] - l1.x1, c_pos[1] - l1.y1),
                    math.hypot(c_pos[0] - l1.x2, c_pos[1] - l1.y2)
                )
                d_end2 = min(
                    math.hypot(c_pos[0] - l2.x1, c_pos[1] - l2.y1),
                    math.hypot(c_pos[0] - l2.x2, c_pos[1] - l2.y2)
                )
                if d_end1 <= dist or d_end2 <= dist:
                    end_evidence.append(
                        SemanticEvidenceItem(
                            source_type="circle",
                            source_id=cf.id,
                            description=f"Rounded end geometry matching slot width (radius {round(cf.radius, 1)})"
                        )
                    )

        # Conservative criteria: must have rounded end evidence to claim slot
        if not end_evidence:
            continue

        evidence = [
            SemanticEvidenceItem(source_type="line", source_id=l1.id, description=f"First slot boundary edge ({l1.id})"),
            SemanticEvidenceItem(source_type="line", source_id=l2.id, description=f"Second slot boundary edge ({l2.id})"),
            *end_evidence
        ]

        slots.append(
            MechanicalFeature(
                id=f"mech_slot_{slot_counter}",
                feature_type=MechanicalFeatureType.SLOT,
                confidence=SLOT_CONFIDENCE,
                evidence=evidence,
                reasoning_basis=(
                    "Detected two elongated parallel boundaries with rounded end geometry "
                    "consistent with a machined slot profile."
                ),
                uncertainties=[
                    "Machined slot geometry inferred from 2D profile; end milling or keyway intent unconfirmed.",
                    "Slot depth and bottom contour cannot be determined without cross-sectional view."
                ],
                attributes={
                    "length": round(avg_len, 2),
                    "width": round(dist, 2),
                    "aspect_ratio": round(aspect_ratio, 2),
                    "boundary_line_ids": [l1.id, l2.id]
                }
            )
        )
        slot_counter += 1

    return slots


def detect_shafts_and_stepped(
    line_features: List[LineFeature],
    relationships: List[GeometricRelationship],
    annotations: Optional[AnnotationsResult] = None
) -> List[MechanicalFeature]:
    """
    Conservative 2D recognizer for shaft sections and stepped features.
    Identifies elongated parallel boundaries associated with diameter callouts
    or coaxial stepped boundaries along a common axis.
    """
    results: List[MechanicalFeature] = []
    lines_by_id = {lf.id: lf for lf in line_features}

    dims = annotations.dimensions if annotations else []
    assocs = annotations.associations if annotations else []

    # Map dimensions with diameter symbols
    diam_dims = {
        d.id: d for d in dims
        if d.dimension_type == DimensionType.DIAMETER or "Ø" in d.raw_text or "ø" in d.raw_text
    }

    # Find parallel pairs
    parallel_pairs: List[Tuple[LineFeature, LineFeature]] = []
    for rel in relationships:
        if rel.relationship_type == RelationshipType.PARALLEL:
            if rel.source_id in lines_by_id and rel.target_id in lines_by_id:
                parallel_pairs.append((lines_by_id[rel.source_id], lines_by_id[rel.target_id]))

    shaft_counter = 0
    candidate_shaft_segments: List[Dict[str, Any]] = []

    for l1, l2 in parallel_pairs:
        avg_len = (l1.length + l2.length) / 2.0
        mid1 = ((l1.x1 + l1.x2) / 2.0, (l1.y1 + l1.y2) / 2.0)
        mid2 = ((l2.x1 + l2.x2) / 2.0, (l2.y1 + l2.y2) / 2.0)
        dist = math.hypot(mid1[0] - mid2[0], mid1[1] - mid2[1])

        if dist < 5.0:
            continue

        aspect_ratio = avg_len / dist
        if aspect_ratio < SHAFT_MIN_ASPECT_RATIO:
            continue

        # Check for diameter dimension associated with either line
        associated_diam_dim: Optional[Dimension] = None
        for a in assocs:
            if (a.feature_id in (l1.id, l2.id)) and a.dimension_id in diam_dims:
                associated_diam_dim = diam_dims[a.dimension_id]
                break

        # A shaft candidate in 2D requires elongated parallel lines AND a diameter dimension callout
        if associated_diam_dim:
            evidence = [
                SemanticEvidenceItem(source_type="line", source_id=l1.id, description=f"Shaft longitudinal boundary ({l1.id})"),
                SemanticEvidenceItem(source_type="line", source_id=l2.id, description=f"Shaft longitudinal boundary ({l2.id})"),
                SemanticEvidenceItem(source_type="dimension", source_id=associated_diam_dim.id, description=f"Associated diameter callout: {associated_diam_dim.raw_text}")
            ]
            axis_mid = ((mid1[0] + mid2[0]) / 2.0, (mid1[1] + mid2[1]) / 2.0)
            axis_orientation = "horizontal" if l1.orientation == LineOrientation.HORIZONTAL else "vertical"

            feature = MechanicalFeature(
                id=f"mech_shaft_{shaft_counter}",
                feature_type=MechanicalFeatureType.SHAFT,
                confidence=SHAFT_CONFIDENCE,
                evidence=evidence,
                reasoning_basis=(
                    "Detected parallel longitudinal boundary lines associated with a diameter callout, "
                    "suggesting a cylindrical shaft section in 2D projection."
                ),
                uncertainties=[
                    "2D projection interpretation; cannot confirm 3D cylindrical geometry without section or orthogonal view correlation.",
                    "May represent a flat rectangular bar or prismatic rail rather than a turned shaft."
                ],
                attributes={
                    "length": round(avg_len, 2),
                    "diameter": round(dist, 2),
                    "dimension_value": associated_diam_dim.value,
                    "axis_orientation": axis_orientation,
                    "boundary_line_ids": [l1.id, l2.id]
                }
            )
            results.append(feature)
            candidate_shaft_segments.append({
                "feature_id": feature.id,
                "lines": (l1, l2),
                "width": dist,
                "length": avg_len,
                "axis_mid": axis_mid,
                "axis_orientation": axis_orientation
            })
            shaft_counter += 1

    # Detect stepped features (multiple aligned shaft/cylindrical segments along a common axis)
    if len(candidate_shaft_segments) >= STEPPED_MIN_STEPS:
        # Group segments by shared axis orientation and centerline alignment
        horiz_segs = [s for s in candidate_shaft_segments if s["axis_orientation"] == "horizontal"]
        vert_segs = [s for s in candidate_shaft_segments if s["axis_orientation"] == "vertical"]

        for seg_group in (horiz_segs, vert_segs):
            if len(seg_group) >= STEPPED_MIN_STEPS:
                # Check centerline alignment
                if seg_group[0]["axis_orientation"] == "horizontal":
                    axis_coords = [s["axis_mid"][1] for s in seg_group]
                else:
                    axis_coords = [s["axis_mid"][0] for s in seg_group]

                axis_aligned = (max(axis_coords) - min(axis_coords)) <= STEPPED_AXIS_ALIGNMENT_TOLERANCE
                widths = [s["width"] for s in seg_group]
                distinct_widths = len(set(round(w, 0) for w in widths)) > 1

                if axis_aligned and distinct_widths:
                    evidence_items = []
                    member_line_ids = []
                    for s in seg_group:
                        l1, l2 = s["lines"]
                        member_line_ids.extend([l1.id, l2.id])
                        evidence_items.append(
                            SemanticEvidenceItem(
                                source_type="shaft_step",
                                source_id=s["feature_id"],
                                description=f"Stepped section (width {round(s['width'], 1)}, length {round(s['length'], 1)})"
                            )
                        )

                    results.append(
                        MechanicalFeature(
                            id="mech_stepped_0",
                            feature_type=MechanicalFeatureType.STEPPED_FEATURE,
                            confidence=STEPPED_FEATURE_CONFIDENCE,
                            evidence=evidence_items,
                            reasoning_basis=(
                                "Detected multiple aligned coaxial segments with stepped widths/diameters along a shared central axis."
                            ),
                            uncertainties=[
                                "Stepped profile interpreted from 2D projection; stepped shaft, counterbore, or shoulder intent requires multi-view verification."
                            ],
                            attributes={
                                "step_count": len(seg_group),
                                "diameters_or_widths": [round(w, 2) for w in widths],
                                "axis_orientation": seg_group[0]["axis_orientation"],
                                "boundary_line_ids": member_line_ids
                            }
                        )
                    )

    return results


def detect_symmetry(
    line_features: List[LineFeature],
    circle_features: List[CircleFeature],
    bounding_info: Optional[BoundingInformation] = None
) -> List[MechanicalFeature]:
    """
    Detects simple geometric symmetry (bilateral reflection across horizontal or vertical axis).
    Uses detected geometry rather than image pixels.
    """
    symmetry_features: List[MechanicalFeature] = []

    # Determine reference center coordinate
    if bounding_info:
        bbox = bounding_info.bounding_box
        cx = bbox[0] + bbox[2] / 2.0
        cy = bbox[1] + bbox[3] / 2.0
    elif line_features or circle_features:
        all_x = [lf.x1 for lf in line_features] + [lf.x2 for lf in line_features] + [cf.center_x for cf in circle_features]
        all_y = [lf.y1 for lf in line_features] + [lf.y2 for lf in line_features] + [cf.center_y for cf in circle_features]
        cx = (min(all_x) + max(all_x)) / 2.0
        cy = (min(all_y) + max(all_y)) / 2.0
    else:
        return symmetry_features

    tol = SYMMETRY_COORDINATE_TOLERANCE

    # --- Vertical Axis Symmetry (reflection across x = cx) ---
    vert_sym_pairs: List[Tuple[str, str]] = []
    # Circle pairs
    for i in range(len(circle_features)):
        for j in range(i + 1, len(circle_features)):
            c1, c2 = circle_features[i], circle_features[j]
            if abs(c1.radius - c2.radius) <= 4.0:
                if abs(c1.center_y - c2.center_y) <= tol:
                    mid_x = (c1.center_x + c2.center_x) / 2.0
                    if abs(mid_x - cx) <= tol:
                        vert_sym_pairs.append((c1.id, c2.id))

    # Vertical line pairs
    vert_lines = [lf for lf in line_features if lf.orientation == LineOrientation.VERTICAL]
    for i in range(len(vert_lines)):
        for j in range(i + 1, len(vert_lines)):
            l1, l2 = vert_lines[i], vert_lines[j]
            if abs(l1.length - l2.length) <= tol:
                mid_x = ((l1.x1 + l1.x2) / 2.0 + (l2.x1 + l2.x2) / 2.0) / 2.0
                if abs(mid_x - cx) <= tol:
                    vert_sym_pairs.append((l1.id, l2.id))

    if len(vert_sym_pairs) >= 2:
        evidence = [
            SemanticEvidenceItem(
                source_type="symmetric_pair",
                source_id=f"{p1}_{p2}",
                description=f"Mirrored geometric features ({p1}, {p2}) equidistant from vertical centerline"
            )
            for p1, p2 in vert_sym_pairs
        ]
        symmetry_features.append(
            MechanicalFeature(
                id="mech_sym_vertical",
                feature_type=MechanicalFeatureType.SYMMETRIC_FEATURE,
                confidence=SYMMETRY_CONFIDENCE,
                evidence=evidence,
                reasoning_basis=(
                    "Geometric elements exhibit bilateral symmetry across the drawing's vertical axis within spatial tolerance."
                ),
                uncertainties=[
                    "Geometric symmetry identified in 2D projection; drawing does not explicitly specify a symmetry center line (CL) symbol."
                ],
                attributes={
                    "axis": "vertical",
                    "centerline_x": round(cx, 2),
                    "symmetric_pair_count": len(vert_sym_pairs),
                    "member_pairs": vert_sym_pairs
                }
            )
        )

    # --- Horizontal Axis Symmetry (reflection across y = cy) ---
    horiz_sym_pairs: List[Tuple[str, str]] = []
    for i in range(len(circle_features)):
        for j in range(i + 1, len(circle_features)):
            c1, c2 = circle_features[i], circle_features[j]
            if abs(c1.radius - c2.radius) <= 4.0:
                if abs(c1.center_x - c2.center_x) <= tol:
                    mid_y = (c1.center_y + c2.center_y) / 2.0
                    if abs(mid_y - cy) <= tol:
                        horiz_sym_pairs.append((c1.id, c2.id))

    horiz_lines = [lf for lf in line_features if lf.orientation == LineOrientation.HORIZONTAL]
    for i in range(len(horiz_lines)):
        for j in range(i + 1, len(horiz_lines)):
            l1, l2 = horiz_lines[i], horiz_lines[j]
            if abs(l1.length - l2.length) <= tol:
                mid_y = ((l1.y1 + l1.y2) / 2.0 + (l2.y1 + l2.y2) / 2.0) / 2.0
                if abs(mid_y - cy) <= tol:
                    horiz_sym_pairs.append((l1.id, l2.id))

    if len(horiz_sym_pairs) >= 2:
        evidence = [
            SemanticEvidenceItem(
                source_type="symmetric_pair",
                source_id=f"{p1}_{p2}",
                description=f"Mirrored geometric features ({p1}, {p2}) equidistant from horizontal centerline"
            )
            for p1, p2 in horiz_sym_pairs
        ]
        symmetry_features.append(
            MechanicalFeature(
                id="mech_sym_horizontal",
                feature_type=MechanicalFeatureType.SYMMETRIC_FEATURE,
                confidence=SYMMETRY_CONFIDENCE,
                evidence=evidence,
                reasoning_basis=(
                    "Geometric elements exhibit bilateral symmetry across the drawing's horizontal axis within spatial tolerance."
                ),
                uncertainties=[
                    "Geometric symmetry identified in 2D projection; drawing does not explicitly specify a symmetry center line (CL) symbol."
                ],
                attributes={
                    "axis": "horizontal",
                    "centerline_y": round(cy, 2),
                    "symmetric_pair_count": len(horiz_sym_pairs),
                    "member_pairs": horiz_sym_pairs
                }
            )
        )

    return symmetry_features
