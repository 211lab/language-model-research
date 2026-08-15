const state = {
  filter: "local",
  overview: { editorial: { models: [] }, assistant: { models: [] } },
  jobs: [],
  runtime: null,
  catalog: [],
};

const $ = (selector) => document.querySelector(selector);
const apiStatus = $("#api-status");

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function setConnection(ok, text) {
  apiStatus.className = `connection ${ok ? "connection--ok" : "connection--error"}`;
  apiStatus.textContent = text;
}

function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function isLocal(record) {
  return record.cost_source === "local" || record.benchmark_track === "local" || /local|llama/i.test(String(record.provider || ""));
}

function filtered(records) {
  if (state.filter === "all") return records;
  return records.filter((record) => (state.filter === "local" ? isLocal(record) : !isLocal(record)));
}

function formatNumber(value, decimals = 1) {
  return isNumber(value) ? value.toFixed(decimals) : "—";
}

function formatCost(value, source) {
  if (source === "local") return "Local";
  return isNumber(value) ? `$${value.toFixed(4)}` : "Unavailable";
}

function formatAssistantCost(record) {
  if (!record) return "—";
  if (isLocal(record)) return "Local";
  const spent = formatCost(record.provider_reported_cost_usd);
  const cap = formatCost(record.provider_cost_limit_usd);
  return cap === "Unavailable" ? spent : `${spent} / cap ${cap}`;
}

function comparisonKey(record) {
  if (record.identity_key) return record.identity_key;
  return `${isLocal(record) ? "local" : "openrouter"}:${record.model || "unknown"}`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleString();
}

function short(value, limit = 27) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function svgElement(name, attributes = {}, text = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text) node.textContent = text;
  return node;
}

function clearSvg(node, width, height) {
  node.replaceChildren();
  node.setAttribute("viewBox", `0 0 ${width} ${height}`);
}

function chartText(svg, x, y, text, className, anchor = "start") {
  svg.append(svgElement("text", { x, y, class: className, "text-anchor": anchor }, text));
}

function drawEditorialChart() {
  const svg = $("#editorial-chart");
  const width = 720;
  const height = 360;
  clearSvg(svg, width, height);
  const models = filtered(state.overview.editorial.models || []).filter((model) => isNumber(model.content_score));
  if (!models.length) {
    chartText(svg, width / 2, height / 2, "No editorial scores match this filter.", "chart-empty", "middle");
    return;
  }
  const left = 58;
  const right = 42;
  const top = 28;
  const bottom = 66;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const priced = models.filter((model) => isNumber(model.cost_usd));
  const maxCost = Math.max(...priced.map((model) => model.cost_usd), 0.000001);
  const x = (model) => {
    if (!isNumber(model.cost_usd) || model.cost_usd === 0) return left + 5;
    return left + (Math.log1p(model.cost_usd) / Math.log1p(maxCost)) * plotWidth;
  };
  const y = (model) => top + plotHeight * (1 - Math.min(100, Math.max(0, model.content_score)) / 100);
  for (let tick = 0; tick <= 5; tick += 1) {
    const score = tick * 20;
    const yValue = top + plotHeight * (1 - score / 100);
    svg.append(svgElement("line", { x1: left, y1: yValue, x2: width - right, y2: yValue, class: "chart-grid-line" }));
    chartText(svg, left - 9, yValue + 4, String(score), "axis-label", "end");
  }
  svg.append(svgElement("line", { x1: left, y1: top, x2: left, y2: height - bottom, class: "chart-grid-line" }));
  svg.append(svgElement("line", { x1: left, y1: height - bottom, x2: width - right, y2: height - bottom, class: "chart-grid-line" }));
  chartText(svg, left, 15, "Editorial quality score", "axis-title");
  chartText(svg, left, height - 22, "Local baseline", "axis-label");
  chartText(svg, width - right, height - 22, "Bundle cost (log scale)", "axis-label", "end");
  models.forEach((model) => {
    const local = isLocal(model);
    const color = local ? "#55e0bf" : "#65b8ff";
    const point = svgElement("circle", { cx: x(model), cy: y(model), r: 6.7, fill: color, class: "chart-point" });
    point.append(svgElement("title", {}, `${model.display_name}\nQuality: ${formatNumber(model.content_score, 2)}\nCost: ${formatCost(model.cost_usd, model.cost_source)}`));
    svg.append(point);
  });
  const legend = models.slice().sort((a, b) => b.content_score - a.content_score).slice(0, 5);
  legend.forEach((model, index) => {
    const yValue = 26 + index * 19;
    svg.append(svgElement("circle", { cx: width - 210, cy: yValue - 4, r: 4, fill: isLocal(model) ? "#55e0bf" : "#65b8ff" }));
    chartText(svg, width - 201, yValue, short(model.display_name, 29), "axis-label");
  });
}

function drawReadabilityChart() {
  const svg = $("#readability-chart");
  const width = 720;
  const height = 360;
  clearSvg(svg, width, height);
  const models = filtered(state.overview.editorial.models || [])
    .map((model) => ({
      ...model,
      ease: model.readability?.["bundle total"]?.flesch_reading_ease,
      grade: model.readability?.["bundle total"]?.flesch_kincaid_grade,
    }))
    .filter((model) => isNumber(model.ease) && isNumber(model.grade));
  if (!models.length) {
    chartText(svg, width / 2, height / 2, "No readability records match this filter.", "chart-empty", "middle");
    return;
  }
  const left = 58;
  const right = 42;
  const top = 28;
  const bottom = 54;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximumGrade = Math.max(12, ...models.map((model) => model.grade));
  const x = (model) => left + Math.min(100, Math.max(0, model.ease)) / 100 * plotWidth;
  const y = (model) => top + Math.min(maximumGrade, Math.max(0, model.grade)) / maximumGrade * plotHeight;
  for (let tick = 0; tick <= 5; tick += 1) {
    const ease = tick * 20;
    const xValue = left + ease / 100 * plotWidth;
    svg.append(svgElement("line", { x1: xValue, y1: top, x2: xValue, y2: height - bottom, class: "chart-grid-line" }));
    chartText(svg, xValue, height - bottom + 18, String(ease), "axis-label", "middle");
  }
  for (let tick = 0; tick <= 4; tick += 1) {
    const grade = maximumGrade * tick / 4;
    const yValue = top + plotHeight * tick / 4;
    svg.append(svgElement("line", { x1: left, y1: yValue, x2: width - right, y2: yValue, class: "chart-grid-line" }));
    chartText(svg, left - 9, yValue + 4, grade.toFixed(1), "axis-label", "end");
  }
  chartText(svg, left, 15, "Lower grade level", "axis-title");
  chartText(svg, width - right, height - 15, "Flesch reading ease (higher is easier)", "axis-label", "end");
  models.forEach((model) => {
    const color = isLocal(model) ? "#55e0bf" : "#65b8ff";
    const point = svgElement("circle", { cx: x(model), cy: y(model), r: 6.7, fill: color, class: "chart-point" });
    point.append(svgElement("title", {}, `${model.display_name}\nFlesch ease: ${formatNumber(model.ease, 2)}\nFlesch-Kincaid grade: ${formatNumber(model.grade, 2)}`));
    svg.append(point);
  });
  models.slice().sort((a, b) => a.grade - b.grade || b.ease - a.ease).slice(0, 5).forEach((model, index) => {
    const yValue = 26 + index * 19;
    svg.append(svgElement("circle", { cx: width - 210, cy: yValue - 4, r: 4, fill: isLocal(model) ? "#55e0bf" : "#65b8ff" }));
    chartText(svg, width - 201, yValue, short(model.display_name, 29), "axis-label");
  });
}

function drawAssistantChart() {
  const svg = $("#assistant-chart");
  const width = 720;
  const models = filtered(state.overview.assistant.models || []).filter((model) => isNumber(model.assistant_score));
  const rowHeight = 31;
  const top = 42;
  const height = Math.max(260, top + models.length * rowHeight + 32);
  clearSvg(svg, width, height);
  if (!models.length) {
    chartText(svg, width / 2, height / 2, "No assistant results match this filter.", "chart-empty", "middle");
    return;
  }
  const sorted = models.slice().sort((a, b) => b.assistant_score - a.assistant_score);
  const left = 230;
  const right = 55;
  const plotWidth = width - left - right;
  for (let tick = 0; tick <= 5; tick += 1) {
    const value = tick * 20;
    const x = left + (value / 100) * plotWidth;
    svg.append(svgElement("line", { x1: x, y1: top - 12, x2: x, y2: height - 24, class: "chart-grid-line" }));
    chartText(svg, x, top - 20, String(value), "axis-label", "middle");
  }
  sorted.forEach((model, index) => {
    const y = top + index * rowHeight;
    const local = isLocal(model);
    const color = local ? "#55e0bf" : "#ae9bff";
    chartText(svg, left - 12, y + 17, short(model.display_name, 31), "axis-label", "end");
    svg.append(svgElement("rect", { x: left, y: y + 5, width: plotWidth, height: 14, rx: 7, fill: "#1b273d" }));
    svg.append(svgElement("rect", { x: left, y: y + 5, width: Math.max(2, (model.assistant_score / 100) * plotWidth), height: 14, rx: 7, fill: color }));
    chartText(svg, width - right + 8, y + 17, formatNumber(model.assistant_score, 1), "axis-title");
  });
}

function cell(text, className = "") {
  const td = document.createElement("td");
  td.className = className;
  td.textContent = text;
  return td;
}

function renderComparisonTable() {
  const body = $("#comparison-table tbody");
  body.replaceChildren();
  const editorial = filtered(state.overview.editorial.models || []);
  const assistant = filtered(state.overview.assistant.models || []);
  const merged = new Map();
  editorial.forEach((item) => {
    const key = comparisonKey(item);
    merged.set(key, { key, model: item.model, display_name: item.display_name, editorial: item });
  });
  assistant.forEach((item) => {
    const key = comparisonKey(item);
    const row = merged.get(key) || { key, model: item.model, display_name: item.display_name };
    row.assistant = item;
    row.display_name ||= item.display_name;
    // Keep the exact artifact identity as the map key. A local display/model
    // reference can be shared by more than one quant, while identity_key
    // includes the repository revision and GGUF filename.
    merged.set(key, row);
  });
  const rows = [...merged.values()].sort((a, b) => {
    const aScore = a.editorial?.content_score ?? a.assistant?.assistant_score ?? -1;
    const bScore = b.editorial?.content_score ?? b.assistant?.assistant_score ?? -1;
    return bScore - aScore;
  });
  $("#result-filter-note").textContent = `${rows.length} model${rows.length === 1 ? "" : "s"} shown`;
  if (!rows.length) {
    const tr = document.createElement("tr");
    const empty = cell("No model results match this filter.", "empty-cell");
    empty.colSpan = 7;
    tr.append(empty);
    body.append(tr);
    return;
  }
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const modelCell = document.createElement("td");
    const modelBlock = document.createElement("div");
    modelBlock.className = "model-cell";
    const name = document.createElement("strong");
    name.textContent = row.display_name || row.model;
    const id = document.createElement("small");
    const localRecord = row.editorial || row.assistant;
    id.textContent = localRecord?.source_file
      ? `${row.model} · ${localRecord.source_file}${localRecord.source_snapshot ? ` · ${short(localRecord.source_snapshot, 13)}` : ""}`
      : row.model;
    modelBlock.append(name, id);
    modelCell.append(modelBlock);
    tr.append(modelCell);
    tr.append(cell(formatNumber(row.editorial?.content_score, 2), "numeric score"));
    tr.append(cell(formatCost(row.editorial?.cost_usd, row.editorial?.cost_source), "numeric"));
    tr.append(cell(formatNumber(row.assistant?.assistant_score, 2), "numeric score"));
    tr.append(cell(formatAssistantCost(row.assistant), "numeric"));
    tr.append(cell(row.assistant ? `${formatNumber(row.assistant.median_task_seconds, 1)} s` : "—", "numeric"));
    const editorialReady = row.editorial?.content_score != null;
    const assistantReady = row.assistant?.run_status;
    tr.append(cell(`${editorialReady ? "Editorial" : "—"} · ${assistantReady || "—"}`, "evidence"));
    body.append(tr);
  });
}

function statusLabel(status) {
  const span = document.createElement("span");
  span.className = `status status--${status}`;
  span.textContent = status;
  return span;
}

function renderJobs() {
  const body = $("#jobs-table tbody");
  body.replaceChildren();
  const jobs = state.jobs || [];
  const active = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;
  $("#active-job-count").textContent = active;
  if (!jobs.length) {
    const row = document.createElement("tr");
    const empty = cell("No queued or recorded operator jobs yet.", "empty-cell");
    empty.colSpan = 6;
    row.append(empty);
    body.append(row);
    return;
  }
  jobs.forEach((job) => {
    const row = document.createElement("tr");
    const statusCell = document.createElement("td");
    statusCell.append(statusLabel(job.status));
    row.append(statusCell);
    row.append(cell(job.display_name || job.model_ref || "Unknown model"));
    row.append(cell(job.cohort));
    row.append(cell(job.queue));
    row.append(cell(formatDate(job.created_at)));
    const actions = document.createElement("td");
    const view = document.createElement("button");
    view.className = "button button--quiet button--small";
    view.textContent = "Events";
    view.addEventListener("click", () => showEvents(job));
    actions.append(view);
    if (job.status === "queued") {
      const cancel = document.createElement("button");
      cancel.className = "button button--danger button--small";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => cancelJob(job));
      actions.append(" ", cancel);
    }
    row.append(actions);
    body.append(row);
  });
}

async function showEvents(job) {
  const dialog = $("#events-dialog");
  $("#events-title").textContent = `${job.display_name || job.model_ref} · ${job.cohort}`;
  $("#events-log").textContent = "Loading…";
  dialog.showModal();
  try {
    const data = await request(`/api/jobs/${job.id}/events`);
    const lines = data.events.map((event) => `[${formatDate(event.recorded_at)}] ${event.level.toUpperCase()}  ${event.message}`);
    $("#events-log").textContent = lines.join("\n") || "No events were recorded.";
  } catch (error) {
    $("#events-log").textContent = error.message;
  }
}

async function cancelJob(job) {
  if (!window.confirm(`Cancel the queued ${job.cohort} job for ${job.display_name || job.model_ref}?`)) return;
  try {
    await request(`/api/jobs/${job.id}`, { method: "DELETE" });
    await refreshJobs();
  } catch (error) {
    window.alert(error.message);
  }
}

function renderCatalog() {
  const select = $("#local-catalog");
  const previous = select.value;
  select.replaceChildren(new Option("Manual source details", ""));
  state.catalog.forEach((model, index) => {
    const label = `${model.display_name}${model.active ? " (active)" : ""}`;
    const option = new Option(label, String(index));
    option.title = `${model.source_repo}@${model.source_revision}${model.source_snapshot ? `#${model.source_snapshot}` : ""} / ${model.source_file}`;
    select.append(option);
  });
  select.value = [...select.options].some((option) => option.value === previous) ? previous : "";
}

function applyCatalogSelection() {
  const value = $("#local-catalog").value;
  if (value === "") {
    $("#local-source-identity").textContent = "Manual source details are selected. The worker will record the exact GGUF and resolved snapshot after activation.";
    return;
  }
  const selected = state.catalog[Number(value)];
  if (!selected) return;
  $("#source-repo").value = selected.source_repo || "";
  $("#source-file").value = selected.source_file || "";
  $("#source-revision").value = selected.source_revision || "main";
  $("#local-model-ref").value = selected.model_ref || "";
  $("#display-name").value = selected.display_name || "";
  $("#local-source-identity").textContent = `Exact artifact: ${selected.source_repo}@${selected.source_revision}${selected.source_snapshot ? `#${selected.source_snapshot}` : ""} / ${selected.source_file}.`;
}

function selectedProvider() {
  return document.querySelector('input[name="provider"]:checked').value;
}

function selectedCohorts() {
  return [
    $("#cohort-editorial").checked && "editorial",
    $("#cohort-assistant").checked && "assistant",
  ].filter(Boolean);
}

function refreshFormMode() {
  const local = selectedProvider() === "local";
  $("#local-fields").classList.toggle("is-hidden", !local);
  $("#remote-fields").classList.toggle("is-hidden", local);
  const editorial = $("#cohort-editorial").checked;
  $("#judge-cost-wrap").classList.toggle("is-hidden", local || !editorial);
}

function formMessage(text = "", kind = "") {
  const target = $("#queue-form-message");
  target.textContent = text;
  target.className = `form-message${kind ? ` is-${kind}` : ""}`;
}

function numberValue(selector) {
  const raw = $(selector).value.trim();
  return raw ? Number(raw) : null;
}

async function submitRun(event) {
  event.preventDefault();
  const provider = selectedProvider();
  const cohorts = selectedCohorts();
  if (!cohorts.length) {
    formMessage("Choose at least one research cohort.", "error");
    return;
  }
  const payload = {
    provider,
    cohorts,
    display_name: $("#display-name").value.trim(),
    assistant_max_tokens: state.runtime?.assistant_max_tokens || 768,
  };
  if (provider === "local") {
    payload.model_ref = $("#local-model-ref").value.trim();
    payload.source_repo = $("#source-repo").value.trim();
    payload.source_file = $("#source-file").value.trim();
    payload.source_revision = $("#source-revision").value.trim() || "main";
    payload.local_model_max_gib = numberValue("#local-model-max-gib");
    payload.allow_capacity_override = $("#capacity-override").checked;
    payload.operator_acknowledged_idle = $("#idle-ack").checked;
    payload.confirm_paid_run = false;
  } else {
    payload.model_ref = $("#remote-model-ref").value.trim();
    payload.confirm_paid_run = $("#paid-ack").checked;
    payload.target_cost_ceiling_usd = numberValue("#target-cost-cap");
    payload.judge_cost_ceiling_usd = cohorts.includes("editorial") ? numberValue("#judge-cost-cap") : null;
  }
  const button = $("#queue-submit");
  button.disabled = true;
  formMessage("Validating and queuing the selected cohort jobs…");
  try {
    const created = await request("/api/runs", { method: "POST", body: JSON.stringify(payload) });
    const preflight = created.preflight_job_id
      ? created.preflight_reused
        ? " The selected jobs will wait for the already-queued Luna preflight."
        : " Luna preflight was added first."
      : "";
    formMessage(`Queued ${created.job_ids.length} research job(s).${preflight}`, "success");
    await refreshJobs();
  } catch (error) {
    formMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function renderOverview() {
  const editorial = state.overview.editorial || { models: [] };
  const assistant = state.overview.assistant || { models: [] };
  $("#editorial-count").textContent = editorial.model_count ?? editorial.models.length;
  $("#assistant-count").textContent = assistant.model_count ?? assistant.models.length;
  $("#editorial-updated").textContent = editorial.generated_at ? `Updated ${formatDate(editorial.generated_at)}` : "No compiled data";
  $("#assistant-updated").textContent = assistant.generated_at ? `Updated ${formatDate(assistant.generated_at)}` : "No compiled data";
  drawEditorialChart();
  drawReadabilityChart();
  drawAssistantChart();
  renderComparisonTable();
}

async function refreshOverview() {
  const data = await request("/api/overview");
  state.overview = data;
  renderOverview();
}

async function refreshRuntime() {
  const runtime = await request("/api/runtime");
  state.runtime = runtime;
  $("#token-cap").textContent = runtime.assistant_max_tokens;
  $("#local-model-max-gib").value = runtime.local_max_model_gib;
  $("#local-endpoint-note").textContent = `Endpoint stays ${runtime.local_endpoint}. The switcher selects the strongest complete GGUF within ${runtime.local_max_model_gib} GiB unless you explicitly override it.`;
}

async function refreshCatalog() {
  try {
    const data = await request("/api/models/local");
    state.catalog = data.models || [];
    renderCatalog();
  } catch (error) {
    state.catalog = [];
    renderCatalog();
  }
}

async function refreshJobs() {
  const data = await request("/api/jobs?limit=150");
  state.jobs = data.jobs || [];
  renderJobs();
}

async function refreshAll() {
  try {
    await Promise.all([refreshOverview(), refreshRuntime(), refreshJobs(), refreshCatalog()]);
    setConnection(true, "Connected");
  } catch (error) {
    setConnection(false, "Unavailable");
    formMessage(`Operator API: ${error.message}`, "error");
  }
}

document.querySelectorAll(".segmented__button").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll(".segmented__button").forEach((item) => item.classList.toggle("is-active", item === button));
    renderOverview();
  });
});
document.querySelectorAll('input[name="provider"]').forEach((input) => input.addEventListener("change", refreshFormMode));
$("#cohort-editorial").addEventListener("change", refreshFormMode);
$("#local-catalog").addEventListener("change", applyCatalogSelection);
$("#run-form").addEventListener("submit", submitRun);
$("#refresh-button").addEventListener("click", refreshAll);

refreshFormMode();
refreshAll();
window.setInterval(() => Promise.all([refreshOverview(), refreshJobs()]).catch(() => setConnection(false, "Unavailable")), 8000);
