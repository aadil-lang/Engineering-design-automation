"""
High-level Design Specification Extractor orchestrating NLP extraction,
deterministic unit normalization, closed-form derivations, and missing information analysis.
"""

import uuid
from typing import Dict, List, Optional, Any
from design.models import (
    EngineeringSpecification,
    EngineeringQuantity,
    LoadRequirement,
    MaterialRequirement,
    OperatingCondition,
    DesignConstraint,
    ConstraintPriority
)
from design.provider import DesignSpecificationProvider, get_design_provider
from design.normalization import normalize_power, normalize_rotational_speed, normalize_quantity_data
from design.derivation import DerivationEngine
from design.missing import detect_missing_information
from design.validation import validate_specification


class DesignSpecificationExtractor:
    """
    Interprets natural language engineering problem statements into structured,
    auditable EngineeringSpecifications with deterministic calculation provenance.
    """

    def __init__(
        self,
        provider: Optional[DesignSpecificationProvider] = None,
        derivation_engine: Optional[DerivationEngine] = None
    ):
        self.provider = provider or get_design_provider()
        self.derivation_engine = derivation_engine or DerivationEngine()

    def extract(
        self,
        problem_statement: str,
        structured_inputs: Optional[Dict[str, Any]] = None
    ) -> EngineeringSpecification:
        """
        Extracts, normalizes, derives, and audits engineering requirements.
        """
        raw = self.provider.extract_raw_data(problem_statement)

        # Merge any caller-provided structured inputs
        extra_inputs = dict(structured_inputs or {})

        spec_id = f"spec-{uuid.uuid4().hex[:8]}"
        machine_elem = extra_inputs.get("machine_element") or raw.get("machine_element")

        operating_conditions: List[OperatingCondition] = []
        geometry_reqs: List[EngineeringQuantity] = []
        load_reqs: List[LoadRequirement] = []
        safety_reqs: List[DesignConstraint] = []
        design_constraints: List[DesignConstraint] = []
        assumptions: List[str] = []
        ambiguities: List[str] = []

        # 1. Operating Conditions (Power & Speed)
        p_data = extra_inputs.get("power") or raw.get("power")
        if p_data:
            p_val = float(p_data["value"]) if isinstance(p_data, dict) else float(p_data)
            p_unit = p_data.get("unit", "kW") if isinstance(p_data, dict) else "kW"
            p_norm_w, _, _ = normalize_power(p_val, p_unit)
            operating_conditions.append(
                OperatingCondition(
                    parameter="power",
                    value=p_val,
                    unit=p_unit,
                    normalized_value=p_norm_w,
                    normalized_unit="W",
                    source="user_statement"
                )
            )

        s_data = extra_inputs.get("speed") or extra_inputs.get("rotational_speed") or raw.get("speed")
        if s_data:
            s_val = float(s_data["value"]) if isinstance(s_data, dict) else float(s_data)
            s_unit = s_data.get("unit", "RPM") if isinstance(s_data, dict) else "RPM"
            rpm_val, _, rad_s, _ = normalize_rotational_speed(s_val, s_unit)
            operating_conditions.append(
                OperatingCondition(
                    parameter="rotational_speed",
                    value=s_val,
                    unit=s_unit,
                    normalized_value=rpm_val,
                    normalized_unit="RPM",
                    source="user_statement"
                )
            )

        # 2. Material Requirements
        mat_data = extra_inputs.get("material") or raw.get("material")
        mat_req: Optional[MaterialRequirement] = None
        if mat_data:
            if isinstance(mat_data, str):
                mat_name = mat_data
                mat_grade = None
            else:
                mat_name = mat_data.get("material_name")
                mat_grade = mat_data.get("material_grade")

            mat_req = MaterialRequirement(
                material_name=mat_name,
                material_grade=mat_grade,
                source="user_statement"
            )

            if mat_name and not mat_grade:
                assumptions.append(
                    f"Material specified as generic '{mat_name}'; specific alloy grade and heat treatment condition not specified."
                )

        # 3. Geometry Requirements
        geom_list = list(raw.get("geometry", []))
        for k in ("shaft_diameter", "bolt_diameter", "diameter"):
            if k in extra_inputs:
                geom_list.append({"value": float(extra_inputs[k]), "unit": "mm", "evidence_id": k})
                break
        for k in ("shaft_length", "span_length", "length", "span"):
            if k in extra_inputs:
                geom_list.append({"value": float(extra_inputs[k]), "unit": "mm", "evidence_id": k})
                break

        for g in geom_list:
            g_val = float(g["value"])
            g_unit = g.get("unit", "mm")
            g_norm, g_norm_u = normalize_quantity_data(g_val, g_unit, "length")
            geometry_reqs.append(
                EngineeringQuantity(
                    value=g_val,
                    unit=g_unit,
                    normalized_value=g_norm,
                    normalized_unit=g_norm_u,
                    source="user_statement",
                    evidence_id=g.get("evidence_id")
                )
            )

        # 4. Load Requirements
        raw_loads = raw.get("loads", [])
        for l in raw_loads:
            mag_data = l.get("magnitude")
            mag_qty = None
            if mag_data:
                m_val = float(mag_data["value"])
                m_u = mag_data.get("unit", "N")
                dim = "force" if m_u.upper() in ("N", "KN", "LBF") else "torque"
                m_norm, m_norm_u = normalize_quantity_data(m_val, m_u, dim)
                mag_qty = EngineeringQuantity(
                    value=m_val,
                    unit=m_u,
                    normalized_value=m_norm,
                    normalized_unit=m_norm_u,
                    source="user_statement"
                )

            load_reqs.append(
                LoadRequirement(
                    load_type=l.get("load_type", "load"),
                    magnitude=mag_qty,
                    direction=l.get("direction"),
                    source="user_statement"
                )
            )

        # 5. Constraints
        raw_constraints = raw.get("constraints", [])
        for c in raw_constraints:
            prio = ConstraintPriority.HIGH
            p_str = c.get("priority", "high").lower()
            if p_str in ("mandatory", "high", "medium", "low"):
                prio = ConstraintPriority(p_str)

            constraint_obj = DesignConstraint(
                constraint_type=c.get("constraint_type", "general"),
                value=float(c["value"]) if c.get("value") is not None else None,
                unit=c.get("unit"),
                priority=prio,
                source="user_statement"
            )
            if "safety" in constraint_obj.constraint_type.lower():
                safety_reqs.append(constraint_obj)
            else:
                design_constraints.append(constraint_obj)

        # 6. Execute Deterministic Derivations (e.g. Power/Speed -> Torque)
        derivation_context: Dict[str, Any] = {}
        for op in operating_conditions:
            if op.parameter == "power":
                derivation_context["power"] = {"value": op.value, "unit": op.unit}
            elif op.parameter in ("speed", "rotational_speed"):
                derivation_context["speed"] = {"value": op.value, "unit": op.unit}

        for k, v in extra_inputs.items():
            if k not in derivation_context:
                derivation_context[k] = v

        derived_values = self.derivation_engine.execute(derivation_context)

        # If torque was derived, add to load requirements
        for dv in derived_values:
            if dv.name == "torque":
                load_reqs.append(
                    LoadRequirement(
                        load_type="torque",
                        magnitude=EngineeringQuantity(
                            value=dv.output_value,
                            unit=dv.output_unit,
                            normalized_value=dv.output_value,
                            normalized_unit="N*m",
                            source="derived_calculation"
                        ),
                        direction="torsional",
                        application_context="transmitted nominal torque derived from power and speed",
                        source="derived_calculation"
                    )
                )
                assumptions.extend(dv.assumptions)

        # 7. Assemble provisional specification
        spec = EngineeringSpecification(
            specification_id=spec_id,
            problem_statement=problem_statement,
            machine_element=machine_elem,
            operating_conditions=operating_conditions,
            geometry_requirements=geometry_reqs,
            material_requirements=mat_req,
            load_requirements=load_reqs,
            safety_requirements=safety_reqs,
            design_constraints=design_constraints,
            derived_values=derived_values,
            assumptions=assumptions,
            ambiguities=ambiguities,
            source_evidence=dict(extra_inputs)
        )

        # 8. Missing Information Analysis
        missing = detect_missing_information(spec)
        spec.missing_information = missing

        # 9. Validation & Conflict Detection
        validate_specification(spec)

        return spec
