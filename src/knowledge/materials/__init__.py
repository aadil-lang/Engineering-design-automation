"""
Material Knowledge Base package (Material Knowledge Base v1).
Provides deterministic material property lookup, authoritative standard datasets,
and requirement resolution hierarchy.
"""

from knowledge.materials.schema import MaterialRecord, MaterialResolutionResult
from knowledge.materials.registry import MaterialRegistry, get_material_registry
from knowledge.materials.repository import (
    MaterialRepository,
    normalize_designation,
    get_default_material_repository
)

__all__ = [
    "MaterialRecord",
    "MaterialResolutionResult",
    "MaterialRegistry",
    "get_material_registry",
    "MaterialRepository",
    "normalize_designation",
    "get_default_material_repository",
]
