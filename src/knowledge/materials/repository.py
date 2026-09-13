"""
Deterministic Material Repository and Resolution Engine (Material Knowledge Base v1).
Performs deterministic lookup and enforces the resolution hierarchy:
explicit structured input > explicit prompt extraction > knowledge-base lookup > unresolved.
"""

import re
from typing import Optional, List, Dict, Any

from knowledge.materials.schema import MaterialRecord, MaterialResolutionResult
from knowledge.materials.registry import MaterialRegistry, get_material_registry


def normalize_designation(raw: str) -> str:
    """
    Deterministically normalizes a material designation string for robust matching:
    - trims whitespace and converts to lowercase
    - removes extraneous punctuation, parentheses, brackets, underscores, hyphens, and spaces
    e.g. 'Steel (S355)' -> 'steels355'
    'AISI 1045' -> 'aisi1045'
    '6061-T6' -> '6061t6'
    """
    if not raw:
        return ""
    s = raw.strip().lower()
    s_clean = re.sub(r"[\s\-_()\[\],/.]+", "", s)
    return s_clean


class MaterialRepository:
    """
    Deterministic query and resolution repository for engineering materials.
    """

    def __init__(self, registry: Optional[MaterialRegistry] = None):
        self.registry = registry or get_material_registry()
        self._build_index()

    def _build_index(self) -> None:
        """Builds fast deterministic lookup indexes."""
        self._by_id: Dict[str, MaterialRecord] = {}
        self._by_exact_designation: Dict[str, MaterialRecord] = {}
        self._by_normalized_key: Dict[str, MaterialRecord] = {}

        for rec in self.registry.get_all():
            self._by_id[rec.material_id] = rec
            self._by_exact_designation[rec.designation.lower()] = rec

            # Map normalized designation
            norm_desig = normalize_designation(rec.designation)
            if norm_desig:
                self._by_normalized_key[norm_desig] = rec

            # Map aliases
            for alias in rec.aliases:
                self._by_exact_designation[alias.lower()] = rec
                norm_alias = normalize_designation(alias)
                if norm_alias:
                    self._by_normalized_key[norm_alias] = rec

    def get_by_id(self, material_id: str) -> Optional[MaterialRecord]:
        """Lookup by exact material ID."""
        return self._by_id.get(material_id)

    def get_by_designation(self, designation: str) -> Optional[MaterialRecord]:
        """Lookup by designation or alias (case-insensitive)."""
        if not designation:
            return None
        return self._by_exact_designation.get(designation.strip().lower())

    def find(self, query: str) -> Optional[MaterialRecord]:
        """
        Deterministic multi-strategy lookup:
        1. Exact ID match
        2. Exact designation / alias match (case-insensitive)
        3. Normalized designation match
        4. Specific substring / token match (e.g. 's355' in 'steel (s355)')
        """
        if not query or not isinstance(query, str):
            return None

        q_trim = query.strip()
        if not q_trim:
            return None

        # 1. Exact ID
        if q_trim in self._by_id:
            return self._by_id[q_trim]

        # 2. Exact designation / alias (case-insensitive)
        q_lower = q_trim.lower()
        if q_lower in self._by_exact_designation:
            return self._by_exact_designation[q_lower]

        # 3. Normalized key
        q_norm = normalize_designation(q_trim)
        if q_norm in self._by_normalized_key:
            return self._by_normalized_key[q_norm]

        # 4. Check if a known specific normalized key appears inside query
        for norm_key, rec in self._by_normalized_key.items():
            if len(norm_key) >= 4 and norm_key in q_norm:
                return rec

        return None

    def resolve(
        self,
        requested_material: Optional[str] = None,
        explicit_yield_strength_mpa: Optional[float] = None
    ) -> MaterialResolutionResult:
        """
        Enforces the deterministic resolution hierarchy:

        explicit structured material / Sy
            >
        explicit material extracted from prompt
            >
        knowledge-base lookup
            >
        unresolved
        """
        result = MaterialResolutionResult(
            requested_material=requested_material
        )

        # 1. Try finding in Knowledge Base
        matched_rec: Optional[MaterialRecord] = None
        if requested_material:
            generic_terms = {"steel", "metal", "alloy", "iron", "aluminum", "aluminium"}
            if requested_material.strip().lower() not in generic_terms:
                matched_rec = self.find(requested_material)

        # 2. Case A: Explicit yield strength supplied by user
        if explicit_yield_strength_mpa is not None and explicit_yield_strength_mpa > 0:
            result.yield_strength_mpa = float(explicit_yield_strength_mpa)
            result.yield_strength_source = "Explicit user requirement"

            if matched_rec:
                result.resolved = True
                result.material_record = matched_rec
                result.resolved_material = matched_rec.designation
                result.standard = matched_rec.standard
                result.knowledge_base_yield_strength_mpa = matched_rec.yield_strength_mpa

                # Check if it overrides the KB value
                if abs(explicit_yield_strength_mpa - matched_rec.yield_strength_mpa) > 1e-4:
                    result.status = "Explicit override"
                    result.yield_strength_status = "Explicit override"
                    result.is_explicit_override = True
                    result.warnings.append(
                        f"Explicit yield strength ({explicit_yield_strength_mpa:.1f} MPa) overrides "
                        f"standard {matched_rec.designation} knowledge-base value ({matched_rec.yield_strength_mpa:.1f} MPa per {matched_rec.standard})."
                    )
                else:
                    result.status = "Verified"
                    result.yield_strength_status = "Verified"
                    result.is_explicit_override = False

                result.properties_used = {
                    "yield_strength_mpa": explicit_yield_strength_mpa,
                    "ultimate_tensile_strength_mpa": matched_rec.ultimate_tensile_strength_mpa,
                    "elastic_modulus_gpa": matched_rec.elastic_modulus_gpa,
                    "poisson_ratio": matched_rec.poisson_ratio,
                    "density_kg_m3": matched_rec.density_kg_m3
                }
                result.property_sources = {
                    "yield_strength_mpa": "Explicit user requirement",
                    "ultimate_tensile_strength_mpa": f"Knowledge Base ({matched_rec.standard})",
                    "elastic_modulus_gpa": f"Knowledge Base ({matched_rec.standard})",
                    "poisson_ratio": f"Knowledge Base ({matched_rec.standard})",
                    "density_kg_m3": f"Knowledge Base ({matched_rec.standard})"
                }
            else:
                # User supplied explicit Sy for generic or custom material
                result.resolved = True
                result.status = "Explicit user value"
                result.yield_strength_status = "Explicit user value"
                result.resolved_material = requested_material or "Custom Material"
                result.standard = "User Defined"
                result.properties_used = {
                    "yield_strength_mpa": explicit_yield_strength_mpa
                }
                result.property_sources = {
                    "yield_strength_mpa": "Explicit user requirement"
                }
            return result

        # 3. Case B: No explicit yield strength, but KB record matched
        if matched_rec:
            result.resolved = True
            result.status = "Verified"
            result.material_record = matched_rec
            result.resolved_material = matched_rec.designation
            result.standard = matched_rec.standard
            result.yield_strength_mpa = matched_rec.yield_strength_mpa
            result.yield_strength_source = "Knowledge Base"
            result.yield_strength_status = "Verified"
            result.knowledge_base_yield_strength_mpa = matched_rec.yield_strength_mpa
            result.is_explicit_override = False

            result.properties_used = {
                "yield_strength_mpa": matched_rec.yield_strength_mpa,
                "ultimate_tensile_strength_mpa": matched_rec.ultimate_tensile_strength_mpa,
                "elastic_modulus_gpa": matched_rec.elastic_modulus_gpa,
                "poisson_ratio": matched_rec.poisson_ratio,
                "density_kg_m3": matched_rec.density_kg_m3
            }
            result.property_sources = {
                "yield_strength_mpa": f"Knowledge Base ({matched_rec.standard})",
                "ultimate_tensile_strength_mpa": f"Knowledge Base ({matched_rec.standard})",
                "elastic_modulus_gpa": f"Knowledge Base ({matched_rec.standard})",
                "poisson_ratio": f"Knowledge Base ({matched_rec.standard})",
                "density_kg_m3": f"Knowledge Base ({matched_rec.standard})"
            }
            return result

        # 4. Case C: Unresolved material and no explicit yield strength
        result.resolved = False
        result.status = "Unresolved"
        result.yield_strength_source = "Unresolved"
        result.yield_strength_status = "Unresolved"
        result.yield_strength_mpa = None

        if requested_material:
            if requested_material.strip().lower() in ("steel", "metal", "alloy", "aluminum"):
                result.errors.append(
                    f"Material '{requested_material}' is generic; a specific standard grade (e.g. 'S355', 'AISI 1045') "
                    f"or explicit yield_strength_mpa is required."
                )
            else:
                result.errors.append(
                    f"Material '{requested_material}' not found in Material Knowledge Base and no explicit yield strength was provided."
                )
        else:
            result.errors.append("No material or yield strength specified.")

        return result


def get_default_material_repository() -> MaterialRepository:
    """Singleton getter for the default MaterialRepository."""
    return MaterialRepository()
