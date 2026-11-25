// Share feedback and availability styling between Food4Thought's menu views.
// Each page retains ownership of its requests and user interactions.

export function setStatus(element, message, tone = "") {
  element.textContent = message;
  element.className = tone ? "status " + tone : "status";
}

export function showAvailability(element, available) {
  element.textContent = available ? "Available" : "Unavailable";
  element.className = available ? "badge badge-available" : "badge badge-unavailable";
}
