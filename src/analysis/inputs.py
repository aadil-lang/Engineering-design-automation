"""
Input reconciliation and validation for engineering analysis planning.
Distinguishes between raw calculation inputs and safety assessment inputs.
"""

from typing import Dict, Any, List, Optional
from semantics.models import MechanicalFeature, MechanicalFeatureType
from analysis.models import AnalysisType
from analysis.config import ANALYSIS_INPUT_SPECS


def extract_feature_input_aliases(feature: Optional[MechanicalFeature]) -> Dict[str, Any]:
    """
    Extracts geometric parameters from a mechanical feature's attributes
    and maps them to standard engineering input names.
    """
    aliases: Dict[str, Any] = {}
    if not feature:
        return aliases

    attrs = feature.attributes or {}

    # Shaft geometric attributes
    if feature.feature_type == MechanicalFeatureType.SHAFT:
        if "diameter" in attrs:
            aliases["shaft_diameter"] = attrs["diameter"]
        if "length" in attrs:
            aliases["shaft_length"] = attrs["length"]
            aliases["geometry"] = f"Shaft L={attrs['length']}, D={attrs.get('diameter')}"

    # Hole geometric attributes
    elif feature.feature_type == MechanicalFeatureType.HOLE:
        if "diameter" in attrs:
            aliases["hole_diameter"] = attrs["diameter"]
            aliases["pin_diameter"] = attrs["diameter"]

    # Hole pattern attributes
    elif feature.feature_type == MechanicalFeatureType.HOLE_PATTERN:
        if "count" in attrs:
            aliases["hole_count"] = attrs["count"]
        if "pitch_circle_diameter" in attrs:
            aliases["pitch_radius"] = attrs["pitch_circle_diameter"] / 2.0
            aliases["pattern_pitch"] = attrs["pitch_circle_diameter"]
        if "spacing" in attrs and attrs["spacing"] is not None:
            aliases["pattern_spacing"] = attrs["spacing"]
            if "pitch_radius" not in aliases:
                aliases["pitch_radius"] = attrs["spacing"]

    # Rectangular plate attributes
    elif feature.feature_type == MechanicalFeatureType.RECTANGULAR_PLATE:
        if "thickness" in attrs:
            aliases["plate_thickness"] = attrs["thickness"]
        if "width" in attrs and "height" in attrs:
            aliases["geometry"] = f"Plate W={attrs['width']}, H={attrs['height']}"

    return aliases


def resolve_analysis_inputs(
    analysis_type: AnalysisType,
    engineering_inputs: Optional[Dict[str, Any]] = None,
    feature: Optional[MechanicalFeature] = None
) -> Dict[str, Any]:
    """
    Reconciles available vs missing inputs for a given analysis type.
    Distinguishes calculation inputs (needed to solve stress/deflection)
    from assessment inputs (needed for safety factor/allowable comparison).
    Never fabricates missing values.
    """
    provided = dict(engineering_inputs or {})
    feature_aliases = extract_feature_input_aliases(feature)
    combined = {**feature_aliases, **provided}

    spec = ANALYSIS_INPUT_SPECS.get(analysis_type, {
        "calculation_inputs": [],
        "assessment_inputs": []
    })
    calc_specs = spec["calculation_inputs"]
    assess_specs = spec["assessment_inputs"]

    available_inputs: List[str] = []
    missing_calc: List[str] = []
    missing_assess: List[str] = []

    for req in calc_specs:
        # Check direct presence
        val = combined.get(req)
        if val is not None:
            available_inputs.append(req)
        else:
            # Check common synonyms
            if req == "torque" and "T" in combined:
                available_inputs.append(req)
            elif req == "shaft_diameter" and ("diameter" in combined or "D" in combined):
                available_inputs.append(req)
            elif req == "applied_load" and any(k in combined for k in ("transverse_load", "force", "load", "torque")):
                available_inputs.append(req)
            elif req == "column_cross_section" and ("shaft_diameter" in combined or "diameter" in combined):
                available_inputs.append(req)
            elif req == "effective_length" and ("shaft_length" in combined or "length" in combined):
                available_inputs.append(req)
            elif req == "pitch_radius" and any(k in combined for k in ("pattern_pitch", "pattern_spacing", "spacing", "pitch")):
                available_inputs.append(req)
            elif req == "hole_count" and "count" in combined:
                available_inputs.append(req)
            else:
                missing_calc.append(req)

    for req in assess_specs:
        val = combined.get(req)
        if val is not None:
            available_inputs.append(req)
        else:
            if req == "material_allowable_stress" and any(k in combined for k in ("allowable_stress", "yield_strength", "Sy")):
                available_inputs.append(req)
            elif req == "yield_strength" and "Sy" in combined:
                available_inputs.append(req)
            else:
                missing_assess.append(req)

    return {
        "required_inputs": calc_specs + assess_specs,
        "available_inputs": available_inputs,
        "missing_inputs": missing_calc + missing_assess,
        "calculation_inputs": calc_specs,
        "assessment_inputs": assess_specs,
        "missing_calculation_inputs": missing_calc,
        "missing_assessment_inputs": missing_assess
    }
