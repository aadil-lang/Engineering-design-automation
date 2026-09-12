"""
Configuration and constants for engineering knowledge and rules.
"""

# Engineering Knowledge Domains
DOMAIN_STRENGTH: str = "strength"
DOMAIN_FATIGUE: str = "fatigue"
DOMAIN_STABILITY: str = "stability"
DOMAIN_STIFFNESS: str = "stiffness"
DOMAIN_TOLERANCING: str = "tolerancing"
DOMAIN_MANUFACTURING: str = "manufacturing"
DOMAIN_MATERIALS: str = "materials"

# Sourcing Defaults
DEFAULT_BUILT_IN_SOURCE: str = "built_in_rule"
DEFAULT_BUILT_IN_REF: str = "internal-engineering-rule"

# Geometry / Applicability Thresholds
BUCKLING_SLENDERNESS_MIN: float = 10.0

# Confidence Ratings
RULE_CONFIDENCE_EXPLICIT: float = 0.95
RULE_CONFIDENCE_POTENTIAL: float = 0.80
