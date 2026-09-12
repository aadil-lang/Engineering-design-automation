import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_analyze_success(synthetic_image_bytes):
    files = {"file": ("test.png", synthetic_image_bytes, "image/png")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    # Assert Slice 1
    assert "image" in data
    assert "lines" in data
    assert "circles" in data
    assert "contours" in data
    
    # Assert Slice 2
    assert "engineering_features" in data
    assert data["engineering_features"] is not None
    
    eng_features = data["engineering_features"]
    assert "line_features" in eng_features
    assert "circle_features" in eng_features
    assert "relationships" in eng_features
    assert "bounding_information" in eng_features
    assert "summary" in eng_features

    # Assert Slice 3: Annotations, Dimensions, Symbols, Associations
    assert "annotations" in data
    assert data["annotations"] is not None
    annotations = data["annotations"]
    assert "ocr_results" in annotations
    assert "dimensions" in annotations
    assert "symbols" in annotations
    assert "associations" in annotations
    assert "summary" in annotations

def test_analyze_empty_file(empty_image_bytes):
    files = {"file": ("empty.png", empty_image_bytes, "image/png")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 400

def test_analyze_corrupt_file(corrupt_image_bytes):
    files = {"file": ("corrupt.txt", corrupt_image_bytes, "text/plain")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 400
