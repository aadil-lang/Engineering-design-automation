"""
End-to-End Engineering Design Pipeline Orchestration (Slice 14.4 & Material Knowledge Base v1).
Connects natural-language requirement interpretation, field-level provenance tracking,
deterministic material property resolution, deterministic schema validation,
closed-form mechanical engineering sizing, parametric 3D BRep CAD modeling,
2D technical drawing derivation, dimensional cross-validation, and unified engineering
handoff packaging without duplicating domain logic.
"""

import os
from typing import Dict, Any, Optional, List

from requirements.models import (
    EngineeringSpec,
    FieldProvenance,
    RequirementValidationStatus,
    PipelineStatus,
    EngineeringResult,
    EndToEndDesignResult
)
from requirements.extractor import RequirementExtractor
from requirements.solver import ShaftEngineeringSolver, solve_engineering_spec
from cad.models import CADSpecification, CADStatus, CADArtifact, EngineeringHandoff
from cad.generator import CADGenerator
from cad.interfaces import CADBackend
from cad.handoff import create_engineering_handoff_package
from knowledge.materials.repository import MaterialRepository, get_default_material_repository
from knowledge.materials.schema import MaterialResolutionResult


class EndToEndPipeline:
    """
    Deterministic End-to-End Engineering Design Pipeline Orchestrator.
    Executes the complete requirement-to-manufacturing-handoff sequence:

    1. Natural Language Requirement Interpretation (LLM / Rule-based)
    2. Structured Input Overlay & Field-Level Provenance Tracking
    3. Deterministic Material Property Resolution (Material Knowledge Base v1)
    4. Deterministic Engineering Validation & Analytical Solver Execution
    5. Parametric 3D Solid Model Synthesis (BRep topology & volume validation)
    6. ISO-10303-21 STEP File Export
    7. 2D Technical Drawing Projections & SVG Rendering
    8. CAD <-> Drawing Dimensional Cross-Validation
    9. Unified Engineering Handoff Package Construction
    """

    def __init__(
        self,
        llm_provider: Optional[Any] = None,
        cad_backend: Optional[CADBackend] = None,
        extractor: Optional[RequirementExtractor] = None,
        solver: Optional[ShaftEngineeringSolver] = None,
        cad_generator: Optional[CADGenerator] = None,
        material_repository: Optional[MaterialRepository] = None
    ):
        self.extractor = extractor or RequirementExtractor(provider=llm_provider)
        self.solver = solver or ShaftEngineeringSolver()
        self.cad_generator = cad_generator or CADGenerator(backend=cad_backend)
        self.material_repository = material_repository or get_default_material_repository()

    def run(
        self,
        problem_statement: str,
        extra_inputs: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None
    ) -> EndToEndDesignResult:
        """
        Executes the complete deterministic engineering pipeline from problem statement to handoff.
        """
        extra_inputs = extra_inputs or {}
        warnings: List[str] = []
        errors: List[str] = []

        # ======================================================================
        # Step 1: Requirement Extraction & Provenance Tracking (Slice 14.2)
        # ======================================================================
        spec: EngineeringSpec = self.extractor.extract(problem_statement)

        if "fields" not in spec.provenance:
            spec.provenance["fields"] = {}

        # ======================================================================
        # Step 2: Overlay Explicit Structured Inputs & Update Provenance
        # ======================================================================
        # Yield strength (Sy) tracking
        explicit_sy_supplied = False
        if "yield_strength_mpa" in extra_inputs or "yield_strength" in extra_inputs:
            sy_val = (
                extra_inputs.get("yield_strength_mpa")
                if extra_inputs.get("yield_strength_mpa") is not None
                else extra_inputs.get("yield_strength")
            )
            spec.yield_strength_mpa = float(sy_val) if sy_val is not None else None
            explicit_sy_supplied = (spec.yield_strength_mpa is not None)
            sy_prov = {
                "field_name": "yield_strength_mpa",
                "value": spec.yield_strength_mpa,
                "source_text": "structured_input",
                "is_explicit": True,
                "confidence": 1.0
            }
            spec.provenance["fields"]["yield_strength_mpa"] = sy_prov
            spec.provenance["yield_strength_mpa"] = sy_prov
        elif spec.yield_strength_mpa is not None:
            explicit_sy_supplied = True

        # Length (L) must be explicitly supplied
        if "length_mm" in extra_inputs or "length" in extra_inputs:
            len_val = (
                extra_inputs.get("length_mm")
                if extra_inputs.get("length_mm") is not None
                else extra_inputs.get("length")
            )
            spec.length_mm = float(len_val) if len_val is not None else None
            len_prov = {
                "field_name": "length_mm",
                "value": spec.length_mm,
                "source_text": "structured_input",
                "is_explicit": True,
                "confidence": 1.0
            }
            spec.provenance["fields"]["length_mm"] = len_prov
            spec.provenance["length_mm"] = len_prov

        # Material from structured input takes precedence over prompt material
        if "material" in extra_inputs and extra_inputs["material"]:
            spec.material = str(extra_inputs["material"])
            mat_prov = {
                "field_name": "material",
                "value": spec.material,
                "source_text": "structured_input",
                "is_explicit": True,
                "confidence": 1.0
            }
            spec.provenance["fields"]["material"] = mat_prov
            spec.provenance["material"] = mat_prov

        # Overlay any additional explicit parameters
        for k, v in extra_inputs.items():
            if k not in ("yield_strength_mpa", "yield_strength", "length_mm", "length", "material"):
                if hasattr(spec, k) and getattr(spec, k) is None:
                    setattr(spec, k, v)
                    k_prov = {
                        "field_name": k,
                        "value": v,
                        "source_text": "structured_input",
                        "is_explicit": True,
                        "confidence": 1.0
                    }
                    spec.provenance["fields"][k] = k_prov
                    spec.provenance[k] = k_prov
                spec.extra_parameters[k] = v

        # ======================================================================
        # Step 3: Deterministic Material Knowledge Base Resolution (v1)
        # ======================================================================
        mat_res: MaterialResolutionResult = self.material_repository.resolve(
            requested_material=spec.material,
            explicit_yield_strength_mpa=spec.yield_strength_mpa
        )

        if explicit_sy_supplied:
            # User explicitly supplied yield strength -> takes precedence over KB value
            if mat_res.is_explicit_override:
                warnings.extend(mat_res.warnings)
            if mat_res.resolved and mat_res.material_record:
                spec.material = mat_res.resolved_material
                spec.extra_parameters["material_record"] = mat_res.material_record.model_dump()
        else:
            if mat_res.resolved and mat_res.yield_strength_mpa is not None:
                # KB resolved yield strength
                spec.yield_strength_mpa = mat_res.yield_strength_mpa
                spec.material = mat_res.resolved_material
                if mat_res.material_record:
                    spec.extra_parameters["material_record"] = mat_res.material_record.model_dump()
                kb_prov = {
                    "field_name": "yield_strength_mpa",
                    "value": spec.yield_strength_mpa,
                    "source_text": f"Knowledge Base ({mat_res.standard})",
                    "is_explicit": False,
                    "confidence": 1.0
                }
                spec.provenance["fields"]["yield_strength_mpa"] = kb_prov
                spec.provenance["yield_strength_mpa"] = kb_prov
            else:
                # Unresolved -> do NOT fabricate
                spec.yield_strength_mpa = None

        serialized_mat_res = mat_res.model_dump()
        spec.provenance["material_resolution"] = serialized_mat_res

        # Flatten field provenances into top-level for convenience as well
        for fn, fprov in spec.provenance.get("fields", {}).items():
            if fn not in spec.provenance:
                spec.provenance[fn] = fprov

        # ======================================================================
        # Step 4: Deterministic Mechanical Sizing via Analytical Solver (Slice 14.3)
        # ======================================================================
        solver_result: EngineeringResult = self.solver.solve(spec)

        # Serialize provenance dict for safety
        serialized_prov = {
            k: (v.model_dump() if hasattr(v, "model_dump") else v)
            for k, v in spec.provenance.items()
        }

        # If solver blocked or invalid, halt pipeline cleanly before CAD generation
        if solver_result.status == RequirementValidationStatus.BLOCKED:
            report = self._generate_report(
                status=PipelineStatus.BLOCKED,
                spec=spec,
                solver_result=solver_result,
                cad_res=None,
                handoff=None,
                material_resolution=serialized_mat_res
            )
            return EndToEndDesignResult(
                status=PipelineStatus.BLOCKED,
                spec=spec,
                provenance=serialized_prov,
                material_resolution=serialized_mat_res,
                solver_result=solver_result,
                cad_status=CADStatus.BLOCKED.value,
                missing_information=solver_result.missing_information,
                errors=solver_result.errors,
                warnings=warnings + solver_result.warnings,
                report=report
            )

        if solver_result.status == RequirementValidationStatus.INVALID:
            report = self._generate_report(
                status=PipelineStatus.INVALID,
                spec=spec,
                solver_result=solver_result,
                cad_res=None,
                handoff=None,
                material_resolution=serialized_mat_res
            )
            return EndToEndDesignResult(
                status=PipelineStatus.INVALID,
                spec=spec,
                provenance=serialized_prov,
                material_resolution=serialized_mat_res,
                solver_result=solver_result,
                cad_status=CADStatus.FAILED.value,
                missing_information=solver_result.missing_information,
                errors=solver_result.errors,
                warnings=warnings + solver_result.warnings,
                report=report
            )

        # ======================================================================
        # Step 5: Parametric CAD & 2D Engineering Drawing Synthesis (Slice 13)
        # ======================================================================
        cad_spec = CADSpecification(
            machine_element=solver_result.component or "shaft",
            part_name=f"SHAFT_{int(solver_result.selected_diameter_mm)}X{int(solver_result.length_mm)}",
            material=solver_result.material,
            diameter=solver_result.selected_diameter_mm,
            length=solver_result.length_mm,
            units="mm",
            parameters={
                "power_kw": solver_result.power_kw,
                "rpm": solver_result.rpm,
                "torque_nm": solver_result.torque_nm,
                "yield_strength_mpa": solver_result.yield_strength_mpa,
                "factor_of_safety_required": solver_result.factor_of_safety,
                "allowable_stress_mpa": solver_result.allowable_stress_mpa,
                "minimum_required_diameter_mm": solver_result.minimum_required_diameter_mm,
                "selected_diameter_mm": solver_result.selected_diameter_mm,
                "design_stress_mpa": solver_result.design_stress_mpa,
                "achieved_factor_of_safety": solver_result.achieved_factor_of_safety,
                "length_mm": solver_result.length_mm
            },
            provenance=serialized_prov,
            assumptions=solver_result.assumptions
        )

        try:
            cad_res = self.cad_generator.generate(cad_spec, output_dir=output_dir)
        except Exception as e:
            err_msg = f"CAD synthesis failed: {str(e)}"
            errors.append(err_msg)
            report = self._generate_report(
                status=PipelineStatus.FAILED,
                spec=spec,
                solver_result=solver_result,
                cad_res=None,
                handoff=None,
                material_resolution=serialized_mat_res
            )
            return EndToEndDesignResult(
                status=PipelineStatus.FAILED,
                spec=spec,
                provenance=serialized_prov,
                material_resolution=serialized_mat_res,
                solver_result=solver_result,
                cad_status=CADStatus.FAILED.value,
                errors=errors,
                warnings=warnings,
                report=report
            )

        # ======================================================================
        # Step 6: Construct Engineering Handoff Package (Slice 13)
        # ======================================================================
        handoff: EngineeringHandoff = create_engineering_handoff_package(
            cad_specification=cad_spec,
            cad_artifacts=cad_res.artifacts,
            drawing_document=cad_res.drawing_document,
            validation_result=cad_res.validation,
            design_result=solver_result
        )

        # Enrich traceability matrix with analytical solver and material resolution outputs
        if "parameters" in handoff.traceability_matrix:
            handoff.traceability_matrix["solver_metrics"] = {
                "torque_nm": solver_result.torque_nm,
                "yield_strength_mpa": solver_result.yield_strength_mpa,
                "allowable_stress_mpa": solver_result.allowable_stress_mpa,
                "minimum_required_diameter_mm": solver_result.minimum_required_diameter_mm,
                "selected_diameter_mm": solver_result.selected_diameter_mm,
                "diameter_selection_policy": solver_result.diameter_selection_policy,
                "diameter_selection_reason": solver_result.diameter_selection_reason,
                "design_stress_mpa": solver_result.design_stress_mpa,
                "achieved_factor_of_safety": solver_result.achieved_factor_of_safety,
                "is_safe": solver_result.is_safe
            }
            handoff.traceability_matrix["material_resolution"] = serialized_mat_res

        # Determine overall pipeline status
        if cad_res.status == CADStatus.REQUIRES_REVIEW:
            overall_status = PipelineStatus.REQUIRES_REVIEW
            warnings.append("CAD/Drawing dimensional cross-validation or BRep checks requires engineering review.")
        elif cad_res.status == CADStatus.GENERATED:
            overall_status = PipelineStatus.SUCCESS
        else:
            overall_status = PipelineStatus.FAILED

        warnings.extend(cad_res.warnings)

        # ======================================================================
        # Step 7: Build Comprehensive Audit Report
        # ======================================================================
        report = self._generate_report(
            status=overall_status,
            spec=spec,
            solver_result=solver_result,
            cad_res=cad_res,
            handoff=handoff,
            material_resolution=serialized_mat_res
        )

        return EndToEndDesignResult(
            status=overall_status,
            spec=spec,
            provenance=serialized_prov,
            material_resolution=serialized_mat_res,
            solver_result=solver_result,
            cad_result=cad_res,
            cad_status=cad_res.status.value,
            drawing_document=cad_res.drawing_document,
            cross_validation=cad_res.dimensional_cross_validation,
            handoff=handoff,
            artifacts=cad_res.artifacts,
            missing_information=[],
            errors=errors,
            warnings=warnings,
            report=report
        )

    def _generate_report(
        self,
        status: PipelineStatus,
        spec: EngineeringSpec,
        solver_result: Optional[EngineeringResult],
        cad_res: Optional[Any],
        handoff: Optional[EngineeringHandoff],
        material_resolution: Optional[Dict[str, Any]] = None
    ) -> str:
        """Constructs an auditable markdown engineering report for the pipeline execution."""
        lines = [
            f"# End-to-End Mechanical Design Pipeline Report",
            f"**Pipeline Status**: `{status.value}`",
            "",
            "> [!NOTE]",
            "> **Disclaimer**: This automated pipeline produces preliminary engineering sizing, parametric CAD models,",
            "> and 2D technical drawings. All calculations and geometric callouts require verification and formal review",
            "> by a qualified engineering professional prior to manufacturing release. This system does not grant certified manufacturing approval.",
            "",
            "## 1. Requirement Extraction & Provenance",
            f"- **Component**: {spec.component}",
            f"- **Material**: {spec.material or 'Unspecified'}",
            f"- **Power**: {spec.power_kw} kW",
            f"- **Speed**: {spec.rpm} RPM",
            f"- **Factor of Safety (Required)**: {spec.factor_of_safety}",
            f"- **Length**: {spec.length_mm} mm",
            f"- **Yield Strength**: {spec.yield_strength_mpa} MPa",
            ""
        ]

        if material_resolution:
            lines.append("### Material Traceability & Knowledge Base Resolution")
            lines.append(f"- **Requested Material**: `{material_resolution.get('requested_material') or 'Unstated'}`")
            lines.append(f"- **Resolved Material**: `{material_resolution.get('resolved_material') or 'Unresolved'}`")
            lines.append(f"- **Standard**: `{material_resolution.get('standard') or 'N/A'}`")
            if material_resolution.get("is_explicit_override"):
                lines.append(f"- **Yield Strength Used**: `{material_resolution.get('yield_strength_mpa')} MPa`")
                lines.append(f"- **Yield Strength Source**: `{material_resolution.get('yield_strength_source')}`")
                lines.append(f"- **Knowledge Base Standard Yield Strength**: `{material_resolution.get('knowledge_base_yield_strength_mpa')} MPa`")
                lines.append(f"- **Status**: `Explicit override`")
            elif material_resolution.get("resolved"):
                lines.append(f"- **Yield Strength**: `{material_resolution.get('yield_strength_mpa')} MPa`")
                lines.append(f"- **Yield Strength Source**: `{material_resolution.get('yield_strength_source')}`")
                lines.append(f"- **Status**: `{material_resolution.get('status', 'Verified')}`")
            else:
                lines.append(f"- **Status**: `Unresolved`")
                if material_resolution.get("errors"):
                    lines.append(f"- **Resolution Errors**: {', '.join(material_resolution.get('errors', []))}")
            lines.append("")

        if spec.provenance:
            lines.append("### Parameter Provenance")
            lines.append("| Field | Value | Source Text / Origin | Explicit | Confidence |")
            lines.append("|---|---|---|---|---|")
            fields_dict = spec.provenance.get("fields", spec.provenance)
            for k, p in fields_dict.items():
                if k == "material_resolution":
                    continue
                if isinstance(p, dict):
                    lines.append(f"| `{p.get('field_name', k)}` | `{p.get('value')}` | `{p.get('source_text')}` | `{p.get('is_explicit')}` | `{p.get('confidence', 1.0):.2f}` |")
                elif hasattr(p, "field_name"):
                    lines.append(f"| `{p.field_name}` | `{p.value}` | `{p.source_text}` | `{p.is_explicit}` | `{p.confidence:.2f}` |")
            lines.append("")

        if solver_result:
            lines.append("## 2. Deterministic Mechanical Calculation Certificate")
            lines.append(f"- **Solver Status**: `{solver_result.status.value}`")
            if solver_result.is_valid:
                lines.append(f"- **Transmitted Torque ($T$)**: `{solver_result.torque_nm:.3f} N*m`")
                lines.append(f"- **Allowable Shear Stress ($\tau_{{allow}}$)**: `{solver_result.allowable_stress_mpa:.2f} MPa`")
                lines.append(f"- **Minimum Required Diameter ($d_{{req}}$)**: `{solver_result.minimum_required_diameter_mm:.2f} mm`")
                lines.append(f"- **Selected Nominal Diameter ($d_{{nominal}}$)**: `{solver_result.selected_diameter_mm:.1f} mm`")
                if solver_result.diameter_selection_policy:
                    lines.append(f"- **Nominal Diameter Policy**: `{solver_result.diameter_selection_policy}`")
                if solver_result.diameter_selection_reason:
                    lines.append(f"- **Diameter Selection Rationale**: {solver_result.diameter_selection_reason}")
                lines.append(f"- **Design Shear Stress ($\tau_{{design}}$)**: `{solver_result.design_stress_mpa:.2f} MPa`")
                lines.append(f"- **Achieved Factor of Safety ($\text{{FoS}}_{{achieved}}$)**: `{solver_result.achieved_factor_of_safety:.2f}`")
                lines.append(f"- **Yield-Strength Design Constraint Check**: `{'Yield-Strength Design Constraint Satisfied (τ_design ≤ τ_allow)' if solver_result.is_safe else 'Design Constraint Not Satisfied'}`")
                lines.append("")
                lines.append("### Calculation Steps (Deterministic Derivations)")
                for step in solver_result.calculation_steps:
                    lines.append(f"- {step}")
                lines.append("")
            else:
                if solver_result.missing_information:
                    lines.append(f"- **Missing Information**: {', '.join(solver_result.missing_information)}")
                if solver_result.errors:
                    lines.append(f"- **Errors**: {', '.join(solver_result.errors)}")
                lines.append("")

        if cad_res:
            lines.append("## 3. Parametric 3D CAD & 2D Engineering Drawing Verification")
            lines.append(f"- **CAD Status**: `{cad_res.status.value}`")
            if cad_res.validation:
                lines.append(f"- **BRep Solid Validity**: `{'VALID' if cad_res.validation.is_valid else 'INVALID'}`")
                lines.append(f"- **Calculated Volume**: `{cad_res.validation.calculated_volume:.2f} mm^3` (Theoretical: `{cad_res.validation.theoretical_volume:.2f} mm^3`)")
                lines.append(f"- **Volume Error**: `{cad_res.validation.volume_error_rel * 100.0:.4f}%`")

            lines.append("")
            lines.append("### Generated Artifacts")
            for fmt, art in cad_res.artifacts.items():
                lines.append(f"- **{fmt.upper()}**: `{art.filename}` ({art.file_size_bytes} bytes) -> `{art.file_path}`")

            lines.append("")
            lines.append("### Dimensional Cross-Validation Matrix")
            all_match = cad_res.dimensional_cross_validation.get("all_match", False)
            lines.append(f"- **Overall Cross-Validation Agreement**: `{'VERIFIED (100% Match)' if all_match else 'MISMATCH DETECTED'}`")
            for chk_name, chk_val in cad_res.dimensional_cross_validation.items():
                if isinstance(chk_val, dict):
                    lines.append(f"  - `{chk_name}`: Drawing=`{chk_val.get('drawing_value')}`, CAD=`{chk_val.get('cad_value')}`, Match=`{chk_val.get('match')}`")
            lines.append("")

        if handoff:
            lines.append("## 4. Engineering Handoff Package")
            lines.append(f"- **Handoff ID**: `{handoff.handoff_id}`")
            lines.append(f"- **Status**: `{handoff.handoff_status}`")
            lines.append(f"- **Machine Element**: `{handoff.machine_element}`")
            lines.append("")

        return "\n".join(lines)


def run_design_pipeline(
    problem_statement: str,
    extra_inputs: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
    llm_provider: Optional[Any] = None,
    cad_backend: Optional[CADBackend] = None,
    material_repository: Optional[MaterialRepository] = None
) -> EndToEndDesignResult:
    """
    Convenience function for executing the end-to-end engineering design pipeline.
    """
    pipeline = EndToEndPipeline(
        llm_provider=llm_provider,
        cad_backend=cad_backend,
        material_repository=material_repository
    )
    return pipeline.run(
        problem_statement=problem_statement,
        extra_inputs=extra_inputs,
        output_dir=output_dir
    )
