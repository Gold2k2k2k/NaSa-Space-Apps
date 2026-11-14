/** Evidence-driven summaries for the five-view dashboard. */
import { $, finite, fmt, integer, percent, signed, h, replace, table, badge, metric, unit, utcLabel } from "./ui.js";
import { color } from "./theme.js";
import { renderBridgePlot } from "./charts.js";

export function renderContext(run) {
  const calendar = run.calendar, focus = calendar.focus_comparison, audit = run.sensor_calibration_audit;
  const kind = run.provenance.source_kind;
  $("source-badge").dataset.kind = kind;
  replace($("source-badge"), h("i", { "aria-hidden": "true" }), kind === "generated_demo" ? "Generated demo" : kind === "uploaded_csv" ? "Uploaded CSV" : "Provided records");
  $("aoi-heading").textContent = run.aoi.name;
  $("aoi-description").textContent = run.aoi.country + " · " + fmt(run.aoi.area_km2, 1) + " km² · " + focus.month_name + " " + focus.year + " comparison";
  $("snapshot-reference").textContent = "Snapshot reference: " + utcLabel(run.reference_time);
  replace($("hero-verdict-tag"), badge(run.verdict));
  $("hero-verdict-tag").className = "";
  $("run-seal-pill").textContent = "Rule " + run.deciding_rule + " · " + run.verdict_sha256.slice(0, 12) + "…";
  $("selection-label").textContent = focus.month_name + " " + focus.year + " · " + calendar.year_start + "–" + calendar.year_end;
  $("scenario-banner").hidden = !run.counterfactual;
  const note = kind === "generated_demo" ?
    "Generated fixture data · simulated coverage from November 2000 through November 2026. This is a reproducible demonstration, not observed regional conditions." :
    "Uploaded/provided detections · missing months are unknown, not zero. Source authenticity and complete observation coverage are unestablished.";
  const ingestion = run.ingestion ? " Accepted " + integer(run.ingestion.accepted_rows) + "; rejected " + integer(run.ingestion.rejected_rows) + " row(s)." : "";
  replace($("data-note"), note + ingestion + " ", h("a", { href: "/static/samples/generated-firms-demo.csv", download: "", text: "Synthetic CSV sample" }));
  $("kpi-focus-val").textContent = finite(focus.value) ? fmt(focus.value) : "Unavailable";
  $("kpi-focus-sub").textContent = unit(run) + " · reference median " + fmt(focus.hist_median) + (run.counterfactual ? " · hypothetical" : "");
  $("kpi-z-val").textContent = finite(focus.z_robust) ? signed(focus.z_robust) : "Unavailable";
  $("kpi-z-sub").textContent = "Empirical percentile " + (finite(focus.empirical_percentile) ? fmt(focus.empirical_percentile, 1) : "unavailable") + " · descriptive scale";
  $("kpi-baseline-val").textContent = calendar.baseline_complete_year_count + " complete";
  $("kpi-baseline-sub").textContent = calendar.baseline_year_count + " recorded reference months · focus " + focus.coverage_status.replaceAll("_", " ");
  $("kpi-frp-val").textContent = finite(focus.frp_total_mw) ? integer(focus.frp_total_mw) + " MW" : "Unavailable";
  $("kpi-frp-sub").textContent = "Known D/N night share " + percent(focus.night_share) + " · power, not energy";
  $("btn-toggle-mode").setAttribute("aria-checked", String(calendar.mode === "harmonized"));
  $("mode-switch-label").textContent = calendar.mode === "harmonized" ? "Harmonized index" : "Raw detection count";
  $("btn-toggle-flare").setAttribute("aria-checked", String(run.options.flare_guard));
  $("flare-switch-label").textContent = "Non-vegetation guard " + (run.options.flare_guard ? "on" : "off");
  $("briefing-role-label").textContent = run.briefing.persona_label;
  $("briefing-rules-ver").textContent = "Rules " + run.rules_version + " · " + run.calculation_version;
  $("briefing-headline").textContent = run.briefing.headline;
  replace($("briefing-actions"), run.briefing.actions.map((action) => h("li", { text: action })));
  replace($("findings-list"), run.findings.map((finding) => h("article", { class: "finding" },
    h("div", {}, badge(finding.verdict), h("span", { class: "small muted", text: " · Rule " + finding.rule + " · " + finding.code })),
    h("p", { text: finding.detail }))));
  renderSourceContext(run);
  renderPasses(run);
}

function renderSourceContext(run) {
  const audit = run.sensor_calibration_audit, total = audit.total_raw_detections;
  const low = audit.category_counts.LOW_FRP_DAYTIME || 0, typed = audit.static_flare_detections;
  const parts = [["Supplied non-vegetation types", typed, "excluded"], ["Low-FRP daytime pattern", low, "ember"],
    ["Other / persistent vegetation patterns", Math.max(0, total - typed - low), "accent"]];
  replace($("attribution-bars"), parts.map(([label, count, tone]) => h("div", { class: "attr-row" },
    h("span", { text: label }), h("span", { class: "mono", text: integer(count) + " · " + percent(total ? count / total : null) }),
    h("div", { class: "attr-track", "aria-hidden": "true" }, h("div", { class: "attr-fill", style: "width:" + (total ? count / total * 100 : 0) + "%;background:" + color(tone) })))));
  const quality = audit.quality;
  $("quality-note").textContent = integer(total) + " selected rows. Filtered by confidence: " + integer(quality.confidence_filtered_rows) +
    "; outside AOI: " + integer(quality.outside_aoi_rows) + "; invalid: " + integer(quality.invalid_rows) +
    ". Before the confidence filter, valid in-AOI rows with missing FRP: " + integer(quality.missing_measurements.frp || 0) + "; missing time: " + integer(quality.missing_measurements.acq_time || 0) + ".";
}

function renderPasses(run) {
  const passes = run.passes;
  $("passes-note").textContent = passes.pass_count + " modeled opportunities · five days from " + utcLabel(passes.reference_time) + ". Not ephemeris predictions.";
  replace($("passes-tbody"), passes.passes.map((row) => h("tr", {},
    h("td", {}, row.satellite, h("div", { class: "small muted", text: row.instrument })),
    h("td", { class: "mono", text: utcLabel(row.utc_time) }), h("td", { text: row.pass_type === "DAY" ? "Nominal day" : "Nominal night" }),
    h("td", { class: "numeric", text: fmt(row.max_elevation_deg, 1) + "°" }))));
  if (!passes.pass_count) replace($("passes-tbody"), h("tr", {}, h("td", { colspan: 4, text: "No opportunities in this modeled window." })));
  $("passes-limits").textContent = passes.note;
  replace($("passes-excluded"), passes.excluded_sources.map((source) => h("li", { text: source.satellite + ": " + source.reason })));
}

export function renderBridge(run) {
  renderBridgePlot(run);
  const audit = run.sensor_calibration_audit;
  replace($("bridge-audit-kpis"),
    metric("Pooled multiplier κ", fmt(audit.calibrated_kappa, 3), audit.calibration_valid ? "Empirical monthly sum ratio" : "Explicit demo assumption"),
    metric("Correlation R²", finite(audit.bridge_r2) ? fmt(audit.bridge_r2, 3) : "Undefined", "Correlation is not one-to-one agreement"),
    metric("Agreement efficiency", finite(audit.bridge_efficiency) ? fmt(audit.bridge_efficiency, 3) : "Undefined", "1 − squared error / reference variation"),
    metric("Overlap RMSE", fmt(audit.bridge_rmse, 2), audit.overlap_months_count + " overlap month pairs · index units"));
  replace($("transition-audits"), audit.transition_audits.map((transition) => h("article", { class: "finding" },
    h("h3", { text: transition.transition_year + " transition" }),
    h("p", { text: "Raw " + signed(transition.raw_step_pct, 1) + "% → harmonized " + signed(transition.harmonized_step_pct, 1) + "%. Change reduction: " + (finite(transition.bias_reduction_pct) ? fmt(transition.bias_reduction_pct, 1) + "%" : "undefined") + "." }),
    h("p", { class: "small muted", text: transition.status.replaceAll("_", " ") + ". This before/after comparison does not establish a cause." }))));
  $("calibration-note").textContent = "Applied bridge: " + audit.calibration_basis.replaceAll("_", " ") +
    ". Era ratios are diagnostics only. FRP conversion: " + fmt(audit.frp_conversion_ratio, 3) + " (" + audit.frp_calibration_basis.replaceAll("_", " ") + ").";
  replace($("era-table"), table(["Years", "Pairs", "Era κ", "Pooled RMSE", "Efficiency"],
    audit.era_diagnostics.map((era) => [era.years, era.overlap_months, fmt(era.empirical_kappa, 3),
      fmt(era.agreement_at_pooled_kappa.rmse, 2), fmt(era.agreement_at_pooled_kappa.efficiency, 3)]), { numeric: [1, 2, 3, 4] }));
  replace($("bridge-tbody"), run.calendar.annual_series.map((row) => h("tr", {},
    h("th", { scope: "row", text: row.year }), h("td", { class: "numeric", text: integer(row.raw_modis) }),
    h("td", { class: "numeric", text: integer(row.raw_viirs) }), h("td", { class: "numeric", text: fmt(row.hhe_total) }),
    h("td", { class: "numeric", text: integer(row.frp_total_mw) }), h("td", { text: row.is_complete ? "Complete" : row.observed_months ? "Partial · " + row.observed_months + " months" : "Missing" }))));
}

export function renderAudit(run, experiment) {
  replace($("whatif-grid"), run.what_if.experiments.map((item) => h("article", { class: "sub-card" },
    h("h3", { text: item.label }), h("p", {}, badge(item.verdict_before), " → ", badge(item.verdict_after)),
    h("p", { text: item.available === false ? "Requires an observed focus period and reference median." : item.flips_verdict ? "Changes this demo verdict." : "Keeps this demo verdict." }),
    h("button", { type: "button", class: "btn requires-run", disabled: item.available === false, "data-available": String(item.available !== false),
      onclick: () => experiment(item.field, item.value), text: "Run experiment" }))));
  replace($("refutation-grid"), run.refutations.map((item) => h("article", { class: "sub-card" },
    badge(item.status), h("h3", { text: item.title }), h("p", { text: item.hypothesis_tested }), h("p", { text: item.evidence }))));
  replace($("trace-tbody"), run.trace.map((row) => h("tr", {}, h("th", { scope: "row", text: row.agent_name }),
    h("td", { text: row.action.replaceAll("_", " ") }), h("td", { text: row.input_summary }),
    h("td", { text: row.output_summary }), h("td", { class: "numeric", text: integer(row.rows) }))));
  $("verify-cli-hint").textContent = "Download the audit ZIP, extract it, then run: python -S -B verify.py receipt.json";
  replace($("queries-tbody"), run.queries.map((query) => h("tr", {}, h("th", { scope: "row", text: query.query_id }),
    h("td", { text: query.title }), h("td", { class: "numeric", text: query.row_count }), h("td", {}, h("code", { text: query.sha256 })))));
}

export function renderManifesto(data) {
  replace($("manifesto-sources"), Object.entries(data.source_schemas).map(([name, source]) => h("article", { class: "sub-card" },
    h("h2", { class: "mono", text: name }), h("p", { text: source.description }),
    h("details", { class: "data-alternative" }, h("summary", { text: "Inspect source fields" }),
      h("pre", { class: "code-box", tabindex: 0, text: Object.entries(source.fields).map(([field, type]) => field + ": " + type).join("\n") })))));
  replace($("manifesto-targets"), data.manifesto.map((mapping) => h("article", { class: "panel" },
    h("p", { class: "eyebrow", text: "Logical target mapping" }), h("h2", { class: "mono", text: mapping.target_table }),
    h("p", { class: "small muted", text: mapping.anchor_source }),
    h("div", { class: "table-scroll" }, table(["Target field", "Source / calculation", "Kind", "Meaning"],
      mapping.fields.map((field) => [h("code", { text: field.target }), field.source, field.type, field.rationale]))))));
  $("manifesto-status").textContent = "Loaded " + Object.keys(data.source_schemas).length + " source schema groups and " + data.manifesto.length + " logical target mappings.";
}

export function renderBench(result, cases = []) {
  const rows = result ? result.results : cases;
  replace($("bench-tbody"), rows.map((row) => h("tr", {}, h("th", { scope: "row", text: row.id }),
    h("td", {}, h("strong", { text: row.name }), h("p", { class: "small muted", text: row.why })),
    h("td", {}, badge(row.expected_verdict)), h("td", {}, result ? badge(row.actual_verdict) : "Not run"),
    h("td", { class: "numeric", text: result ? signed(row.z_robust) : "—" }),
    h("td", {}, result ? badge(row.pass ? "PASS" : "FAIL") : "Ready"))));
  if (result) $("bench-summary").textContent = result.passed + " / " + result.total + " generated scenarios matched their expected verdicts. This checks demonstration behavior.";
}
