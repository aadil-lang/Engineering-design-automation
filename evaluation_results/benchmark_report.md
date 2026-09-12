# Mechanical Engineering Drawing Intelligence Evaluation

## Dataset
- 8 synthetic benchmark cases
- Deterministic fixed-coordinate generation
- Generated with OpenCV (white canvas, black geometry)

## Aggregate Results

| Metric | Precision | Recall | F1 |
| :--- | :---: | :---: | :---: |
| Line Detection | 0.47 | 1.00 | 0.63 |
| Circle Detection | 0.36 | 1.00 | 0.39 |
| Relationship Detection | N/A | N/A | 0.08 |
| Dimension Parsing | N/A | N/A | 0.00 |
| Symbol Detection | N/A | N/A | N/A |

- **Orientation Accuracy:** 100.0%
- **Reasoning Evidence Validity Rate:** 100.0%
- **Reasoning Evidence Hallucination Rate:** 0.0%

## Per-Case Results

| Case | Line F1 | Circle F1 | Relationship F1 | Orientation Acc | Dimension F1 | Symbol F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| case_horizontal_line | 0.67 | N/A | N/A | 1.00 | N/A | N/A |
| case_vertical_line | 0.67 | N/A | N/A | 1.00 | N/A | N/A |
| case_diagonal_lines | 0.44 | N/A | N/A | 1.00 | N/A | N/A |
| case_parallel_lines | 0.67 | N/A | 0.22 | 1.00 | N/A | N/A |
| case_perpendicular_lines | 0.67 | N/A | 0.20 | 1.00 | N/A | N/A |
| case_hole | 0.67 | 0.08 | N/A | 1.00 | N/A | N/A |
| case_multiple_holes | N/A | 1.00 | N/A | N/A | N/A | N/A |
| case_mixed_geometry | 0.67 | 0.08 | N/A | 1.00 | 0.00 | N/A |

## Error Analysis

- Line Fragmentation: Hough line transform produces multiple overlapping segments per ground-truth line (predicted 35 lines for 16 ground-truth lines, ratio=2.2x). Recall remains 1.00, but precision is reduced due to unmerged collinear segments.
- Corner Sensitivity in Circle Detector: HoughCircles exhibits false-positive circular detections along sharp 90-degree rectangular boundary corners (44 false positives observed across plate cases). Circular holes isolated without surrounding sharp corners (case_multiple_holes) achieved perfect F1=1.00.
- Relationship Sensitivity: Segment fragmentation impacts connectivity heuristics. When single lines fragment into multiple segments, endpoint connection distances may exceed the 10px threshold.
- OCR Dependency Limitation: Dimension callout in case_mixed_geometry was unread because FallbackOCREngine is active in environments without native Tesseract binaries. The system correctly refrained from fabricating text.

## Limitations

- **Synthetic Simplicity**: High-contrast, clean 2D pixel drawings without paper texture, warping, or low-DPI scan degradation.
- **Hough Collinear Fragmentation**: Multiple collinear or duplicate boundary segments are counted as individual false positives without a merging pre-pass.
- **Circle Corner False Positives**: HoughCircles detector responds to sharp 90-degree orthogonal corners in rectangular boundaries.
- **OCR Environment Dependency**: If tesseract binary is unavailable, FallbackOCREngine returns empty results rather than fabricating detections.
