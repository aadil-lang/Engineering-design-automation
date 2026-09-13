"""
Pydantic schemas for Material Knowledge Base (Material Knowledge Base v1).
Defines authoritative material record structure, physical property constraints,
and audit/traceability models.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class MaterialRecord(BaseModel):
    """
    Authoritative engineering material record backed by published standards.
    Uses explicit engineering units in all numeric field names.
    """
    material_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'mat_s355j2')")
    designation: str = Field(..., description="Standard engineering designation (e.g. 'S355J2', 'AISI 1045')")
    standard: str = Field(..., description="Governing standard specification (e.g. 'EN 10025-2:2019')")
    category: str = Field(..., description="Material classification (e.g. 'structural_steel', 'carbon_steel')")

    # Mechanical & Physical Properties (explicit units)
    yield_strength_mpa: float = Field(..., description="Tensile yield strength in MPa")
    ultimate_tensile_strength_mpa: Optional[float] = Field(None, description="Ultimate tensile strength in MPa")
    elastic_modulus_gpa: float = Field(..., description="Young's modulus of elasticity in GPa")
    poisson_ratio: float = Field(..., description="Poisson's ratio (dimensionless)")
    density_kg_m3: float = Field(..., description="Mass density in kg/m^3")

    # Metadata, Provenance & Verification
    source: str = Field(..., description="Authoritative publication or standard table reference")
    source_revision: str = Field(..., description="Revision, edition, or publication year of the source")
    status: str = Field("verified", description="Verification status (e.g. 'verified', 'active')")
    aliases: List[str] = Field(default_factory=list, description="Common aliases, equivalent standard names, or trade designations")

    @field_validator("yield_strength_mpa")
    @classmethod
    def validate_yield_strength(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"yield_strength_mpa must be strictly positive (> 0); got {v}")
        return v

    @field_validator("elastic_modulus_gpa")
    @classmethod
    def validate_elastic_modulus(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"elastic_modulus_gpa must be strictly positive (> 0); got {v}")
        return v

    @field_validator("poisson_ratio")
    @classmethod
    def validate_poisson_ratio(cls, v: float) -> float:
        if not (0.0 < v < 0.5):
            raise ValueError(f"poisson_ratio must be between 0.0 and 0.5 (exclusive); got {v}")
        return v

    @field_validator("density_kg_m3")
    @classmethod
    def validate_density(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"density_kg_m3 must be strictly positive (> 0); got {v}")
        return v

    @field_validator("ultimate_tensile_strength_mpa")
    @classmethod
    def validate_uts(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError(f"ultimate_tensile_strength_mpa must be strictly positive (> 0) if specified; got {v}")
        return v


class MaterialResolutionResult(BaseModel):
    """
    Structured outcome of deterministic material resolution against the Material Knowledge Base.
    Preserves audit trail distinguishing explicit user requirements from database-derived properties.
    """
    requested_material: Optional[str] = None
    resolved: bool = False
    status: str = "Unresolved"  # "Verified", "Explicit override", "Explicit user value", "Unresolved"

    # Matched record from knowledge base (None if unresolved or purely custom)
    material_record: Optional[MaterialRecord] = None
    resolved_material: Optional[str] = None
    standard: Optional[str] = None

    # Active mechanical properties used in calculation
    yield_strength_mpa: Optional[float] = None
    yield_strength_source: Optional[str] = None  # "Knowledge Base", "Explicit user requirement", "Unresolved"
    yield_strength_status: Optional[str] = None  # "Verified", "Explicit override", "Explicit user value", "Unresolved"
    knowledge_base_yield_strength_mpa: Optional[float] = None
    is_explicit_override: bool = False

    # Complete property dictionary and provenance
    properties_used: Dict[str, Any] = Field(default_factory=dict)
    property_sources: Dict[str, str] = Field(default_factory=dict)

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
