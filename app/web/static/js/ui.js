/** DOM construction never interprets uploaded content as markup. */
export const $ = (id) => document.getElementById(id);
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const finite = (value) => typeof value === "number" && Number.isFinite(value);
export const fmt = (value, digits = 1) => finite(value) ? value.toLocaleString("en", { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "—";
export const integer = (value) => finite(value) ? value.toLocaleString("en", { maximumFractionDigits: 0 }) : "—";
export const signed = (value, digits = 2) => finite(value) ? (value >= 0 ? "+" : "") + fmt(value, digits) : "—";
export const percent = (value, digits = 0) => finite(value) ? fmt(value * 100, digits) + "%" : "Unavailable";
export const verdictLabel = (value) => String(value || "Unavailable").toLowerCase().replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
export const unit = (run) => run.calendar.mode === "raw" ? "raw detections" : "HHE index";

function make(namespace, name, attributes, children) {
  const node = namespace ? document.createElementNS(namespace, name) : document.createElement(name);
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  for (const [key, value] of Object.entries(attributes || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "value") node.value = value;
    else if (key === "class") node.setAttribute("class", value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  return node;
}

export const h = (name, attributes = {}, ...children) => make(null, name, attributes, children);
export const s = (name, attributes = {}, ...children) => make("http://www.w3.org/2000/svg", name, attributes, children);
export const replace = (node, ...children) => node.replaceChildren(...children.flat(Infinity));

export function badge(value) {
  const className = { CRITICAL_ANOMALY: "critical", ELEVATED_WATCH: "elevated", NOMINAL_REGIME: "nominal", UNVERIFIABLE: "unverifiable" }[value] || String(value).toLowerCase();
  return h("span", { class: "tag " + className, text: verdictLabel(value) });
}

export function table(headers, rows, { caption = "", numeric = [] } = {}) {
  const node = h("table", { class: "data-table" },
    caption ? h("caption", { text: caption }) : null,
    h("thead", {}, h("tr", {}, headers.map((header) => h("th", { scope: "col", text: header })))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((value, index) => h("td", { class: numeric.includes(index) ? "numeric" : "" }, value ?? "—"))))),
  );
  return node;
}

export function metric(label, value, detail) {
  return h("article", { class: "metric" }, h("p", { class: "eyebrow", text: label }),
    h("strong", { class: "metric-value mono", text: value }), h("p", { class: "small muted", text: detail }));
}

export function utcLabel(iso) {
  return typeof iso === "string" ? iso.replace("T", " ").replace(/:\d\dZ$/, " UTC") : "Unavailable";
}
