import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_analyze_success(synthetic_image_bytes):
    files = {"file": ("test.png", synthetic_image_bytes, "image/png")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "image" in data
    assert "lines" in data
    assert "circles" in data
    assert "contours" in data

def test_analyze_empty_file(empty_image_bytes):
    files = {"file": ("empty.png", empty_image_bytes, "image/png")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 400

def test_analyze_corrupt_file(corrupt_image_bytes):
    files = {"file": ("corrupt.txt", corrupt_image_bytes, "text/plain")}
    response = client.post("/analyze", files=files)
    
    assert response.status_code == 400
