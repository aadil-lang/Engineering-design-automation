import pytest
from vision.processor import load_and_validate_image
from vision.detector import extract_features
from fastapi import HTTPException
import numpy as np

def test_load_and_validate_image_success(synthetic_image_bytes):
    img = load_and_validate_image(synthetic_image_bytes)
    assert isinstance(img, np.ndarray)
    assert img.shape == (500, 500, 3)

def test_load_and_validate_image_empty(empty_image_bytes):
    with pytest.raises(HTTPException) as excinfo:
        load_and_validate_image(empty_image_bytes)
    assert excinfo.value.status_code == 400

def test_load_and_validate_image_corrupt(corrupt_image_bytes):
    with pytest.raises(HTTPException) as excinfo:
        load_and_validate_image(corrupt_image_bytes)
    assert excinfo.value.status_code == 400

def test_extract_features(synthetic_image_np):
    response = extract_features(synthetic_image_np)
    
    assert response.image.width == 500
    assert response.image.height == 500
    
    # Check if lines were detected
    assert len(response.lines) > 0
    
    # Check if circles were detected
    assert len(response.circles) > 0
    
    # Check if contours were detected
    assert len(response.contours) > 0
