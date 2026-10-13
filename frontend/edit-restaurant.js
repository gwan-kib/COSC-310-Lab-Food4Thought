// Load a restaurant from the REST API and submit only edited fields through PATCH.
// Keep the stable ID and menu untouched; preserve entered values on validation,
// storage, and uncertain network failures so the user can verify before retrying.

const editForm = document.getElementById("edit-form");
const editFields = document.getElementById("edit-fields");
const editStatus = document.getElementById("edit-status");
const editErrors = document.getElementById("edit-errors");
const returnLink = document.getElementById("return-link");
const retryLoad = document.getElementById("retry-load");

const fieldLabels = { name: "Name", cuisine: "Cuisine", description: "Description" };
const editableFields = Object.fromEntries(
  Object.keys(fieldLabels).map(name => [name, editForm.elements.namedItem(name)])
);
const requestedId = new URLSearchParams(window.location.search).get("id");
const requestTimeoutMs = 15_000;
const uncertainUpdate = "Could not confirm whether changes were saved. Check the restaurant details before trying again.";
let original = null;
let loading = false;
let saving = false;

function clearFieldErrors() {
  editErrors.replaceChildren();
  for (const field of Object.values(editableFields)) {
    field.removeAttribute("aria-invalid");
    field.removeAttribute("aria-describedby");
  }
}

function showFieldErrors(details) {
  const heading = document.createElement("p");
  heading.textContent = "Please correct the following fields.";
  const list = document.createElement("ul");
  let firstInvalid = null;
  for (const detail of details) {
    const name = detail.loc?.[1];
    const field = Object.hasOwn(editableFields, name) ? editableFields[name] : null;
    const item = document.createElement("li");
    item.textContent = `${field ? fieldLabels[name] : "Form"}: ${detail.msg || "Invalid value."}`;
    if (field) {
      item.id = `${name}-edit-error`;
      field.setAttribute("aria-invalid", "true");
      field.setAttribute("aria-describedby", item.id);
      firstInvalid ||= field;
    }
    list.append(item);
  }
  editErrors.append(heading, list);
  return firstInvalid;
}

for (const [name, field] of Object.entries(editableFields)) {
  field.addEventListener("input", () => {
    if (field.getAttribute("aria-invalid") !== "true" || !field.value.trim()) return;
    field.removeAttribute("aria-invalid");
    field.removeAttribute("aria-describedby");
    document.getElementById(`${name}-edit-error`)?.remove();
    if (!editErrors.querySelector("li")) editErrors.replaceChildren();
  });
}

async function fetchWithTimeout(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const response = await fetch(path, {
      ...options,
      signal: controller.signal,
      headers: { Accept: "application/json", ...options.headers },
    });
    let body = null;
    try {
      body = await response.json();
    } catch (error) {
      // An interrupted body read must be handled as a timeout, not a success.
      if (controller.signal.aborted) throw error;
    }
    return { response, body };
  } finally {
    clearTimeout(timer);
  }
}

function validRestaurant(body) {
  return body && body.id === requestedId &&
    ["id", "name", "cuisine", "description"].every(
      key => typeof body[key] === "string" && body[key].length > 0
    );
}

async function loadRestaurant() {
  if (loading || saving || !requestedId) return;
  loading = true;
  original = null;
  editFields.disabled = true;
  returnLink.hidden = true;
  retryLoad.hidden = true;
  clearFieldErrors();
  editStatus.textContent = "Loading restaurant…";

  try {
    const { response, body } = await fetchWithTimeout(
      `/restaurants/${encodeURIComponent(requestedId)}`
    );
    if (!response.ok) {
      if (response.status === 404) throw new Error("That restaurant doesn't exist.");
      const detail = typeof body?.detail === "string" ? body.detail :
        `Request failed (HTTP ${response.status}).`;
      throw new Error(detail);
    }
    if (response.status !== 200 || !validRestaurant(body)) {
      throw new Error("The server returned unexpected restaurant data.");
    }

    original = Object.fromEntries(
      Object.keys(editableFields).map(name => [name, body[name]])
    );
    for (const [name, field] of Object.entries(editableFields)) {
      field.value = original[name];
    }
    returnLink.href = `./#/restaurants/${encodeURIComponent(requestedId)}`;
    returnLink.hidden = false;
    editFields.disabled = false;
    editStatus.textContent = "";
  } catch (error) {
    editStatus.textContent = "";
    editErrors.textContent = `Could not load restaurant: ${error.message || "Could not reach the server."}`;
    retryLoad.hidden = false;
  } finally {
    loading = false;
  }
}

retryLoad.addEventListener("click", loadRestaurant);

editForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (saving || loading || !original || !editForm.reportValidity()) return;

  clearFieldErrors();
  // Sending an empty PATCH is invalid under the adopted API contract.
  const changes = Object.fromEntries(
    Object.entries(editableFields)
      .filter(([name, field]) => field.value !== original[name])
      .map(([name, field]) => [name, field.value])
  );
  if (Object.keys(changes).length === 0) {
    editStatus.textContent = "No changes to save.";
    return;
  }

  saving = true;
  editFields.disabled = true;
  editForm.setAttribute("aria-busy", "true");
  editStatus.textContent = "Saving changes…";
  let focusAfter = null;

  try {
    const { response, body } = await fetchWithTimeout(
      `/restaurants/${encodeURIComponent(requestedId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      }
    );
    editStatus.textContent = "";
    if (!response.ok) {
      if (response.status === 422 && Array.isArray(body?.detail) && body.detail.length) {
        focusAfter = showFieldErrors(body.detail);
      } else {
        const detail = typeof body?.detail === "string" ? body.detail :
          `Request failed (HTTP ${response.status}).`;
        editErrors.textContent = `Could not save restaurant: ${detail}`;
      }
      return;
    }
    if (response.status !== 200 || !validRestaurant(body) ||
        Object.entries(changes).some(([name, value]) => body[name] !== value.trim())) {
      editErrors.textContent = uncertainUpdate;
      return;
    }

    original = Object.fromEntries(
      Object.keys(editableFields).map(name => [name, body[name]])
    );
    for (const [name, field] of Object.entries(editableFields)) {
      field.value = original[name];
    }
    editStatus.textContent = "Changes saved.";
  } catch {
    editStatus.textContent = "";
    editErrors.textContent = uncertainUpdate;
  } finally {
    saving = false;
    editFields.disabled = false;
    editForm.removeAttribute("aria-busy");
    focusAfter?.focus();
  }
});

if (!requestedId) {
  editErrors.textContent = "Select a restaurant from the list before editing.";
} else {
  loadRestaurant();
}
