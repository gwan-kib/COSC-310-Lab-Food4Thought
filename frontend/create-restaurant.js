// Submit Food4Thought's Create restaurant form to the API, which owns validation and
// persistence. Manage accessible feedback and pending submissions while preserving
// input on failures; an unconfirmed POST is never retried automatically because the
// server may already have saved it.

import { setStatus } from "./ui.js";
import { managementError, staffRequest, staffRestriction, staffSignInHref } from "./staff-session.js";

document.getElementById("staff-signin-link").href = staffSignInHref();
const form = document.getElementById("create-form");
const fieldset = document.getElementById("create-fields");
const status = document.getElementById("create-status");
const errors = document.getElementById("create-errors");
const createdLink = document.getElementById("created-link");
const labels = { name: "Name", cuisine: "Cuisine", description: "Description" };
const fields = Object.fromEntries(
  Object.keys(labels).map(name => [name, form.elements.namedItem(name)])
);
let submitting = false;

function updateAccess() {
  const restriction = staffRestriction("administrator");
  document.getElementById("create-access").textContent = restriction;
  fieldset.disabled = Boolean(restriction) || submitting;
}

updateAccess();

// A lost POST response does not tell us whether the server saved the record.
const uncertainOutcome = "Could not confirm creation. Check the restaurant list before trying again to avoid creating a duplicate.";

function showValidation(details) {
  const summary = document.createElement("p");
  summary.textContent = "Please correct the following fields.";
  const list = document.createElement("ul");
  let firstInvalid = null;
  for (const detail of details) {
    const name = detail.loc?.[1];
    const field = Object.hasOwn(fields, name) ? fields[name] : null;
    const item = document.createElement("li");
    item.textContent = `${field ? labels[name] : "Form"}: ${detail.msg || "Invalid value."}`;
    if (field) {
      item.id = `${name}-error`;
      field.setAttribute("aria-invalid", "true");
      field.setAttribute("aria-describedby", item.id);
      firstInvalid ||= field;
    }
    list.append(item);
  }
  errors.append(summary, list);
  return firstInvalid;
}

for (const [name, field] of Object.entries(fields)) {
  field.addEventListener("input", () => {
    // These three text fields require nonblank values; the API still validates on submit.
    if (field.getAttribute("aria-invalid") !== "true" || !field.value.trim()) return;
    field.removeAttribute("aria-invalid");
    field.removeAttribute("aria-describedby");
    document.getElementById(`${name}-error`)?.remove();
    if (!errors.querySelector("li")) errors.replaceChildren();
  });
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (fieldset.disabled || !form.reportValidity()) return;

  errors.replaceChildren();
  createdLink.hidden = true;
  createdLink.removeAttribute("href");
  for (const field of Object.values(fields)) {
    field.removeAttribute("aria-invalid");
    field.removeAttribute("aria-describedby");
  }
  // Send the entered values; the existing backend owns trimming and validation.
  const payload = Object.fromEntries(
    Object.entries(fields).map(([name, field]) => [name, field.value])
  );
  submitting = true;
  fieldset.disabled = true;
  form.setAttribute("aria-busy", "true");
  setStatus(status, "Creating restaurant…", "loading");
  let focusAfter = null;

  try {
    const { ok, status: statusCode, body } = await staffRequest("/restaurants", {
      method: "POST", payload,
    });
    status.textContent = "";
    if (!ok) {
      if (statusCode === 422 && Array.isArray(body?.detail) && body.detail.length) {
        focusAfter = showValidation(body.detail);
      } else {
        const detail = managementError(statusCode, body);
        errors.textContent = `Could not create restaurant: ${detail}`;
      }
      return;
    }
    if (statusCode !== 201 || !body || !["id", "name", "cuisine", "description"].every(
      name => typeof body[name] === "string" && body[name].length > 0
    )) {
      errors.textContent = uncertainOutcome;
      return;
    }
    createdLink.href = `./#/restaurants/${encodeURIComponent(body.id)}`;
    setStatus(status, `Created restaurant: ${body.name}.`, "success");
    createdLink.hidden = false;
    form.reset();
    focusAfter = fields.name;
  } catch {
    status.textContent = "";
    errors.textContent = uncertainOutcome;
  } finally {
    submitting = false;
    updateAccess();
    form.removeAttribute("aria-busy");
    focusAfter?.focus();
  }
});
