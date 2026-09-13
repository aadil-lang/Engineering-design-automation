"""
Markdown Report Generator for Parametric CAD & 2D Engineering Drawings.
Produces audit-ready summaries of geometric verification, STEP artifacts,
drawing dimensions, and cross-validation integrity.
"""

from cad.models import CADGenerationResponse, CADStatus


def generate_cad_report(response: CADGenerationResponse) -> str:
    """
    Renders an auditable GitHub-flavored Markdown report documenting CAD generation.
    """
    lines = []
    spec = response.cad_specification
    val = response.validation
    cross = response.dimensional_cross_validation

    status_icon = "🟢" if response.status == CADStatus.GENERATED else ("🟡" if response.status == CADStatus.REQUIRES_REVIEW else "🔴")

    lines.extend([
        "# Parametric CAD & Engineering Drawing Report",
        "Deterministic 3D Solid Modeling & 2D Drawing Traceability Audit",
        "",
        "> [!NOTE]",
        "> The 3D CAD solid model represents the geometric engineering truth.",
        "> 2D SVG drawings are derived representations. Generated artifacts require human review prior to manufacturing release.",
        "",
        f"- **CAD Status:** {status_icon} **`{response.status.value}`**",
        f"- **Part Name:** `{spec.part_name}`",
        f"- **Machine Element:** `{spec.machine_element.upper()}`",
        f"- **Material:** `{spec.material or 'steel'}`",
        f"- **Source Design ID:** `{spec.source_design_id or 'DIRECT_INPUT'}`",
        f"- **Candidate ID:** `{spec.source_design_candidate_id or 'DIRECT_INPUT'}`",
        ""
    ])

    if response.warnings:
        lines.append("> [!WARNING]")
        lines.append("> **Engineering Warnings & Flags:**")
        for w in response.warnings:
            lines.append(f"> - {w}")
        lines.append("")

    # 1. Geometry Specification
    lines.extend([
        "## 1. Governing Geometry Parameters",
        "| Parameter | Value | Unit | Source / Provenance |",
        "|---|---|---|---|",
        f"| `diameter` | {spec.diameter} | {spec.units} | Selected Design Candidate |",
        f"| `length` | {spec.length} | {spec.units} | Specification / Constraint |",
        ""
    ])

    # 2. 3D BRep Validation
    if val:
        v_icon = "PASS" if val.is_valid else "FAIL"
        lines.extend([
            "## 2. 3D BRep Solid Geometry & Topological Validation",
            f"- **Validation Status:** **`{v_icon}`**",
            f"- **Analytical Volume:** `{val.calculated_volume:.2f} mm³` (Error: `{val.volume_error_rel * 100:.4f}%`)",
            f"- **Surface Area:** `{val.calculated_surface_area:.2f} mm²`",
            "- **3D Bounding Box Boundaries (mm):**",
            f"  - Length ($X$): `[{val.bounding_box.get('min_x', 0):.2f}, {val.bounding_box.get('max_x', 0):.2f}]` (dx: `{val.bounding_box.get('dx', 0):.2f}`)",
            f"  - Diameter ($Y$): `[{val.bounding_box.get('min_y', 0):.2f}, {val.bounding_box.get('max_y', 0):.2f}]` (dy: `{val.bounding_box.get('dy', 0):.2f}`)",
            f"  - Diameter ($Z$): `[{val.bounding_box.get('min_z', 0):.2f}, {val.bounding_box.get('max_z', 0):.2f}]` (dz: `{val.bounding_box.get('dz', 0):.2f}`)",
            ""
        ])

    # 3. Generated Artifacts
    lines.extend([
        "## 3. Generated CAD & Drawing Artifacts",
        "| Artifact Format | Filename | Size | Backend | Path |",
        "|---|---|---|---|---|"
    ])
    for fmt, art in response.artifacts.items():
        size_str = f"{art.file_size_bytes} bytes" if art.file_size_bytes < 1024 else f"{art.file_size_bytes / 1024:.1f} KB"
        lines.append(f"| `{fmt.upper()}` | `{art.filename}` | {size_str} | {art.backend} | `{art.file_path}` |")
    lines.append("")

    # 4. Dimensional Cross-Validation
    if cross:
        lines.extend([
            "## 4. Drawing ↔ CAD Dimensional Cross-Validation",
            "| Feature Parameter | Drawing Callout | CAD Model Value | Delta | Status |",
            "|---|---|---|---|---|"
        ])
        for param, chk in cross.items():
            if isinstance(chk, dict) and "drawing_value" in chk:
                m_icon = "🟢 MATCH" if chk["match"] else "🔴 MISMATCH"
                lines.append(f"| `{param}` | {chk['drawing_value']} mm | {chk['cad_value']} mm | {chk['delta_mm']:.4f} mm | {m_icon} |")
        lines.append("")

    # 5. Drawing Document Details
    if response.drawing_document:
        doc = response.drawing_document
        lines.extend([
            "## 5. Derived 2D Drawing Document",
            f"- **Drawing ID:** `{doc.drawing_id}`",
            f"- **Drawing Sheet Format:** `A3 Landscape ({doc.sheet_width} x {doc.sheet_height} mm)`",
            f"- **Title Block Revision:** `{doc.title_block.revision}`",
            f"- **Drawing Scale:** `{doc.title_block.scale}`",
            "- **Views Projected from BRep:**",
        ])
        for v in doc.views:
            lines.append(f"  - `{v.view_type}` (Elements: {len(v.lines)} lines, {len(v.arcs)} arcs, {len(v.centerlines)} centerlines)")
        lines.append("")

    # 6. Assumptions & Review
    lines.extend([
        "## 6. Tracked Assumptions & Engineering Review",
        "- Ideal smooth circular geometry without keyways, snap rings, or shoulder steps.",
        "- Material preserved as generic steel; exact alloy and heat-treatment certification not claimed.",
        "- CAD solid model requires engineering review prior to manufacturing or detailing.",
        ""
    ])

    return "\n".join(lines)
