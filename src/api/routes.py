import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from core.models import AnalyzeResponse
from vision.processor import load_and_validate_image
from vision.detector import extract_features
from geometry.extractor import extract_engineering_features
from annotations.extractor import extract_annotations
from semantics.extractor import extract_mechanical_semantics
from knowledge.applicability import EngineeringApplicabilityEngine
from analysis.models import AnalysisPlanningRequest
from analysis.planner import AnalysisPlanner
from solvers.runner import SolverRunner
from reasoning.models import (
    ReasoningRequest,
    ReasoningResponse,
    AnalyzeAndReasonResponse
)
from reasoning.reasoner import reason_about_drawing

router = APIRouter()


async def _run_analysis_pipeline(
    file: UploadFile,
    engineering_inputs: Optional[Dict[str, Any]] = None,
    planning_request: Optional[AnalysisPlanningRequest] = None,
    execute_analyses: bool = False
) -> AnalyzeResponse:
    """Internal helper running the complete Slice 1-3, 6, 7, 8, and optional 9 CV, annotation, semantic, knowledge, planning, and solver pipeline."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # 1. Process & Validate Image
    img = load_and_validate_image(contents)

    # 2. Extract Low-Level CV Features (Slice 1)
    cv_response = extract_features(img)

    # 3. Extract High-Level Engineering Features (Slice 2)
    engineering_features = extract_engineering_features(
        cv_response.lines,
        cv_response.circles,
        cv_response.contours,
        cv_response.image
    )
    cv_response.engineering_features = engineering_features

    # 4. Extract Annotations, Dimensions, Symbols, and Associations (Slice 3)
    annotations = extract_annotations(
        image=img,
        engineering_features=engineering_features
    )
    cv_response.annotations = annotations

    # 5. Extract Mechanical Engineering Semantics (Slice 6)
    mechanical_semantics = extract_mechanical_semantics(
        engineering_features=engineering_features,
        annotations=annotations
    )
    cv_response.mechanical_semantics = mechanical_semantics

    # 6. Evaluate Engineering Knowledge & Rules (Slice 7)
    knowledge_engine = EngineeringApplicabilityEngine()
    engineering_knowledge = knowledge_engine.evaluate(
        mechanical_semantics=mechanical_semantics,
        annotations=annotations,
        engineering_inputs=engineering_inputs
    )
    cv_response.engineering_knowledge = engineering_knowledge

    # 7. Formulate Analysis Execution Plan (Slice 8)
    planner = AnalysisPlanner()
    plan_req = planning_request or AnalysisPlanningRequest(engineering_inputs=engineering_inputs or {})
    analysis_plan = planner.create_plan(
        mechanical_semantics=mechanical_semantics,
        engineering_knowledge=engineering_knowledge,
        engineering_inputs=engineering_inputs,
        request=plan_req
    )
    cv_response.analysis_plan = analysis_plan

    # 8. Deterministic Mechanical Solver Execution (Slice 9)
    if execute_analyses and analysis_plan:
        runner = SolverRunner()
        features = mechanical_semantics.features if mechanical_semantics else None
        certificates = runner.execute_plan(
            plan=analysis_plan,
            features=features,
            operating_inputs=engineering_inputs
        )
        cv_response.calculation_certificates = certificates

    return cv_response


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drawing(
    file: UploadFile = File(...),
    engineering_inputs: Optional[str] = Form(None),
    planning_request: Optional[str] = Form(None),
    execute_analyses: bool = Form(False)
):
    """
    Analyzes an uploaded engineering drawing image and returns structured CV primitives,
    engineering features, relationships, annotations, mechanical engineering semantics,
    applicable engineering knowledge, analysis execution plan, and optional calculation certificates.
    """
    inputs_dict = None
    if engineering_inputs:
        try:
            inputs_dict = json.loads(engineering_inputs)
        except Exception:
            inputs_dict = None

    plan_req = None
    if planning_request:
        try:
            req_dict = json.loads(planning_request)
            plan_req = AnalysisPlanningRequest(**req_dict)
        except Exception:
            plan_req = None

    return await _run_analysis_pipeline(
        file,
        engineering_inputs=inputs_dict,
        planning_request=plan_req,
        execute_analyses=execute_analyses
    )


@router.post("/reason", response_model=ReasoningResponse)
async def reason_drawing(request: ReasoningRequest):
    """
    Grounded Engineering Reasoning endpoint (Slice 4).
    Accepts a natural language engineering question and a structured drawing context,
    returning an evidence-grounded answer with verified fact citations and uncertainties.
    """
    try:
        return reason_about_drawing(request)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning error: {str(e)}")


@router.post("/analyze-and-reason", response_model=AnalyzeAndReasonResponse)
async def analyze_and_reason_drawing(
    file: UploadFile = File(...),
    question: str = Form(...),
    engineering_inputs: Optional[str] = Form(None),
    planning_request: Optional[str] = Form(None),
    execute_analyses: bool = Form(False)
):
    """
    Convenience endpoint combining analysis and grounded engineering reasoning.
    Accepts an engineering drawing image and a question, executes the pipeline,
    and returns both the structured analysis and evidence-grounded answer.
    """
    inputs_dict = None
    if engineering_inputs:
        try:
            inputs_dict = json.loads(engineering_inputs)
        except Exception:
            inputs_dict = None

    plan_req = None
    if planning_request:
        try:
            req_dict = json.loads(planning_request)
            plan_req = AnalysisPlanningRequest(**req_dict)
        except Exception:
            plan_req = None

    analysis = await _run_analysis_pipeline(
        file,
        engineering_inputs=inputs_dict,
        planning_request=plan_req,
        execute_analyses=execute_analyses
    )
    req = ReasoningRequest(question=question, drawing=analysis)
    reasoning = reason_about_drawing(req)
    return AnalyzeAndReasonResponse(analysis=analysis, reasoning=reasoning)


from design.models import DesignSpecificationRequest, DesignSpecificationResponse
from design.extractor import DesignSpecificationExtractor
from design.provider import get_design_provider
from design.planner_bridge import plan_analyses_for_specification
from design.report import generate_design_specification_report


@router.post("/design/specification", response_model=DesignSpecificationResponse)
async def create_design_specification(request: DesignSpecificationRequest):
    """
    Interprets natural language engineering problem statements into structured,
    auditable Engineering Specifications (Slice 11).
    Performs deterministic unit normalization, closed-form derivations (e.g. power + RPM -> torque),
    missing information analysis, and links directly to downstream analysis planning.
    """
    try:
        provider = get_design_provider(request.provider)
        extractor = DesignSpecificationExtractor(provider=provider)
        spec = extractor.extract(
            problem_statement=request.problem_statement,
            structured_inputs=request.engineering_inputs
        )
        plan = plan_analyses_for_specification(spec)
        report = generate_design_specification_report(spec, plan)

        return DesignSpecificationResponse(
            specification=spec,
            derived_values=spec.derived_values,
            missing_information=spec.missing_information,
            validation_issues=[c.description for c in spec.conflicts],
            analysis_plan=plan,
            report=report
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Design specification interpretation error: {str(e)}")


from design_engine.models import DesignRequest, DesignResponse, DesignObjective, ShaftDesignRequirements
from design_engine.designer import design_from_specification, design_from_problem_statement, ShaftDesigner


@router.post("/design", response_model=DesignResponse)
async def create_parametric_design(request: DesignRequest):
    """
    Parametric Mechanical Design Engine endpoint (Slice 12).
    Generates, evaluates, and ranks deterministic candidate designs based on an
    EngineeringSpecification or natural-language problem statement.
    """
    try:
        obj = None
        if request.objective:
            try:
                obj = DesignObjective(request.objective)
            except ValueError:
                pass

        if request.specification:
            res = design_from_specification(
                spec=request.specification,
                extra_inputs=request.engineering_inputs,
                constraints=request.design_constraints,
                objective=obj
            )
        elif request.problem_statement:
            res = design_from_problem_statement(
                statement=request.problem_statement,
                extra_inputs=request.engineering_inputs,
                constraints=request.design_constraints,
                objective=obj
            )
        elif request.engineering_inputs:
            req = ShaftDesignRequirements(**request.engineering_inputs)
            designer = ShaftDesigner()
            res = designer.design(
                req=req,
                objective=obj or DesignObjective.MINIMIZE_SHAFT_DIAMETER
            )
        else:
            raise HTTPException(status_code=400, detail="Must provide problem_statement, specification, or engineering_inputs.")

        return DesignResponse(
            result=res,
            report=res.report or ""
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mechanical design synthesis error: {str(e)}")

