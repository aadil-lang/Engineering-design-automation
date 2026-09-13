"""
Explicit Nominal Shaft Diameter Selection Policy (Slice 14.5).
Provides deterministic nominal diameter selection from configured standard metric shaft series.
Enforces strict boundary selection (smallest nominal size >= required diameter)
and out-of-series blocking when required diameter exceeds the configured series.
"""

import math
from typing import List, Optional
from pydantic import BaseModel, Field


# Standard ordered metric nominal shaft diameter series (in mm).
# Covers preferred shaft dimensions commonly specified for mechanical transmission shafts.
DEFAULT_NOMINAL_SHAFT_SERIES: List[float] = [
    6.0, 8.0, 10.0, 12.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0,
    22.0, 24.0, 25.0, 28.0, 30.0, 32.0, 35.0, 38.0, 40.0, 42.0,
    45.0, 48.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0,
    90.0, 95.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 180.0, 200.0
]


class NominalDiameterSelectionResult(BaseModel):
    """
    Structured outcome of deterministic nominal diameter selection.
    Distinguishes theoretical required diameter from selected nominal diameter,
    recording the policy name, series used, and selection rationale.
    """
    is_supported: bool
    selected_diameter_mm: Optional[float] = None
    required_diameter_mm: float
    policy_name: str
    series_used: List[float] = Field(default_factory=list)
    selection_reason: str
    error_message: Optional[str] = None


class NominalDiameterSelectionPolicy:
    """
    Deterministic nominal shaft diameter selection policy.
    Selects the smallest nominal size in the configured series that satisfies d_nominal >= d_required.
    """

    def __init__(
        self,
        series: Optional[List[float]] = None,
        policy_name: str = "metric_nominal_shaft_series_r20_custom"
    ):
        raw_series = series if series is not None else DEFAULT_NOMINAL_SHAFT_SERIES
        # Ensure ordered and unique strictly positive floats
        self.series: List[float] = sorted(list(set(float(x) for x in raw_series if x > 0)))
        if not self.series:
            raise ValueError("Nominal diameter series must contain at least one positive diameter value.")
        self.policy_name: str = policy_name

    @property
    def min_diameter(self) -> float:
        return self.series[0]

    @property
    def max_diameter(self) -> float:
        return self.series[-1]

    def select(self, required_diameter_mm: float) -> NominalDiameterSelectionResult:
        """
        Selects the smallest nominal diameter in the configured series that is >= required_diameter_mm.
        If required_diameter_mm exceeds max_diameter, returns an unsupported result with an explicit error.
        """
        if required_diameter_mm <= 0 or math.isnan(required_diameter_mm) or math.isinf(required_diameter_mm):
            return NominalDiameterSelectionResult(
                is_supported=False,
                selected_diameter_mm=None,
                required_diameter_mm=required_diameter_mm,
                policy_name=self.policy_name,
                series_used=self.series,
                selection_reason=f"Invalid unphysical required diameter: {required_diameter_mm}",
                error_message=f"Required diameter must be a finite positive number; received {required_diameter_mm}."
            )

        # Tolerant comparison for floating point equality
        tol = 1e-9
        for d in self.series:
            if d >= (required_diameter_mm - tol):
                return NominalDiameterSelectionResult(
                    is_supported=True,
                    selected_diameter_mm=d,
                    required_diameter_mm=required_diameter_mm,
                    policy_name=self.policy_name,
                    series_used=self.series,
                    selection_reason=(
                        f"Selected smallest nominal diameter {d:.1f} mm from configured series "
                        f"({self.policy_name}) satisfying d_nominal >= {required_diameter_mm:.2f} mm."
                    ),
                    error_message=None
                )

        # If required diameter exceeds maximum diameter in configured series
        err = (
            f"Required diameter {required_diameter_mm:.2f} mm exceeds maximum nominal diameter "
            f"in configured series ({self.max_diameter:.1f} mm). Requires custom heavy forging or engineering review."
        )
        return NominalDiameterSelectionResult(
            is_supported=False,
            selected_diameter_mm=None,
            required_diameter_mm=required_diameter_mm,
            policy_name=self.policy_name,
            series_used=self.series,
            selection_reason=(
                f"Required diameter {required_diameter_mm:.2f} mm exceeds maximum nominal diameter "
                f"in configured series ({self.max_diameter:.1f} mm)."
            ),
            error_message=err
        )


def select_nominal_diameter(
    required_diameter_mm: float,
    policy: Optional[NominalDiameterSelectionPolicy] = None
) -> NominalDiameterSelectionResult:
    """Convenience function for deterministic nominal diameter selection."""
    pol = policy or NominalDiameterSelectionPolicy()
    return pol.select(required_diameter_mm)
