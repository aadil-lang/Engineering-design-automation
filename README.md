# Mechanical Engineering Drawing Intelligence

## Purpose
An AI-assisted system that analyzes mechanical engineering drawing images and converts them into a structured representation suitable for downstream engineering reasoning.

## Architecture

```
Engineering Drawing Image
        ↓
Slice 1: Computer Vision
        ↓ (Lines / Circles / Contours)
Slice 2: Geometric Reasoning
        ↓ (Orientations / Relationships / Hole Candidates)
Slice 3: Dimensions + OCR + Symbols
        ↓ (Structured Annotations & Candidate Associations)
Slice 4: Grounded Engineering Reasoning
        ↓ (Question Router → Context Selector → Grounded Prompts → LLM → Evidence Validator)
Evidence-Grounded Engineering Answer
```

- **Core Models:** Typed Pydantic models for geometric entities (Lines, Circles, Contours), engineering features, annotations, and reasoning responses.
- **Vision Processing (Slice 1):** OpenCV-based pipeline for noise reduction, edge detection, and geometric primitive extraction.
- **Geometry Processing (Slice 2):** High-level layer that transforms low-level OpenCV primitives into contextual engineering relationships.
- **Annotations & Dimensions (Slice 3):** Dedicated OCR preprocessing, pluggable OCR abstraction, deterministic dimension and engineering symbol parsing, and candidate spatial geometry association.
- **Grounded Reasoning (Slice 4):** Evidence-grounded reasoning layer that answers engineering questions strictly based on structured drawing evidence, with deterministic question routing, token-efficient context selection, and hallucination-preventing post-generation validation.
- **API:** FastAPI endpoints (`POST /analyze`, `POST /reason`, `POST /analyze-and-reason`).

## Current Capabilities (Slice 4)
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
- **Grounded Engineering Reasoning:**
  - Answers specific engineering queries using structured evidence without raw pixel hallucination.
  - Categorizes queries deterministically via regex/keyword routing (`hole_analysis`, `dimension_summary`, `relationship_analysis`, `geometry_summary`, `annotation_summary`).
  - Context selection strategy minimizes token consumption by transmitting only relevant entities per category.
  - Strictly distinguishes **Detected Facts**, **Inferences**, and **Uncertainties**.
  - Validates every referenced entity ID (`circle_0`, `dim_1`) against the grounded context, demoting and penalizing unsupported claims.
  - Surfaces contradictory evidence (e.g., conflicting measurement vs callout) as explicit uncertainties.

---

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

---

## Grounded Engineering Reasoning

### Why Structured Evidence Instead of Raw Image Prompting?
Generic multimodal prompts ("look at this image and tell me what it means") suffer from high hallucination rates on technical drawings: small text numbers blur together, leader lines are misinterpreted, and models invent measurements not present on the drawing. 

By operating strictly on the structured evidence produced by Slices 1–3, the reasoning engine:
1. **Never hallucinates geometry or measurements:** The LLM only reasons over verified coordinates, diameters, tolerances, and OCR tokens.
2. **Cites specific entity IDs:** Every claim points back to a concrete entity (`circle_0`, `dim_1`, `line_0`).
3. **Preserves uncertainties:** Ambiguities and measurement discrepancies are brought forward rather than smoothed over.

### Architecture & Reasoning Pipeline

```
Question + Drawing Context
            ↓
1. Deterministic Question Router
   (hole_analysis | dimension_summary | relationship_analysis | ...)
            ↓
2. Context Selection (Token/Cost Efficiency)
   (Pulls only relevant geometry, dimensions, and associations)
            ↓
3. Grounded Prompt Construction
   (System prompt with strict citation and evidence boundaries)
            ↓
4. LLM Provider (MockLLMProvider / GeminiProvider via httpx)
            ↓
5. Deterministic Post-Generation Evidence Validator
   - Checks every cited evidence ID against DrawingContext
   - Flags/demotes hallucinated IDs to uncertainties
   - Checks for contradictory evidence
   - Clamps & calibrates confidence
            ↓
Validated ReasoningResponse
```

### Context Selection Strategy (Cost / Token Efficiency)
Rather than dumping the entire drawing dataset into every LLM call, the prompt builder applies a targeted context filter:
- **`hole_analysis`:** Prioritizes circle features, hole candidates, diameter/radius dimensions, and circle associations.
- **`dimension_summary`:** Prioritizes dimensions, tolerances, units, and symbols.
- **`relationship_analysis`:** Prioritizes line features and geometric relationships.
- **`geometry_summary`:** Prioritizes line features, circle features, and bounding dimensions.
- **`annotation_summary`:** Prioritizes OCR text tokens, symbols, and dimensions.
- **`general_engineering_question`:** Compact full representation.

### Evidence Validation & Hallucination Prevention
A deterministic validator inspects every JSON response from the LLM before returning it to the user:
- Compiles the set of all valid IDs from the context (`line_0`, `circle_0`, `dim_1`, etc.).
- Verifies that all IDs cited in `facts`, `inferences`, and `evidence` exist.
- If the model references a nonexistent entity (e.g. `circle_99`), the claim is demoted from `facts` to `uncertainties`, tagged as `[UNVERIFIED ID]`, and a confidence penalty is applied.
- If physical circle measurements conflict with dimension callouts (e.g. diameter 20 vs Ø25), the validator verifies that the conflict is surfaced as an uncertainty.

### Example Reasoning Flow

**Question:**
> "What are the likely hole diameters?"

**Structured Evidence Provided:**
- `circle_0`: center=(50, 100), radius=10, diameter=20, likely_hole=true
- `dim_1`: raw_text="Ø20", value=20.0, dimension_type="diameter"
- `assoc_0`: links `dim_1` to `circle_0`

**Reasoning Response:**
```json
{
  "answer": "The drawing contains 1 likely hole(s) with nominal diameter around 20.0 mm.",
  "facts": [
    {
      "statement": "Feature circle_0 has detected circle diameter of 20.0.",
      "evidence": ["circle_0"]
    },
    {
      "statement": "Dimension dim_1 specifies 20.0.",
      "evidence": ["dim_1"]
    }
  ],
  "inferences": [
    {
      "statement": "Dimension dim_1 corresponds to candidate hole circle_0.",
      "evidence": ["circle_0", "dim_1"]
    }
  ],
  "uncertainties": [],
  "evidence": ["circle_0", "dim_1"],
  "confidence": {
    "score": 0.88,
    "source": "validated_grounded_evidence"
  },
  "metadata": {
    "question_type": "hole_analysis",
    "provider": "MockLLMProvider",
    "model": "deterministic_mock",
    "validation_status": "passed",
    "estimated_prompt_tokens": 142
  }
}
```

---

## API Usage

### 1. Start Server
```bash
uvicorn api.main:app --reload
```

### 2. Analyze Drawing (`POST /analyze`)
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drawing.png"
```

### 3. Reason Over Drawing Context (`POST /reason`)
```bash
curl -X POST "http://localhost:8000/reason" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the likely hole diameters?",
    "drawing": { ... }
  }'
```

### 4. Direct Convenience Endpoint (`POST /analyze-and-reason`)
```bash
curl -X POST "http://localhost:8000/analyze-and-reason" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@drawing.png" \
  -F "question=What dimensions and holes are present?"
```

---

## Testing
Run the complete test suite across Slices 1, 2, 3, and 4:
```bash
PYTHONPATH=src pytest -q
```
All tests run 100% deterministically offline using `MockLLMProvider` without requiring external API credentials.

---

## Limitations
- Full composite GD&T datum reference frame decoding is deferred to future work.
- In low-contrast or degraded scans, severe OCR omissions may require manual review of the detected evidence before drawing conclusions.
