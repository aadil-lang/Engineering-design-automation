"""
Deterministic built-in engineering rules and knowledge definitions.

IMPORTANT:
These rules represent deterministic engineering heuristics and requirements.
They do NOT execute physical stress calculations, nor do they fabricate values.
"""

from typing import List
from knowledge.models import (
    EngineeringRule,
    EngineeringKnowledgeItem,
    KnowledgeSourceType
)
from knowledge.config import (
    DOMAIN_STRENGTH,
    DOMAIN_FATIGUE,
    DOMAIN_STABILITY,
    DOMAIN_STIFFNESS,
    DOMAIN_TOLERANCING,
    DOMAIN_MATERIALS,
    DEFAULT_BUILT_IN_SOURCE,
    DEFAULT_BUILT_IN_REF
)


BUILT_IN_RULES: List[EngineeringRule] = [
    # A. Shaft Torsion
    EngineeringRule(
        id="shaft_torsion_applicability",
        title="Shaft torsional stress analysis applicability",
        domain=DOMAIN_STRENGTH,
        feature_types=["shaft"],
        required_inputs=["torque", "shaft_diameter", "material_allowable_stress"],
        rationale="A shaft transmitting torque requires torsional shear stress assessment (tau = T*r/J).",
        limitations=["Establishes analysis applicability only; does not calculate stress or certify the design."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # B. Shaft Bending
    EngineeringRule(
        id="shaft_bending_applicability",
        title="Shaft bending stress analysis applicability",
        domain=DOMAIN_STRENGTH,
        feature_types=["shaft"],
        required_inputs=["transverse_load", "shaft_length", "shaft_diameter", "support_conditions", "material_allowable_stress"],
        rationale="A shaft subjected to transverse loads or bending moments develops normal bending stresses (sigma = M*y/I).",
        limitations=["Requires defined bearing locations and transverse loads; does not perform beam deflection integration."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # C. Combined Shaft Loading
    EngineeringRule(
        id="shaft_combined_stress_applicability",
        title="Shaft combined torsional and bending stress applicability",
        domain=DOMAIN_STRENGTH,
        feature_types=["shaft"],
        required_inputs=["torque", "bending_moment", "shaft_diameter", "yield_strength"],
        rationale="When both torsion and bending act simultaneously, multiaxial failure criteria (e.g., von Mises or Tresca) must be evaluated.",
        limitations=["Analysis applicability rule only; does not solve equivalent stress tensors or fatigue stress concentrations."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # D. Fatigue
    EngineeringRule(
        id="fatigue_analysis_applicability",
        title="Fatigue and cyclic loading analysis applicability",
        domain=DOMAIN_FATIGUE,
        feature_types=["shaft", "hole", "rectangular_plate", "slot"],
        required_inputs=["cyclic_loading", "stress_amplitude", "mean_stress", "endurance_limit", "surface_finish_factor"],
        rationale="Components subjected to cyclic or repeated loading are vulnerable to progressive fatigue failure below static yield.",
        limitations=["Requires cycle count, stress ratio R, and S-N endurance data; not automatically assumed for static drawings."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # E. Buckling
    EngineeringRule(
        id="buckling_analysis_applicability",
        title="Column buckling and elastic stability applicability",
        domain=DOMAIN_STABILITY,
        feature_types=["shaft"],
        required_inputs=["compressive_load", "effective_length", "column_cross_section", "elastic_modulus"],
        rationale="Slender structural members subjected to axial compressive loads can experience sudden structural instability (buckling) before material yielding.",
        limitations=["Applies only to slender compression members under verified compressive loading; geometric aspect ratio alone is insufficient."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # F. Deflection
    EngineeringRule(
        id="deflection_analysis_applicability",
        title="Structural deflection and stiffness analysis applicability",
        domain=DOMAIN_STIFFNESS,
        feature_types=["shaft", "rectangular_plate"],
        required_inputs=["applied_load", "geometry", "support_conditions", "elastic_modulus"],
        rationale="Excessive elastic deflection can cause binding, misalignment, or serviceability failure even when stress is below allowable limits.",
        limitations=["Requires elastic modulus and clear boundary conditions; 2D drawings lack support reaction details."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # G. Hole Requirements
    EngineeringRule(
        id="hole_engineering_requirements",
        title="Hole sizing, tolerancing, and manufacturing intent",
        domain=DOMAIN_TOLERANCING,
        feature_types=["hole"],
        required_inputs=["hole_diameter", "positional_tolerance", "hole_depth_or_through"],
        rationale="Holes require specification of diameter, tolerance class, true position, and depth (through vs blind) for manufacturing.",
        limitations=["Manufacturing method (drilled, reamed, milled, bored) must not be assumed from 2D circular geometry alone."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # H. Hole Pattern Requirements
    EngineeringRule(
        id="hole_pattern_engineering_requirements",
        title="Hole pattern spacing and positional tolerance",
        domain=DOMAIN_TOLERANCING,
        feature_types=["hole_pattern"],
        required_inputs=["hole_diameter", "pattern_pitch_or_spacing", "pattern_position", "composite_positional_tolerance"],
        rationale="Patterns of fastener holes require cumulative pitch spacing verification and composite positional tolerancing for mating assembly.",
        limitations=["Pattern arrangement identified from 2D coordinates; mating part datum alignment unverified."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # I. Rectangular Plate Analysis
    EngineeringRule(
        id="rectangular_plate_analysis_applicability",
        title="Rectangular plate stress and deflection analysis",
        domain=DOMAIN_STRENGTH,
        feature_types=["rectangular_plate"],
        required_inputs=["plate_thickness", "material", "applied_pressure_or_load", "boundary_conditions"],
        rationale="Flat plates subjected to out-of-plane pressure or in-plane membrane loads require thickness, support conditions, and material properties for bending/deflection analysis.",
        limitations=["Plate thickness cannot be determined from a 2D outline view; plate stock specification unconfirmed."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),

    # J. Material Specification Requirement
    EngineeringRule(
        id="material_specification_requirement",
        title="Engineering material specification and property verification",
        domain=DOMAIN_MATERIALS,
        feature_types=["shaft", "rectangular_plate", "slot", "hole"],
        required_inputs=["material_grade", "yield_strength", "ultimate_tensile_strength", "elastic_modulus"],
        rationale="Deterministic engineering stress, fatigue, and deflection calculations require certified mechanical material properties; properties must never be fabricated.",
        limitations=["Material grade and heat treatment cannot be inferred from geometry; must be explicitly specified in title block, notes, or inputs."],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF
    ),
]


BUILT_IN_KNOWLEDGE_ITEMS: List[EngineeringKnowledgeItem] = [
    EngineeringKnowledgeItem(
        id="know_shaft_torsion",
        title="Shaft Torsional Shear Stress Principle",
        domain=DOMAIN_STRENGTH,
        statement="Torsional shear stress in a circular shaft is given by tau = (T * r) / J, where J = pi * d^4 / 32.",
        applicability=["shaft transmitting torque"],
        required_inputs=["torque", "shaft_diameter", "material_allowable_stress"],
        related_features=["shaft"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Assumes linear-elastic isotropic material and circular cross section without stress concentration factor (Kt)."],
        tags=["torsion", "shaft", "shear_stress"]
    ),
    EngineeringKnowledgeItem(
        id="know_shaft_bending",
        title="Shaft Normal Bending Stress Principle",
        domain=DOMAIN_STRENGTH,
        statement="Normal bending stress in a beam/shaft is given by sigma = (M * y) / I, where I = pi * d^4 / 64 for circular sections.",
        applicability=["shaft with transverse loads or bending moments"],
        required_inputs=["transverse_load", "shaft_length", "shaft_diameter", "support_conditions"],
        related_features=["shaft"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Assumes Euler-Bernoulli beam theory and known boundary reaction conditions."],
        tags=["bending", "shaft", "normal_stress"]
    ),
    EngineeringKnowledgeItem(
        id="know_combined_loading",
        title="von Mises Multiaxial Equivalent Stress Principle",
        domain=DOMAIN_STRENGTH,
        statement="Under simultaneous torsion (tau) and bending (sigma), the equivalent von Mises stress is sigma_vm = sqrt(sigma^2 + 3 * tau^2).",
        applicability=["shaft or member under simultaneous torsion and bending"],
        required_inputs=["torque", "bending_moment", "shaft_diameter", "yield_strength"],
        related_features=["shaft"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Applies to ductile isotropic materials under static loading."],
        tags=["combined_loading", "von_mises", "ductile_yield"]
    ),
    EngineeringKnowledgeItem(
        id="know_fatigue_cyclic",
        title="Fatigue and High Cycle Loading Criterion",
        domain=DOMAIN_FATIGUE,
        statement="Fluctuating stress states produce fatigue damage; Goodman or Gerber criteria require endurance limit Se and stress amplitude Sa.",
        applicability=["components with explicit cyclic or alternating loads"],
        required_inputs=["cyclic_loading", "stress_amplitude", "mean_stress", "endurance_limit"],
        related_features=["shaft", "hole", "rectangular_plate", "slot"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Cannot be applied without verified cyclic loading profile and surface condition factors."],
        tags=["fatigue", "cyclic_loading", "goodman"]
    ),
    EngineeringKnowledgeItem(
        id="know_buckling_stability",
        title="Euler Column Buckling Stability Criterion",
        domain=DOMAIN_STABILITY,
        statement="Critical buckling load is P_cr = (pi^2 * E * I) / (K * L)^2 for long slender columns under compressive axial load.",
        applicability=["slender compression members"],
        required_inputs=["compressive_load", "effective_length", "column_cross_section", "elastic_modulus"],
        related_features=["shaft"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Valid only when slenderness ratio exceeds the critical Euler threshold; requires verified axial compression."],
        tags=["buckling", "stability", "euler"]
    ),
    EngineeringKnowledgeItem(
        id="know_deflection_stiffness",
        title="Structural Elastic Deflection and Stiffness",
        domain=DOMAIN_STIFFNESS,
        statement="Elastic deflection under load depends on geometry (I or J), material modulus (E or G), span, and boundary constraints.",
        applicability=["shafts, plates, and beams requiring deflection limits"],
        required_inputs=["applied_load", "geometry", "support_conditions", "elastic_modulus"],
        related_features=["shaft", "rectangular_plate"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Requires complete constraint definition (fixed, pinned, simple supports)."],
        tags=["deflection", "stiffness", "serviceability"]
    ),
    EngineeringKnowledgeItem(
        id="know_hole_tolerancing",
        title="Hole Specification and Positional Tolerancing",
        domain=DOMAIN_TOLERANCING,
        statement="Holes require specified diameter limits (fit classes) and GD&T position relative to datums for interchangeability.",
        applicability=["holes in machined or fabricated components"],
        required_inputs=["hole_diameter", "positional_tolerance", "hole_depth_or_through"],
        related_features=["hole"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Manufacturing process cannot be inferred from 2D boundary alone."],
        tags=["hole", "tolerancing", "gdt"]
    ),
    EngineeringKnowledgeItem(
        id="know_hole_pattern_pitch",
        title="Fastener Hole Pattern Spacing and Assembly",
        domain=DOMAIN_TOLERANCING,
        statement="Hole patterns require cumulative pitch tolerance control and pitch circle diameter verification to guarantee mating alignment.",
        applicability=["hole patterns for bolt circles or linear fastener arrays"],
        required_inputs=["hole_diameter", "pattern_pitch_or_spacing", "pattern_position"],
        related_features=["hole_pattern"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Mating part tolerance stack-up must be analyzed concurrently."],
        tags=["hole_pattern", "bolt_circle", "pitch"]
    ),
    EngineeringKnowledgeItem(
        id="know_rectangular_plate_bending",
        title="Plate Bending and Membrane Stress Principle",
        domain=DOMAIN_STRENGTH,
        statement="Plate stress and deflection vary inversely with plate thickness squared (stress) and cubed (deflection).",
        applicability=["rectangular plates subjected to out-of-plane pressure or in-plane loads"],
        required_inputs=["plate_thickness", "material", "applied_pressure_or_load", "boundary_conditions"],
        related_features=["rectangular_plate"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Plate thickness cannot be determined from 2D boundary geometry alone."],
        tags=["plate", "bending", "thickness"]
    ),
    EngineeringKnowledgeItem(
        id="know_material_properties_requirement",
        title="Certified Engineering Material Property Requirement",
        domain=DOMAIN_MATERIALS,
        statement="Engineering stress, safety factor, and deformation calculations require certified material yield (Sy), ultimate (Sut), and modulus (E).",
        applicability=["all mechanical calculations and structural assessments"],
        required_inputs=["material_grade", "yield_strength", "ultimate_tensile_strength", "elastic_modulus"],
        related_features=["shaft", "rectangular_plate", "slot", "hole"],
        source_type=KnowledgeSourceType.BUILT_IN_RULE,
        source_reference=DEFAULT_BUILT_IN_REF,
        confidence=1.0,
        limitations=["Properties must never be fabricated or assumed without engineering specification."],
        tags=["material", "properties", "yield_strength"]
    )
]
