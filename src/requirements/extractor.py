"""
LLM Requirement Extractor & Provenance Engine (Slice 14.2).
Extracts explicitly stated engineering requirements from natural-language problem statements.
Strictly adheres to the zero-inference boundary: never calculates diameter, torque, stress, or material properties.
"""

import os
import re
import json
from typing import Optional, Dict, Any, Tuple
from reasoning.provider import LLMProvider, get_llm_provider, MockLLMProvider
from requirements.models import EngineeringSpec, FieldProvenance

EXTRACTION_SYSTEM_PROMPT = """You are a strict mechanical engineering requirement extraction engine.
Your task is to extract explicitly stated engineering requirements from a user's natural language problem statement.

CRITICAL RULES:
1. Extract ONLY parameters that are explicitly stated in the input text.
2. DO NOT calculate, infer, estimate, or hallucinate missing parameters.
3. DO NOT calculate shaft diameter, torque, section modulus, yield strength, or allowable stress.
4. If a parameter is not explicitly stated in the input, set its value to null.
5. For every extracted field, provide provenance with the exact matching source_text from the input.
6. Normalize units to standard engineering units:
   - Power: kW (convert W to kW if given in Watts, e.g. 5000 W -> 5.0 kW)
   - Speed: RPM (convert rad/s if explicit, or preserve RPM)
   - Length: mm (convert m to mm if given in meters, e.g. 0.3 m -> 300.0 mm)
   - Factor of Safety: dimensionless number
7. Output MUST be valid JSON with the following structure:
{
  "component": "shaft" | null,
  "material": string | null,
  "power_kw": float | null,
  "rpm": float | null,
  "factor_of_safety": float | null,
  "length_mm": float | null,
  "provenance": {
    "component": {"source_text": string | null, "value": string | null, "is_explicit": boolean},
    "material": {"source_text": string | null, "value": string | null, "is_explicit": boolean},
    "power_kw": {"source_text": string | null, "value": float | null, "is_explicit": boolean},
    "rpm": {"source_text": string | null, "value": float | null, "is_explicit": boolean},
    "factor_of_safety": {"source_text": string | null, "value": float | null, "is_explicit": boolean},
    "length_mm": {"source_text": string | null, "value": float | null, "is_explicit": boolean}
  }
}
"""


class RequirementExtractor:
    """
    Extracts structured requirements with parameter-level provenance from natural language statements.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or get_llm_provider()

    def extract(self, problem_statement: str) -> EngineeringSpec:
        """
        Extracts EngineeringSpec and per-field provenance from a problem statement.
        """
        raw_text = problem_statement.strip()
        user_prompt = (
            f"Extract explicitly stated engineering requirements from this statement. "
            f"Do not calculate or infer any unstated parameters:\n\n"
            f"\"{raw_text}\""
        )

        extracted_data = {}
        llm_succeeded = False

        # Attempt LLM extraction
        try:
            raw_response = self.provider.generate(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
            parsed_json = self._parse_json(raw_response)
            if parsed_json and isinstance(parsed_json, dict):
                extracted_data = parsed_json
                # Check if it produced meaningful fields
                if any(k in extracted_data for k in ("component", "material", "power_kw", "rpm", "factor_of_safety", "length_mm")):
                    llm_succeeded = True
        except Exception:
            llm_succeeded = False

        # If LLM did not return structured data or if MockLLMProvider default was triggered,
        # run the deterministic grounded rule-based pattern extractor
        if not llm_succeeded or isinstance(self.provider, MockLLMProvider):
            fallback_data = self._deterministic_extract(raw_text)
            # If extracted_data from LLM was empty or incomplete, merge with fallback
            if not llm_succeeded:
                extracted_data = fallback_data
            else:
                # Merge: prefer LLM if explicitly present, else fallback
                for k, v in fallback_data.items():
                    if k not in extracted_data or extracted_data[k] is None:
                        extracted_data[k] = v

        # Build field provenances
        provenance_dict = extracted_data.get("provenance", {})
        fields_provenance = {}

        for field_name in ("component", "material", "power_kw", "rpm", "factor_of_safety", "length_mm"):
            val = extracted_data.get(field_name)
            prov_item = provenance_dict.get(field_name, {})
            if isinstance(prov_item, dict):
                src_text = prov_item.get("source_text")
                is_exp = prov_item.get("is_explicit", val is not None)
            else:
                src_text = str(prov_item) if prov_item else None
                is_exp = val is not None

            fields_provenance[field_name] = {
                "field_name": field_name,
                "value": val,
                "source_text": src_text,
                "is_explicit": is_exp,
                "confidence": 1.0 if is_exp else 0.0
            }

        # Construct EngineeringSpec with strict field sanitation (NO diameter, torque, stress, etc.)
        spec = EngineeringSpec(
            component=extracted_data.get("component"),
            material=extracted_data.get("material"),
            power_kw=float(extracted_data["power_kw"]) if extracted_data.get("power_kw") is not None else None,
            rpm=float(extracted_data["rpm"]) if extracted_data.get("rpm") is not None else None,
            factor_of_safety=float(extracted_data["factor_of_safety"]) if extracted_data.get("factor_of_safety") is not None else None,
            length_mm=float(extracted_data["length_mm"]) if extracted_data.get("length_mm") is not None else None,
            raw_text=raw_text,
            provenance={
                "provider": self.provider.__class__.__name__,
                "fields": fields_provenance
            }
        )

        return spec

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Cleans and extracts JSON object from LLM response string."""
        if not text:
            return None
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            obj_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if obj_match:
                cleaned = obj_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def _deterministic_extract(self, text: str) -> Dict[str, Any]:
        """
        Grounded pattern-based extractor for deterministic offline operation.
        Extracts explicitly stated values and their exact source text spans with zero arithmetic.
        """
        lower = text.lower()
        res: Dict[str, Any] = {
            "component": None,
            "material": None,
            "power_kw": None,
            "rpm": None,
            "factor_of_safety": None,
            "length_mm": None,
            "provenance": {}
        }

        # 1. Component
        comp_match = re.search(r'\b(solid\s+circular\s+shaft|solid\s+shaft|circular\s+shaft|shaft)\b', lower)
        if comp_match:
            span_text = text[comp_match.start():comp_match.end()]
            res["component"] = "shaft"
            res["provenance"]["component"] = {"source_text": span_text, "value": "shaft", "is_explicit": True}
        else:
            res["provenance"]["component"] = {"source_text": None, "value": None, "is_explicit": False}

        # 2. Material: check specific engineering grades, explicit made of clauses, or generic base materials
        # 2a. Explicit clause e.g. "made of S355", "material: AISI 1045", "material is 6061-T6"
        mat_clause = re.search(
            r'(?:made\s+of|material\s*(?:is|:|=)?)\s*([a-zA-Z0-9_\-\s()]+?)(?=\s+(?:to|with|for|at|having|of|having|\.|\,|$))',
            text,
            re.IGNORECASE
        )
        if mat_clause:
            val = mat_clause.group(1).strip()
            span_text = text[mat_clause.start():mat_clause.end()]
            res["material"] = val
            res["provenance"]["material"] = {"source_text": span_text, "value": val, "is_explicit": True}
        else:
            # 2b. Explicit standard designations (S355, AISI 1045, 6061-T6, etc.)
            desig_match = re.search(
                r'\b(s355(?:j2|jr)?|s275(?:jr)?|s235(?:jr)?|aisi\s*1045|aisi\s*1018|aisi\s*4140|aisi\s*304|6061(?:-t6)?|c45|42crmo4)\b',
                lower
            )
            if desig_match:
                span_text = text[desig_match.start():desig_match.end()]
                val = span_text.strip()
                res["material"] = val
                res["provenance"]["material"] = {"source_text": span_text, "value": val, "is_explicit": True}
            else:
                # 2c. Base generic materials
                mat_match = re.search(r'\b(steel|aluminum|brass|bronze|titanium|cast\s+iron)\b', lower)
                if mat_match:
                    span_text = text[mat_match.start():mat_match.end()]
                    res["material"] = mat_match.group(1).lower()
                    res["provenance"]["material"] = {"source_text": span_text, "value": res["material"], "is_explicit": True}
                else:
                    res["provenance"]["material"] = {"source_text": None, "value": None, "is_explicit": False}

        # 3. Power: e.g. "5 kW", "-5 kW", "5000 W", "10 hp"
        power_match = re.search(r'(-?\d+(?:\.\d+)?)\s*(kw|kilowatts?|w|watts?|hp|horsepower)\b', lower)
        if power_match:
            span_text = text[power_match.start():power_match.end()]
            raw_val = float(power_match.group(1))
            unit = power_match.group(2)
            if "w" == unit or "watt" in unit:
                norm_val = raw_val / 1000.0
            elif "hp" in unit:
                norm_val = raw_val * 0.7457
            else:
                norm_val = raw_val
            res["power_kw"] = norm_val
            res["provenance"]["power_kw"] = {"source_text": span_text, "value": norm_val, "is_explicit": True}
        else:
            res["provenance"]["power_kw"] = {"source_text": None, "value": None, "is_explicit": False}

        # 4. Rotational Speed: e.g. "1500 RPM", "-1500 rpm", "0 RPM"
        rpm_match = re.search(r'(-?\d+(?:\.\d+)?)\s*(rpm|rev/min|rad/s)\b', lower)
        if rpm_match:
            span_text = text[rpm_match.start():rpm_match.end()]
            res["rpm"] = float(rpm_match.group(1))
            res["provenance"]["rpm"] = {"source_text": span_text, "value": res["rpm"], "is_explicit": True}
        else:
            res["provenance"]["rpm"] = {"source_text": None, "value": None, "is_explicit": False}

        # 5. Factor of Safety: e.g. "factor of safety of 2", "FoS 2", "safety factor 2.5", "FoS of 2"
        fos_match = re.search(
            r'(?:factor\s+of\s+safety|safety\s+factor|fos|design\s+factor)\s*(?:of|=|is|:)?\s*(-?\d+(?:\.\d+)?)',
            lower
        )
        if fos_match:
            span_text = text[fos_match.start():fos_match.end()]
            res["factor_of_safety"] = float(fos_match.group(1))
            res["provenance"]["factor_of_safety"] = {
                "source_text": span_text,
                "value": res["factor_of_safety"],
                "is_explicit": True
            }
        else:
            res["provenance"]["factor_of_safety"] = {"source_text": None, "value": None, "is_explicit": False}

        # 6. Length: e.g. "length 300 mm", "length of 300 mm", "0.3 m length", "300 mm long", "length: 300 mm"
        len_match = re.search(
            r'(?:length|span)\s*(?:of|=|is|:)?\s*(-?\d+(?:\.\d+)?)\s*(mm|m|cm|in|inch(?:es)?)\b|'
            r'(-?\d+(?:\.\d+)?)\s*(mm|m|cm|in|inch(?:es)?)\s*(?:in\s+length|long|length|span)\b',
            lower
        )
        if len_match:
            span_text = text[len_match.start():len_match.end()]
            if len_match.group(1) is not None:
                raw_l = float(len_match.group(1))
                unit_l = len_match.group(2)
            else:
                raw_l = float(len_match.group(3))
                unit_l = len_match.group(4)

            if unit_l == "m":
                norm_l = raw_l * 1000.0
            elif unit_l == "cm":
                norm_l = raw_l * 10.0
            elif "in" in unit_l:
                norm_l = raw_l * 25.4
            else:
                norm_l = raw_l

            res["length_mm"] = norm_l
            res["provenance"]["length_mm"] = {"source_text": span_text, "value": norm_l, "is_explicit": True}
        else:
            res["provenance"]["length_mm"] = {"source_text": None, "value": None, "is_explicit": False}

        return res


def extract_requirements(problem_statement: str, provider: Optional[LLMProvider] = None) -> EngineeringSpec:
    """Convenience function for requirement extraction from natural language."""
    return RequirementExtractor(provider=provider).extract(problem_statement)
