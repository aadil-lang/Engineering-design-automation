from fastapi import APIRouter, File, UploadFile, HTTPException
from core.models import AnalyzeResponse
from vision.processor import load_and_validate_image
from vision.detector import extract_features
from geometry.extractor import extract_engineering_features
from annotations.extractor import extract_annotations

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drawing(file: UploadFile = File(...)):
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
    
    return cv_response
