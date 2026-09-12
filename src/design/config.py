"""
Configuration, machine element taxonomies, and missing-information templates for the Design module.
"""

from typing import Dict, List, Any
from design.models import MissingInformation, MissingImportance

# Machine element taxonomy with detection keywords
MACHINE_ELEMENT_SYNONYMS: Dict[str, List[str]] = {
    "shaft": ["shaft", "drive shaft", "transmission shaft", "axle", "rotor", "spindle"],
    "bolted_joint": ["bolted joint", "bolt", "bolts", "fastener", "fasteners", "threaded connection", "cap screw"],
    "beam": ["beam", "cantilever", "girder", "i-beam", "joist"],
    "gear": ["gear", "pinion", "spur gear", "helical gear", "bevel gear"],
    "bearing": ["bearing", "ball bearing", "roller bearing", "journal bearing"],
    "spring": ["spring", "helical spring", "coil spring", "leaf spring", "torsion spring"],
    "column": ["column", "strut", "compression member"],
    "pressure_vessel": ["pressure vessel", "tank", "cylinder", "boiler", "pipe"],
    "key_joint": ["key", "keyway", "spline", "feather key"]
}

# Standard template for missing information by machine element
MISSING_INFO_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "shaft": [
        {
            "field": "shaft_diameter",
            "reason": "Required for cross-sectional area, polar moment of inertia, and torsional shear stress calculations.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": True,
            "suggested_input": "Specify nominal shaft diameter (e.g., 25 mm)."
        },
        {
            "field": "shaft_length",
            "reason": "Required for shaft span deflection, critical speed, and angle of twist evaluation.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": False,
            "suggested_input": "Specify total length or bearing span (e.g., 500 mm)."
        },
        {
            "field": "support_arrangement",
            "reason": "Required to determine bearing reaction forces, moment diagrams, and boundary conditions.",
            "importance": MissingImportance.REQUIRED_FOR_DESIGN,
            "blocks_analysis": False,
            "suggested_input": "Specify bearing types and locations (e.g., simply supported on two bearings)."
        },
        {
            "field": "bending_loads",
            "reason": "Transverse forces from gears, pulleys, or belts induce combined bending and torsional stress.",
            "importance": MissingImportance.OPTIONAL,
            "blocks_analysis": False,
            "suggested_input": "Specify radial/transverse forces or pulley/gear pitch diameters if present."
        },
        {
            "field": "material_grade",
            "reason": "Generic 'steel' lacks yield and tensile strength limits required for pass/fail stress assessment.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": False,
            "suggested_input": "Specify explicit steel grade (e.g., AISI 1045, AISI 4140, S275, S355)."
        },
        {
            "field": "required_factor_of_safety",
            "reason": "Design target safety margin against static yielding or fatigue failure.",
            "importance": MissingImportance.REQUIRED_FOR_DESIGN,
            "blocks_analysis": False,
            "suggested_input": "Specify target design factor or factor of safety (e.g., 2.0)."
        }
    ],
    "bolted_joint": [
        {
            "field": "bolt_diameter",
            "reason": "Required for tensile stress area and direct shear area calculations.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": True,
            "suggested_input": "Specify nominal bolt diameter (e.g., M12 or 12 mm)."
        },
        {
            "field": "bolt_grade",
            "reason": "Proof strength and ultimate tensile strength depend on ISO or SAE property class.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": False,
            "suggested_input": "Specify fastener property class (e.g., ISO Class 8.8, 10.9, or SAE Grade 5)."
        },
        {
            "field": "num_bolts",
            "reason": "Total fastener count sharing the applied tensile or shear load.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": False,
            "suggested_input": "Specify number of bolts (defaults to 1 if single fastener)."
        },
        {
            "field": "clamp_length",
            "reason": "Required for joint stiffness ratio, bolt compliance, and external load partitioning.",
            "importance": MissingImportance.REQUIRED_FOR_DESIGN,
            "blocks_analysis": False,
            "suggested_input": "Specify total clamped flange thickness in mm."
        }
    ],
    "beam": [
        {
            "field": "cross_section_profile",
            "reason": "Area moment of inertia I and section modulus Z depend on cross-sectional geometry.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": True,
            "suggested_input": "Specify profile dimensions (e.g., Rectangular 50x100 mm or standard I-beam profile)."
        },
        {
            "field": "span_length",
            "reason": "Required to calculate maximum bending moment and deflection.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": True,
            "suggested_input": "Specify clear span length in mm or m."
        },
        {
            "field": "support_conditions",
            "reason": "Boundary conditions (simply supported, cantilever, fixed-fixed) govern bending moment distributions.",
            "importance": MissingImportance.REQUIRED_FOR_ANALYSIS,
            "blocks_analysis": True,
            "suggested_input": "Specify support type (e.g., simply supported, cantilever)."
        }
    ]
}
