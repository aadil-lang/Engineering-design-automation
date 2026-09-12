# Deterministic Mechanical Solver Engine

This module provides a deterministic, machine-element agnostic calculation framework for mechanical engineering analysis.

---

## 1. Architectural Philosophy

1. **Deterministic Execution**: Numerical calculations are performed solely by deterministic analytical Python solvers. LLMs are strictly forbidden from performing arithmetic or altering equations.
2. **Machine-Element Agnosticism**: The engine supports multiple machine element families (`MachineElementType`), including `shaft`, `bolted_joint`, `beam`, `gear`, `bearing`, `spring`, `pressure_vessel`, `column`, `key_joint`, etc.
3. **Traceability & Auditability**: Every calculation generates an immutable `CalculationCertificate` containing:
   - Analytical formula and governing theory
   - Substituted numerical values with SI-converted quantities
   - Canonical physical dimensions and explicit units
   - Explicit engineering assumptions and operational limitations
   - Input provenance linking parameters back to drawing geometry, OCR annotations, user input, or defaults.
4. **Separation of Concerns**:
   - **Semantic Extraction / Geometry**: Identifies features (e.g. shafts, holes, bolts).
   - **LLM / Engineering Reasoner**: Reasons qualitatively, interprets standards, and formulates user intent.
   - **Analysis Planner**: Formulates candidate calculation plans without running numerical routines.
   - **Solver Engine**: Validates inputs deterministically and executes analytical equations.

---

## 2. Machine Element Architecture

### `MachineElementType`
An enumeration of supported mechanical components:
```python
class MachineElementType(str, Enum):
    SHAFT = "shaft"
    BOLTED_JOINT = "bolted_joint"
    BEAM = "beam"
    GEAR = "gear"
    BEARING = "bearing"
    SPRING = "spring"
    PRESSURE_VESSEL = "pressure_vessel"
    COLUMN = "column"
    KEY_JOINT = "key_joint"
    GENERIC = "generic"
```

### `AnalysisCapability`
Metadata describing each solver:
- `solver_id`: Unique canonical identifier (e.g., `py_mech_bolt_tension_v1`).
- `machine_element`: The target `MachineElementType`.
- `name` & `description`: Human-readable title and summary.
- `governing_equation`: Symbolic formula (e.g., `sigma_t = F_t / A_t`).
- `required_inputs` & `optional_inputs`: Typed parameter requirements.
- `output_fields`: Names of computed scalar outputs.
- `assumptions` & `limitations`: Engineering boundaries and valid regimes.

---

## 3. Capability Discovery

The `SolverRegistry` acts as the central capability broker:
```python
from solvers import default_registry, MachineElementType

# Discover supported machine elements
elements = default_registry.list_machine_elements()
# ['shaft', 'bolted_joint']

# Query available capabilities for an element
bolt_caps = default_registry.get_capabilities_for_element(MachineElementType.BOLTED_JOINT)
for cap in bolt_caps:
    print(f"{cap.solver_id}: {cap.name}")

# Retrieve a specific solver
solver = default_registry.get_solver("py_mech_bolt_tension_v1")
```

---

## 4. Supported Solvers

### Shaft Analysis (`MachineElementType.SHAFT`)
| Solver ID | Name | Governing Equation | Primary Outputs |
| :--- | :--- | :--- | :--- |
| `py_mech_shaft_torsion_v1` | Shaft Torsion Analysis | $\tau = \frac{T \cdot r}{J}$ | `shear_stress`, `polar_moment_of_inertia`, `safety_factor` |
| `py_mech_shaft_bending_v1` | Shaft Bending Stress Analysis | $\sigma = \frac{M \cdot c}{I}$ | `bending_stress`, `area_moment_of_inertia`, `safety_factor` |
| `py_mech_shaft_combined_stress_v1` | Shaft Combined Stress Analysis | $\sigma_v = \sqrt{\sigma^2 + 3\tau^2}$ | `von_mises_stress`, `max_principal_stress`, `safety_factor` |

### Bolted Joint Analysis (`MachineElementType.BOLTED_JOINT`)
| Solver ID | Name | Governing Equation | Primary Outputs |
| :--- | :--- | :--- | :--- |
| `py_mech_bolt_tension_v1` | Bolt Tensile Stress Analysis | $\sigma_t = \frac{F_t}{n \cdot A_t}$ | `tensile_stress`, `tensile_stress_area`, `safety_factor` |
| `py_mech_bolt_shear_v1` | Bolt Direct Shear Analysis | $\tau = \frac{F_v}{n \cdot m \cdot A_s}$ | `shear_stress`, `shear_area`, `safety_factor` |
| `py_mech_bolt_combined_stress_v1` | Bolt Combined Stress Analysis | $\sigma_v = \sqrt{\sigma_t^2 + 3\tau^2}$ | `von_mises_stress`, `max_principal_stress`, `safety_factor` |
| `py_mech_bolt_preload_v1` | Bolt Preload Analysis | $F_i = k_{preload} \cdot S_p \cdot A_t$ | `preload_force`, `tightening_torque`, `proof_load` |

---

## 5. Adding New Machine Elements

To add a new machine element family (e.g., `BEAM`, `GEAR`, or `BEARING`):

1. **Ensure `MachineElementType` contains the element**:
   In `src/solvers/models.py`, verify or add the member to `MachineElementType`.

2. **Implement Subclass of `MechanicalSolver`**:
   Create a new module, e.g., `src/solvers/beam.py`:
   ```python
   from solvers.base import MechanicalSolver
   from solvers.models import MachineElementType, SolverResult, SolverInputSpec

   class BeamDeflectionSolver(MechanicalSolver):
       machine_element = MachineElementType.BEAM

       def __init__(self):
           super().__init__(
               solver_id="py_mech_beam_deflection_v1",
               name="Beam Deflection Solver",
               description="Calculates simply supported beam midpoint deflection under central point load.",
               governing_equation="delta = (F * L^3) / (48 * E * I)",
               required_inputs=[
                   SolverInputSpec(name="load", physical_dimension="force", default_unit="N"),
                   SolverInputSpec(name="span_length", physical_dimension="length", default_unit="mm"),
                   SolverInputSpec(name="youngs_modulus", physical_dimension="pressure", default_unit="GPa"),
                   SolverInputSpec(name="area_moment_of_inertia", physical_dimension="second_moment_of_area", default_unit="mm^4"),
               ],
               output_fields=["deflection"],
               assumptions=["Linear elastic material", "Euler-Bernoulli beam theory", "Small deflections"],
               limitations=["Does not account for shear deformation (Timoshenko effect)"],
           )

       def solve(self, inputs: dict) -> SolverResult:
           # 1. Deterministic validation
           # 2. Canonical SI conversion
           # 3. Calculation
           # 4. Return SolverResult with steps and certificate
           ...
   ```

3. **Register the Solver in `src/solvers/registry.py`**:
   ```python
   registry.register_solver("py_mech_beam_deflection_v1", BeamDeflectionSolver())
   ```

4. **Add Analysis Type and Mappings in `src/analysis/`**:
   - Define enum in `src/analysis/models.py`.
   - Add mapping, priority, and required inputs in `src/analysis/config.py`.
   - Update planner heuristics in `src/analysis/planner.py` to recognize relevant geometry/features or opt-in flags.

5. **Write Comprehensive Unit Tests**:
   - Verify calculation correctness against textbook or standard benchmark values.
   - Verify input validation (missing inputs, non-positive values, invalid units).
   - Verify capability discovery and registry indexing.
