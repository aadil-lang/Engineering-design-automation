from fastapi import APIRouter, File, UploadFile, HTTPException
from core.models import AnalyzeResponse
from vision.processor import load_and_validate_image
from vision.detector import extract_features
from geometry.extractor import extract_engineering_features

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drawing(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
        
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # Process Image
    img = load_and_validate_image(contents)
    
    # Extract Low-Level CV Features (Slice 1)
    cv_response = extract_features(img)
    
    # Extract High-Level Engineering Features (Slice 2)
    engineering_features = extract_engineering_features(
        cv_response.lines,
        cv_response.circles,
        cv_response.contours,
        cv_response.image
    )
    
    # Enrich the response
    cv_response.engineering_features = engineering_features
    
    return cv_response
