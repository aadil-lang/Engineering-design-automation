"""
Configuration and constants for mechanical engineering analysis planning.
"""

from typing import Dict, List
from analysis.models import AnalysisType

DEFAULT_PLANNER_VERSION: str = "1.0.0"

# Priority levels
PRIORITY_CRITICAL: str = "critical"
PRIORITY_HIGH: str = "high"
PRIORITY_MEDIUM: str = "medium"
PRIORITY_LOW: str = "low"

# Deterministic solver registry mapping
DEFAULT_SOLVER_MAP: Dict[AnalysisType, str] = {
    AnalysisType.TORSION: "shaft_torsion_v1",
    AnalysisType.BENDING: "beam_bending_v1",
    AnalysisType.COMBINED_STRESS: "combined_shaft_stress_v1",
    AnalysisType.DEFLECTION: "beam_deflection_v1",
    AnalysisType.FATIGUE: "fatigue_assessment_v1",
    AnalysisType.BUCKLING: "euler_buckling_v1",
    AnalysisType.BEARING_STRESS: "pin_bearing_stress_v1",
    AnalysisType.HOLE_PATTERN_LOAD: "bolt_pattern_shear_v1",
    AnalysisType.VON_MISES: "von_mises_v1",
    AnalysisType.THERMAL_EXPANSION: "thermal_strain_v1",

    # Slice 10: Bolted Joint Solvers
    AnalysisType.BOLT_TENSION: "py_mech_bolt_tension_v1",
    AnalysisType.BOLT_SHEAR: "py_mech_bolt_shear_v1",
    AnalysisType.BOLT_COMBINED_STRESS: "py_mech_bolt_combined_stress_v1",
    AnalysisType.BOLT_PRELOAD: "py_mech_bolt_preload_v1"
}

# Default priorities by analysis type
DEFAULT_PRIORITIES: Dict[AnalysisType, str] = {
    AnalysisType.COMBINED_STRESS: PRIORITY_HIGH,
    AnalysisType.TORSION: PRIORITY_HIGH,
    AnalysisType.BENDING: PRIORITY_HIGH,
    AnalysisType.FATIGUE: PRIORITY_HIGH,
    AnalysisType.BUCKLING: PRIORITY_HIGH,
    AnalysisType.HOLE_PATTERN_LOAD: PRIORITY_MEDIUM,
    AnalysisType.DEFLECTION: PRIORITY_MEDIUM,
    AnalysisType.BEARING_STRESS: PRIORITY_MEDIUM,
    AnalysisType.VON_MISES: PRIORITY_HIGH,
    AnalysisType.THERMAL_EXPANSION: PRIORITY_LOW,

    # Slice 10: Bolted Joint Priorities
    AnalysisType.BOLT_TENSION: PRIORITY_HIGH,
    AnalysisType.BOLT_SHEAR: PRIORITY_HIGH,
    AnalysisType.BOLT_COMBINED_STRESS: PRIORITY_HIGH,
    AnalysisType.BOLT_PRELOAD: PRIORITY_MEDIUM
}

# Input specifications segregating calculation inputs vs safety assessment inputs
ANALYSIS_INPUT_SPECS: Dict[AnalysisType, Dict[str, List[str]]] = {
    AnalysisType.TORSION: {
        "calculation_inputs": ["torque", "shaft_diameter"],
        "assessment_inputs": ["material_allowable_stress"]
    },
    AnalysisType.BENDING: {
        "calculation_inputs": ["transverse_load", "shaft_length", "shaft_diameter", "support_conditions"],
        "assessment_inputs": ["material_allowable_stress"]
    },
    AnalysisType.COMBINED_STRESS: {
        "calculation_inputs": ["torque", "bending_moment", "shaft_diameter"],
        "assessment_inputs": ["yield_strength"]
    },
    AnalysisType.DEFLECTION: {
        "calculation_inputs": ["applied_load", "geometry", "support_conditions", "elastic_modulus"],
        "assessment_inputs": ["allowable_deflection"]
    },
    AnalysisType.FATIGUE: {
        "calculation_inputs": ["cyclic_loading", "stress_amplitude", "mean_stress"],
        "assessment_inputs": ["endurance_limit", "surface_finish_factor"]
    },
    AnalysisType.BUCKLING: {
        "calculation_inputs": ["compressive_load", "effective_length", "column_cross_section", "elastic_modulus"],
        "assessment_inputs": ["buckling_safety_factor"]
    },
    AnalysisType.BEARING_STRESS: {
        "calculation_inputs": ["pin_load", "pin_diameter", "plate_thickness"],
        "assessment_inputs": ["bearing_yield_strength"]
    },
    AnalysisType.HOLE_PATTERN_LOAD: {
        "calculation_inputs": ["pattern_load", "hole_count", "pitch_radius"],
        "assessment_inputs": ["fastener_shear_allowable"]
    },
    AnalysisType.VON_MISES: {
        "calculation_inputs": ["normal_stress", "shear_stress"],
        "assessment_inputs": ["yield_strength"]
    },
    AnalysisType.THERMAL_EXPANSION: {
        "calculation_inputs": ["initial_length", "delta_temperature", "thermal_expansion_coefficient"],
        "assessment_inputs": ["gap_clearance"]
    },

    # Slice 10: Bolted Joint Specs
    AnalysisType.BOLT_TENSION: {
        "calculation_inputs": ["bolt_diameter", "tensile_load"],
        "assessment_inputs": ["allowable_tensile_stress"]
    },
    AnalysisType.BOLT_SHEAR: {
        "calculation_inputs": ["bolt_diameter", "shear_load"],
        "assessment_inputs": ["allowable_shear_stress"]
    },
    AnalysisType.BOLT_COMBINED_STRESS: {
        "calculation_inputs": ["bolt_diameter", "tensile_load", "shear_load"],
        "assessment_inputs": ["allowable_equivalent_stress"]
    },
    AnalysisType.BOLT_PRELOAD: {
        "calculation_inputs": ["bolt_diameter", "preload_factor", "proof_stress"],
        "assessment_inputs": []
    }
}
