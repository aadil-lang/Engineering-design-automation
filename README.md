# Mechanical Engineering Drawing Intelligence

## Purpose
An AI-assisted system that analyzes mechanical engineering drawing images and converts them into a structured representation suitable for downstream engineering reasoning.

## Architecture
- **Core Models:** Typed Pydantic models for geometric entities (Lines, Circles, Contours) and API responses.
- **Vision Processing:** OpenCV-based pipeline for noise reduction, edge detection, and geometric feature extraction.
- **API:** FastAPI endpoint (`POST /analyze`) handling multipart image uploads, validation, and responding with structured JSON.

## Current Capabilities (Slice 1)
- Validates and loads uploaded image files.
- Detects straight lines (HoughLinesP).
- Detects circles (HoughCircles).
- Extracts basic contours.

## API Usage
Start the development server:
```bash
uvicorn src.api.main:app --reload
```

Send an image for analysis:
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drawing.png"
```

## Example Response
```json
{
  "image": {
    "width": 500,
    "height": 500
  },
  "lines": [
    {
      "x1": 50.0,
      "y1": 50.0,
      "x2": 450.0,
      "y2": 50.0,
      "length": 400.0,
      "angle": 0.0
    }
  ],
  "circles": [
    {
      "center_x": 250.0,
      "center_y": 250.0,
      "radius": 100.0
    }
  ],
  "contours": [
    {
      "area": 10000.0,
      "perimeter": 400.0,
      "bounding_box": [50.0, 350.0, 100.0, 100.0]
    }
  ]
}
```

## Limitations
- Only basic geometric primitives are extracted.
- Does not yet interpret OCR, dimensions, or engineering symbols (GD&T).
- Optimized for clear, high-contrast images.
