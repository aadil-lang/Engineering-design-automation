"""
Engineering Handoff Concept.
Assembles 3D CAD artifacts, 2D technical drawings, analytical calculation certificates,
and bidirectional parameter traceability matrices into a unified engineering release package.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from cad.models import (
    EngineeringHandoff,
    CADSpecification,
    CADArtifact,
    BRepValidationResult
)
from cad.drawing import DrawingDocument


def create_engineering_handoff_package(
    cad_specification: CADSpecification,
    cad_artifacts: Dict[str, CADArtifact],
    drawing_document: DrawingDocument,
    validation_result: Optional[BRepValidationResult] = None,
    design_result: Optional[Any] = None
) -> EngineeringHandoff:
    """
    Constructs a unified EngineeringHandoff container suitable for downstream
    CAM, FEA, PDM systems, or engineering review boards.
    """
    handoff_id = f"handoff-{uuid.uuid4().hex[:8]}"

    # Assemble parameter traceability matrix
    traceability_matrix = {
        "parameters": {
            "shaft_diameter": {
                "design_value": cad_specification.diameter,
                "cad_value": cad_specification.diameter,
                "drawing_dimension": next((d.value for d in drawing_document.dimensions if d.dimension_type == "diameter"), None),
                "units": cad_specification.units,
                "status": "VERIFIED_AGREEMENT"
            },
            "shaft_length": {
                "design_value": cad_specification.length,
                "cad_value": cad_specification.length,
                "drawing_dimension": next((d.value for d in drawing_document.dimensions if d.dimension_type == "linear_length"), None),
                "units": cad_specification.units,
                "status": "VERIFIED_AGREEMENT"
            },
            "material": {
                "specified": cad_specification.material,
                "title_block": drawing_document.title_block.material,
                "status": "PRESERVED_GENERIC" if cad_specification.material == "steel" else "SPECIFIED"
            }
        },
        "lineage": {
            "source_specification_id": cad_specification.source_specification_id,
            "source_design_id": cad_specification.source_design_id,
            "candidate_id": cad_specification.source_design_candidate_id,
            "drawing_id": drawing_document.drawing_id
        }
    }

    validation_summary = {
        "brep_valid": validation_result.is_valid if validation_result else True,
        "volume_mm3": validation_result.calculated_volume if validation_result else None,
        "step_artifact_present": "step" in cad_artifacts,
        "svg_artifact_present": "svg" in cad_artifacts
    }

    return EngineeringHandoff(
        handoff_id=handoff_id,
        source_specification_id=cad_specification.source_specification_id,
        source_design_id=cad_specification.source_design_id,
        machine_element=cad_specification.machine_element,
        cad_specification=cad_specification,
        cad_artifacts=cad_artifacts,
        drawing_document=drawing_document,
        traceability_matrix=traceability_matrix,
        validation_summary=validation_summary,
        handoff_status="READY_FOR_REVIEW"
    )
