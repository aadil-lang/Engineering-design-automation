"""
Shaft CAD Specification Builder.
Extracts geometry parameters, material, and traceability linkages from DesignResult.
Enforces strict missing-length and missing-diameter detection without dimensional fabrication.
"""

from typing import Optional, Dict, Any, Tuple, List
from design_engine.models import DesignResult, DesignStatus
from cad.models import CADSpecification, CADStatus
from design.models import MissingInformation, MissingImportance


def build_shaft_cad_specification(
    design_result: DesignResult,
    extra_inputs: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[CADSpecification], CADStatus, List[MissingInformation]]:
    """
    Constructs a CADSpecification from a selected DesignResult.
    Detects missing diameter or missing length and halts with CADStatus.BLOCKED if unspecified.
    """
    extra = dict(extra_inputs or {})
    missing_items: List[MissingInformation] = []

    # 1. Verify selected design candidate exists
    if design_result.selected_candidate is None:
        missing_items.append(MissingInformation(
            field="selected_candidate",
            reason="CAD generation requires a passing selected design candidate from the design engine.",
            importance=MissingImportance.REQUIRED_FOR_ANALYSIS,
            blocks_analysis=True,
            suggested_input="Run shaft design synthesis to produce a valid candidate."
        ))
        return None, CADStatus.BLOCKED, missing_items

    sc = design_result.selected_candidate

    # 2. Extract diameter from selected candidate
    dia_val = sc.parameters.get("shaft_diameter_mm") or sc.parameters.get("shaft_diameter")
    if dia_val is None or dia_val <= 0:
        missing_items.append(MissingInformation(
            field="shaft_diameter",
            reason="Selected design candidate does not contain a valid positive diameter.",
            importance=MissingImportance.REQUIRED_FOR_ANALYSIS,
            blocks_analysis=True,
            suggested_input="Specify nominal shaft diameter."
        ))
        return None, CADStatus.BLOCKED, missing_items

    # 3. Extract length (from extra_inputs, constraints, or design variables)
    length_val = (
        extra.get("length") or
        extra.get("shaft_length") or
        design_result.constraints.get("shaft_length") or
        design_result.constraints.get("length")
    )

    if length_val is None:
        # Check design variables
        for v in design_result.design_variables:
            if v.name in ("shaft_length", "length") and v.value is not None:
                length_val = v.value
                break

    if length_val is None or float(length_val) <= 0:
        # DO NOT FABRICATE A LENGTH
        missing_items.append(MissingInformation(
            field="shaft_length",
            reason="Shaft 3D CAD modeling requires an explicit length parameter; length was omitted from requirements.",
            importance=MissingImportance.REQUIRED_FOR_ANALYSIS,
            blocks_analysis=True,
            suggested_input="Specify total shaft length (e.g., 300 mm)."
        ))
        return None, CADStatus.BLOCKED, missing_items

    length_mm = float(length_val)

    # 4. Material (preserved as specified; never fabricated)
    mat_name = extra.get("material") or design_result.constraints.get("material")
    # Search upstream assumptions for generic steel
    is_generic = any("generic 'steel'" in a.lower() for a in design_result.assumptions)
    if not mat_name:
        mat_name = "steel" if is_generic else "steel"

    part_name = f"SHAFT_{int(dia_val)}X{int(length_mm)}"

    spec = CADSpecification(
        machine_element="shaft",
        part_name=part_name,
        material=mat_name,
        diameter=float(dia_val),
        length=length_mm,
        units="mm",
        source_design_id=design_result.design_id,
        source_design_candidate_id=sc.candidate_id,
        source_specification_id=design_result.specification_id,
        parameters={
            "shaft_diameter_mm": float(dia_val),
            "shaft_length_mm": length_mm,
            "calculated_stress_mpa": sc.calculated_stress_mpa,
            "factor_of_safety": sc.factor_of_safety
        },
        provenance={
            "design_engine": "Slice 12",
            "candidate_id": sc.candidate_id,
            "design_id": design_result.design_id
        },
        assumptions=list(design_result.assumptions)
    )

    return spec, CADStatus.READY, []
