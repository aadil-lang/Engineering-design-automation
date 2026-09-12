"""
Unit tests for generalized machine-element analysis architecture and capability discovery.
"""

import pytest
from solvers import (
    get_solver_registry,
    SolverRegistry,
    MachineElementType,
    AnalysisCapability,
    solve_torsion,
    solve_bolt_tension
)
from solvers.torsion import ShaftTorsionSolver


def test_machine_element_listing():
    """Registry must discover supported machine element classifications."""
    reg = get_solver_registry()
    elements = reg.list_machine_elements()

    assert MachineElementType.SHAFT in elements
    assert MachineElementType.BOLTED_JOINT in elements


def test_shaft_capabilities_discovery():
    """Verify discovery of all shaft analysis capabilities."""
    reg = get_solver_registry()
    shaft_caps = reg.get_capabilities_for_element(MachineElementType.SHAFT)

    assert len(shaft_caps) >= 3
    types = [c.analysis_type for c in shaft_caps]
    assert "shaft_torsion" in types
    assert "shaft_bending" in types
    assert "shaft_combined_stress" in types

    for cap in shaft_caps:
        assert cap.machine_element == MachineElementType.SHAFT
        assert cap.is_solver_available is True
        assert len(cap.required_inputs) > 0
        assert len(cap.limitations) > 0


def test_bolted_joint_capabilities_discovery():
    """Verify discovery of all bolted joint analysis capabilities."""
    reg = get_solver_registry()
    bolt_caps = reg.get_capabilities_for_element(MachineElementType.BOLTED_JOINT)

    assert len(bolt_caps) >= 4
    types = [c.analysis_type for c in bolt_caps]
    assert "bolt_tension" in types
    assert "bolt_shear" in types
    assert "bolt_combined_stress" in types
    assert "bolt_preload" in types

    for cap in bolt_caps:
        assert cap.machine_element == MachineElementType.BOLTED_JOINT
        assert cap.is_solver_available is True


def test_get_capability_by_key():
    """Lookup capability metadata by analysis type string or legacy alias."""
    reg = get_solver_registry()

    cap_tension = reg.get_capability("bolt_tension")
    assert cap_tension is not None
    assert cap_tension.analysis_type == "bolt_tension"
    assert cap_tension.machine_element == MachineElementType.BOLTED_JOINT
    assert "bolt_diameter" in cap_tension.required_inputs
    assert "tensile_load" in cap_tension.required_inputs

    cap_torsion = reg.get_capability("torsion")
    assert cap_torsion is not None
    assert cap_torsion.machine_element == MachineElementType.SHAFT

    assert reg.get_capability("non_existent_capability") is None


def test_unknown_machine_element_discovery():
    """Querying capabilities for an unimplemented machine element returns an empty list."""
    reg = get_solver_registry()
    gear_caps = reg.get_capabilities_for_element(MachineElementType.GEAR)
    assert gear_caps == []

    spring_caps = reg.get_capabilities_for_element(MachineElementType.SPRING)
    assert spring_caps == []


def test_certificate_records_machine_element():
    """Generated certificates must explicitly record the machine element type."""
    shaft_cert = solve_torsion(torque=31.8, shaft_diameter=25.0)
    assert shaft_cert.machine_element == MachineElementType.SHAFT

    bolt_cert = solve_bolt_tension(bolt_diameter=12.0, tensile_load=10000.0)
    assert bolt_cert.machine_element == MachineElementType.BOLTED_JOINT


def test_extensible_custom_element_registration():
    """Verify extending registry with a new machine element category (e.g. BEAM)."""
    custom_reg = SolverRegistry()
    solver = ShaftTorsionSolver()

    # Register under custom element
    custom_reg.register_solver(
        solver_id="custom_beam_v1",
        solver=solver,
        analysis_types=["beam_torsion"],
        machine_element=MachineElementType.BEAM
    )

    assert custom_reg.is_available("beam_torsion")
    assert MachineElementType.BEAM in custom_reg.list_machine_elements()
    beam_caps = custom_reg.get_capabilities_for_element(MachineElementType.BEAM)
    assert len(beam_caps) == 1
    assert beam_caps[0].solver_id == "custom_beam_v1"
