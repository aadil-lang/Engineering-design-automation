import os
import json
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LLMProvider(ABC):
    """Abstract interface for Large Language Model generation providers."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a text completion from system and user prompts.
        """
        pass


class MockLLMProvider(LLMProvider):
    """
    Deterministic Mock LLM Provider for offline operation and reproducible unit tests.
    Generates structured, grounded responses from context evidence without external network calls.
    """

    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response

    def set_response(self, response: str) -> None:
        self.canned_response = response

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.canned_response is not None:
            return self.canned_response

        # Parse evidence JSON embedded in user_prompt
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", user_prompt, re.DOTALL)
        data: Dict[str, Any] = {}
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except Exception:
                data = {}

        q_cat_match = re.search(r"Question Category:\s*(\w+)", user_prompt)
        q_cat = q_cat_match.group(1) if q_cat_match else "general_engineering_question"

        circles = data.get("circle_features", [])
        dimensions = data.get("dimensions", [])
        associations = data.get("associations", [])
        lines = data.get("line_features", [])
        relationships = data.get("relationships", [])

        # Deterministic generation based on category
        if q_cat == "hole_analysis":
            hole_circles = [c for c in circles if c.get("likely_hole")]
            if hole_circles:
                c = hole_circles[0]
                c_id = c.get("id", "circle_0")
                dia = c.get("diameter", 0.0)

                # Check if an associated dimension exists
                assoc_dim_id = None
                dim_val = None
                for a in associations:
                    if a.get("feature_id") == c_id:
                        assoc_dim_id = a.get("dimension_id")
                        break

                for d in dimensions:
                    if d.get("id") == assoc_dim_id:
                        dim_val = d.get("value")
                        break

                ev = [c_id]
                if assoc_dim_id:
                    ev.append(assoc_dim_id)

                facts = [{"statement": f"Feature {c_id} has detected circle diameter of {dia}.", "evidence": [c_id]}]
                inferences = []
                uncertainties = []

                if assoc_dim_id and dim_val is not None:
                    facts.append({"statement": f"Dimension {assoc_dim_id} specifies {dim_val}.", "evidence": [assoc_dim_id]})
                    if abs(dia - dim_val) > 2.0:
                        uncertainties.append({
                            "statement": f"Conflict detected: circle {c_id} measured diameter {dia} differs from dimension {assoc_dim_id} ({dim_val}).",
                            "evidence": [c_id, assoc_dim_id]
                        })
                    else:
                        inferences.append({
                            "statement": f"Dimension {assoc_dim_id} corresponds to candidate hole {c_id}.",
                            "evidence": [c_id, assoc_dim_id]
                        })

                ans = f"The drawing contains {len(hole_circles)} likely hole(s) with nominal diameter around {dia}."
                if uncertainties:
                    ans += f" Note: A discrepancy was observed between measurement ({dia}) and callout ({dim_val})."

                return json.dumps({
                    "answer": ans,
                    "facts": facts,
                    "inferences": inferences,
                    "uncertainties": uncertainties,
                    "evidence": ev,
                    "confidence": {"score": 0.88, "source": "model_heuristic"}
                })
            else:
                return json.dumps({
                    "answer": "No hole candidates were detected in the drawing evidence.",
                    "facts": [],
                    "inferences": [],
                    "uncertainties": [{"statement": "No circular hole features detected.", "evidence": []}],
                    "evidence": [],
                    "confidence": {"score": 0.95, "source": "model_heuristic"}
                })

        elif q_cat == "dimension_summary":
            dim_facts = [
                {"statement": f"Dimension {d['id']} specifies {d.get('raw_text')}.", "evidence": [d['id']]}
                for d in dimensions
            ]
            ev = [d["id"] for d in dimensions]
            return json.dumps({
                "answer": f"Detected {len(dimensions)} dimensions: " + ", ".join(d.get("raw_text", "") for d in dimensions) if dimensions else "No dimensions found.",
                "facts": dim_facts,
                "inferences": [],
                "uncertainties": [],
                "evidence": ev,
                "confidence": {"score": 0.92, "source": "model_heuristic"}
            })

        elif q_cat == "relationship_analysis":
            rel_facts = [
                {"statement": f"Relationship {r.get('type')} detected between {r.get('source_id')} and {r.get('target_id')}.", "evidence": [r.get('source_id'), r.get('target_id')]}
                for r in relationships if r.get('source_id') and r.get('target_id')
            ]
            ev = list(set([r['source_id'] for r in relationships if 'source_id' in r] + [r['target_id'] for r in relationships if 'target_id' in r]))
            return json.dumps({
                "answer": f"Detected {len(relationships)} geometric relationship(s).",
                "facts": rel_facts,
                "inferences": [],
                "uncertainties": [],
                "evidence": ev,
                "confidence": {"score": 0.90, "source": "model_heuristic"}
            })

        # Generic fallback
        return json.dumps({
            "answer": "Analyzed drawing evidence based on detected geometric entities.",
            "facts": [{"statement": f"Drawing contains {len(lines)} lines, {len(circles)} circles, and {len(dimensions)} dimensions.", "evidence": [c['id'] for c in circles[:2]] + [l['id'] for l in lines[:2]]}],
            "inferences": [],
            "uncertainties": [],
            "evidence": [c['id'] for c in circles[:2]] + [l['id'] for l in lines[:2]],
            "confidence": {"score": 0.85, "source": "model_heuristic"}
        })


class GeminiProvider(LLMProvider):
    """
    Lightweight Gemini API provider using httpx.
    Requires GEMINI_API_KEY or LLM_API_KEY environment variable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL", "gemini-2.5-flash")
        self.base_url = base_url or os.environ.get(
            "LLM_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/models"
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError(
                "Gemini API key not configured. Please set GEMINI_API_KEY or LLM_API_KEY."
            )

        import httpx

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
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

            return parts[0].get("text", "")


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory to retrieve an LLM provider.
    Defaults to MockLLMProvider when no API key is set or when provider_name is 'mock'.
    """
    p_name = provider_name or os.environ.get("LLM_PROVIDER")

    if p_name == "mock":
        return MockLLMProvider()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
    if p_name == "gemini" or (p_name is None and api_key):
        try:
            return GeminiProvider(api_key=api_key)
        except Exception:
            return MockLLMProvider()

    return MockLLMProvider()
