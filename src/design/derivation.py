"""
Deterministic engineering derivation framework for design specifications.
Executes closed-form mathematical derivations (e.g., Power + Speed -> Torque) with zero LLM arithmetic.
"""

import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from design.models import DerivedEngineeringValue, OperatingCondition
from design.normalization import normalize_power, normalize_rotational_speed


class DerivationRule(ABC):
    """Abstract base class for extensible deterministic engineering derivations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the derived engineering parameter."""
        pass

    @abstractmethod
    def can_derive(self, context: Dict[str, Any]) -> bool:
        """Determines if sufficient input parameters exist to execute this closed-form derivation."""
        pass

    @abstractmethod
    def derive(self, context: Dict[str, Any]) -> Optional[DerivedEngineeringValue]:
        """Executes the closed-form calculation and returns auditable mathematical steps."""
        pass


class PowerSpeedToTorqueRule(DerivationRule):
    """
    Derives nominal transmitted shaft torque from mechanical power and rotational speed:
    omega = 2 * pi * N / 60
    T = P / omega
    """

    @property
    def name(self) -> str:
        return "torque"

    def can_derive(self, context: Dict[str, Any]) -> bool:
        has_power = "power" in context and context["power"] is not None
        has_speed = any(k in context and context[k] is not None for k in ("speed", "rotational_speed", "rpm", "N"))
        return has_power and has_speed

    def derive(self, context: Dict[str, Any]) -> Optional[DerivedEngineeringValue]:
        if not self.can_derive(context):
            return None

        # 1. Extract and normalize Power
        p_raw = context.get("power")
        if p_raw is None and "P" in context:
            p_raw = context["P"]

        if p_raw is None:
            raise ValueError("Power must be specified for torque derivation.")

        if isinstance(p_raw, dict):
            p_val = float(p_raw.get("value", 0.0))
            p_unit = p_raw.get("unit", "kW")
        else:
            p_val = float(p_raw)
            p_unit = context.get("power_unit", "kW")

        if p_val <= 0:
            raise ValueError(f"Power must be strictly positive for torque derivation; received {p_val}.")

        p_watts, _, _ = normalize_power(p_val, p_unit)

        # 2. Extract and normalize Speed
        s_raw = None
        for k in ("speed", "rotational_speed", "rpm", "N"):
            if k in context and context[k] is not None:
                s_raw = context[k]
                break

        if s_raw is None:
            raise ValueError("Rotational speed must be specified for torque derivation.")

        if isinstance(s_raw, dict):
            s_val = float(s_raw.get("value", 0.0))
            s_unit = s_raw.get("unit", "RPM")
        else:
            s_val = float(s_raw)
            s_unit = context.get("speed_unit", "RPM")

        if s_val <= 0:
            raise ValueError(f"Rotational speed must be strictly positive for torque derivation; received {s_val}.")

        rpm_val, _, omega_rad_s, _ = normalize_rotational_speed(s_val, s_unit)

        # 3. Calculate Torque T = P / omega
        torque_nm = p_watts / omega_rad_s

        steps = [
            f"1. Normalize power: P = {p_val:.4g} {p_unit} = {p_watts:.2f} W",
            f"2. Convert rotational speed to angular velocity: omega = 2 * pi * N / 60 = 2 * pi * ({rpm_val:.4g} RPM) / 60 = {omega_rad_s:.4f} rad/s",
            f"3. Calculate transmitted torque: T = P / omega = {p_watts:.2f} W / {omega_rad_s:.4f} rad/s = {torque_nm:.3f} N*m"
        ]

        assumptions = [
            "Steady-state torsional load without dynamic service shock factor (service factor Ka = 1.0).",
            "100% mechanical drive transmission efficiency (ideal mechanical coupling assumed)."
        ]

        return DerivedEngineeringValue(
            name="torque",
            formula="T = P / omega = 60 * P / (2 * pi * N)",
            inputs={
                "power": f"{p_val:.4g} {p_unit}",
                "power_normalized_w": p_watts,
                "rotational_speed": f"{s_val:.4g} {s_unit}",
                "speed_normalized_rpm": rpm_val,
                "angular_velocity_rad_s": round(omega_rad_s, 4)
            },
            output_value=round(torque_nm, 4),
            output_unit="N*m",
            calculation_steps=steps,
            provenance="derived_calculation",
            assumptions=assumptions
        )


class DerivationEngine:
    """Orchestrates available deterministic derivation rules over extracted context."""

    def __init__(self, rules: Optional[List[DerivationRule]] = None):
        self.rules = rules or [PowerSpeedToTorqueRule()]

    def execute(self, context: Dict[str, Any]) -> List[DerivedEngineeringValue]:
        derived: List[DerivedEngineeringValue] = []
        for rule in self.rules:
            if rule.can_derive(context):
                res = rule.derive(context)
                if res:
                    derived.append(res)
        return derived
