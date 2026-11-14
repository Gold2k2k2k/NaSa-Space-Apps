/** Original SVG plots and a keyboard-operated semantic calendar table. */
import { $, MONTHS, finite, fmt, integer, signed, h, s, replace, table, unit } from "./ui.js";
import { color, rampStops, cellColors } from "./theme.js";

function svgFrame(host, title, description, height = 310, minimumWidth = 300) {
  const width = Math.max(minimumWidth, host.clientWidth - 2);
  const graphic = s("svg", { viewBox: "0 0 " + width + " " + height, class: minimumWidth > 300 ? "wide-chart" : "", role: "img", "aria-label": title + ". " + description },
    s("title", { text: title }), s("desc", { text: description }));
  return { graphic, width, height };
}

function text(graphic, x, y, value, options = {}) {
  graphic.append(s("text", { x, y, fill: color("subtle"), "font-size": "var(--font-size-caption)", ...options, text: value }));
}

function axis(graphic, width, top, bottom, maximum, labels) {
  const left = 42, right = width - 20;
  const ymax = maximum > 0 ? maximum * 1.12 : 1;
  const x = (index) => left + index * (right - left) / Math.max(1, labels.length - 1);
  const y = (value) => bottom - value / ymax * (bottom - top);
  for (let tick = 0; tick <= 4; tick++) {
    const value = ymax * tick / 4;
    graphic.append(s("line", { x1: left, x2: right, y1: y(value), y2: y(value), stroke: color("line") }));
    text(graphic, left - 8, y(value) + 4, value >= 1000 ? (value / 1000).toFixed(1) + "k" : fmt(value, value < 10 ? 1 : 0), { "text-anchor": "end" });
  }
  labels.forEach((label, index) => { if (label) text(graphic, x(index), bottom + 24, label, { "text-anchor": "middle" }); });
  return { x, y, left, right };
}

function linePath(values, x, y) {
  let path = "", drawing = false;
  values.forEach((value, index) => {
    if (!finite(value)) { drawing = false; return; }
    path += (drawing ? "L" : "M") + x(index) + "," + y(value);
    drawing = true;
  });
  return path;
}

function addLine(graphic, values, scales, stroke, dash = "") {
  graphic.append(s("path", { d: linePath(values, scales.x, scales.y), fill: "none", stroke, "stroke-width": 2.5, "stroke-dasharray": dash }));
  values.forEach((value, index) => {
    if (finite(value)) graphic.append(s("circle", { cx: scales.x(index), cy: scales.y(value), r: 3, fill: stroke }));
  });
}

function legend(items) {
  return h("div", { class: "chart-legend" }, items.map(([label, tone, dashed]) =>
    h("span", { style: "color:" + color(tone) }, h("i", { class: "legend-line" + (dashed ? " dashed" : ""), "aria-hidden": "true" }), label)));
}

function coverageText(cell, run) {
  if (!cell.is_observed) return "Missing coverage";
  if (!cell.is_complete) return "Recorded detections only; incomplete coverage";
  return run.provenance.source_kind === "generated_demo" ? "Complete simulated period" : "Declared complete period";
}

function inspectCell(cell, run) {
  replace($("cell-inspector"),
    h("strong", { text: cell.month_name + " " + cell.year }),
    h("span", {}, h("strong", { text: fmt(cell.value) }), " " + unit(run) + (cell.value_is_counterfactual ? " · hypothetical" : "")),
    h("span", { text: "Median " + fmt(cell.hist_median_hhe) + " · Z " + signed(cell.z_robust) }),
    h("span", { text: "MODIS " + integer(cell.raw_modis) + " / VIIRS " + integer(cell.raw_viirs) }),
    h("span", { text: coverageText(cell, run) }));
}

function compact(value) {
  if (!finite(value)) return "—";
  return value >= 1000 ? new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value) : fmt(value, value >= 100 ? 0 : 1);
}

export function renderCalendar(run, state, selectPeriod) {
  const host = $("calendar-container"), calendar = run.calendar;
  const activeKey = document.activeElement?.dataset?.cellKey;
  if (host.querySelector(".cal-matrix")) state.calendarScroll = host.scrollLeft;
  $("cal-title").textContent = calendar.year_start + "–" + calendar.year_end + " · " + (calendar.mode === "raw" ? "Raw detections" : "Harmonized occupancy index");
  $("calendar-window").textContent = "Reference: " + calendar.baseline_window + " · missing ≠ zero";
  const stops = rampStops(state.ramp);
  replace($("ramp-legend"),
    h("span", { class: "ramp-bar", style: "background:linear-gradient(to right," + stops.join(",") + ")", "aria-hidden": "true" }),
    h("span", { text: state.ramp === "diverging" ? "Color: robust Z −3 to +3, clamped · numbers: activity" : "0 → " + fmt(calendar.max_cell_value) + " " + unit(run) + " · square-root color scale" }),
    h("span", {}, h("i", { class: "legend-swatch", "aria-hidden": "true" }), "Missing / undefined"),
    h("span", { text: "Dotted edge: incomplete coverage" }));
  if (state.granularity === "dekadal") {
    renderProfile(host, calendar.dekadal_profile, run, true);
    $("calendar-help").textContent = "Three dekads per month (days 1–10, 11–20, 21–month end). Missing periods remain gaps.";
    return;
  }
  $("calendar-help").textContent = "Scroll for all years. Arrow keys explore; Enter selects the comparison period. A dash means missing evidence.";
  const years = Array.from({ length: calendar.year_end - calendar.year_start + 1 }, (_, index) => calendar.year_start + index);
  const cells = new Map(calendar.cells.map((cell) => [cell.year + "-" + cell.month, cell]));
  const focusKey = calendar.focus_year + "-" + calendar.focus_month;
  const keyboardKey = activeKey && cells.has(activeKey) ? activeKey : focusKey;
  const buttons = new Map();
  const matrix = h("table", { class: "cal-matrix", "aria-label": "Monthly " + unit(run) + " by month and year" },
    h("caption", { class: "sr-only", text: "Calendar. Arrow left/right moves by year; up/down by month. Enter sets the focus period. Values are " + unit(run) + "." }),
    h("thead", {}, h("tr", {}, h("th", { scope: "col", class: "month-col", text: "Month" }),
      years.map((year) => h("th", { scope: "col", text: year })))));
  const body = h("tbody");
  MONTHS.forEach((monthName, monthIndex) => {
    const row = h("tr", {}, h("th", { scope: "row", class: "month-col", text: monthName }));
    years.forEach((year, yearIndex) => {
      const key = year + "-" + (monthIndex + 1), cell = cells.get(key), colors = cellColors(cell, calendar.max_cell_value, state.ramp);
      const label = monthName + " " + year + ": " + (cell.is_observed ? fmt(cell.value) + " " + unit(run) : "missing evidence") +
        ". " + coverageText(cell, run) + ". Reference median " + fmt(cell.hist_median_hhe) + ", robust Z " + signed(cell.z_robust) + ". Enter selects this period.";
      const button = h("button", { type: "button", class: "cal-cell" + (key === focusKey ? " is-focus" : "") + (!cell.is_observed ? " is-missing" : !cell.is_complete ? " is-partial" : ""),
        "data-cell-key": key, tabindex: key === keyboardKey ? 0 : -1, title: label, "aria-label": label,
        "aria-pressed": String(key === focusKey), style: "background:" + colors.bg + ";color:" + colors.fg,
        onfocus: () => inspectCell(cell, run), onmouseenter: () => inspectCell(cell, run),
        onclick: () => selectPeriod(year, monthIndex + 1),
        onkeydown: (event) => {
          let x = yearIndex, y = monthIndex;
          if (event.key === "ArrowLeft") x--;
          else if (event.key === "ArrowRight") x++;
          else if (event.key === "ArrowUp") y--;
          else if (event.key === "ArrowDown") y++;
          else if (event.key === "Home") { x = 0; if (event.ctrlKey) y = 0; }
          else if (event.key === "End") { x = years.length - 1; if (event.ctrlKey) y = 11; }
          else return;
          event.preventDefault();
          x = Math.max(0, Math.min(years.length - 1, x)); y = Math.max(0, Math.min(11, y));
          const next = buttons.get(years[x] + "-" + (y + 1));
          button.tabIndex = -1; next.tabIndex = 0; next.focus();
        } }, compact(cell.value));
      buttons.set(key, button); row.append(h("td", {}, button));
    });
    body.append(row);
  });
  matrix.append(body); replace(host, matrix);
  host.scrollLeft = state.calendarScroll ?? host.scrollWidth;
  if (activeKey && buttons.has(activeKey)) buttons.get(activeKey).focus({ preventScroll: true });
  inspectCell(cells.get(focusKey), run);
}

function renderProfile(host, profile, run, withTable = false) {
  const frame = svgFrame(host, "36-dekad activity profile", "Focus metric, reference median and reference P90. Gaps indicate missing evidence.", 310, 600);
  const values = profile.flatMap((row) => [row.focus_value, row.hist_p90]).filter(finite);
  const scales = axis(frame.graphic, frame.width, 30, 255, Math.max(0, ...values), profile.map((row, index) => index % 3 === 1 ? MONTHS[row.month - 1] : ""));
  addLine(frame.graphic, profile.map((row) => row.hist_p90), scales, color("muted"), "4 4");
  addLine(frame.graphic, profile.map((row) => row.hist_median), scales, color("accent"));
  addLine(frame.graphic, profile.map((row) => row.focus_value), scales, color("ember"));
  text(frame.graphic, 58, 18, unit(run));
  const items = [frame.graphic, legend([["Reference median", "accent"], ["Reference P90", "muted", true], [run.counterfactual ? "Scenario metric" : "Focus year", "ember"]])];
  if (withTable) items.push(h("details", { class: "data-alternative" }, h("summary", { text: "Dekadal values as a table" }),
    h("div", { class: "table-scroll" }, table(["Dekad", "Focus", "Median", "P90", "Reference years"],
      profile.map((row) => [row.label, fmt(row.focus_value), fmt(row.hist_median), fmt(row.hist_p90), row.baseline_year_count]), { numeric: [1, 2, 3, 4] }))));
  replace(host, items);
}

export function renderSeason(run) {
  const host = $("season-chart-box"), calendar = run.calendar;
  const focus = calendar.climatology.map((row) => calendar.cells.find((cell) => cell.year === calendar.focus_year && cell.month === row.month));
  const frame = svgFrame(host, "Monthly seasonal comparison", "Reference median, interquartile range, P95 and focus-year metric. Missing months remain gaps.");
  const maximum = Math.max(0, ...calendar.climatology.flatMap((row, index) => [row.p95, focus[index].value]).filter(finite));
  const labels = MONTHS.map((month, index) => frame.width < 480 && index % 2 ? "" : month);
  const scales = axis(frame.graphic, frame.width, 30, 255, maximum, labels);
  let segment = [];
  const flushBand = () => {
    if (segment.length) {
      const upper = segment.map((index) => scales.x(index) + "," + scales.y(calendar.climatology[index].q75));
      const lower = [...segment].reverse().map((index) => scales.x(index) + "," + scales.y(calendar.climatology[index].q25));
      frame.graphic.append(s("polygon", { points: [...upper, ...lower].join(" "), fill: color("accent"), opacity: .16 }));
      segment = [];
    }
  };
  calendar.climatology.forEach((row, index) => { if (finite(row.q25) && finite(row.q75)) segment.push(index); else flushBand(); });
  flushBand();
  addLine(frame.graphic, calendar.climatology.map((row) => row.p95), scales, color("muted"), "4 4");
  addLine(frame.graphic, calendar.climatology.map((row) => row.median), scales, color("accent"));
  addLine(frame.graphic, focus.map((row) => row.value), scales, color("ember"));
  text(frame.graphic, 58, 18, unit(run));
  replace(host, frame.graphic, legend([["Reference median / IQR band", "accent"], ["Reference P95", "muted", true], [run.counterfactual ? "Scenario metric" : "Focus " + calendar.focus_year, "ember"]]));
  replace($("season-data"), table(["Month", "Focus", "Median", "Q25", "Q75", "P95", "Coverage"],
    calendar.climatology.map((row, index) => [row.month_name, fmt(focus[index].value), fmt(row.median), fmt(row.q25), fmt(row.q75), fmt(row.p95), focus[index].coverage_status]), { numeric: [1, 2, 3, 4, 5] }));
  const season = calendar.phenology, records = calendar.summary_records;
  const dekadLabel = (value) => value ? MONTHS[Math.floor((value - 1) / 3)] + " D" + ((value - 1) % 3 + 1) : "Undefined";
  replace($("season-summary"),
    h("p", {}, "90% seasonal window", h("strong", { text: season.season_defined ? dekadLabel(season.season_onset_dekad) + " → " + dekadLabel(season.season_cessation_dekad) : "Undefined profile" })),
    h("p", {}, "Peak / duration", h("strong", { text: season.season_defined ? dekadLabel(season.season_peak_dekad) + " / " + season.season_duration_dekads + " dekads" : "Insufficient seasonal evidence" })),
    h("p", {}, "Theil–Sen trend", h("strong", { text: signed(records.theil_sen_slope_per_decade) + " / decade" })),
    h("p", {}, "OLS trend · complete years", h("strong", { text: signed(records.trend_slope_per_decade) + " / decade · n=" + records.trend_complete_year_count })));
}

export function renderBridgePlot(run) {
  const host = $("bridge-chart-box"), series = run.calendar.annual_series;
  const frame = svgFrame(host, "Raw detections and harmonized occupancy in separate panels", "The two panels have separate vertical scales and common years. Partial totals are labeled.", 440);
  const stride = frame.width < 480 ? 6 : 3;
  const labels = series.map((row, index) => index === 0 || index === series.length - 1 || (index % stride === 0 && series.length - 1 - index >= stride / 2) ? String(row.year) : "");
  const raw = axis(frame.graphic, frame.width, 32, 177, Math.max(0, ...series.map((row) => row.raw_total).filter(finite)), labels);
  const harm = axis(frame.graphic, frame.width, 260, 401, Math.max(0, ...series.map((row) => row.hhe_total).filter(finite)), labels);
  text(frame.graphic, 58, 18, "Raw detection count");
  text(frame.graphic, 58, 241, "HHE occupancy index");
  const barWidth = Math.min(30, (raw.right - raw.left) / Math.max(1, series.length) * .65);
  series.forEach((row, index) => {
    if (!finite(row.raw_total)) return;
    const x = raw.x(index), modis = row.raw_modis, viirs = row.raw_viirs;
    frame.graphic.append(s("rect", { x: x - barWidth / 2, y: raw.y(modis), width: barWidth, height: raw.y(0) - raw.y(modis), fill: color("modis"), opacity: row.is_complete ? .9 : .45 }));
    frame.graphic.append(s("rect", { x: x - barWidth / 2, y: raw.y(modis + viirs), width: barWidth, height: raw.y(modis) - raw.y(modis + viirs), fill: color("viirs"), opacity: row.is_complete ? .9 : .45 }));
    if (!row.is_complete) text(frame.graphic, x, raw.y(row.raw_total) - 6, "partial", { "text-anchor": "middle" });
  });
  addLine(frame.graphic, series.map((row) => row.hhe_total), harm, color("accent"));
  for (const year of [2012, 2018]) {
    const index = series.findIndex((row) => row.year === year);
    if (index < 0) continue;
    const x = raw.x(index);
    for (const [top, bottom] of [[32, 177], [260, 401]]) frame.graphic.append(s("line", { x1: x, x2: x, y1: top, y2: bottom, stroke: color("subtle"), "stroke-dasharray": "3 4" }));
    text(frame.graphic, x + 4, 31, String(year));
  }
  replace(host, frame.graphic, legend([["MODIS rows", "modis"], ["VIIRS rows", "viirs"], ["HHE · separate axis", "accent"]]));
}
