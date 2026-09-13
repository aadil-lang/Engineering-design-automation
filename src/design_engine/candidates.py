"""
Candidate Generation for Parametric Mechanical Design.
Produces discrete mechanical candidates over parameterized search spaces.
"""

import math
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from design_engine.models import DesignVariable


class CandidateGenerator(ABC):
    """Abstract base class for parametric machine element candidate generators."""

    @abstractmethod
    def generate(self, **kwargs) -> List[Dict[str, Any]]:
        """Generates a list of discrete candidate parameter configurations."""
        pass


class ShaftDiameterCandidateGenerator(CandidateGenerator):
    """
    Generates discrete diameter candidates for solid circular shafts.
    Explores candidate sizes around and above the analytically required minimum diameter.
    """

    def __init__(self, max_candidates: int = 12):
        self.max_candidates = max_candidates

    def generate(
        self,
        variable: DesignVariable,
        required_min_diameter_mm: Optional[float] = None,
        include_sub_critical: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Produces discrete candidate diameters based on design variable bounds and required minimum.

        Args:
            variable: The DesignVariable defining lower/upper bounds and step increment.
            required_min_diameter_mm: The continuous closed-form minimum diameter required.
            include_sub_critical: If True, includes one candidate immediately below required minimum
                                  to demonstrate constraint violation and prove boundary enforcement.
        """
        step = variable.step or 1.0
        lb = variable.lower_bound if variable.lower_bound is not None else 5.0
        ub = variable.upper_bound if variable.upper_bound is not None else 250.0

        if required_min_diameter_mm is not None and required_min_diameter_mm > 0:
            # Baseline is the integer step bracket enclosing required_min_diameter
            first_passing_step = math.ceil(round(required_min_diameter_mm, 6) / step) * step

            if include_sub_critical:
                start_d = first_passing_step - step
            else:
                start_d = first_passing_step

            # Ensure start_d stays within configured bounds
            if start_d < lb:
                start_d = lb
        else:
            start_d = lb

        candidates: List[Dict[str, Any]] = []
        curr_d = start_d
        count = 0

        while curr_d <= ub and count < self.max_candidates:
            # Avoid floating point precision issues like 25.000000000000004
            clean_d = round(curr_d, 4)
            cand_id = f"cand-shaft-{clean_d:.3g}mm".replace(".", "_")

            candidates.append({
                "candidate_id": cand_id,
                "shaft_diameter": clean_d,
                "shaft_diameter_mm": clean_d,
                "is_below_theoretical_min": (required_min_diameter_mm is not None and clean_d < required_min_diameter_mm)
            })

            curr_d += step
            count += 1

        return candidates
