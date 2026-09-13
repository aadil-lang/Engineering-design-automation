"""
Exporters for Engineering Drawings and 3D CAD Exchange Formats.
Includes an SVGRenderer embedding semantic engineering metadata (data-*)
and extensible interfaces for future DXF/PDF generators.
"""

import os
from typing import Optional, Dict, Any
from cad.drawing import DrawingDocument, DrawingView, DrawingDimension, DrawingLine, DrawingArc
from cad.models import CADArtifact, CADStatus


class SVGRenderer:
    """
    Renders structured DrawingDocuments into crisp, standards-compliant 2D Engineering Drawings in SVG.
    Includes technical borders, dimension lines with arrowheads, centerlines, and semantic data attributes.
    """

    def render(self, doc: DrawingDocument) -> str:
        """
        Produces clean vector SVG content adhering to engineering drafting conventions.
        """
        w = doc.sheet_width
        h = doc.sheet_height
        tb = doc.title_block

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%" '
            f'data-drawing-id="{doc.drawing_id}" data-source-design-id="{doc.source_design_id or ""}" '
            f'style="background-color: #ffffff; font-family: \'Roboto Mono\', \'Courier New\', monospace;">',
            '  <defs>',
            '    <!-- Standard Engineering Arrowheads -->',
            '    <marker id="arrow-start" viewBox="0 0 10 10" refX="0" refY="5" markerWidth="6" markerHeight="6" orient="auto">',
            '      <path d="M 10 0 L 0 5 L 10 10 z" fill="#1e40af" />',
            '    </marker>',
            '    <marker id="arrow-end" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">',
            '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#1e40af" />',
            '    </marker>',
            '    <marker id="arrow-vert-start" viewBox="0 0 10 10" refX="5" refY="0" markerWidth="6" markerHeight="6" orient="auto">',
            '      <path d="M 0 10 L 5 0 L 10 10 z" fill="#1e40af" />',
            '    </marker>',
            '    <marker id="arrow-vert-end" viewBox="0 0 10 10" refX="5" refY="10" markerWidth="6" markerHeight="6" orient="auto">',
            '      <path d="M 0 0 L 5 10 L 10 0 z" fill="#1e40af" />',
            '    </marker>',
            '  </defs>',
            '',
            '  <!-- Drawing Border and Margins -->',
            '  <rect x="15" y="15" width="810" height="564" fill="none" stroke="#0f172a" stroke-width="2.0" />',
            '  <rect x="25" y="25" width="790" height="544" fill="none" stroke="#475569" stroke-width="1.0" />',
            '',
            '  <!-- Drawing Views -->'
        ]

        # Render Views
        for view in doc.views:
            lines.append(f'  <g id="{view.view_id}" data-view-type="{view.view_type}">')
            
            # View Labels
            for ann in view.annotations:
                lines.append(
                    f'    <text x="{view.origin[0]}" y="{view.bounding_box.get("y_max", view.origin[1]) + 25.0}" '
                    f'text-anchor="middle" font-size="12" font-weight="bold" fill="#334155">{ann}</text>'
                )

            # Centerlines (long-dash-short-dash)
            for cl in view.centerlines:
                lines.append(
                    f'    <line x1="{cl.start[0]:.2f}" y1="{cl.start[1]:.2f}" x2="{cl.end[0]:.2f}" y2="{cl.end[1]:.2f}" '
                    f'stroke="#dc2626" stroke-width="1.0" stroke-dasharray="12,3,2,3" data-feature-type="centerline" />'
                )

            # Visible Lines
            for vl in view.lines:
                lines.append(
                    f'    <line x1="{vl.start[0]:.2f}" y1="{vl.start[1]:.2f}" x2="{vl.end[0]:.2f}" y2="{vl.end[1]:.2f}" '
                    f'stroke="#0f172a" stroke-width="2.5" stroke-linecap="round" data-feature-type="shaft" />'
                )

            # Arcs / Circles
            for arc in view.arcs:
                lines.append(
                    f'    <circle cx="{arc.center[0]:.2f}" cy="{arc.center[1]:.2f}" r="{arc.radius:.2f}" '
                    f'fill="none" stroke="#0f172a" stroke-width="2.5" data-feature-type="shaft" />'
                )

            # Dimensions
            for dim in view.dimensions:
                d_type = dim.dimension_type
                p_attr = (
                    f'data-feature-type="dimension" data-dimension-id="{dim.dimension_id}" '
                    f'data-dimension-type="{dim.dimension_type}" data-source-parameter="{dim.source_parameter}" '
                    f'data-value="{dim.value}" data-unit="{dim.unit}" data-source-design-id="{doc.source_design_id or ""}"'
                )

                if d_type == "linear_length":
                    # Horizontal dimension with witness lines
                    y_dim = dim.start_point[1]
                    x_start, x_end = dim.start_point[0], dim.end_point[0]
                    # Extension lines down to dimension line
                    lines.append(f'    <line x1="{x_start:.2f}" y1="{y_dim - 35.0:.2f}" x2="{x_start:.2f}" y2="{y_dim + 8.0:.2f}" stroke="#64748b" stroke-width="1.0" />')
                    lines.append(f'    <line x1="{x_end:.2f}" y1="{y_dim - 35.0:.2f}" x2="{x_end:.2f}" y2="{y_dim + 8.0:.2f}" stroke="#64748b" stroke-width="1.0" />')
                    # Dimension line with arrows
                    lines.append(
                        f'    <line x1="{x_start:.2f}" y1="{y_dim:.2f}" x2="{x_end:.2f}" y2="{y_dim:.2f}" '
                        f'stroke="#1e40af" stroke-width="1.5" marker-start="url(#arrow-start)" marker-end="url(#arrow-end)" {p_attr} />'
                    )
                    # Dimension text
                    lines.append(
                        f'    <text x="{dim.text_position[0]:.2f}" y="{dim.text_position[1]:.2f}" '
                        f'text-anchor="middle" font-size="13" font-weight="bold" fill="#1e40af">{dim.annotation_text}</text>'
                    )

                elif d_type == "diameter":
                    if "front" in dim.dimension_id:
                        # Vertical diameter dimension on front view
                        x_dim = dim.start_point[0]
                        y_start, y_end = dim.start_point[1], dim.end_point[1]
                        # Extension lines
                        lines.append(f'    <line x1="{x_dim - 8.0:.2f}" y1="{y_start:.2f}" x2="{x_dim + 35.0:.2f}" y2="{y_start:.2f}" stroke="#64748b" stroke-width="1.0" />')
                        lines.append(f'    <line x1="{x_dim - 8.0:.2f}" y1="{y_end:.2f}" x2="{x_dim + 35.0:.2f}" y2="{y_end:.2f}" stroke="#64748b" stroke-width="1.0" />')
                        # Dimension line with arrows
                        lines.append(
                            f'    <line x1="{x_dim:.2f}" y1="{y_start:.2f}" x2="{x_dim:.2f}" y2="{y_end:.2f}" '
                            f'stroke="#1e40af" stroke-width="1.5" marker-start="url(#arrow-vert-start)" marker-end="url(#arrow-vert-end)" {p_attr} />'
                        )
                        # Text rotated or beside
                        lines.append(
                            f'    <text x="{dim.text_position[0]:.2f}" y="{dim.text_position[1]:.2f}" '
                            f'text-anchor="end" dominant-baseline="middle" font-size="13" font-weight="bold" fill="#1e40af">{dim.annotation_text}</text>'
                        )
                    else:
                        # Callout on End View
                        lines.append(
                            f'    <line x1="{dim.start_point[0]:.2f}" y1="{dim.start_point[1]:.2f}" '
                            f'x2="{dim.end_point[0]:.2f}" y2="{dim.end_point[1]:.2f}" '
                            f'stroke="#1e40af" stroke-width="1.5" marker-start="url(#arrow-start)" marker-end="url(#arrow-end)" {p_attr} />'
                        )
                        lines.append(
                            f'    <text x="{dim.text_position[0]:.2f}" y="{dim.text_position[1]:.2f}" '
                            f'font-size="13" font-weight="bold" fill="#1e40af">{dim.annotation_text}</text>'
                        )

            lines.append('  </g>')

        # Title Block (Bottom Right)
        tb_x, tb_y = 515.0, 449.0
        tb_w, tb_h = 300.0, 120.0

        lines.extend([
            '  <!-- Engineering Title Block -->',
            f'  <g id="title_block" transform="translate({tb_x}, {tb_y})">',
            f'    <rect x="0" y="0" width="{tb_w}" height="{tb_h}" fill="#f8fafc" stroke="#0f172a" stroke-width="1.5" />',
            f'    <line x1="0" y1="30" x2="{tb_w}" y2="30" stroke="#0f172a" stroke-width="1.0" />',
            f'    <line x1="0" y1="60" x2="{tb_w}" y2="60" stroke="#0f172a" stroke-width="1.0" />',
            f'    <line x1="0" y1="90" x2="{tb_w}" y2="90" stroke="#0f172a" stroke-width="1.0" />',
            f'    <line x1="150" y1="30" x2="150" y2="120" stroke="#0f172a" stroke-width="1.0" />',
            f'    <line x1="225" y1="60" x2="225" y2="90" stroke="#0f172a" stroke-width="1.0" />',
            # Content
            f'    <text x="10" y="20" font-size="13" font-weight="bold" fill="#0f172a">{tb.organization}</text>',
            f'    <text x="10" y="48" font-size="11" fill="#475569">PART: <tspan font-weight="bold" fill="#0f172a">{tb.title}</tspan></text>',
            f'    <text x="160" y="48" font-size="11" fill="#475569">DWG: <tspan font-weight="bold" fill="#0f172a">{tb.drawing_number}</tspan></text>',
            f'    <text x="10" y="78" font-size="11" fill="#475569">MATERIAL: <tspan font-weight="bold" fill="#0f172a">{tb.material or "STEEL"}</tspan></text>',
            f'    <text x="160" y="78" font-size="11" fill="#475569">REV: <tspan font-weight="bold" fill="#0f172a">{tb.revision}</tspan></text>',
            f'    <text x="235" y="78" font-size="11" fill="#475569">SCALE: <tspan font-weight="bold" fill="#0f172a">{tb.scale}</tspan></text>',
            f'    <text x="10" y="108" font-size="10" fill="#64748b">DESIGN ID: {tb.source_design_id or "UNASSIGNED"}</text>',
            f'    <text x="160" y="108" font-size="10" fill="#dc2626" font-weight="bold">HUMAN REVIEW REQUIRED</text>',
            '  </g>',
            '</svg>'
        ])

        return "\n".join(lines)


class DrawingExporter:
    """Saves SVG rendering to disk and provides extensible paths for PDF/DXF."""

    def __init__(self, renderer: Optional[SVGRenderer] = None):
        self.renderer = renderer or SVGRenderer()

    def export_svg(self, doc: DrawingDocument, file_path: str) -> CADArtifact:
        """Renders DrawingDocument and saves to an SVG file artifact."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        svg_content = self.renderer.render(doc)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # Extract primary dimensions for metadata
        dim_map = {d.dimension_id: d.value for d in doc.dimensions}

        return CADArtifact(
            artifact_id=f"art-svg-{doc.drawing_id}",
            machine_element="shaft",
            backend="SVGRenderer",
            format="svg",
            filename=os.path.basename(file_path),
            file_path=os.path.abspath(file_path),
            file_size_bytes=file_size,
            source_design_id=doc.source_design_id,
            parameters=dim_map,
            metadata={"drawing_number": doc.title_block.drawing_number, "sheet": "A3"},
            status=CADStatus.GENERATED
        )
