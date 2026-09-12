# Mechanical Engineering Drawing Intelligence

## Purpose
An AI-assisted system that analyzes mechanical engineering drawing images and converts them into a structured representation suitable for downstream engineering reasoning.

## Architecture
- **Core Models:** Typed Pydantic models for geometric entities (Lines, Circles, Contours), engineering features, and annotations.
- **Vision Processing (Slice 1):** OpenCV-based pipeline for noise reduction, edge detection, and geometric primitive extraction.
- **Geometry Processing (Slice 2):** High-level layer that transforms low-level OpenCV primitives into contextual engineering relationships.
- **Annotations & Dimensions (Slice 3):** Dedicated OCR preprocessing, pluggable OCR abstraction, deterministic dimension and engineering symbol parsing, and candidate spatial geometry association.
- **API:** FastAPI endpoint (`POST /analyze`) handling multipart image uploads, validation, and responding with structured JSON.

## Current Capabilities (Slice 3)
- Validates and loads uploaded image files.
- Detects straight lines (`HoughLinesP`), circles (`HoughCircles`), and contours.
- **Engineering Feature Extraction:**
  - Infers deterministic orientations (Horizontal, Vertical, Diagonal) with angular tolerances.
  - Generates Line and Circle features with hole candidate heuristics.
  - Detects spatial relationships (parallelism, perpendicularity, endpoint connectivity).
- **Dimensions and Annotation Extraction:**
  - Dedicated OCR image enhancement (CLAHE, upscaling, denoising, adaptive thresholding).
  - OCR abstraction layer supporting local and mock OCR engines without internet/cloud dependencies.
  - Deterministic parsing of engineering dimensions (linear, diameter, radius, angular, symmetric/bilateral tolerances, unit suffixes).
  - Deterministic symbol detection (Ø, ⌀, R, ±, °, and preparatory GD&T representations).
  - Spatial candidate association between dimension bounding boxes and nearby geometric lines/circles.

## Dimensions and Annotation Extraction

### Architectural Separation
- **OCR is separated from engineering interpretation:** The raw optical character detection produces candidate text tokens and bounding boxes without assuming engineering meaning.
- **Raw OCR text is preserved:** All original detected text strings (`raw_text`) and source IDs are preserved alongside parsed numeric values.
- **Deterministic notation parsing:** Dimension strings are parsed using deterministic regex rules rather than probabilistic models. Supported notations include:
  - Plain linear dimensions (e.g., `50`, `25.5`, `100`)
  - Diameter callouts (e.g., `Ø20`, `⌀20`, `Dia 20`, `D20` [heuristic])
  - Radius callouts (e.g., `R10`, `R 10`, `Rad 10`)
  - Angular callouts (e.g., `45°`, `45 deg`, `45 degree`)
  - Tolerances (symmetric `50 ±0.02`, `50 +/- 0.02`; bilateral `50 +0.02/-0.01`)
  - Units (`mm`, `cm`, `in`, `inch`). Units are returned as `null` if not explicitly present; the system never fabricates units.
- **Candidate-based geometry association:** Dimensions are spatially linked to nearby geometric features (lines or circles) based on Euclidean distance thresholds. These links are explicitly marked as candidate associations (`association_type`, `distance`, `confidence`) rather than guaranteed semantic ground truth.
- **No LLM in Slice 3:** All parsing, symbol matching, and spatial associations are 100% deterministic and rule-based. Downstream reasoning will be added in Slice 4.

### Real-World Ambiguity and OCR Errors
Engineering drawings often contain speckle noise, broken leader lines, font distortions, and ambiguous text (e.g., distinguishing the letter `D` in a part code vs. diameter notation). The parser applies heuristic confidence scoring (such as assigning lower confidence to ambiguous `D20` strings compared to explicit `Ø20` symbols) and allows upstream/downstream layers to handle ambiguous interpretations.

### Example Dimension JSON
```json
{
  "raw_text": "Ø20",
  "value": 20.0,
  "dimension_type": "diameter",
  "unit": null,
  "confidence": 0.95
}
```

## API Usage
Start the development server:
```bash
uvicorn api.main:app --reload
```

Send an image for analysis:
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drawing.png"
```

## Example Response (Slice 3)
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
    "line_features": [],
    "circle_features": [
      {
        "id": "circle_0",
        "center_x": 100.0,
        "center_y": 100.0,
        "radius": 10.0,
        "diameter": 20.0,
        "likely_hole": true,
        "confidence": 0.8
      }
    ],
    "relationships": [],
    "bounding_information": {
      "bounding_box": [0.0, 0.0, 500.0, 500.0],
      "width": 500.0,
      "height": 500.0
    },
    "summary": {
      "total_line_features": 0,
      "total_circle_features": 1,
      "total_relationships": 0,
      "hole_candidates": 1
    }
  },
  "annotations": {
    "ocr_results": [
      {
        "id": "ocr_1",
        "text": "Ø20",
        "confidence": 0.95,
        "bounding_box": [95.0, 115.0, 30.0, 12.0]
      }
    ],
    "dimensions": [
      {
        "id": "dim_1",
        "raw_text": "Ø20",
        "value": 20.0,
        "unit": null,
        "dimension_type": "diameter",
        "tolerance": null,
        "confidence": 0.95,
        "bounding_box": [95.0, 115.0, 30.0, 12.0],
        "source_text_id": "ocr_1"
      }
    ],
    "symbols": [
      {
        "id": "sym_1",
        "symbol_type": "diameter",
        "raw_symbol": "Ø",
        "bounding_box": [95.0, 115.0, 30.0, 12.0],
        "confidence": 0.95,
        "source_text_id": "ocr_1"
      }
    ],
    "associations": [
      {
        "dimension_id": "dim_1",
        "feature_id": "circle_0",
        "association_type": "circle_diameter",
        "distance": 15.81,
        "confidence": 0.90,
        "metadata": {
          "matched_geometry": "circle",
          "circle_diameter": 20.0,
          "nominal_diameter_match": true
        }
      }
    ],
    "summary": {
      "total_ocr_detections": 1,
      "total_dimensions": 1,
      "dimensions_by_type": {
        "diameter": 1
      },
      "total_symbols": 1,
      "symbols_by_type": {
        "diameter": 1
      },
      "total_associations": 1,
      "associated_dimensions": 1
    }
  }
}
```

## Limitations
- Full GD&T symbol decoding (datum frames, feature control frames) is prepared architecturally but deferred to subsequent slices.
- OCR text detection quality is sensitive to low-resolution or heavily degraded scans.
