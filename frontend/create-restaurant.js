// Connect Food4Thought's management form to the restaurant-creation API and display the
// saved result.
// It manages field errors and submission state, preserves values on failures, and
// handles uncertain or timed-out responses without automatically retrying a POST.

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

// A lost POST response does not tell us whether the server saved the record.
const uncertainOutcome = "Could not confirm creation. Check the restaurant list before trying again to avoid creating a duplicate.";
const requestTimeoutMs = 15_000;

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
  if (submitting || !form.reportValidity()) return;

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
  status.textContent = "Creating restaurant…";
  let focusAfter = null;
  const controller = new AbortController();
  // Bound both the request and response-body read; cancellation cannot undo a save.
  const timeout = setTimeout(() => controller.abort(), requestTimeoutMs);

  try {
    const response = await fetch("/restaurants", {
      signal: controller.signal,
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    let body = null;
    try {
      body = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      // Non-JSON failures still need useful feedback, without erasing input.
    }
    status.textContent = "";
    if (!response.ok) {
      if (response.status === 422 && Array.isArray(body?.detail) && body.detail.length) {
        focusAfter = showValidation(body.detail);
      } else {
        const detail = typeof body?.detail === "string" ? body.detail : `Request failed (HTTP ${response.status}).`;
        errors.textContent = `Could not create restaurant: ${detail}`;
      }
      return;
    }
    if (response.status !== 201 || !body || !["id", "name", "cuisine", "description"].every(
      name => typeof body[name] === "string" && body[name].length > 0
    )) {
      errors.textContent = uncertainOutcome;
      return;
    }
    createdLink.href = `./#/restaurants/${encodeURIComponent(body.id)}`;
    status.textContent = `Created restaurant: ${body.name}.`;
    createdLink.hidden = false;
    form.reset();
    focusAfter = fields.name;
  } catch {
    status.textContent = "";
    errors.textContent = uncertainOutcome;
  } finally {
    clearTimeout(timeout);
    submitting = false;
    fieldset.disabled = false;
    form.removeAttribute("aria-busy");
    focusAfter?.focus();
  }
});
