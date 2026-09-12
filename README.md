# Mechanical Engineering Drawing Intelligence

## Purpose
An AI-assisted system that analyzes mechanical engineering drawing images and converts them into a structured representation suitable for downstream engineering reasoning.

## Architecture
- **Core Models:** Typed Pydantic models for geometric entities (Lines, Circles, Contours) and API responses.
- **Vision Processing:** OpenCV-based pipeline for noise reduction, edge detection, and geometric feature extraction.
- **Geometry Processing:** High-level layer that transforms low-level OpenCV primitives into contextual engineering relationships.
- **API:** FastAPI endpoint (`POST /analyze`) handling multipart image uploads, validation, and responding with structured JSON.

## Current Capabilities (Slice 2)
- Validates and loads uploaded image files.
- Detects straight lines (HoughLinesP).
- Detects circles (HoughCircles).
- Extracts basic contours.
- **Engineering Feature Extraction:**
  - Infers deterministic orientations (Horizontal, Vertical, Diagonal) with angular tolerances.
  - Generates Line and Circle features.
  - Determines hole candidates deterministically based on radius constraints.
  - Detects spatial relationships including parallelism, perpendicularity, and endpoint connections.

## Engineering Feature Extraction
CV primitives (arrays of pixels representing lines or circles) do not map directly to mechanical engineering design concepts (such as edges, hole cutouts, and parallelism tolerances). This system runs a conservative geometry extraction service that transforms those pixels into meaningful engineering features.

The extraction process involves:
- **Orientation:** Lines are normalized to [0, 180) degrees. Lines within ±5 degrees of the major axes are classified as Horizontal or Vertical.
- **Geometric Relationships:** Using identical configurable ±5 degree tolerances, parallel and perpendicular intersections are resolved.
- **Connectivity:** Lines with endpoints located within 10 pixels of another are flagged as connected.
- **Hole Candidates:** Detected circles with a radius between 2.0 and 50.0 pixels are deterministically flagged as candidate holes (`likely_hole`). We use conservative bounds since symbols or small textual O's might mistakenly trigger the detector.

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
  "lines": [],
  "circles": [],
  "contours": [],
  "engineering_features": {
    "line_features": [
      {
        "id": "line_0",
        "x1": 50.0,
        "y1": 50.0,
        "x2": 450.0,
        "y2": 50.0,
        "length": 400.0,
        "angle_degrees": 0.0,
        "orientation": "horizontal"
      }
    ],
    "circle_features": [
      {
        "id": "circle_0",
        "center_x": 250.0,
        "center_y": 250.0,
        "radius": 10.0,
        "diameter": 20.0,
        "likely_hole": true,
        "confidence": 0.8
      }
    ],
    "relationships": [
      {
        "source_id": "line_0",
        "target_id": "line_1",
        "relationship_type": "perpendicular",
        "metadata": null
      }
    ],
    "bounding_information": {
      "bounding_box": [50.0, 50.0, 400.0, 400.0],
      "width": 400.0,
      "height": 400.0
    },
    "summary": {
      "total_line_features": 1,
      "total_circle_features": 1,
      "total_relationships": 1,
      "hole_candidates": 1
    }
  }
}
```

## Limitations
- Does not yet interpret OCR, dimensions, or engineering symbols (GD&T).
- Optimized for clear, high-contrast images.
