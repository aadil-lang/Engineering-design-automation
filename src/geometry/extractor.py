from typing import List, Tuple
from core.models import Line, Circle, Contour, ImageMetadata, EngineeringFeatures, BoundingInformation
from geometry.features import derive_line_features, derive_circle_features
from geometry.relationships import extract_relationships

def calculate_bounding_information(img_meta: ImageMetadata, contours: List[Contour]) -> BoundingInformation:
    """Calculate overall bounding information for the detected drawing."""
    if not contours:
        return BoundingInformation(
            bounding_box=(0.0, 0.0, float(img_meta.width), float(img_meta.height)),
            width=float(img_meta.width),
            height=float(img_meta.height)
        )
        
    min_x = min([c.bounding_box[0] for c in contours])
    min_y = min([c.bounding_box[1] for c in contours])
    max_x = max([c.bounding_box[0] + c.bounding_box[2] for c in contours])
    max_y = max([c.bounding_box[1] + c.bounding_box[3] for c in contours])
    
    w = max_x - min_x
    h = max_y - min_y
    
    return BoundingInformation(
        bounding_box=(float(min_x), float(min_y), float(w), float(h)),
        width=float(w),
        height=float(h)
    )

def extract_engineering_features(
    lines: List[Line], 
    circles: List[Circle], 
    contours: List[Contour], 
    img_meta: ImageMetadata
) -> EngineeringFeatures:
    """
    Main service function to transform CV primitives into higher-level engineering features.
    """
    # Extract feature primitives
    line_features = derive_line_features(lines)
    circle_features = derive_circle_features(circles)
    
    # Extract relationships between primitives
    relationships = extract_relationships(line_features)
    
    # Compute bounding information
    bounding_info = calculate_bounding_information(img_meta, contours)
    
    # Summary statistics
    summary = {
        "total_line_features": len(line_features),
        "total_circle_features": len(circle_features),
        "total_relationships": len(relationships),
        "hole_candidates": sum(1 for c in circle_features if c.likely_hole)
    }
    
    return EngineeringFeatures(
        line_features=line_features,
        circle_features=circle_features,
        relationships=relationships,
        bounding_information=bounding_info,
        summary=summary
    )
