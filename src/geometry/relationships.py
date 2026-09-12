import math
from typing import List, Tuple
from core.models import LineFeature, GeometricRelationship, RelationshipType
from geometry.config import PARALLEL_TOLERANCE_DEG, PERPENDICULAR_TOLERANCE_DEG, CONNECTION_DISTANCE_TOLERANCE

def is_parallel(angle1: float, angle2: float) -> bool:
    """Check if two normalized angles are parallel within tolerance."""
    diff = abs(angle1 - angle2)
    return diff <= PARALLEL_TOLERANCE_DEG or diff >= (180.0 - PARALLEL_TOLERANCE_DEG)

def is_perpendicular(angle1: float, angle2: float) -> bool:
    """Check if two normalized angles are perpendicular within tolerance."""
    diff = abs(angle1 - angle2)
    return abs(diff - 90.0) <= PERPENDICULAR_TOLERANCE_DEG

def are_endpoints_connected(l1: LineFeature, l2: LineFeature) -> bool:
    """Check if any endpoint of l1 is within tolerance to any endpoint of l2."""
    points1 = [(l1.x1, l1.y1), (l1.x2, l1.y2)]
    points2 = [(l2.x1, l2.y1), (l2.x2, l2.y2)]
    
    for p1 in points1:
        for p2 in points2:
            dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            if dist <= CONNECTION_DISTANCE_TOLERANCE:
                return True
    return False

def extract_relationships(lines: List[LineFeature]) -> List[GeometricRelationship]:
    """Extract geometric relationships between a list of line features."""
    relationships = []
    n = len(lines)
    
    for i in range(n):
        for j in range(i + 1, n):
            l1 = lines[i]
            l2 = lines[j]
            
            # Parallel check
            if is_parallel(l1.angle_degrees, l2.angle_degrees):
                relationships.append(GeometricRelationship(
                    source_id=l1.id,
                    target_id=l2.id,
                    relationship_type=RelationshipType.PARALLEL
                ))
            
            # Perpendicular check
            if is_perpendicular(l1.angle_degrees, l2.angle_degrees):
                relationships.append(GeometricRelationship(
                    source_id=l1.id,
                    target_id=l2.id,
                    relationship_type=RelationshipType.PERPENDICULAR
                ))
                
            # Connection check
            if are_endpoints_connected(l1, l2):
                relationships.append(GeometricRelationship(
                    source_id=l1.id,
                    target_id=l2.id,
                    relationship_type=RelationshipType.CONNECTED
                ))
                
    return relationships
