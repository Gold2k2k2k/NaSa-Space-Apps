/** A local coordinate preview; no external basemap, tiles or geographic claims. */
import { $, finite, fmt, integer, h, s, replace, table } from "./ui.js";
import { color } from "./theme.js";

const wrap = (longitude) => ((longitude + 180) % 360 + 360) % 360 - 180;

export function renderMap(run, draw, addPoint) {
  const host = $("map-viewport"), bounds = run.aoi.bbox;
  const width = Math.max(280, host.clientWidth - 2), height = width / 1.6;
  const center = (bounds.lon_min + bounds.lon_max) / 2;
  const unwrap = (longitude) => longitude + 360 * Math.round((center - longitude) / 360);
  const spanX = Math.max(.001, bounds.lon_max - bounds.lon_min), spanY = Math.max(.001, bounds.lat_max - bounds.lat_min);
  const west = bounds.lon_min - spanX * .1, east = bounds.lon_max + spanX * .1;
  const south = Math.max(-90, bounds.lat_min - spanY * .1), north = Math.min(90, bounds.lat_max + spanY * .1);
  const left = 54, right = width - 14, top = 18, bottom = height - 32;
  const x = (longitude) => left + (unwrap(longitude) - west) / (east - west) * (right - left);
  const y = (latitude) => bottom - (latitude - south) / (north - south) * (bottom - top);
  const graphic = s("svg", { viewBox: "0 0 " + width + " " + height, role: "img",
    "aria-label": "Coordinate preview of the full area geometry and sampled hotspot windows. A data table and GeoJSON input provide keyboard alternatives." },
    s("title", { text: "Full AOI boundary and sampled cell windows" }),
    s("desc", { text: "Longitude and latitude axes. Holes and separate polygon components are preserved. Points show a sample, not burned area. Non-vegetation types use cross symbols." }));
  const ticks = width < 400 ? 2 : 4;
  for (let index = 0; index <= ticks; index++) {
    const longitude = west + index / ticks * (east - west), latitude = south + index / ticks * (north - south);
    graphic.append(s("line", { x1: x(longitude), x2: x(longitude), y1: top, y2: bottom, stroke: color("line") }),
      s("line", { x1: left, x2: right, y1: y(latitude), y2: y(latitude), stroke: color("line") }),
      s("text", { x: x(longitude), y: height - 10, fill: color("subtle"), "font-size": "var(--font-size-caption)", "text-anchor": index === ticks ? "end" : index === 0 ? "start" : "middle", text: fmt(wrap(longitude), 2) + "°" }),
      s("text", { x: left - 5, y: y(latitude) + 4, fill: color("subtle"), "font-size": "var(--font-size-caption)", "text-anchor": "end", text: fmt(latitude, 2) }));
  }
  const geometry = run.aoi.geometry;
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  let path = "";
  for (const polygon of polygons) for (const ring of polygon) {
    path += ring.map(([longitude, latitude], index) => (index ? "L" : "M") + x(longitude) + "," + y(latitude)).join("") + "Z";
  }
  graphic.append(s("path", { d: path, fill: color("accent"), "fill-opacity": .08, "fill-rule": "evenodd", stroke: color("accent"), "stroke-width": 1.5 }));
  const spots = run.map_hotspots || [];
  for (const spot of spots) {
    const tone = spot.source_type ? "excluded" : spot.sensor_family === "MODIS" ? "modis" : spot.sensor_family === "VIIRS" ? "viirs" : "both";
    const px = x(spot.lon), py = y(spot.lat);
    const detail = spot.acq_date + " · " + spot.sensor_family + " · " + spot.fire_category.replaceAll("_", " ").toLowerCase() +
      " · HHE " + fmt(spot.hhe, 2) + " · FRP " + (finite(spot.hfre_mw) ? fmt(spot.hfre_mw) + " MW" : "unavailable") +
      " · " + (spot.include_in_calendar ? "included" : "excluded") + " · " + fmt(spot.lat, 5) + ", " + fmt(spot.lon, 5);
    const node = spot.source_type ? s("path", { d: "M" + (px - 3) + "," + (py - 3) + "L" + (px + 3) + "," + (py + 3) + "M" + (px - 3) + "," + (py + 3) + "L" + (px + 3) + "," + (py - 3), stroke: color(tone), "stroke-width": 1.4 }) :
      s("circle", { cx: px, cy: py, r: spot.year === run.calendar.focus_year && spot.month === run.calendar.focus_month ? 3.5 : 2.2, fill: color(tone), "fill-opacity": .85, stroke: color("well"), "stroke-width": .7 });
    node.append(s("title", { text: detail }));
    node.addEventListener("mouseenter", () => { $("map-hover-readout").textContent = detail; });
    graphic.append(node);
  }
  if (draw.points.length) {
    graphic.append(s("polyline", { points: draw.points.map(([longitude, latitude]) => x(longitude) + "," + y(latitude)).join(" "),
      fill: "none", stroke: color("ember"), "stroke-width": 2, "stroke-dasharray": "5 3" }));
    draw.points.forEach(([longitude, latitude], index) => {
      graphic.append(s("circle", { cx: x(longitude), cy: y(latitude), r: 5, fill: color("ember"), stroke: color("well") }),
        s("text", { x: x(longitude) + 7, y: y(latitude) - 7, fill: color("text"), "font-size": 12, text: index + 1 }));
    });
  }
  if (draw.active) graphic.addEventListener("click", (event) => {
    const rect = graphic.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width * width, py = (event.clientY - rect.top) / rect.height * height;
    if (px < left || px > right || py < top || py > bottom) return;
    const longitude = wrap(west + (px - left) / (right - left) * (east - west));
    const latitude = north - (py - top) / (bottom - top) * (north - south);
    addPoint([Number(longitude.toFixed(6)), Number(latitude.toFixed(6))]);
  });
  replace(host, graphic);
  host.classList.toggle("is-drawing", draw.active);
  $("btn-draw-mode").setAttribute("aria-pressed", String(draw.active));
  $("btn-draw-mode").textContent = draw.active ? "Cancel drawing" : "Draw polygon";
  $("btn-draw-undo").hidden = !draw.active;
  $("btn-draw-apply").hidden = !draw.active;
  $("btn-draw-undo").disabled = !draw.points.length;
  $("btn-draw-apply").disabled = draw.points.length < 3;
  const total = run.sensor_calibration_audit.total_raw_detections - run.sensor_calibration_audit.overpass_duplicates_removed;
  const holes = polygons.reduce((count, polygon) => count + polygon.length - 1, 0);
  $("map-hover-readout").textContent = draw.active ? "Add at least three map points, then use the polygon. GeoJSON paste in Region & period is the keyboard alternative. Points: " + draw.points.length :
    integer(spots.length) + " sampled windows of " + integer(total) + " · " + polygons.length + " polygon component(s), " + holes + " hole(s) · coordinate preview, not burned area.";
  replace($("map-legend"), [["MODIS", "modis"], ["VIIRS", "viirs"], ["Both families", "both"], ["× Non-vegetation type", "excluded"]].map(([label, tone]) =>
    h("span", {}, h("i", { style: "background:" + color(tone), "aria-hidden": "true" }), label)));
  replace($("map-data"), table(["Date", "Latitude", "Longitude", "Family", "HHE", "Source type", "Use"],
    spots.slice(0, 50).map((spot) => [spot.acq_date, fmt(spot.lat, 5), fmt(spot.lon, 5), spot.sensor_family, fmt(spot.hhe, 2), spot.source_type, spot.include_in_calendar ? "Included" : "Excluded"]),
    { caption: "First " + Math.min(50, spots.length) + " sampled windows. Download GeoJSON or CSV for every retained event.", numeric: [1, 2, 4] }));
}
