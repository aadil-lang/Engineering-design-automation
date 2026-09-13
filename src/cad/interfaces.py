"""
Abstract interfaces and protocols for CAD geometric modeling backends.
Enables pluggable geometry adapters (OpenCascade, CadQuery, FreeCAD, SOLIDWORKS, NX).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from cad.models import (
    CADSpecification,
    CADArtifact,
    BRepValidationResult
)


class CADBackend(ABC):
    """
    Abstract Protocol defining the contract for all parametric CAD modeling backends.
    Isolates higher-level mechanical engineering workflows from kernel-specific APIs.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for the CAD backend (e.g., 'OpenCascade', 'FreeCAD', 'SolidWorks')."""
        pass

    @abstractmethod
    def generate_part(self, spec: CADSpecification) -> Any:
        """
        Creates a parametric 3D BRep solid geometry instance from the CAD specification.
        Returns the kernel-specific solid representation (e.g. TopoDS_Shape or analytical BRep).
        """
        pass

    @abstractmethod
    def validate_brep(self, solid: Any, spec: CADSpecification) -> BRepValidationResult:
        """
        Validates topological closure, 3D bounding-box boundaries, analytical volume,
        and surface area against governing geometric criteria.
        """
        pass

    @abstractmethod
    def export_step(
        self,
        solid: Any,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> CADArtifact:
        """
        Exports the 3D solid geometry into a standardized ISO-10303-21 STEP exchange file.
        Attaches header metadata including design traceability and units.
        """
        pass

    @abstractmethod
    def derive_drawing_geometry(self, solid: Any, spec: CADSpecification) -> Any:
        """
        Derives an intermediate structured 2D DrawingDocument by projecting the actual 3D BRep.
        Extracts silhouette lines, planar edges, centerlines, and dimensional parameters.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Returns backend version, capabilities, and geometric kernel information."""
        pass
