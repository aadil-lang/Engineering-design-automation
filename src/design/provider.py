"""
Natural language requirement extraction provider abstraction and implementations.
Extracts qualitative and stated mechanical requirements without performing arithmetic calculations.
"""

import os
import re
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from design.config import MACHINE_ELEMENT_SYNONYMS


class DesignSpecificationProvider(ABC):
    """Abstract provider for extracting raw requirement data from problem statements."""

    @abstractmethod
    def extract_raw_data(self, problem_statement: str) -> Dict[str, Any]:
        """Extracts structured raw requirements from natural language problem statement."""
        pass


class MockDesignSpecificationProvider(DesignSpecificationProvider):
    """
    Deterministic rule and pattern-based extractor for offline execution and automated tests.
    Parses machine elements, operating parameters, materials, and loads via grounded regex patterns.
    """

    def __init__(self, canned_data: Optional[Dict[str, Any]] = None):
        self.canned_data = canned_data

    def set_canned_data(self, data: Dict[str, Any]) -> None:
        self.canned_data = data

    def extract_raw_data(self, problem_statement: str) -> Dict[str, Any]:
        if self.canned_data is not None:
            return self.canned_data

        text = problem_statement.strip()
        lower_text = text.lower()

        # 1. Identify machine element(s)
        detected_elements = []
        for elem, syns in MACHINE_ELEMENT_SYNONYMS.items():
            for syn in syns:
                if re.search(r'\b' + re.escape(syn) + r'\b', lower_text):
                    if elem not in detected_elements:
                        detected_elements.append(elem)
                    break

        primary_element = detected_elements[0] if detected_elements else "unknown"

        # 2. Extract Power: e.g. "5 kW", "5000 W", "10 hp"
        power_data = None
        power_match = re.search(r'(\d+(?:\.\d+)?)\s*(kw|w|hp|kilowatts?|watts?|horsepower)\b', lower_text)
        if power_match:
            p_val = float(power_match.group(1))
            p_unit = power_match.group(2).upper()
            if p_unit == "KW":
                p_unit = "kW"
            elif p_unit == "HP":
                p_unit = "hp"
            power_data = {"value": p_val, "unit": p_unit}

        # 3. Extract Speed: e.g. "1500 RPM", "3000 rpm", "100 rad/s"
        speed_data = None
        speed_match = re.search(r'(\d+(?:\.\d+)?)\s*(rpm|rev/min|rad/s)\b', lower_text)
        if speed_match:
            s_val = float(speed_match.group(1))
            s_unit = speed_match.group(2).upper()
            if s_unit == "RAD/S":
                s_unit = "rad/s"
            speed_data = {"value": s_val, "unit": s_unit}

        # 4. Extract Material: e.g. "steel", "aluminum", "AISI 1045", "Grade 8.8"
        material_data = None
        # Check explicit grades first
        grade_match = re.search(r'\b(aisi\s*\d{4}|grade\s*\d+(?:\.\d+)?|class\s*\d+(?:\.\d+)?|6061-t6|s275|s355)\b', lower_text)
        grade_str = grade_match.group(1).upper() if grade_match else None

        mat_name = None
        for m in ("steel", "aluminum", "titanium", "brass", "bronze", "cast iron"):
            if re.search(r'\b' + re.escape(m) + r'\b', lower_text):
                mat_name = m
                break

        if mat_name or grade_str:
            material_data = {
                "material_name": mat_name or "steel",
                "material_grade": grade_str,
                "source": "user_statement"
            }

        # 5. Extract Dimensions: e.g. "diameter of 25 mm", "d=25 mm", "length of 500 mm", "M12"
        geometry = []
        d_match = re.search(r'(?:diameter|dia|d)\s*(?:of|=|is)?\s*(\d+(?:\.\d+)?)\s*(mm|m|in)\b', lower_text)
        if d_match:
            geometry.append({
                "value": float(d_match.group(1)),
                "unit": d_match.group(2),
                "evidence_id": "diameter"
            })

        m_bolt_match = re.search(r'\bm(\d+)\b', lower_text)
        if m_bolt_match and not d_match:
            geometry.append({
                "value": float(m_bolt_match.group(1)),
                "unit": "mm",
                "evidence_id": "bolt_diameter"
            })

        l_match = re.search(r'(?:length|span|l)\s*(?:of|=|is)?\s*(\d+(?:\.\d+)?)\s*(mm|m|in)\b', lower_text)
        if not l_match:
            l_match = re.search(r'(\d+(?:\.\d+)?)\s*(mm|m|in)\s*(?:span|length)\b', lower_text)
        if l_match:
            geometry.append({
                "value": float(l_match.group(1)),
                "unit": l_match.group(2),
                "evidence_id": "length"
            })

        # 6. Extract Loads: e.g. "20 kN tensile load", "load of 15 kN", "torque of 50 N*m"
        loads = []
        tensile_match = re.search(r'(\d+(?:\.\d+)?)\s*(kn|n|lbf)\s*(?:tensile\s+load|axial\s+tension|tension)', lower_text)
        if tensile_match:
            loads.append({
                "load_type": "axial_tension",
                "magnitude": {"value": float(tensile_match.group(1)), "unit": tensile_match.group(2).upper()},
                "direction": "axial"
            })

        shear_match = re.search(r'(\d+(?:\.\d+)?)\s*(kn|n|lbf)\s*(?:shear\s+load|direct\s+shear|transverse)', lower_text)
        if shear_match:
            loads.append({
                "load_type": "direct_shear",
                "magnitude": {"value": float(shear_match.group(1)), "unit": shear_match.group(2).upper()},
                "direction": "transverse"
            })

        # 7. Extract Safety Factor / Constraints
        constraints = []
        fos_match = re.search(r'(?:safety\s+factor|factor\s+of\s+safety|fos|sf)\s*(?:of|>=|=|is)?\s*(\d+(?:\.\d+)?)', lower_text)
        if fos_match:
            constraints.append({
                "constraint_type": "min_safety_factor",
                "value": float(fos_match.group(1)),
                "priority": "high"
            })

        return {
            "machine_element": primary_element,
            "detected_elements": detected_elements,
            "power": power_data,
            "speed": speed_data,
            "material": material_data,
            "geometry": geometry,
            "loads": loads,
            "constraints": constraints,
            "raw_text": text
        }


class GeminiDesignSpecificationProvider(DesignSpecificationProvider):
    """
    LLM-powered extraction provider using the Gemini API.
    Restricted strictly to qualitative requirement extraction and structured JSON generation.
    Does not perform numerical calculations.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-pro"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def extract_raw_data(self, problem_statement: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("Gemini API key not configured.")

        import httpx

        system_prompt = (
            "You are an expert mechanical engineering requirement interpreter. "
            "Extract structured engineering facts from the user's design problem statement. "
            "CRITICAL: Do NOT perform arithmetic or calculate derived quantities (e.g. do not calculate torque from power and speed). "
            "Output strictly valid JSON matching this schema:\n"
            "{\n"
            '  "machine_element": "shaft" | "bolted_joint" | "beam" | "gear" | "bearing" | "spring" | "column" | "pressure_vessel" | "key_joint" | "unknown",\n'
            '  "power": {"value": float, "unit": str} or null,\n'
            '  "speed": {"value": float, "unit": str} or null,\n'
            '  "material": {"material_name": str, "material_grade": str or null} or null,\n'
            '  "geometry": [{"value": float, "unit": str, "evidence_id": str}],\n'
            '  "loads": [{"load_type": str, "magnitude": {"value": float, "unit": str}, "direction": str}],\n'
            '  "constraints": [{"constraint_type": str, "value": float, "priority": str}]\n'
            "}"
        )

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": problem_statement}]}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise RuntimeError("No candidates returned from Gemini API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise RuntimeError("Empty response parts from Gemini API")

            raw_text = parts[0].get("text", "{}")
            return json.loads(raw_text)


def get_design_provider(provider_name: Optional[str] = None) -> DesignSpecificationProvider:
    """Factory to retrieve a design specification provider."""
    p_name = provider_name or os.environ.get("LLM_PROVIDER")
    if p_name == "mock":
        return MockDesignSpecificationProvider()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
    if p_name == "gemini" or (p_name is None and api_key):
        try:
            return GeminiDesignSpecificationProvider(api_key=api_key)
        except Exception:
            return MockDesignSpecificationProvider()

    return MockDesignSpecificationProvider()
