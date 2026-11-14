/* FireTrace Interactive Field Instrument — Zero-Build Vanilla JS */
(() => {
  "use strict";

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const SVG_NS = "http://www.w3.org/2000/svg";
  const $ = (id) => document.getElementById(id);

  const RAMPS = {
    viridis: [
      [68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37],
    ],
    cividis: [
      [0, 32, 76], [65, 77, 107], [124, 123, 120], [189, 175, 111], [253, 234, 69],
    ],
    ylorrd: [
      [25, 29, 26], [128, 38, 22], [217, 98, 43], [245, 166, 35], [254, 240, 148],
    ],
    diverging: [
      [43, 131, 186], [116, 173, 209], [42, 56, 48], [244, 145, 67], [215, 48, 39],
    ],
  };

  const state = {
    setup: null,
    run: null,
    manifesto: null,
    passes: null,
    ramp: "viridis",
    persona: "responder",
    granularity: "monthly", // "monthly" | "dekadal"
    draw: { active: false, points: [] },
  };

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    return fill(el, attrs, children);
  }
  function s(tag, attrs, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    return fill(el, attrs, children);
  }
  function fill(el, attrs, children) {
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.setAttribute("class", v);
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  async function apiJSON(url, opts) {
    const res = await fetch(url, opts);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return body;
  }

  function interpColor(rampKey, t) {
    const stops = RAMPS[rampKey] || RAMPS.viridis;
    const clamped = Math.max(0, Math.min(1, t));
    const pos = clamped * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(pos));
    const frac = pos - i;
    const c0 = stops[i];
    const c1 = stops[i + 1];
    const r = Math.round(c0[0] + (c1[0] - c0[0]) * frac);
    const g = Math.round(c0[1] + (c1[1] - c0[1]) * frac);
    const b = Math.round(c0[2] + (c1[2] - c0[2]) * frac);
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    return { bg: `rgb(${r},${g},${b})`, fg: lum > 142 ? "#0A120D" : "#E7EEE9" };
  }

  function cellColor(cell, maxVal) {
    if (!cell.is_observed) return { bg: "#08130D", fg: "#8A978F" };
    if (state.ramp === "diverging") {
      const t = (Math.max(-2.5, Math.min(3.5, cell.z_robust)) + 2.5) / 6.0;
      return interpColor("diverging", t);
    }
    const t = maxVal > 0 ? Math.sqrt(Math.max(0, cell.value) / maxVal) : 0;
    return interpColor(state.ramp, t);
  }

  function showError(msg) {
    const box = $("global-error");
    box.textContent = msg || "";
    box.hidden = !msg;
  }

  function setLoading(busy) {
    $("btn-analyze").disabled = busy;
    $("btn-analyze").textContent = busy ? "Analyzing..." : "Analyze Region";
  }

  // ---- Routing --------------------------------------------------------------------------------
  const ROUTES = { "": "calendar", bridge: "bridge", audit: "audit", manifesto: "manifesto", bench: "bench" };
  function route() {
    const hash = location.hash.replace(/^#\/?/, "").split("/")[0];
    const view = ROUTES[hash] || "calendar";
    for (const name of Object.values(ROUTES)) {
      $(`view-${name}`).hidden = name !== view;
      const tab = $(`tab-${name}`);
      if (tab) {
        if (name === view) tab.setAttribute("aria-current", "page");
        else tab.removeAttribute("aria-current");
      }
    }
    $("control-deck").hidden = view === "manifesto" || view === "bench";
    if (view === "manifesto" && !state.manifesto) loadManifesto();
    if (view === "bridge" && state.run) renderBridge();
    if (view === "audit" && state.run) renderAudit();
  }

  // ---- Initialization & Setup -----------------------------------------------------------------
  async function init() {
    MONTHS.forEach((m, i) => $("in-fm").append(h("option", { value: i + 1, text: `${i + 1} · ${m}` })));
    try {
      state.setup = await apiJSON("/ui/setup");
    } catch (err) {
      showError(`Failed to initialize setup: ${err.message}`);
      return;
    }

    state.setup.color_ramps.forEach((r) => $("ramp-select").append(h("option", { value: r.id, text: r.name })));
    state.setup.personas.forEach((p) => $("persona-select").append(h("option", { value: p.id, text: p.label })));
    $("ramp-select").value = state.ramp;
    $("persona-select").value = state.persona;

    const presetRow = $("preset-row");
    state.setup.aois.forEach((aoi) => {
      presetRow.append(
        h("button", {
          type: "button",
          class: "preset-pill",
          "data-aoi": aoi.aoi_id,
          onclick: () => selectPresetAOI(aoi),
        },
        h("strong", { text: aoi.aoi_id }),
        h("span", { text: aoi.name }),
        ),
      );
    });

    wireEvents();
    route();
    const first = state.setup.aois[0];
    if (first) selectPresetAOI(first);
  }

  function wireEvents() {
    window.addEventListener("hashchange", route);

    $("ramp-select").addEventListener("change", (e) => {
      state.ramp = e.target.value;
      if (state.run) renderCalendar();
    });

    $("persona-select").addEventListener("change", async (e) => {
      state.persona = e.target.value;
      if (state.run) {
        await runWhatIf("persona", state.persona);
      }
    });

    $("query-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      await runAnalyze({
        lat: parseFloat($("in-lat").value),
        lon: parseFloat($("in-lon").value),
        radius_km: parseFloat($("in-radius").value),
        year_start: parseInt($("in-y0").value, 10),
        year_end: parseInt($("in-y1").value, 10),
        focus_year: parseInt($("in-fy").value, 10),
        focus_month: parseInt($("in-fm").value, 10),
        confidence_min: $("in-conf").value,
        persona: state.persona,
      });
    });

    $("btn-toggle-granularity").addEventListener("click", () => {
      state.granularity = state.granularity === "monthly" ? "dekadal" : "monthly";
      $("btn-toggle-granularity").textContent = state.granularity === "monthly" ? "View: Monthly Matrix" : "View: 36-Dekad Profile";
      if (state.run) renderCalendar();
    });

    $("btn-toggle-mode").addEventListener("click", async () => {
      if (!state.run) return;
      const next = state.run.options.mode === "harmonized" ? "raw" : "harmonized";
      await runWhatIf("mode", next);
    });

    $("btn-toggle-flare").addEventListener("click", async () => {
      if (!state.run) return;
      await runWhatIf("flare_guard", !state.run.options.flare_guard);
    });

    $("btn-upload-trigger").addEventListener("click", () => $("csv-file-input").click());
    $("csv-file-input").addEventListener("change", handleCsvUpload);

    $("btn-draw-mode").addEventListener("click", toggleDrawMode);
    $("btn-draw-undo").addEventListener("click", () => {
      state.draw.points.pop();
      renderMap();
    });
    $("btn-draw-apply").addEventListener("click", submitDrawnPolygon);

    $("btn-load-receipt").addEventListener("click", loadReceiptJson);
    $("btn-run-bench").addEventListener("click", runBenchSuite);
  }

  async function selectPresetAOI(aoi) {
    $("in-lat").value = aoi.lat;
    $("in-lon").value = aoi.lon;
    $("in-radius").value = aoi.radius_km;
    $("in-y0").value = 2000;
    $("in-y1").value = 2026;
    $("in-fy").value = aoi.default_focus_year;
    $("in-fm").value = aoi.default_focus_month;
    for (const btn of document.querySelectorAll(".preset-pill")) {
      btn.classList.toggle("active", btn.getAttribute("data-aoi") === aoi.aoi_id);
    }
    await runAnalyze({
      aoi_id: aoi.aoi_id,
      year_start: 2000,
      year_end: 2026,
      focus_year: aoi.default_focus_year,
      focus_month: aoi.default_focus_month,
      confidence_min: $("in-conf").value,
      persona: state.persona,
    });
  }

  async function runAnalyze(payload) {
    showError("");
    setLoading(true);
    state.draw.active = false;
    state.draw.points = [];
    syncDrawControls();
    try {
      const data = await apiJSON("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.run = data;
      await loadPasses(data.aoi.lat, data.aoi.lon);
      renderAll();
    } catch (err) {
      showError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function runWhatIf(field, value) {
    if (!state.run) return;
    showError("");
    try {
      const updated = await apiJSON(`/runs/${encodeURIComponent(state.run.run_id)}/what_if`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value }),
      });
      state.run = updated;
      renderAll();
    } catch (err) {
      showError(err.message);
    }
  }

  async function handleCsvUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    showError("");
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/upload-csv?persona=${encodeURIComponent(state.persona)}`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "CSV upload failed");
      state.run = data;
      $("in-lat").value = data.aoi.lat;
      $("in-lon").value = data.aoi.lon;
      $("in-fy").value = data.calendar.focus_year;
      $("in-fm").value = data.calendar.focus_month;
      for (const btn of document.querySelectorAll(".preset-pill")) btn.classList.remove("active");
      await loadPasses(data.aoi.lat, data.aoi.lon);
      renderAll();
    } catch (err) {
      showError(err.message);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  async function loadPasses(lat, lon) {
    try {
      state.passes = await apiJSON(`/api/passes?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&days=5`);
    } catch {
      state.passes = null;
    }
  }

  // ---- Rendering ------------------------------------------------------------------------------
  function renderAll() {
    const r = state.run;
    if (!r) return;
    const aoi = r.aoi;
    const cal = r.calendar;
    const fc = cal.focus_comparison;
    const audit = r.sensor_calibration_audit;

    $("aoi-heading").textContent = `${aoi.name} (${aoi.country})`;
    $("aoi-description").textContent = `${aoi.biome} · Area ${aoi.area_km2.toLocaleString()} km² · Peak Season: ${aoi.peak_season} · ${aoi.description}`;
    $("run-seal-pill").textContent = `seal ${r.verdict_sha256.slice(0, 12)}…`;
    const vtag = $("hero-verdict-tag");
    vtag.className = `tag tag-${r.verdict}`;
    vtag.textContent = r.verdict.replace(/_/g, " ");

    // Briefing & Findings
    $("briefing-role-label").textContent = r.briefing.persona_label;
    $("briefing-rules-ver").textContent = `rules v${r.rules_version} · Rule ${r.deciding_rule}`;
    $("briefing-headline").textContent = r.briefing.headline;
    const actionsEl = $("briefing-actions");
    actionsEl.replaceChildren(...r.briefing.actions.map((a) => h("li", { text: a })));

    const findingsEl = $("findings-list");
    findingsEl.replaceChildren(...r.findings.map((f) => h("div", { class: "finding-item" },
      h("div", { class: "finding-meta" },
        h("span", { class: `tag tag-${f.verdict}`, text: f.verdict }),
        h("span", { class: "mono sub", text: `Rule ${f.rule} · ${f.code}` }),
      ),
      h("span", { text: f.detail }),
    )));

    // 4 KPI Cards
    const unit = cal.mode === "raw" ? "Raw Det." : "HHE";
    $("kpi-focus-val").textContent = `${fc.value.toFixed(1)} vs ${fc.hist_median.toFixed(1)} ${unit}`;
    $("kpi-focus-sub").textContent = `${fc.month_name} ${fc.year}: ${fc.anomaly_pct >= 0 ? "+" : ""}${fc.anomaly_pct.toFixed(1)}% vs 2001–2020 median`;

    $("kpi-z-val").textContent = `Z = ${fc.z_robust >= 0 ? "+" : ""}${fc.z_robust.toFixed(2)}`;
    $("kpi-z-sub").textContent = `Rank #${fc.rank_in_history} of ${fc.history_years_count} yrs · Peak: ${cal.summary_records.peak_month_names.join(", ")}`;

    $("kpi-bias-val").textContent = `${audit.bias_reduction_pct.toFixed(1)}%`;
    $("kpi-bias-sub").textContent = `2012 jump ${audit.raw_step_jump_2012_pct >= 0 ? "+" : ""}${audit.raw_step_jump_2012_pct.toFixed(0)}% → ${audit.harmonized_step_diff_2012_pct >= 0 ? "+" : ""}${audit.harmonized_step_diff_2012_pct.toFixed(1)}% (κ=${audit.calibrated_kappa.toFixed(3)})`;

    $("kpi-frp-val").textContent = `${Math.round(fc.frp_total_mw).toLocaleString()} MW`;
    $("kpi-frp-sub").textContent = `Nighttime persistence: ${(fc.night_share * 100).toFixed(0)}% · ${audit.overpass_duplicates_removed.toLocaleString()} co-passes deduped`;

    // Sync Switches
    const isHarm = cal.mode === "harmonized";
    $("btn-toggle-mode").setAttribute("aria-checked", String(isHarm));
    $("mode-switch-label").textContent = isHarm ? "Mode: Harmonized (HHE)" : "Mode: Raw Unharmonized";

    const fg = Boolean(r.options.flare_guard);
    $("btn-toggle-flare").setAttribute("aria-checked", String(fg));
    $("flare-switch-label").textContent = fg ? "Flare Filter: ON" : "Flare Filter: OFF";

    // Download URLs
    const rid = encodeURIComponent(r.run_id);
    $("dl-hotspots-csv").href = `/api/export/${rid}/hotspots.csv`;
    $("dl-calendar-csv").href = `/api/export/${rid}/calendar.csv`;
    $("dl-geojson").href = `/api/export/${rid}/hotspots.geojson`;
    $("dl-ics").href = `/api/export/${rid}/calendar.ics`;
    $("dl-receipt").href = `/runs/${rid}/receipt`;
    $("dl-package").href = `/runs/${rid}/package`;

    renderCalendar();
    renderMap();
    renderSeasonChart();
    renderAttributionAndPasses();
    renderBridge();
    renderAudit();
  }

  function renderCalendar() {
    const r = state.run;
    const cal = r.calendar;
    const container = $("calendar-container");
    $("cal-title").textContent = cal.mode === "raw"
      ? "Unharmonized Raw Detections (MODIS + VIIRS) by Year & Month"
      : "Harmonized Hotspot Equivalents (HHE) by Year & Month";

    // Color ramp legend
    const stops = RAMPS[state.ramp] || RAMPS.viridis;
    const grad = `linear-gradient(90deg, ${stops.map((c) => `rgb(${c[0]},${c[1]},${c[2]})`).join(", ")})`;
    const leg = $("ramp-legend");
    leg.replaceChildren(
      h("span", { text: state.ramp === "diverging" ? "Below Median (-2.5σ)" : "0" }),
      h("div", { class: "ramp-bar", style: `background: ${grad}` }),
      h("span", { text: state.ramp === "diverging" ? "Extreme Surge (+3.5σ)" : `${cal.max_cell_value.toFixed(0)} ${cal.mode === "raw" ? "raw" : "HHE"}` }),
    );

    if (state.granularity === "dekadal") {
      renderDekadalChart(container, cal);
      return;
    }

    const byYm = new Map();
    for (const c of cal.cells) byYm.set(`${c.year}-${c.month}`, c);

    const years = [];
    for (let y = cal.year_end; y >= cal.year_start; y--) years.push(y);

    const table = h("table", { class: "cal-matrix" },
      h("thead", {},
        h("tr", {},
          h("th", { class: "yr-col", text: "Year" }),
          ...MONTHS.map((m) => h("th", { text: m })),
        ),
      ),
      h("tbody", {},
        ...years.map((yr) => h("tr", {},
          h("th", { class: "yr-col", text: String(yr) }),
          ...MONTHS.map((_, idx) => {
            const mo = idx + 1;
            const c = byYm.get(`${yr}-${mo}`);
            if (!c || !c.is_observed) {
              return h("td", { class: "cal-cell is-pending", title: `${MONTHS[idx]} ${yr}: pending` }, "—");
            }
            const { bg, fg } = cellColor(c, cal.max_cell_value);
            const isFocus = yr === cal.focus_year && mo === cal.focus_month;
            return h("td", {
              class: "cal-cell" + (isFocus ? " is-focus" : ""),
              style: `background:${bg};color:${fg}`,
              title: `${c.month_name} ${c.year}: ${c.value.toFixed(1)} (Med ${c.hist_median_hhe.toFixed(1)}, Z=${c.z_robust >= 0 ? "+" : ""}${c.z_robust.toFixed(2)})`,
              onmouseenter: () => inspectCell(c),
              onclick: () => {
                $("in-fy").value = c.year;
                $("in-fm").value = c.month;
                runWhatIf("focus_period", [c.year, c.month]);
              },
              text: c.value >= 100 ? Math.round(c.value) : c.value.toFixed(0),
            });
          }),
        )),
      ),
    );
    container.replaceChildren(table);
  }

  function renderDekadalChart(container, cal) {
    const W = 720, H = 260, pad = { l: 44, r: 16, t: 20, b: 36 };
    const iw = W - pad.l - pad.r;
    const ih = H - pad.t - pad.b;
    const prof = cal.dekadal_profile;
    const maxV = Math.max(10, ...prof.map((d) => Math.max(d.focus_value, d.hist_p90, d.hist_median)));
    const bw = iw / prof.length;
    const yOf = (v) => pad.t + ih - (v / maxV) * ih;

    const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
    prof.forEach((d, i) => {
      const x = pad.l + i * bw + 1;
      const y = yOf(d.focus_value);
      const rect = s("rect", {
        x: x.toFixed(1),
        y: y.toFixed(1),
        width: Math.max(4, bw - 3).toFixed(1),
        height: Math.max(1, pad.t + ih - y).toFixed(1),
        rx: 2,
        fill: d.focus_value > d.hist_p90 ? "#D9622B" : "#9BE3B4",
      });
      rect.addEventListener("mouseenter", () => {
        $("cell-inspector").textContent = `${d.label} (${cal.focus_year}): ${d.focus_value.toFixed(1)} vs Historical Median ${d.hist_median.toFixed(1)} (P90 ${d.hist_p90.toFixed(1)})`;
      });
      svg.append(rect);
      if (i % 3 === 0) {
        svg.append(s("text", { x: x + 2, y: H - 10, fill: "#8A978F", "font-size": 10, text: MONTHS[Math.floor(i / 3)] }));
      }
    });
    const medPts = prof.map((d, i) => `${(pad.l + (i + 0.5) * bw).toFixed(1)},${yOf(d.hist_median).toFixed(1)}`).join(" ");
    svg.append(s("polyline", { points: medPts, fill: "none", stroke: "#E7EEE9", "stroke-width": 2 }));
    container.replaceChildren(svg);
  }

  function inspectCell(c) {
    $("cell-inspector").textContent =
      `${c.month_name} ${c.year} · HHE: ${c.hhe_total.toFixed(1)} | Raw: ${c.raw_total} (MODIS ${c.raw_modis} + VIIRS ${c.raw_viirs}) | ` +
      `2001–2020 Med: ${c.hist_median_hhe.toFixed(1)} | P95: ${c.hist_p95_hhe.toFixed(1)} | ` +
      `Anomaly: ${c.anomaly_pct >= 0 ? "+" : ""}${c.anomaly_pct.toFixed(1)}% (Z = ${c.z_robust >= 0 ? "+" : ""}${c.z_robust.toFixed(2)}) · Click to focus`;
  }

  // ---- Interactive Spatial Map & Polygon Drawing ----------------------------------------------
  function toggleDrawMode() {
    state.draw.active = !state.draw.active;
    if (!state.draw.active) state.draw.points = [];
    syncDrawControls();
    renderMap();
  }

  function syncDrawControls() {
    $("btn-draw-mode").setAttribute("aria-pressed", String(state.draw.active));
    $("btn-draw-mode").textContent = state.draw.active ? "Cancel Draw" : "Draw Polygon";
    $("btn-draw-undo").hidden = !state.draw.active;
    $("btn-draw-apply").hidden = !state.draw.active || state.draw.points.length < 3;
  }

  async function submitDrawnPolygon() {
    if (state.draw.points.length < 3) return;
    const ring = state.draw.points.map((p) => [p.lon, p.lat]);
    ring.push([...ring[0]]);
    for (const btn of document.querySelectorAll(".preset-pill")) btn.classList.remove("active");
    await runAnalyze({
      name: "Drawn Custom AOI",
      geojson: { type: "Polygon", coordinates: [ring] },
      year_start: parseInt($("in-y0").value, 10),
      year_end: parseInt($("in-y1").value, 10),
      focus_year: parseInt($("in-fy").value, 10),
      focus_month: parseInt($("in-fm").value, 10),
      confidence_min: $("in-conf").value,
      persona: state.persona,
    });
  }

  function renderMap() {
    const r = state.run;
    if (!r) return;
    const aoi = r.aoi;
    const bbox = aoi.bbox;
    const padLat = Math.max(0.25, (bbox.lat_max - bbox.lat_min) * 0.25);
    const padLon = Math.max(0.25, (bbox.lon_max - bbox.lon_min) * 0.25);
    const minLon = bbox.lon_min - padLon, maxLon = bbox.lon_max + padLon;
    const minLat = bbox.lat_min - padLat, maxLat = bbox.lat_max + padLat;
    const W = 520, H = 390;

    const xOf = (lon) => ((lon - minLon) / (maxLon - minLon)) * W;
    const yOf = (lat) => H - ((lat - minLat) / (maxLat - minLat)) * H;
    const lonOf = (x) => minLon + (x / W) * (maxLon - minLon);
    const latOf = (y) => minLat + ((H - y) / H) * (maxLat - minLat);

    const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
    // Background 1 km style reference grid
    for (let i = 1; i < 10; i++) {
      const gx = (W / 10) * i, gy = (H / 8) * i;
      svg.append(s("line", { x1: gx, y1: 0, x2: gx, y2: H, stroke: "#18271E", "stroke-width": 1 }));
      if (i < 8) svg.append(s("line", { x1: 0, y1: gy, x2: W, y2: gy, stroke: "#18271E", "stroke-width": 1 }));
    }

    // AOI polygon outline
    const polyPts = aoi.polygon.map((p) => `${xOf(p[0]).toFixed(1)},${yOf(p[1]).toFixed(1)}`).join(" ");
    svg.append(s("polygon", {
      points: polyPts,
      fill: "rgba(155, 227, 180, 0.06)",
      stroke: "#9BE3B4",
      "stroke-width": 2,
      "stroke-dasharray": "5 3",
    }));

    // Plot harmonized hotspots
    const colorMap = { MODIS: "#38BDF8", VIIRS: "#F97316", HARMONIZED_BOTH: "#9BE3B4" };
    r.map_hotspots.forEach((spot) => {
      const cx = xOf(spot.lon), cy = yOf(spot.lat);
      const fillCol = spot.fire_category === "STATIC_FLARE" ? "#A855F7" : (colorMap[spot.sensor_family] || "#9BE3B4");
      const rad = Math.max(2.4, Math.min(7.5, 2.2 + Math.sqrt(spot.hfre_mw) * 0.38));
      const dot = s("circle", {
        cx: cx.toFixed(1),
        cy: cy.toFixed(1),
        r: rad.toFixed(1),
        fill: fillCol,
        "fill-opacity": 0.78,
        stroke: "#0A120D",
        "stroke-width": 0.6,
      });
      dot.addEventListener("mouseenter", () => {
        $("map-hover-readout").textContent =
          `${spot.cell_id} · ${spot.acq_date} (${spot.daynight}) · ${spot.sensor_family} · ` +
          `HHE ${spot.hhe.toFixed(2)} (raw=${spot.raw_detections}) · ${spot.hfre_mw.toFixed(1)} MW · ${spot.fire_category}`;
      });
      svg.append(dot);
    });

    // Drawn polygon vertices
    if (state.draw.active) {
      if (state.draw.points.length >= 2) {
        const dPts = state.draw.points.map((p) => `${xOf(p.lon).toFixed(1)},${yOf(p.lat).toFixed(1)}`).join(" ");
        svg.append(s("polygon", { points: dPts, fill: "rgba(245, 196, 105, 0.16)", stroke: "#F5C469", "stroke-width": 2 }));
      }
      state.draw.points.forEach((p) => {
        svg.append(s("circle", { cx: xOf(p.lon), cy: yOf(p.lat), r: 4.5, fill: "#F5C469", stroke: "#0A120D" }));
      });
      svg.addEventListener("click", (ev) => {
        const rect = svg.getBoundingClientRect();
        const sx = ((ev.clientX - rect.left) / rect.width) * W;
        const sy = ((ev.clientY - rect.top) / rect.height) * H;
        state.draw.points.push({ lon: Number(lonOf(sx).toFixed(4)), lat: Number(latOf(sy).toFixed(4)) });
        syncDrawControls();
        renderMap();
      });
    }

    $("map-card-title").textContent = `${aoi.name} (${aoi.lat.toFixed(2)}°, ${aoi.lon.toFixed(2)}°)`;
    $("map-viewport").replaceChildren(svg);
  }

  // ---- Seasonal Climatology Fan Chart ---------------------------------------------------------
  function renderSeasonChart() {
    const cal = state.run.calendar;
    const clim = cal.climatology;
    const focusCells = new Map();
    cal.cells.filter((c) => c.year === cal.focus_year && c.is_observed).forEach((c) => focusCells.set(c.month, c.value));

    const W = 640, H = 250, pad = { l: 48, r: 20, t: 24, b: 34 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const maxV = Math.max(10, ...clim.map((c) => c.p95), ...Array.from(focusCells.values()));
    const xOf = (i) => pad.l + (i / 11) * iw;
    const yOf = (v) => pad.t + ih - (v / maxV) * ih;

    const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
    // Grid ticks
    [0, 0.5, 1].forEach((frac) => {
      const y = pad.t + ih * (1 - frac);
      svg.append(s("line", { x1: pad.l, y1: y, x2: W - pad.r, y2: y, stroke: "#1F2E25", "stroke-width": 1 }));
      svg.append(s("text", { x: 4, y: y + 4, fill: "#8A978F", "font-size": 10, text: Math.round(maxV * frac) }));
    });

    // Q25-Q75 IQR Band
    const upper = clim.map((c, i) => `${xOf(i).toFixed(1)},${yOf(c.q75).toFixed(1)}`);
    const lower = clim.slice().reverse().map((c, i) => `${xOf(11 - i).toFixed(1)},${yOf(c.q25).toFixed(1)}`);
    svg.append(s("polygon", { points: upper.concat(lower).join(" "), fill: "rgba(155, 227, 180, 0.16)" }));

    // P95 critical threshold
    const p95Pts = clim.map((c, i) => `${xOf(i).toFixed(1)},${yOf(c.p95).toFixed(1)}`).join(" ");
    svg.append(s("polyline", { points: p95Pts, fill: "none", stroke: "#F5C469", "stroke-width": 1.5, "stroke-dasharray": "4 4" }));

    // Historical Median
    const medPts = clim.map((c, i) => `${xOf(i).toFixed(1)},${yOf(c.median).toFixed(1)}`).join(" ");
    svg.append(s("polyline", { points: medPts, fill: "none", stroke: "#9BE3B4", "stroke-width": 2 }));

    // Focus year series
    const fPts = [];
    clim.forEach((c, i) => {
      const mo = i + 1;
      if (focusCells.has(mo)) {
        const x = xOf(i), y = yOf(focusCells.get(mo));
        fPts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      svg.append(s("text", { x: xOf(i) - 10, y: H - 10, fill: "#8A978F", "font-size": 10, text: c.month_name }));
    });
    if (fPts.length) {
      svg.append(s("polyline", { points: fPts.join(" "), fill: "none", stroke: "#D9622B", "stroke-width": 2.6 }));
      clim.forEach((c, i) => {
        const mo = i + 1;
        if (!focusCells.has(mo)) return;
        svg.append(s("circle", {
          cx: xOf(i),
          cy: yOf(focusCells.get(mo)),
          r: mo === cal.focus_month ? 5.5 : 3.2,
          fill: mo === cal.focus_month ? "#FDE68A" : "#D9622B",
          stroke: "#0A120D",
        }));
      });
    }

    $("season-chart-title").textContent = `${cal.focus_year} Trajectory (Orange) vs. 2001–2020 Median (Mint), IQR (Shaded) & P95 (Dashed)`;
    $("season-chart-box").replaceChildren(svg);
  }

  function renderAttributionAndPasses() {
    const audit = state.run.sensor_calibration_audit;
    const bars = [
      { label: "Wildfires", val: audit.wildfire_share * 100, color: "#D9622B" },
      { label: "Agricultural Burns", val: audit.agricultural_share * 100, color: "#F5C469" },
      { label: "Static Gas Flares", val: audit.flare_contamination_share * 100, color: "#A855F7" },
    ];
    $("attribution-bars").replaceChildren(...bars.map((b) =>
      h("div", { class: "attr-row" },
        h("span", { text: b.label }),
        h("div", { class: "attr-track" }, h("div", { class: "attr-fill", style: `width:${Math.min(100, b.val).toFixed(1)}%;background:${b.color}` })),
        h("span", { class: "mono", text: `${b.val.toFixed(1)}%` }),
      ),
    ));

    const tbody = $("passes-tbody");
    if (!state.passes || !state.passes.passes.length) {
      tbody.replaceChildren(h("tr", {}, h("td", { colspan: 5, text: "No upcoming passes loaded" })));
      return;
    }
    tbody.replaceChildren(...state.passes.passes.slice(0, 7).map((p) =>
      h("tr", {},
        h("td", { text: p.satellite }),
        h("td", { text: `${p.instrument} ${p.resolution_m}m` }),
        h("td", { text: p.utc_time.replace("T", " ").replace("Z", "") }),
        h("td", { text: p.pass_type }),
        h("td", { text: `${p.max_elevation_deg}°` }),
      ),
    ));
  }

  // ---- View 2: Sensor Bridge ------------------------------------------------------------------
  function renderBridge() {
    const r = state.run;
    if (!r) return;
    const rows = r.annual_sensor_breakdown;
    const audit = r.sensor_calibration_audit;
    $("bridge-r2-badge").textContent = `Overlap R² = ${audit.bridge_r2.toFixed(3)} · κ = ${audit.calibrated_kappa.toFixed(3)}`;

    const W = 900, H = 340, pad = { l: 56, r: 24, t: 24, b: 36 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const maxV = Math.max(10, ...rows.map((d) => Math.max(d.raw_total, d.hhe_total)));
    const xOf = (i) => pad.l + (i / Math.max(1, rows.length - 1)) * iw;
    const yOf = (v) => pad.t + ih - (v / maxV) * ih;

    const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
    [0, 0.25, 0.5, 0.75, 1].forEach((f) => {
      const y = pad.t + ih * (1 - f);
      svg.append(s("line", { x1: pad.l, y1: y, x2: W - pad.r, y2: y, stroke: "#1F2E25" }));
      svg.append(s("text", { x: 4, y: y + 4, fill: "#8A978F", "font-size": 10, text: Math.round(maxV * f) }));
    });

    // Vertical marker at 2012 VIIRS launch
    const idx2012 = rows.findIndex((d) => d.year === 2012);
    if (idx2012 >= 0) {
      const vx = xOf(idx2012);
      svg.append(s("line", { x1: vx, y1: pad.t, x2: vx, y2: pad.t + ih, stroke: "#F5C469", "stroke-dasharray": "4 4" }));
      svg.append(s("text", { x: vx + 5, y: pad.t + 14, fill: "#F5C469", "font-size": 11, text: "2012 VIIRS S-NPP Launch" }));
    }

    const rawPts = rows.map((d, i) => `${xOf(i).toFixed(1)},${yOf(d.raw_total).toFixed(1)}`).join(" ");
    const hhePts = rows.map((d, i) => `${xOf(i).toFixed(1)},${yOf(d.hhe_total).toFixed(1)}`).join(" ");
    svg.append(s("polyline", { points: rawPts, fill: "none", stroke: "#D9622B", "stroke-width": 2.2, "stroke-dasharray": "5 3" }));
    svg.append(s("polyline", { points: hhePts, fill: "none", stroke: "#9BE3B4", "stroke-width": 3 }));

    rows.forEach((d, i) => {
      if (d.year % 2 === 0 || d.year === 2026) {
        svg.append(s("text", { x: xOf(i) - 12, y: H - 10, fill: "#8A978F", "font-size": 10, text: String(d.year) }));
      }
      svg.append(s("circle", { cx: xOf(i), cy: yOf(d.hhe_total), r: 3.5, fill: "#9BE3B4" }));
    });
    $("bridge-chart-box").replaceChildren(svg);

    $("bridge-audit-kpis").replaceChildren(
      kpiCard("Raw VIIRS / MODIS Ratio", `${audit.raw_viirs_to_modis_ratio.toFixed(2)}×`, "Before 1 km clustering & κ calibration"),
      kpiCard("Calibrated Bridge Factor κ", audit.calibrated_kappa.toFixed(4), `Fitted across ${audit.overlap_years} overlap`),
      kpiCard("2012 Step Bias Reduction", `${audit.bias_reduction_pct.toFixed(1)}%`, `Raw ${audit.raw_step_jump_2012_pct.toFixed(1)}% → Harmonized ${audit.harmonized_step_diff_2012_pct.toFixed(1)}%`),
      kpiCard("Overpass Duplicates Removed", audit.overpass_duplicates_removed.toLocaleString(), "Aqua + S-NPP + NOAA-20/21 afternoon passes collapsed"),
    );

    $("bridge-tbody").replaceChildren(...rows.map((d) =>
      h("tr", {},
        h("td", { text: d.year }),
        h("td", { text: d.raw_modis.toLocaleString() }),
        h("td", { text: d.raw_viirs.toLocaleString() }),
        h("td", { text: d.raw_total.toLocaleString() }),
        h("td", { text: d.hhe_total.toFixed(1) }),
        h("td", { text: d.frp_total_mw.toLocaleString() }),
        h("td", { text: d.raw_flares.toLocaleString() }),
      ),
    ));
  }

  function kpiCard(title, val, sub) {
    return h("div", { class: "panel kpi" },
      h("span", { class: "sub", text: title }),
      h("strong", { class: "kpi-val mono", text: val }),
      h("span", { class: "small muted", text: sub }),
    );
  }

  // ---- View 3: Evaluator & Receipt ------------------------------------------------------------
  function renderAudit() {
    const r = state.run;
    if (!r) return;
    $("whatif-grid").replaceChildren(...r.what_if.experiments.map((exp) =>
      h("div", { class: "sub-card" },
        h("strong", { class: "small", text: exp.label }),
        h("div", { class: "finding-meta" },
          h("span", { class: `tag tag-${exp.verdict_before}`, text: exp.verdict_before }),
          h("span", { text: "→" }),
          h("span", { class: `tag tag-${exp.verdict_after}`, text: exp.verdict_after }),
        ),
        h("button", {
          type: "button",
          class: "btn btn-sm",
          text: exp.flips_verdict ? "Apply Flip Counterfactual" : "Apply Counterfactual",
          onclick: () => runWhatIf(exp.field, exp.value),
        }),
      ),
    ));

    $("refutation-grid").replaceChildren(...r.refutations.map((ref) =>
      h("div", { class: "sub-card" },
        h("div", { class: "finding-meta" },
          h("span", { class: `tag tag-${ref.status}`, text: ref.status }),
          h("strong", { class: "small", text: ref.title }),
        ),
        h("p", { class: "small muted", text: `Tested: ${ref.hypothesis_tested}` }),
        h("p", { class: "small", text: ref.evidence }),
      ),
    ));

    $("trace-tbody").replaceChildren(...r.trace.map((t) =>
      h("tr", {},
        h("td", { text: t.agent_name }),
        h("td", { text: t.action }),
        h("td", { text: t.input_summary }),
        h("td", { text: t.output_summary }),
        h("td", { text: t.rows }),
        h("td", { text: t.status }),
      ),
    ));

    $("verify-cli-hint").textContent =
      `Offline verification: download Receipt JSON and run "python verify.py receipt.json" -> VALID: ${r.verdict} (seal ${r.verdict_sha256.slice(0, 16)}...)`;

    $("queries-tbody").replaceChildren(...r.queries.map((q) =>
      h("tr", {},
        h("td", { text: q.query_id }),
        h("td", { text: q.title }),
        h("td", { text: q.row_count }),
        h("td", { text: q.sha256.slice(0, 20) + "…" }),
      ),
    ));
    $("receipt-json-box").hidden = true;
  }

  async function loadReceiptJson() {
    if (!state.run) return;
    const box = $("receipt-json-box");
    if (!box.hidden) { box.hidden = true; return; }
    const receipt = await apiJSON(`/runs/${encodeURIComponent(state.run.run_id)}/receipt`);
    box.textContent = JSON.stringify(receipt, null, 2);
    box.hidden = false;
  }

  // ---- View 4: Schema Mapping Manifesto -------------------------------------------------------
  async function loadManifesto() {
    const data = await apiJSON("/api/schema-mapping");
    state.manifesto = data;

    $("manifesto-sources").replaceChildren(...Object.entries(data.source_schemas).map(([name, info]) =>
      h("div", { class: "sub-card" },
        h("strong", { class: "mono", text: name }),
        h("p", { class: "small muted", text: info.description }),
        h("pre", { class: "code-box mono", text: Object.entries(info.fields).map(([f, t]) => `${f}: ${t}`).join("\n") }),
      ),
    ));

    $("manifesto-targets").replaceChildren(...data.manifesto.map((t) =>
      h("section", { class: "panel card" },
        h("div", { class: "stack-4" },
          h("span", { class: "eyebrow eyebrow-signal", text: "Target Table Mapping Plan" }),
          h("h3", { class: "h-card mono", text: t.target_table }),
          h("p", { class: "small muted", text: `Anchor: ${t.anchor_source}` }),
        ),
        h("div", { class: "table-scroll" },
          h("table", { class: "data-table" },
            h("thead", {}, h("tr", {}, h("th", { text: "Target Field" }), h("th", { text: "Source / Logic" }), h("th", { text: "Type" }), h("th", { text: "Rationale" }))),
            h("tbody", {}, ...t.fields.map((f) =>
              h("tr", {},
                h("td", { class: "mono", text: f.target }),
                h("td", { class: "mono small", text: f.source }),
                h("td", { text: f.type }),
                h("td", { class: "small", text: f.rationale }),
              ),
            )),
          ),
        ),
      ),
    ));
  }

  // ---- View 5: Judge & Trap Bench -------------------------------------------------------------
  async function runBenchSuite() {
    const btn = $("btn-run-bench");
    btn.disabled = true;
    btn.textContent = "Running 12 cases...";
    try {
      const res = await apiJSON("/api/bench", { method: "POST" });
      $("bench-summary").textContent = `Bench Result: ${res.passed} / ${res.total} PASSED (${res.all_pass ? "ALL CLAIMS VERIFIED" : "FAILURES DETECTED"})`;
      $("bench-tbody").replaceChildren(...res.results.map((r) =>
        h("tr", {},
          h("td", { class: "mono", text: r.id }),
          h("td", {}, h("strong", { text: r.name }), h("div", { class: "sub", text: r.why })),
          h("td", {}, h("span", { class: `tag tag-${r.expected_verdict}`, text: r.expected_verdict })),
          h("td", {}, h("span", { class: `tag tag-${r.actual_verdict}`, text: r.actual_verdict })),
          h("td", { class: "mono", text: (r.z_robust >= 0 ? "+" : "") + r.z_robust.toFixed(2) }),
          h("td", { class: "mono", text: `${r.bias_reduction_pct.toFixed(1)}%` }),
          h("td", {}, h("span", { class: `tag tag-${r.pass ? "PASS" : "FAIL"}`, text: r.pass ? "PASS" : "FAIL" })),
        ),
      ));
    } finally {
      btn.disabled = false;
      btn.textContent = "Run All 12 Bench Cases";
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();

