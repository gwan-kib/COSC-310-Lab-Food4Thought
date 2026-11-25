// Load Food4Thought's selected restaurant through the API and send only changed
// fields with PATCH. Compare against values displayed by the form controls, preserve
// edits on failures, and manage the selected restaurant's menu availability.
// The backend decides whether the signed-in staff member may change the restaurant.

import { requestJson } from "./api-client.js";
import { managementError, staffRequest, staffRestriction, staffSignInHref } from "./staff-session.js";
import { setStatus, showAvailability } from "./ui.js";

document.getElementById("staff-signin-link").href = staffSignInHref();
const editForm = document.getElementById("edit-form");
const editFields = document.getElementById("edit-fields");
const editStatus = document.getElementById("edit-status");
const editErrors = document.getElementById("edit-errors");
const returnLink = document.getElementById("return-link");
const retryLoad = document.getElementById("retry-load");
const menuPanel = document.getElementById("menu-management");
const menuList = document.getElementById("management-menu");
const menuFeedback = document.getElementById("availability-feedback");
const accessFeedback = document.getElementById("edit-access");

const fieldLabels = { name: "Name", cuisine: "Cuisine", description: "Description" };
const editableFields = Object.fromEntries(
  Object.keys(fieldLabels).map(name => [name, editForm.elements.namedItem(name)])
);
const requestedId = new URLSearchParams(window.location.search).get("id");
const uncertainUpdate = "Could not confirm whether changes were saved. Check the restaurant details before trying again.";
let original = null;
let loading = false;
let saving = false;
let denied = "";

function updateAccess() {
  const restriction = denied || staffRestriction("restaurant_user");
  accessFeedback.textContent = restriction;
  editFields.disabled = Boolean(restriction) || !original || saving;
  if (restriction) {
    for (const action of menuList.querySelectorAll("button")) action.hidden = true;
  }
  return restriction;
}

function recordDenial(status) {
  if (status === 403) {
    denied = "Operation not permitted. Only a manager assigned to this restaurant can make changes.";
  }
  updateAccess();
}

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

function validRestaurant(body) {
  return body && body.id === requestedId &&
    ["id", "name", "cuisine", "description"].every(
      key => typeof body[key] === "string" && body[key].length > 0
    );
}

function populateFields(restaurant) {
  for (const [name, field] of Object.entries(editableFields)) {
    field.value = restaurant[name];
  }
  // Browser controls can normalize the API text (e.g., CRLF or newlines).
  // Compare edits with what was actually displayed, not the raw API value.
  original = Object.fromEntries(
    Object.entries(editableFields).map(([name, field]) => [name, field.value])
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
    const { ok, status, body } = await requestJson(
      `/restaurants/${encodeURIComponent(requestedId)}`
    );
    if (!ok) {
      if (status === 404) throw new Error("That restaurant doesn't exist.");
      const detail = typeof body?.detail === "string" ? body.detail :
        `Request failed (HTTP ${status}).`;
      throw new Error(detail);
    }
    if (status !== 200 || !validRestaurant(body)) {
      throw new Error("The server returned unexpected restaurant data.");
    }

    populateFields(body);
    returnLink.href = `./#/restaurants/${encodeURIComponent(requestedId)}`;
    returnLink.hidden = false;
    updateAccess();
    editStatus.textContent = "";
    loadMenu();
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
  if (editFields.disabled || !editForm.reportValidity()) return;

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
    const { ok, status, body } = await staffRequest(
      `/restaurants/${encodeURIComponent(requestedId)}`,
      {
        method: "PATCH",
        payload: changes,
      }
    );
    editStatus.textContent = "";
    if (!ok) {
      if (status === 422 && Array.isArray(body?.detail) && body.detail.length) {
        focusAfter = showFieldErrors(body.detail);
      } else {
        const detail = managementError(status, body);
        editErrors.textContent = `Could not save restaurant: ${detail}`;
        recordDenial(status);
      }
      return;
    }
    // The API owns whitespace normalization; JavaScript trim() differs from
    // Pydantic (including for U+0085). Trust the validated 200 response.
    if (status !== 200 || !validRestaurant(body)) {
      editErrors.textContent = uncertainUpdate;
      return;
    }

    populateFields(body);
    setStatus(editStatus, "Changes saved.", "success");
  } catch {
    editStatus.textContent = "";
    editErrors.textContent = uncertainUpdate;
  } finally {
    saving = false;
    updateAccess();
    editForm.removeAttribute("aria-busy");
    focusAfter?.focus();
  }
});

function renderMenuItem(menuItem, menuPath, readOnly) {
  const row = document.createElement("li");
  const name = document.createElement("strong");
  const controls = document.createElement("div");
  const availability = document.createElement("span");
  const action = document.createElement("button");

  name.textContent = menuItem.name;
  controls.className = "management-menu-controls";
  action.type = "button";
  action.hidden = readOnly;
  function render() {
    showAvailability(availability, menuItem.available);
    action.textContent = menuItem.available ? "Mark unavailable" : "Mark available";
    action.setAttribute("aria-label", action.textContent + " for " + menuItem.name);
  }
  render();

  action.addEventListener("click", async () => {
    if (action.disabled || updateAccess()) return;
    action.disabled = true;
    setStatus(menuFeedback, "Saving availability.", "loading");
    const uncertain = "Could not confirm availability. Reload the menu before trying again.";
    try {
      const response = await staffRequest(menuPath + "/items/" + encodeURIComponent(menuItem.id), {
        method: "PATCH", payload: { available: !menuItem.available },
      });
      if (!response.ok) {
        setStatus(menuFeedback, managementError(response.status, response.body), "error");
        recordDenial(response.status);
        action.disabled = false;
        return;
      }
      const item = response.body;
      if (response.status !== 200 || item?.id !== menuItem.id || typeof item.available !== "boolean") {
        throw new Error(uncertain);
      }
      menuItem.available = item.available;
      render();
      action.disabled = false;
      setStatus(menuFeedback, "Availability saved.", "success");
    } catch {
      // A write may have reached the server before the response failed.
      setStatus(menuFeedback, uncertain, "error");
    }
  });
  controls.append(availability, action);
  row.append(name, controls);
  return row;
}

async function loadMenu() {
  const menuPath = "/restaurants/" + encodeURIComponent(requestedId) + "/menu";
  menuPanel.hidden = false;
  setStatus(menuFeedback, "Loading menu.", "loading");
  try {
    const { ok, body } = await requestJson(menuPath);
    if (!ok || !Array.isArray(body?.items)) {
      throw new Error(typeof body?.detail === "string" ? body.detail : "The menu could not be read.");
    }
    const readOnly = Boolean(updateAccess());
    menuList.replaceChildren(...body.items.map(item => renderMenuItem(item, menuPath, readOnly)));
    setStatus(menuFeedback, body.items.length ? "" : "This restaurant has no menu items yet.", "empty");
  } catch (error) {
    setStatus(menuFeedback, "Could not load the menu: " + error.message, "error");
  }
}

updateAccess();
if (!requestedId) {
  editErrors.textContent = "Select a restaurant from the list before editing.";
} else {
  loadRestaurant();
}
