/**
 * MechaAI Engineering Design Review Console (Slice 15)
 * Client-side presentation layer for verified deterministic design pipeline.
 * Zero UI engineering math: strictly presents backend derivations and statuses.
 */

// Global State
let currentPipelineResult = null;

// ==============================================================================
// Preset Scenarios
// ==============================================================================
const SCENARIOS = {
  benchmark: {
    prompt: "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2.",
    sy: "355.0",
    length: "300.0"
  },
  missing_sy: {
    prompt: "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a minimum factor of safety of 2 and length 300 mm.",
    sy: "",
    length: "300.0"
  },
  missing_length: {
    prompt: "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2.",
    sy: "355.0",
    length: ""
  },
  invalid_sy: {
    prompt: "Design a solid circular steel shaft to transmit 5 kW at 1500 RPM with a factor of safety of 2.",
    sy: "-355.0",
    length: "300.0"
  },
  heavy_power: {
    prompt: "Design a heavy solid circular steel shaft to transmit 5000 kW at 10 RPM with FoS 3.",
    sy: "250.0",
    length: "1000.0"
  }
};

function loadScenario(scenarioKey) {
  const sc = SCENARIOS[scenarioKey];
  if (!sc) return;

  document.getElementById("problemStatement").value = sc.prompt;
  document.getElementById("yieldStrength").value = sc.sy;
  document.getElementById("shaftLength").value = sc.length;

  // Auto-run for rapid review
  document.getElementById("designForm").dispatchEvent(new Event("submit"));
}

function resetForm() {
  document.getElementById("problemStatement").value = "";
  document.getElementById("yieldStrength").value = "";
  document.getElementById("shaftLength").value = "";
}

// ==============================================================================
// Pipeline Execution via POST /design/pipeline
// ==============================================================================
async function handleRunDesign(event) {
  if (event) event.preventDefault();

  const prompt = document.getElementById("problemStatement").value.trim();
  const syRaw = document.getElementById("yieldStrength").value.trim();
  const lenRaw = document.getElementById("shaftLength").value.trim();

  const engInputs = {};
  if (syRaw !== "") {
    const num = Number(syRaw);
    engInputs["yield_strength_mpa"] = isNaN(num) ? syRaw : num;
  }
  if (lenRaw !== "") {
    const num = Number(lenRaw);
    engInputs["length_mm"] = isNaN(num) ? lenRaw : num;
  }

  const payload = {
    problem_statement: prompt,
    engineering_inputs: engInputs
  };

  setLoadingState(true);

  try {
    const response = await fetch("/design/pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned ${response.status}`);
    }

    const data = await response.json();
    currentPipelineResult = data;
    renderPipelineResult(data);
  } catch (err) {
    renderExecutionError(err.message);
  } finally {
    setLoadingState(false);
  }
}

function setLoadingState(isLoading) {
  const btn = document.getElementById("runDesignBtn");
  const icon = document.getElementById("btnIcon");
  const text = document.getElementById("btnText");

  if (isLoading) {
    btn.disabled = true;
    icon.textContent = "⏳";
    text.textContent = "Synthesizing Design...";
  } else {
    btn.disabled = false;
    icon.textContent = "⚡";
    text.textContent = "Run Design Pipeline";
  }
}

// ==============================================================================
// Result Rendering Orchestrator
// ==============================================================================
function renderPipelineResult(data) {
  const status = data.status || "UNKNOWN";

  // 1. Status Badges & Pills
  updateStatusPills(status);

  // 2. Summary Card & Metrics
  renderSummaryCard(data);

  // 3. Verification Gates
  renderVerificationGates(data);

  // 4. Tab 1: Extracted Requirements & Provenance
  renderRequirementsTable(data);

  // 5. Tab 2: Engineering Certificate & Sizing
  renderEngineeringCertificate(data);

  // 6. Tab 3: 2D SVG Technical Drawing
  renderSvgDrawing(data);

  // 7. Tab 4: Traceability Matrix
  renderTraceabilityMatrix(data);

  // 8. Tab 5: Artifact Package
  renderArtifactsGrid(data);

  // 9. Tab 6: Audit Report
  renderReport(data);
}

function updateStatusPills(status) {
  const topPill = document.getElementById("topStatusPill");
  const overallBadge = document.getElementById("overallStatusBadge");

  const clsMap = {
    SUCCESS: "status-success",
    BLOCKED: "status-blocked",
    INVALID: "status-invalid",
    REQUIRES_REVIEW: "status-review",
    FAILED: "status-invalid"
  };

  const statusCls = clsMap[status] || "status-neutral";

  topPill.className = `status-pill ${statusCls}`;
  topPill.textContent = `STATUS: ${status}`;

  overallBadge.className = `status-badge ${statusCls}`;
  overallBadge.textContent = status;
}

function renderSummaryCard(data) {
  const status = data.status;
  const sol = data.solver_result;

  document.getElementById("summaryStatusVal").textContent = status;
  document.getElementById("summaryStatusVal").className = `metric-val ${
    status === "SUCCESS" ? "text-success-strong" : (status === "BLOCKED" ? "badge-missing" : "badge-invalid")
  }`;

  if (sol && sol.is_valid && sol.selected_diameter_mm != null) {
    document.getElementById("summarySizeVal").textContent = `Ø ${sol.selected_diameter_mm.toFixed(1)} mm`;
    document.getElementById("summaryFosVal").textContent = `${sol.achieved_factor_of_safety.toFixed(2)} (Req: ${sol.factor_of_safety.toFixed(1)})`;
    document.getElementById("summarySafetyVal").textContent = sol.is_safe ? "Yield-Strength Design Constraint Satisfied" : "Design Constraint Not Satisfied";
    document.getElementById("summarySafetyVal").className = `metric-val ${sol.is_safe ? "text-success-strong" : "badge-invalid"}`;
  } else {
    document.getElementById("summarySizeVal").textContent = "—";
    document.getElementById("summaryFosVal").textContent = "—";
    document.getElementById("summarySafetyVal").textContent = status === "BLOCKED" ? "EXECUTION BLOCKED" : (status === "INVALID" ? "INVALID INPUT" : "—");
    document.getElementById("summarySafetyVal").className = "metric-val text-muted";
  }
}

function renderVerificationGates(data) {
  const status = data.status;
  const sol = data.solver_result;
  const cad = data.cad_result;
  const cross = data.cross_validation || {};

  setGate("gateExtraction", data.spec ? "pass" : "fail", "Requirement Extraction & Provenance");
  
  // Explicit Validation Gate
  if (status === "INVALID") {
    setGate("gateValidation", "fail", `Explicit Parameter Validation (Error: ${data.errors.join(", ")})`);
  } else if (status === "BLOCKED") {
    setGate("gateValidation", "blocked", `Explicit Parameter Validation (Missing: ${data.missing_information.join(", ")})`);
  } else {
    setGate("gateValidation", "pass", "Explicit Parameter Validation");
  }

  // Solver Gate
  if (sol && sol.is_valid) {
    setGate("gateSolver", "pass", `Closed-Form Mechanical Solver (T = ${sol.torque_nm.toFixed(2)} N·m)`);
  } else if (status === "BLOCKED") {
    setGate("gateSolver", "blocked", "Closed-Form Mechanical Solver (Execution Blocked)");
  } else {
    setGate("gateSolver", "fail", "Closed-Form Mechanical Solver (Invalid Input)");
  }

  // Nominal Policy Gate
  if (sol && sol.is_valid && sol.selected_diameter_mm != null) {
    setGate("gateNominalPolicy", "pass", `Configured Nominal Series Policy (d_nominal = ${sol.selected_diameter_mm.toFixed(1)} mm)`);
  } else if (status === "BLOCKED") {
    setGate("gateNominalPolicy", "blocked", "Configured Nominal Series Policy (Not Evaluated)");
  } else {
    setGate("gateNominalPolicy", "fail", "Configured Nominal Series Policy");
  }

  // BRep Topology Gate
  if (cad && cad.validation && cad.validation.is_valid) {
    setGate("gateBrep", "pass", `Parametric 3D BRep Topology & Volume (${cad.validation.calculated_volume.toFixed(1)} mm³)`);
  } else if (status === "BLOCKED" || status === "INVALID") {
    setGate("gateBrep", "neutral", "Parametric 3D BRep Topology (No CAD Generated)");
  } else {
    setGate("gateBrep", "fail", "Parametric 3D BRep Topology");
  }

  // Drawing Derivation Gate
  if (cad && cad.drawing_document) {
    setGate("gateDrawing", "pass", "2D Technical Drawing Derivation");
  } else if (status === "BLOCKED" || status === "INVALID") {
    setGate("gateDrawing", "neutral", "2D Technical Drawing Derivation (Not Generated)");
  } else {
    setGate("gateDrawing", "fail", "2D Technical Drawing Derivation");
  }

  // Cross-Validation Gate
  if (cross && cross.all_match === true) {
    setGate("gateCrossVal", "pass", "CAD ↔ Drawing Dimensional Agreement (100% Match)");
  } else if (cross && cross.all_match === false) {
    setGate("gateCrossVal", "review", "CAD ↔ Drawing Dimensional Agreement (MISMATCH - Review Req'd)");
  } else {
    setGate("gateCrossVal", "neutral", "CAD ↔ Drawing Dimensional Agreement");
  }
}

function setGate(elementId, state, text) {
  const el = document.getElementById(elementId);
  if (!el) return;

  const iconMap = {
    pass: "✓",
    blocked: "⊘",
    fail: "✗",
    review: "⚠️",
    neutral: "○"
  };

  el.className = `gate-item gate-${state}`;
  el.innerHTML = `<span class="gate-icon">${iconMap[state] || "○"}</span> ${text}`;
}

// ==============================================================================
// Tab 1: Extracted Requirements Table
// ==============================================================================
function renderRequirementsTable(data) {
  const tbody = document.getElementById("requirementsTableBody");
  tbody.innerHTML = "";

  const spec = data.spec || {};
  const provDict = data.provenance?.fields || data.provenance || {};
  const missing = data.missing_information || [];
  const errors = data.errors || [];

  const fields = [
    { key: "component", label: "Component Type", val: spec.component, unit: "—" },
    { key: "material", label: "Material Specification", val: spec.material, unit: "—" },
    { key: "power_kw", label: "Transmitted Power (P)", val: spec.power_kw, unit: "kW" },
    { key: "rpm", label: "Rotational Speed (N)", val: spec.rpm, unit: "RPM" },
    { key: "factor_of_safety", label: "Design Factor of Safety (FoS)", val: spec.factor_of_safety, unit: "—" },
    { key: "yield_strength_mpa", label: "Tensile Yield Strength (S_y)", val: spec.yield_strength_mpa, unit: "MPa" },
    { key: "length_mm", label: "Shaft Length (L)", val: spec.length_mm, unit: "mm" }
  ];

  fields.forEach(f => {
    const tr = document.createElement("tr");
    const prov = provDict[f.key] || {};
    const isMissing = missing.includes(f.key) || (f.val == null);
    const hasError = errors.some(e => e.includes(f.key));

    let stateBadge = "";
    if (hasError) {
      stateBadge = '<span class="badge badge-invalid">INVALID</span>';
    } else if (isMissing) {
      stateBadge = '<span class="badge badge-missing">MISSING (BLOCKED)</span>';
    } else if (prov.source_text === "structured_input") {
      stateBadge = '<span class="badge badge-structured">STRUCTURED INPUT</span>';
    } else if (prov.is_explicit) {
      stateBadge = '<span class="badge badge-explicit">EXPLICIT IN PROMPT</span>';
    } else {
      stateBadge = '<span class="badge badge-missing">UNSTATED</span>';
    }

    const valDisplay = f.val != null ? `<span class="font-mono font-bold">${f.val}</span>` : '<span class="text-muted">null</span>';
    const srcDisplay = prov.source_text ? `<code class="font-mono text-sm">${prov.source_text}</code>` : '<span class="text-muted">—</span>';
    const confDisplay = prov.confidence != null ? `<span class="font-mono">${(prov.confidence * 100).toFixed(0)}%</span>` : '<span class="text-muted">—</span>';

    tr.innerHTML = `
      <td><strong>${f.label}</strong> <span class="text-muted text-sm">(${f.key})</span></td>
      <td>${valDisplay}</td>
      <td class="font-mono">${f.unit}</td>
      <td>${stateBadge}</td>
      <td>${srcDisplay}</td>
      <td>${confDisplay}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ==============================================================================
// Tab 2: Engineering Sizing Certificate
// ==============================================================================
function renderEngineeringCertificate(data) {
  const sol = data.solver_result;
  const spec = data.spec || {};

  // User Inputs
  document.getElementById("engValSy").textContent = spec.yield_strength_mpa != null ? `${spec.yield_strength_mpa} MPa` : "Missing (null)";
  document.getElementById("engValL").textContent = spec.length_mm != null ? `${spec.length_mm} mm` : "Missing (null)";
  document.getElementById("engValP").textContent = spec.power_kw != null ? `${spec.power_kw} kW` : "—";
  document.getElementById("engValN").textContent = spec.rpm != null ? `${spec.rpm} RPM` : "—";
  document.getElementById("engValFosReq").textContent = spec.factor_of_safety != null ? `${spec.factor_of_safety.toFixed(2)}` : "—";

  if (sol && sol.is_valid) {
    document.getElementById("engValTorque").textContent = `${sol.torque_nm.toFixed(3)} N·m`;
    document.getElementById("engValTauAllow").textContent = `${sol.allowable_stress_mpa.toFixed(2)} MPa`;
    document.getElementById("engValDreq").textContent = `${sol.minimum_required_diameter_mm.toFixed(2)} mm`;

    document.getElementById("engValDsel").textContent = `Ø ${sol.selected_diameter_mm.toFixed(1)} mm`;
    document.getElementById("engValPolicyName").textContent = sol.diameter_selection_policy || "metric_nominal_shaft_series_r20_custom";
    document.getElementById("engValPolicyReason").textContent = sol.diameter_selection_reason || "Smallest nominal size >= d_required";

    document.getElementById("engValTauDesign").textContent = `${sol.design_stress_mpa.toFixed(2)} MPa`;
    document.getElementById("engValFosAchieved").textContent = `${sol.achieved_factor_of_safety.toFixed(2)}`;
    document.getElementById("engValSafetyStatus").textContent = sol.is_safe ? "Yield-Strength Design Constraint Satisfied (τ_design ≤ τ_allow)" : "Design Constraint Not Satisfied (τ_design > τ_allow)";
    document.getElementById("engValSafetyStatus").className = `v font-bold ${sol.is_safe ? "text-success-strong" : "badge-invalid"}`;

    // Derivation steps
    const stepsList = document.getElementById("derivationStepsList");
    stepsList.innerHTML = "";
    sol.calculation_steps.forEach(st => {
      const li = document.createElement("li");
      li.textContent = st;
      stepsList.appendChild(li);
    });
  } else {
    document.getElementById("engValTorque").textContent = "—";
    document.getElementById("engValTauAllow").textContent = "—";
    document.getElementById("engValDreq").textContent = "—";
    document.getElementById("engValDsel").textContent = "—";
    document.getElementById("engValPolicyName").textContent = "—";
    document.getElementById("engValPolicyReason").textContent = "—";
    document.getElementById("engValTauDesign").textContent = "—";
    document.getElementById("engValFosAchieved").textContent = "—";
    document.getElementById("engValSafetyStatus").textContent = data.status === "BLOCKED" ? "EXECUTION BLOCKED" : (data.status === "INVALID" ? "INVALID INPUT" : "—");
    document.getElementById("engValSafetyStatus").className = "v text-muted";

    const stepsList = document.getElementById("derivationStepsList");
    stepsList.innerHTML = `<li class="text-muted">Calculations halted (${data.status}). ${data.errors.concat(data.missing_information.map(m => `Missing: ${m}`)).join("; ")}</li>`;
  }
}

// ==============================================================================
// Tab 3: 2D SVG Technical Drawing Viewport
// ==============================================================================
async function renderSvgDrawing(data) {
  const viewport = document.getElementById("svgViewport");
  const downloadBtn = document.getElementById("downloadSvgBtn");

  const svgArtifact = data.artifacts?.svg;
  if (!svgArtifact || !svgArtifact.file_path) {
    viewport.innerHTML = `<div class="empty-viewport-msg text-muted"><span>📐 No 2D engineering drawing generated (Status: ${data.status}).</span></div>`;
    downloadBtn.className = "btn btn-sm btn-outline disabled";
    downloadBtn.removeAttribute("href");
    return;
  }

  // Construct artifact download/preview URL
  // file_path is e.g. artifacts/drawings/shaft_12x300_drawing.svg
  const normPath = svgArtifact.file_path.replace(/\\/g, "/");
  const relativePath = normPath.substring(normPath.indexOf("artifacts/"));
  const svgUrl = `/${relativePath}`;

  downloadBtn.className = "btn btn-sm btn-outline";
  downloadBtn.href = svgUrl;
  downloadBtn.download = svgArtifact.filename || "drawing.svg";

  try {
    const res = await fetch(svgUrl);
    if (res.ok) {
      const svgText = await res.text();
      viewport.innerHTML = svgText;
    } else {
      viewport.innerHTML = `<img src="${svgUrl}" alt="2D Engineering Drawing" style="max-width:100%;">`;
    }
  } catch {
    viewport.innerHTML = `<img src="${svgUrl}" alt="2D Engineering Drawing" style="max-width:100%;">`;
  }
}

// ==============================================================================
// Tab 4: Traceability Matrix
// ==============================================================================
function renderTraceabilityMatrix(data) {
  const tbody = document.getElementById("traceabilityTableBody");
  tbody.innerHTML = "";

  const handoff = data.handoff;
  if (!handoff || !handoff.traceability_matrix) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No handoff traceability package available (Status: ${data.status}).</td></tr>`;
    return;
  }

  const mat = handoff.traceability_matrix;
  const params = mat.parameters || {};
  const metrics = mat.solver_metrics || {};

  const rows = [
    {
      name: "Shaft Diameter",
      origin: metrics.minimum_required_diameter_mm != null ? `Theoretical required: ${metrics.minimum_required_diameter_mm} mm` : "Unstated in prompt",
      solver: metrics.selected_diameter_mm != null ? `Selected nominal: ${metrics.selected_diameter_mm} mm` : "—",
      cad: params.shaft_diameter ? `Ø ${params.shaft_diameter.cad_value} mm` : "—",
      drawing: params.shaft_diameter ? `Ø ${params.shaft_diameter.drawing_dimension} mm` : "—",
      status: params.shaft_diameter?.status || "VERIFIED"
    },
    {
      name: "Shaft Length",
      origin: data.spec?.length_mm != null ? "Explicit structured input" : "Unstated in prompt",
      solver: data.spec?.length_mm != null ? `${data.spec.length_mm} mm` : "—",
      cad: params.shaft_length ? `${params.shaft_length.cad_value} mm` : "—",
      drawing: params.shaft_length ? `${params.shaft_length.drawing_dimension} mm` : "—",
      status: params.shaft_length?.status || "VERIFIED"
    },
    {
      name: "Material Specification",
      origin: data.spec?.material || "Unstated in prompt",
      solver: metrics.yield_strength_mpa != null ? `S_y = ${metrics.yield_strength_mpa} MPa` : "—",
      cad: params.material?.specified || (data.spec?.material || "—"),
      drawing: params.material?.title_block || (data.spec?.material ? data.spec.material.toUpperCase() : "—"),
      status: params.material?.status || "SPECIFIED"
    },
    {
      name: "Transmitted Torque",
      origin: (data.spec?.power_kw != null && data.spec?.rpm != null) ? `${data.spec.power_kw} kW @ ${data.spec.rpm} RPM` : "Unstated in prompt",
      solver: metrics.torque_nm != null ? `${metrics.torque_nm.toFixed(3)} N·m` : "—",
      cad: "Embedded in STEP parameters",
      drawing: "Title Block / Calculation Handoff",
      status: "DERIVED"
    }
  ];

  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.name}</strong></td>
      <td><code class="font-mono text-sm">${r.origin}</code></td>
      <td><span class="font-mono font-bold">${r.solver}</span></td>
      <td><span class="font-mono">${r.cad}</span></td>
      <td><span class="font-mono">${r.drawing}</span></td>
      <td><span class="badge badge-explicit">${r.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ==============================================================================
// Tab 5: Artifact Release Package
// ==============================================================================
function renderArtifactsGrid(data) {
  const grid = document.getElementById("artifactsGrid");
  grid.innerHTML = "";

  const artifacts = data.artifacts || {};
  const entries = Object.entries(artifacts);

  if (entries.length === 0) {
    grid.innerHTML = `<div class="artifact-card text-muted">No geometric or drawing artifacts generated (${data.status}).</div>`;
    return;
  }

  entries.forEach(([fmt, art]) => {
    const card = document.createElement("div");
    card.className = "artifact-card";
    
    const normPath = art.file_path.replace(/\\/g, "/");
    const relativePath = normPath.substring(normPath.indexOf("artifacts/"));
    const downloadUrl = `/${relativePath}`;

    card.innerHTML = `
      <div class="artifact-title">📦 ${fmt.toUpperCase()} Artifact: ${art.filename}</div>
      <div class="artifact-meta">Format: ${art.format.toUpperCase()} • Size: ${art.file_size_bytes} bytes</div>
      <div class="artifact-meta">Path: <code>${art.file_path}</code></div>
      <div style="margin-top:8px;">
        <a href="${downloadUrl}" class="btn btn-sm btn-outline" download="${art.filename}">⬇️ Download ${fmt.toUpperCase()}</a>
      </div>
    `;
    grid.appendChild(card);
  });
}

// ==============================================================================
// Tab 6: Report Viewer
// ==============================================================================
function renderReport(data) {
  const viewer = document.getElementById("reportViewer");
  viewer.textContent = data.report || "No report available.";
}

function copyReportToClipboard() {
  const text = document.getElementById("reportViewer").textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert("Report copied to clipboard!");
  });
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));

  const targetPane = document.getElementById(tabId);
  if (targetPane) targetPane.classList.add("active");

  const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(btn => btn.getAttribute("onclick")?.includes(tabId));
  if (activeBtn) activeBtn.classList.add("active");
}

function renderExecutionError(errMsg) {
  updateStatusPills("FAILED");
  alert(`Pipeline Error: ${errMsg}`);
}

// Initial default run on page load for immediate portfolio presentation
window.addEventListener("DOMContentLoaded", () => {
  handleRunDesign();
});
