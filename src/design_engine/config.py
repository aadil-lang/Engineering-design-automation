"""
Configuration parameters and engineering defaults for the Parametric Mechanical Design Engine.
"""

# Default search bounds for solid circular shaft diameter when unspecified by user
DEFAULT_DIAMETER_MIN_MM: float = 5.0
DEFAULT_DIAMETER_MAX_MM: float = 250.0
DEFAULT_DIAMETER_STEP_MM: float = 1.0

# Conflict detection threshold between explicit torque and power/speed-derived torque
# Divergence greater than this percentage triggers requirement conflict and human review
TORQUE_CONFLICT_TOLERANCE_PCT: float = 1.0

# Yield strength to shear yield strength conversion factors
# Based on classical failure theories for ductile metals
DISTORTION_ENERGY_SHEAR_FACTOR: float = 0.57735  # S_sy = 1/sqrt(3) * S_y (von Mises)
TRESCA_SHEAR_FACTOR: float = 0.50                # S_sy = 0.5 * S_y (Maximum Shear Stress)
DEFAULT_SHEAR_STRENGTH_THEORY: str = "von_mises"

# Standard assumptions text for candidate generation
ASSUMPTION_DEFAULT_SEARCH_RANGE = (
    f"Candidate diameter search range configured to default [{DEFAULT_DIAMETER_MIN_MM} mm - {DEFAULT_DIAMETER_MAX_MM} mm] "
    f"with {DEFAULT_DIAMETER_STEP_MM} mm increment; specific manufacturing size catalogue not supplied."
)
ASSUMPTION_SOLID_CIRCULAR = (
    "Uniform solid circular cross-section assumed throughout evaluated torque transmission zone."
)
ASSUMPTION_STATIC_TORSION = (
    "Sizing evaluated under static steady-state torsional load; fatigue endurance limit and dynamic shock factors omitted."
)
ASSUMPTION_NO_STRESS_CONCENTRATION = (
    "Ideal smooth shaft without keyways, splines, snap-ring grooves, or shoulder fillets (Kt = 1.0)."
)
