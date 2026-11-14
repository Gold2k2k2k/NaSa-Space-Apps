/** Shared JSON-generated CSS tokens and linear-sRGB contrast calculations. */
import { finite } from "./ui.js";

const cache = new Map();
export function color(name) {
  const key = "--color-" + name;
  if (!cache.has(key)) cache.set(key, getComputedStyle(document.documentElement).getPropertyValue(key).trim());
  return cache.get(key);
}

export function rampStops(name) {
  return Array.from({ length: 5 }, (_, index) =>
    getComputedStyle(document.documentElement).getPropertyValue("--ramp-" + name + "-" + index).trim());
}

function rgb(hex) {
  return [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
}

export function luminance(hex) {
  const channels = rgb(hex).map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

export function contrastRatio(first, second) {
  const values = [luminance(first), luminance(second)].sort((a, b) => a - b);
  return (values[1] + 0.05) / (values[0] + 0.05);
}

export function interpolate(stops, fraction) {
  const position = Math.max(0, Math.min(1, fraction)) * (stops.length - 1);
  const lower = Math.min(stops.length - 2, Math.floor(position));
  const amount = position - lower;
  const a = rgb(stops[lower]), b = rgb(stops[lower + 1]);
  return "#" + a.map((channel, index) => Math.round(channel + amount * (b[index] - channel)).toString(16).padStart(2, "0")).join("");
}

export function cellColors(cell, maximum, ramp) {
  if (!cell.is_observed || (ramp === "diverging" && !finite(cell.z_robust))) return { bg: color("well"), fg: color("subtle") };
  const fraction = ramp === "diverging" ? (Math.max(-3, Math.min(3, cell.z_robust)) + 3) / 6 :
    maximum > 0 ? Math.sqrt(Math.max(0, cell.value) / maximum) : 0;
  const bg = interpolate(rampStops(ramp), fraction);
  const white = color("white"), black = color("black");
  return { bg, fg: contrastRatio(bg, white) >= contrastRatio(bg, black) ? white : black };
}
