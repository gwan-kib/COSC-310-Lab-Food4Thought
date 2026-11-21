// Sign staff into Food4Thought through the shared role-aware login API.
 // Redirect only to known local management pages; never place credentials or
 // tokens in the URL or expose backend authorization decisions in the browser.
import { requestJson } from "./api-client.js";
import { saveStaffToken } from "./staff-session.js";

const form = document.getElementById("staff-signin-form");
const fieldset = document.getElementById("staff-signin-fields");
const status = document.getElementById("staff-signin-status");
const errors = document.getElementById("staff-signin-errors");
const email = form.elements.namedItem("email");
const password = form.elements.namedItem("password");
let pending = false;

function returnTarget() {
  const candidate = new URLSearchParams(location.search).get("next") || "create-restaurant.html";
  const target = new URL(candidate, location.href);
  const create = new URL("create-restaurant.html", location.href);
  const edit = new URL("edit-restaurant.html", location.href);
  if (target.origin !== location.origin) return create.pathname;
  if (target.pathname === create.pathname) return create.pathname;
  if (target.pathname === edit.pathname) {
    const id = target.searchParams.get("id");
    return edit.pathname + (id ? `?id=${encodeURIComponent(id)}` : "");
  }
  return create.pathname;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (pending || !form.reportValidity()) return;

  pending = true;
  fieldset.disabled = true;
  form.setAttribute("aria-busy", "true");
  errors.textContent = "";
  status.textContent = "Signing in…";
  const submittedPassword = password.value;
  try {
    const response = await requestJson("/auth/login", {
      method: "POST", payload: { email: email.value, password: submittedPassword },
    });
    status.textContent = "";
    if (!response.ok) {
      errors.textContent = response.status === 401
        ? "Invalid email or password."
        : `Could not sign in (HTTP ${response.status}).`;
      return;
    }
    const body = response.body;
    if (response.status !== 200 || typeof body?.access_token !== "string" ||
        !body.access_token || body.token_type !== "bearer" || typeof body.role !== "string") {
      errors.textContent = "Sign-in response was unexpected. Try signing in again.";
      return;
    }
    saveStaffToken(body.access_token);
    status.textContent = "Signed in. Opening restaurant management…";
    window.location.assign(returnTarget());
  } catch {
    status.textContent = "";
    errors.textContent = "Could not complete sign-in. Check your connection and try again.";
  } finally {
    password.value = "";
    pending = false;
    fieldset.disabled = false;
    form.removeAttribute("aria-busy");
  }
});
