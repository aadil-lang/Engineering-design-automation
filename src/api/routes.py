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
from reasoning.models import (
    ReasoningRequest,
    ReasoningResponse,
    AnalyzeAndReasonResponse
)
from reasoning.reasoner import reason_about_drawing

router = APIRouter()


async def _run_analysis_pipeline(
    file: UploadFile,
    engineering_inputs: Optional[Dict[str, Any]] = None
) -> AnalyzeResponse:
    """Internal helper running the complete Slice 1-3, 6, and 7 computer vision, annotation, semantic, and knowledge pipeline."""
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
    cv_response.engineering_knowledge = knowledge_engine.evaluate(
        mechanical_semantics=mechanical_semantics,
        annotations=annotations,
        engineering_inputs=engineering_inputs
    )

    return cv_response


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drawing(
    file: UploadFile = File(...),
    engineering_inputs: Optional[str] = Form(None)
):
    """
    Analyzes an uploaded engineering drawing image and returns structured CV primitives,
    engineering features, relationships, annotations, mechanical engineering semantics,
    and applicable engineering knowledge.
    Optionally accepts a JSON string of engineering_inputs (e.g. {"torque": 31.8}).
    """
    inputs_dict = None
    if engineering_inputs:
        try:
            inputs_dict = json.loads(engineering_inputs)
        except Exception:
            inputs_dict = None

    return await _run_analysis_pipeline(file, engineering_inputs=inputs_dict)


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
    engineering_inputs: Optional[str] = Form(None)
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

    analysis = await _run_analysis_pipeline(file, engineering_inputs=inputs_dict)
    req = ReasoningRequest(question=question, drawing=analysis)
    reasoning = reason_about_drawing(req)
    return AnalyzeAndReasonResponse(analysis=analysis, reasoning=reasoning)
