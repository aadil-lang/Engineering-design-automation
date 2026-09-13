"""
Candidate Ranking for the Parametric Mechanical Design Engine.
Implements deterministic ranking rules to select optimal candidates.
"""

from typing import List, Tuple, Optional
from solvers.models import AssessmentStatus
from design_engine.models import (
    DesignCandidate,
    DesignObjective,
    DesignStatus
)


class CandidateRanker:
    """
    Ranks evaluated design candidates deterministically based on engineering objectives
    and constraint satisfactions.
    """

    def __init__(self, objective: DesignObjective = DesignObjective.MINIMIZE_SHAFT_DIAMETER):
        self.objective = objective

    def rank(
        self,
        candidates: List[DesignCandidate],
        target_min_fos: Optional[float] = None
    ) -> Tuple[Optional[DesignCandidate], List[DesignCandidate], DesignStatus]:
        """
        Ranks candidates and selects the optimal candidate meeting all criteria.

        Args:
            candidates: Evaluated DesignCandidates with solver assessments and FoS.
            target_min_fos: Optional explicit safety factor threshold to enforce.

        Returns:
            (selected_candidate, alternative_candidates, overall_status)
        """
        if not candidates:
            return None, [], DesignStatus.FAIL

        # Filter candidates that PASS engineering assessment
        passing: List[DesignCandidate] = []
        failing: List[DesignCandidate] = []

        for c in candidates:
            # Must have AssessmentStatus.PASS
            if c.assessment == AssessmentStatus.PASS:
                if target_min_fos is not None:
                    if c.factor_of_safety is not None and c.factor_of_safety >= target_min_fos:
                        passing.append(c)
                    else:
                        failing.append(c)
                else:
                    passing.append(c)
            else:
                failing.append(c)

        if not passing:
            # All candidates failed constraints or allowable limits
            # Order failing candidates by descending safety factor (closest to passing)
            failing_sorted = sorted(
                failing,
                key=lambda x: (x.factor_of_safety or 0.0),
                reverse=True
            )
            return None, failing_sorted, DesignStatus.FAIL

        # Sort passing candidates based on optimization objective
        if self.objective == DesignObjective.MINIMIZE_SHAFT_DIAMETER:
            passing_sorted = sorted(
                passing,
                key=lambda x: x.parameters.get("shaft_diameter", float("inf"))
            )
        else:
            # Default fallback to diameter minimization
            passing_sorted = sorted(
                passing,
                key=lambda x: x.parameters.get("shaft_diameter", float("inf"))
            )

        selected = passing_sorted[0]
        alternatives = passing_sorted[1:]

        return selected, alternatives, DesignStatus.PASS
