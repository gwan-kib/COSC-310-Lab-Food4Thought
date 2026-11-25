// Share icon markup, status feedback and availability labels across Food4Thought.
// Each page retains ownership of its requests and user interactions.

const SVG_NS = "http://www.w3.org/2000/svg";
const statusIcons = {
  loading: "schedule", empty: "search", success: "check_circle", error: "error", warning: "info",
};

export function icon(name, sprite = "icons.svg") {
  const svg = document.createElementNS(SVG_NS, "svg");
  const use = document.createElementNS(SVG_NS, "use");
  svg.classList.add("icon");
  svg.setAttribute("aria-hidden", "true");
  use.setAttribute("href", sprite + "#" + encodeURIComponent(name));
  svg.append(use);
  return svg;
}

export function setStatus(element, message, tone = "") {
  element.textContent = message;
  const symbol = statusIcons[tone];
  if (message && symbol) element.prepend(icon(symbol));
  element.className = tone ? "status " + tone : "status";
}

export function showAvailability(element, available) {
  element.replaceChildren(icon(available ? "check_circle" : "block"), available ? "Available" : "Unavailable");
  element.className = available ? "badge badge-available" : "badge badge-unavailable";
}
