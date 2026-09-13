"""
CAD Generator Master Orchestrator.
Coordinates BRep solid generation, ISO-10303-21 STEP export, 2D drawing derivation,
SVG rendering, and dimensional cross-validation against design requirements.
"""

import os
import math
from typing import Optional, Dict, Any, List

from cad.interfaces import CADBackend
from cad.backend import OpenCascadeBackend
from cad.models import (
    CADSpecification,
    CADArtifact,
    CADStatus,
    BRepValidationResult,
    CADGenerationResponse
)
from cad.drawing import DrawingDocument
from cad.exporters import DrawingExporter, SVGRenderer
from cad.shaft import build_shaft_cad_specification
from cad.config import (
    DEFAULT_CAD_ARTIFACT_DIR,
    DEFAULT_DRAWING_ARTIFACT_DIR,
    DRAWING_TOLERANCE_MM
)
from cad.report import generate_cad_report
from design_engine.models import DesignResult
from design_engine.designer import design_from_problem_statement


class CADGenerator:
    """
    Parametric CAD and Engineering Drawing orchestrator.
    Translates validated mechanical designs into verified 3D solid geometry and 2D engineering drawings.
    """

    def __init__(
        self,
        backend: Optional[CADBackend] = None,
        drawing_exporter: Optional[DrawingExporter] = None
    ):
        self.backend = backend or OpenCascadeBackend()
        self.drawing_exporter = drawing_exporter or DrawingExporter()

    def generate(
        self,
        spec: CADSpecification,
        output_dir: Optional[str] = None
    ) -> CADGenerationResponse:
        """
        Synthesizes 3D solid model, exports STEP, derives 2D drawing, renders SVG,
        and cross-validates drawing dimensions against CAD parameters.
        """
        out_cad_dir = os.path.join(output_dir or ".", DEFAULT_CAD_ARTIFACT_DIR)
        out_drw_dir = os.path.join(output_dir or ".", DEFAULT_DRAWING_ARTIFACT_DIR)
        os.makedirs(out_cad_dir, exist_ok=True)
        os.makedirs(out_drw_dir, exist_ok=True)

        warnings: List[str] = []

        # 1. Element Support Verification
        if spec.machine_element != "shaft":
            return CADGenerationResponse(
                status=CADStatus.BLOCKED,
                cad_specification=spec,
                warnings=[f"Machine element '{spec.machine_element}' is not currently supported by {self.backend.name}."],
                missing_information=[{"field": "machine_element", "reason": f"Unsupported element: {spec.machine_element}"}],
                report="CAD Generation Blocked: Unsupported machine element."
            )

        # 2. Strict Input Validation
        if spec.diameter is None or spec.diameter <= 0:
            raise ValueError(f"Shaft diameter must be strictly positive; received {spec.diameter}.")
        if spec.length is None or spec.length <= 0:
            raise ValueError(f"Shaft length must be strictly positive; received {spec.length}.")

        # 3. Generate 3D Solid Geometry via Backend
        solid = self.backend.generate_part(spec)

        # 4. Validate BRep Topology, Bounding Box, and Volume
        validation_res: BRepValidationResult = self.backend.validate_brep(solid, spec)
        if not validation_res.is_valid:
            warnings.extend(validation_res.validation_messages)

        # 5. Export STEP Artifact
        step_filename = f"{spec.part_name.lower()}.stp"
        step_path = os.path.join(out_cad_dir, step_filename)
        step_metadata = {
            "part_name": spec.part_name,
            "source_design_id": spec.source_design_id,
            "material": spec.material,
            "geometry_version": "1.0"
        }
        step_artifact: CADArtifact = self.backend.export_step(solid, step_path, step_metadata)

        # 6. Derive 2D Drawing Geometry from 3D BRep
        drawing_doc: DrawingDocument = self.backend.derive_drawing_geometry(solid, spec)

        # 7. Export SVG Engineering Drawing
        svg_filename = f"{spec.part_name.lower()}_drawing.svg"
        svg_path = os.path.join(out_drw_dir, svg_filename)
        svg_artifact: CADArtifact = self.drawing_exporter.export_svg(drawing_doc, svg_path)

        # 8. Drawing <-> CAD Dimensional Cross-Validation
        cross_val = self._cross_validate_dimensions(spec, drawing_doc)
        if not cross_val["all_match"]:
            warnings.append("Dimensional mismatch detected between 3D CAD specification and 2D drawing callouts.")

        artifacts = {
            "step": step_artifact,
            "svg": svg_artifact
        }

        # 9. Determine Status
        status = CADStatus.GENERATED
        if not validation_res.is_valid or not cross_val["all_match"]:
            status = CADStatus.REQUIRES_REVIEW

        resp = CADGenerationResponse(
            status=status,
            cad_specification=spec,
            artifacts=artifacts,
            drawing_document=drawing_doc,
            validation=validation_res,
            dimensional_cross_validation=cross_val,
            warnings=warnings
        )
        resp.report = generate_cad_report(resp)
        return resp

    def generate_from_design_result(
        self,
        design_result: DesignResult,
        extra_inputs: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None
    ) -> CADGenerationResponse:
        """
        Builds a CADSpecification from a DesignResult and executes parametric CAD generation.
        """
        spec, status, missing = build_shaft_cad_specification(design_result, extra_inputs=extra_inputs)
        if spec is None or status == CADStatus.BLOCKED:
            return CADGenerationResponse(
                status=CADStatus.BLOCKED,
                cad_specification=CADSpecification(part_name="UNSPECIFIED_SHAFT"),
                warnings=[f"Missing required parameter: {m.field}" for m in missing],
                missing_information=[m.model_dump() for m in missing],
                report=f"# CAD Generation Blocked\n\nRequired inputs missing: {', '.join(m.field for m in missing)}."
            )

        return self.generate(spec, output_dir=output_dir)

    def generate_from_problem_statement(
        self,
        problem_statement: str,
        extra_inputs: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None
    ) -> CADGenerationResponse:
        """
        End-to-end: Problem Statement -> Design Sizing -> Selected Candidate -> Parametric CAD.
        """
        design_res = design_from_problem_statement(problem_statement, extra_inputs=extra_inputs)
        return self.generate_from_design_result(design_res, extra_inputs=extra_inputs, output_dir=output_dir)

    def _cross_validate_dimensions(
        self,
        spec: CADSpecification,
        drawing_doc: DrawingDocument
    ) -> Dict[str, Any]:
        """
        Deterministically verifies that all drawing dimensions match the CAD specification within tolerance.
        """
        checks = {}
        all_match = True

        for dim in drawing_doc.dimensions:
            if dim.source_parameter == "shaft.diameter":
                match = math.isclose(dim.value, spec.diameter or 0.0, abs_tol=DRAWING_TOLERANCE_MM)
                checks["diameter_matches"] = {
                    "drawing_value": dim.value,
                    "cad_value": spec.diameter,
                    "delta_mm": abs(dim.value - (spec.diameter or 0.0)),
                    "match": match
                }
                if not match:
                    all_match = False

            elif dim.source_parameter == "shaft.length":
                match = math.isclose(dim.value, spec.length or 0.0, abs_tol=DRAWING_TOLERANCE_MM)
                checks["length_matches"] = {
                    "drawing_value": dim.value,
                    "cad_value": spec.length,
                    "delta_mm": abs(dim.value - (spec.length or 0.0)),
                    "match": match
                }
                if not match:
                    all_match = False

        checks["all_match"] = all_match
        return checks
