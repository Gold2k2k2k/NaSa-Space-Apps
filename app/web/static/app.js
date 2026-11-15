/** Zero-build browser orchestration. All analysis changes retain a stored source. */
import { $, MONTHS, h, replace, verdictLabel } from "./js/ui.js";
import { renderCalendar, renderSeason } from "./js/charts.js";
import { renderMap } from "./js/map.js";
import { renderContext, renderBridge, renderAudit, renderManifesto, renderBench } from "./js/views.js";

const state = {
  setup: null, run: null, manifesto: null, bench: null, ramp: "viridis",
  granularity: "monthly", view: "calendar", routed: false, geometryDirty: false,
  draw: { active: false, points: [] }, revision: 0, controller: null, busy: true,
  manifestRevision: 0, lastAction: null, calendarScroll: null,
};
const views = ["calendar", "bridge", "audit", "manifesto", "bench"];
const scrollHints = new WeakMap();
let scrollHintCounter = 0;
const downloadPaths = {
  "dl-hotspots-csv": (id) => "/api/export/" + id + "/hotspots.csv",
  "dl-calendar-csv": (id) => "/api/export/" + id + "/calendar.csv",
  "dl-geojson": (id) => "/api/export/" + id + "/hotspots.geojson",
  "dl-ics": (id) => "/api/export/" + id + "/calendar.ics",
  "dl-receipt": (id) => "/runs/" + id + "/receipt",
  "dl-package": (id) => "/runs/" + id + "/package",
  "dl-brief-receipt": (id) => "/runs/" + id + "/receipt",
  "dl-brief-package": (id) => "/runs/" + id + "/package",
};

async function apiJSON(url, options = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  const upstream = options.signal;
  if (upstream?.aborted) controller.abort();
  else upstream?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, options.timeout || 60000);
  const { timeout, ...request } = options;
  try {
    const response = await fetch(url, { ...request, signal: controller.signal });
    let body;
    try { body = await response.json(); }
    catch { throw new Error("The server returned an unreadable response (HTTP " + response.status + ")."); }
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((entry) => entry.msg || String(entry)).join("; ") : body.detail;
      throw new Error(typeof detail === "string" ? detail : "Request failed (HTTP " + response.status + ").");
    }
    return body;
  } catch (error) {
    if (timedOut) throw new Error("The request timed out. Check the local server and retry.");
    throw error;
  } finally {
    clearTimeout(timer);
    upstream?.removeEventListener("abort", abort);
  }
}

function showError(message, retry = null) {
  $("global-error").hidden = !message;
  $("error-message").textContent = message || "";
  $("btn-retry").hidden = !retry;
  $("btn-retry").onclick = retry;
}

function updateBusy(busy) {
  state.busy = busy;
  document.body.classList.toggle("is-loading", busy);
  $("analysis-context").setAttribute("aria-busy", String(busy));
  $("btn-analyze").disabled = busy || !state.setup;
  $("btn-analyze").textContent = busy ? "Analyzing…" : state.geometryDirty ? "Generate this region" : "Analyze selected region";
  $("btn-upload-trigger").disabled = !state.setup;
  for (const id of ["btn-toggle-mode", "btn-toggle-flare", "btn-clear-scenario", "btn-load-receipt", "btn-draw-mode", "btn-geojson", "btn-point-mode"]) {
    $(id).disabled = busy || (!state.run && id !== "btn-geojson");
  }
  $("persona-select").disabled = busy;
  $("query-form").querySelectorAll("input,select").forEach((input) => {
    input.disabled = busy || (["in-name", "in-lat", "in-lon", "in-radius"].includes(input.id) && !state.geometryDirty);
  });
  for (const button of document.querySelectorAll(".requires-run")) button.disabled = busy || button.dataset.available === "false";
  for (const id of Object.keys(downloadPaths)) {
    $(id).setAttribute("aria-disabled", String(busy || !state.run));
    if (busy || !state.run) $(id).setAttribute("tabindex", "-1"); else $(id).removeAttribute("tabindex");
  }
}

function formOptions() {
  return {
    year_start: Number($("in-y0").value), year_end: Number($("in-y1").value),
    focus_year: Number($("in-fy").value), focus_month: Number($("in-fm").value),
    confidence_min: $("in-conf").value, persona: $("persona-select").value || "responder",
    mode: state.run?.options.mode || "harmonized", flare_guard: state.run?.options.flare_guard ?? true,
  };
}

function validatedFormOptions() {
  if (!$('query-form').reportValidity()) return null;
  const options = formOptions();
  if (options.year_start > options.year_end) {
    showError('The start year must be no later than the last year.');
    $('in-y0').focus();
    return null;
  }
  if (options.focus_year < options.year_start || options.focus_year > options.year_end) {
    showError('The focus year must be within the selected first and last years.');
    $('in-fy').focus();
    return null;
  }
  return options;
}

function syncForm(run) {
  const aoi = run.aoi, options = run.options;
  for (const [id, value] of Object.entries({
    "in-lat": aoi.lat, "in-lon": aoi.lon, "in-radius": aoi.radius_km,
    "in-y0": options.year_start, "in-y1": options.year_end,
    "in-fy": options.focus_year, "in-fm": options.focus_month, "in-conf": options.confidence_min,
    "persona-select": options.persona,
  })) $(id).value = value;
  $("in-name").value = "";
  $("in-name").disabled = true;
  $("selection-help").textContent = ["uploaded_csv", "nasa_firms_archive"].includes(aoi.source_kind) ?
    "Period, confidence and audience changes retain this upload and its full geometry. Coordinates or new geometry create generated demo data." :
    "Form updates retain the stored selection. Edited coordinates create a new approximate rectangular demo region.";
  for (const button of document.querySelectorAll(".preset-pill")) {
    const active = button.dataset.aoi === aoi.aoi_id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  state.geometryDirty = false;
}

function syncScrollHints() {
  for (const container of document.querySelectorAll(".table-scroll,.chart-scroll")) {
    const horizontal = container.clientWidth > 0 && container.scrollWidth > container.clientWidth + 1;
    const vertical = container.clientHeight > 0 && container.scrollHeight > container.clientHeight + 1;
    const scrollable = horizontal || vertical;
    let hint = scrollHints.get(container);
    if (!hint) {
      hint = h("p", { class: "scroll-hint", id: "scroll-hint-" + (++scrollHintCounter) });
      container.before(hint); scrollHints.set(container, hint);
    }
    hint.hidden = !scrollable;
    hint.textContent = horizontal ? (container.classList.contains("chart-scroll") ? "Scroll horizontally for the full timeline." : "Scroll horizontally for the remaining columns.") : "Scroll to explore the complete schedule.";
    if (scrollable) {
      container.tabIndex = 0;
      container.setAttribute("role", "region");
      if (!container.hasAttribute("aria-label")) container.setAttribute("aria-label", "Scrollable data region");
      container.setAttribute("aria-describedby", hint.id);
    }
  }
}

function renderCurrent() {
  if (!state.run) return;
  if (state.view === "calendar") {
    renderCalendar(state.run, state, (year, month) => runWhatIf("focus_period", [year, month]));
    renderSeason(state.run);
    renderMap(state.run, state.draw, (point) => {
      state.draw.points.push(point);
      renderMap(state.run, state.draw, addDrawPoint);
    });
  } else if (state.view === "bridge") renderBridge(state.run);
  syncScrollHints();
}

function addDrawPoint(point) {
  state.draw.points.push(point);
  renderMap(state.run, state.draw, addDrawPoint);
}

function commitRun(run) {
  if (!run || !run.run_id || !run.calendar || !run.provenance || !run.passes) throw new Error("The analysis response is missing required snapshot evidence.");
  state.run = run;
  state.draw = { active: false, points: [] };
  syncForm(run);
  renderContext(run);
  renderAudit(run, runWhatIf);
  $("receipt-json-box").hidden = true;
  $("receipt-json-box").textContent = "";
  $("btn-load-receipt").textContent = "Inspect receipt JSON";
  for (const [id, path] of Object.entries(downloadPaths)) $(id).href = path(encodeURIComponent(run.run_id));
  renderCurrent();
  $("selection-panel").open = false;
  $("global-status").textContent = "Ready · " + run.calendar.focus_comparison.month_name + " " + run.calendar.focus_year + " · " + verdictLabel(run.verdict);
}

async function requestRun(url, request, label, repeat) {
  const revision = ++state.revision;
  state.controller?.abort();
  state.controller = new AbortController();
  state.lastAction = repeat;
  showError("");
  updateBusy(true);
  $("global-status").textContent = label;
  try {
    const result = await apiJSON(url, { ...request, signal: state.controller.signal });
    if (revision !== state.revision) return;
    commitRun(result);
  } catch (error) {
    if (revision !== state.revision || error.name === "AbortError") return;
    showError(error.message, repeat);
    $("global-status").textContent = state.run ? "Request failed · previous snapshot retained: " + state.run.aoi.name : "Analysis unavailable";
  } finally {
    if (revision === state.revision) updateBusy(false);
  }
}

function analyze(payload) {
  return requestRun("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    "Analyzing generated demonstration…", () => analyze(payload));
}

function runWhatIf(field, value) {
  if (!state.run) return;
  const identity = state.run.run_id;
  return requestRun("/runs/" + encodeURIComponent(identity) + "/what_if",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ field, value }) },
    "Building a new snapshot from retained inputs…", () => runWhatIf(field, value));
}

function choosePreset(aoi) {
  state.calendarScroll = null;
  return analyze({ aoi_id: aoi.aoi_id, focus_year: aoi.default_focus_year, focus_month: aoi.default_focus_month,
    year_start: 2000, year_end: 2026, persona: $("persona-select").value || "responder", confidence_min: $("in-conf").value, mode: "harmonized" });
}

function chooseCase(caseId = "central-highlands") {
  state.calendarScroll = null;
  return requestRun("/api/case-studies/" + encodeURIComponent(caseId) + "/analyze",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    "Reading pinned NASA FIRMS records…", () => chooseCase(caseId));
}

function markCoordinates() {
  if (!state.geometryDirty) $("in-name").value = "";
  state.geometryDirty = true;
  for (const id of ["in-name", "in-lat", "in-lon", "in-radius"]) $(id).disabled = false;
  $("selection-help").textContent = "This coordinate selection generates synthetic demo data in an approximate rectangular buffer.";
  $("btn-analyze").textContent = "Generate this region";
}

async function upload(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { showError("CSV files must be 10 MiB or smaller."); return; }
  const options = formOptions(), parameters = new URLSearchParams({
    mode: options.mode, flare_guard: String(options.flare_guard),
    persona: options.persona, confidence_min: options.confidence_min,
  });
  const body = new FormData(); body.append("file", file);
  return requestRun("/api/upload-csv?" + parameters, { method: "POST", body },
    "Reading FIRMS CSV and checking its rows…", () => upload(file));
}

function route(event) {
  if (location.hash === "#main" && state.routed) return;
  const calendarJump = location.hash === "#calendar-matrix";
  const name = calendarJump ? "calendar" : location.hash.replace(/^#\/?/, "").split("/")[0];
  state.view = views.includes(name) ? name : "calendar";
  state.routed = true;
  for (const view of views) {
    $("view-" + view).hidden = view !== state.view;
    if (view === state.view) $("tab-" + view).setAttribute("aria-current", "page"); else $("tab-" + view).removeAttribute("aria-current");
  }
  $("analysis-context").hidden = ["manifesto", "bench"].includes(state.view);
  document.title = "FireTrace · " + ($("tab-" + state.view).getAttribute("aria-label") || $("tab-" + state.view).textContent);
  renderCurrent();
  if (state.view === "manifesto" && !state.manifesto) loadManifesto();
  if (event?.type === "hashchange") {
    const heading = $("view-" + state.view).querySelector("h1,h2");
    heading?.setAttribute("tabindex", "-1"); heading?.focus({ preventScroll: true });
    if (calendarJump) $("calendar-matrix").scrollIntoView({ block: "start", behavior: "auto" });
    else window.scrollTo({ top: 0, behavior: "auto" });
  }
}

async function loadManifesto() {
  const revision = ++state.manifestRevision;
  $("manifesto-status").textContent = "Loading schema mappings…";
  try {
    const data = await apiJSON("/api/schema-mapping");
    if (revision !== state.manifestRevision) return;
    state.manifesto = data; renderManifesto(data); syncScrollHints();
  } catch (error) {
    if (revision !== state.manifestRevision) return;
    $("manifesto-status").textContent = "Schema mappings are unavailable. Reload to retry.";
    showError(error.message, loadManifesto);
  }
}

async function inspectReceipt() {
  if (!state.run) return;
  const box = $("receipt-json-box");
  if (!box.hidden) { box.hidden = true; $("btn-load-receipt").textContent = "Inspect receipt JSON"; return; }
  const identity = state.run.run_id;
  $("btn-load-receipt").disabled = true;
  try {
    const receipt = await apiJSON("/runs/" + encodeURIComponent(identity) + "/receipt");
    if (identity !== state.run?.run_id) return;
    box.textContent = JSON.stringify(receipt, null, 2);
    box.hidden = false;
    $("btn-load-receipt").textContent = "Hide receipt JSON";
  } catch (error) { showError(error.message, inspectReceipt); }
  finally { $("btn-load-receipt").disabled = state.busy; }
}

async function runBench() {
  const button = $("btn-run-bench");
  button.disabled = true; button.textContent = "Running 12 cases…";
  $("bench-summary").textContent = "Running the generated scenarios through the same deterministic engine…";
  showError("");
  try {
    const result = await apiJSON("/api/bench", { method: "POST", timeout: 180000 });
    state.bench = result; renderBench(result); syncScrollHints();
  } catch (error) {
    $("bench-summary").textContent = "The benchmark could not finish. Retry when the local server is available.";
    showError(error.message, runBench);
  } finally { button.disabled = false; button.textContent = "Run all 12 cases"; }
}

function wireEvents() {
  $("btn-real-case").addEventListener("click", () => chooseCase());
  $("btn-guide-source").addEventListener("click", () => {
    $("selection-panel").open = true;
    $("selection-panel").querySelector("summary").focus();
  });
  window.addEventListener("hashchange", route);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.draw.active) {
      state.draw.active = false;
      state.draw.points = [];
      renderMap(state.run, state.draw, addDrawPoint);
      $('btn-draw-mode').focus();
    }
  });
  document.addEventListener("toggle", syncScrollHints, true);
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(renderCurrent, 120); });
  $("ramp-select").addEventListener("change", (event) => { state.ramp = event.target.value; if (state.run) renderCalendar(state.run, state, (year, month) => runWhatIf("focus_period", [year, month])); });
  $("persona-select").addEventListener("change", (event) => runWhatIf("persona", event.target.value));
  $("btn-toggle-mode").addEventListener("click", () => runWhatIf("mode", state.run.options.mode === "harmonized" ? "raw" : "harmonized"));
  $("btn-toggle-flare").addEventListener("click", () => runWhatIf("flare_guard", !state.run.options.flare_guard));
  $("btn-clear-scenario").addEventListener("click", () => runWhatIf("focus_to_median", false));
  $("btn-toggle-granularity").addEventListener("click", () => {
    state.granularity = state.granularity === "monthly" ? "dekadal" : "monthly";
    $("btn-toggle-granularity").textContent = state.granularity === "monthly" ? "Show 36-dekad profile" : "Show monthly matrix";
    $("btn-toggle-granularity").setAttribute("aria-pressed", String(state.granularity === "dekadal"));
    if (state.run) renderCurrent();
  });
  for (const id of ["in-lat", "in-lon", "in-radius"]) $(id).addEventListener("input", markCoordinates);
  $("btn-point-mode").addEventListener("click", markCoordinates);
  $("query-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const options = validatedFormOptions();
    if (!options) return;
    if (state.run && !state.geometryDirty) runWhatIf("options", options);
    else analyze({ ...options, lat: Number($("in-lat").value), lon: Number($("in-lon").value), radius_km: Number($("in-radius").value), ...($("in-name").value.trim() ? { name: $("in-name").value.trim() } : {}) });
  });
  $("btn-geojson").addEventListener("click", () => {
    const options = validatedFormOptions();
    if (!options) return;
    try { analyze({ ...options, geojson: JSON.parse($("geojson-input").value) }); }
    catch { showError("GeoJSON must be valid JSON. Supported: Point, Polygon, MultiPolygon or FeatureCollection."); }
  });
  $("btn-upload-trigger").addEventListener("click", () => $("csv-file-input").click());
  $("csv-file-input").addEventListener("change", (event) => { upload(event.target.files?.[0]); event.target.value = ""; });
  const dropZone = $('csv-drop-zone');
  dropZone.addEventListener('dragover', (event) => {
    event.preventDefault();
    if (state.setup) { event.dataTransfer.dropEffect = 'copy'; dropZone.classList.add('is-over'); }
  });
  dropZone.addEventListener('dragleave', (event) => {
    if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove('is-over');
  });
  dropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    dropZone.classList.remove('is-over');
    if (!state.setup) return;
    const files = event.dataTransfer.files;
    if (files.length !== 1 || !files[0].name.toLowerCase().endsWith('.csv')) {
      showError('Drop one .csv file, or use the Upload FIRMS CSV button.');
      return;
    }
    upload(files[0]);
  });
  $("btn-draw-mode").addEventListener("click", () => {
    state.draw.active = !state.draw.active; state.draw.points = [];
    renderMap(state.run, state.draw, addDrawPoint);
  });
  $("btn-draw-undo").addEventListener("click", () => { state.draw.points.pop(); renderMap(state.run, state.draw, addDrawPoint); });
  $("btn-draw-apply").addEventListener("click", () => {
    if (state.draw.points.length < 3) return;
    const options = validatedFormOptions();
    if (!options) return;
    const ring = [...state.draw.points, state.draw.points[0]];
    analyze({ ...options, geojson: { type: "Polygon", coordinates: [ring] } });
  });
  $("btn-load-receipt").addEventListener("click", inspectReceipt);
  $("btn-load-manifesto").addEventListener("click", loadManifesto);
  $("btn-run-bench").addEventListener("click", runBench);
}

async function init() {
  wireEvents();
  MONTHS.forEach((month, index) => $("in-fm").append(h("option", { value: index + 1, text: month })));
  updateBusy(true);
  route();
  try {
    const setup = await apiJSON("/ui/setup");
    state.setup = setup;
    const audiences = { responder: "Responder", scientist: "Scientist", land_manager: "Land manager", firefighter: "Firefighter" };
    const ramps = { viridis: "Viridis", cividis: "Cividis", ylorrd: "Ember", diverging: "Diverging Z" };
    replace($("persona-select"), setup.personas.map((persona) => h("option", { value: persona.id, text: audiences[persona.id] || persona.label, title: persona.label })));
    replace($("ramp-select"), setup.color_ramps.map((ramp) => h("option", { value: ramp.id, text: ramps[ramp.id] || ramp.name, title: ramp.name })));
    $("ramp-select").value = state.ramp;
    replace($("preset-row"), setup.aois.map((aoi) => h("button", { type: "button", class: "preset-pill",
      "data-aoi": aoi.aoi_id, "aria-label": "Generated preset: " + aoi.name, "aria-pressed": "false",
      title: aoi.aoi_id + " · " + aoi.name, text: aoi.name, onclick: () => choosePreset(aoi) })));
    renderBench(state.bench, setup.bench_cases);
    const first = setup.aois.find((aoi) => aoi.aoi_id === setup.default_aoi) || setup.aois[0];
    if (first && state.revision === 0) await choosePreset(first); else updateBusy(false);
  } catch (error) {
    showError("Setup unavailable: " + error.message, () => location.reload());
    $("global-status").textContent = "Setup unavailable";
    updateBusy(false);
  }
  document.fonts?.ready.then(renderCurrent);
}

init();

