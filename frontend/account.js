// Customer account forms use the M2 REST contract. The local demo server can
// provide sign-in presets, and the backend still decides every account's role.
import { setStatus } from "./ui.js";
import { requestJson } from "./api-client.js";
import { saveStaffToken } from "./staff-session.js";

const TOKEN_KEY = "food4thought.customer.token";
const signedOut = document.getElementById("signed-out");
const signedIn = document.getElementById("signed-in");
const sessionStatus = document.getElementById("session-status");
const signInForm = document.getElementById("signin-form");
const registerForm = document.getElementById("register-form");
const profileForm = document.getElementById("profile-form");
const deactivateForm = document.getElementById("deactivate-form");
const refreshButton = document.getElementById("refresh-profile");
const signOutButton = document.getElementById("signout-button");
const pendingForms = new Set();

let token = sessionStorage.getItem(TOKEN_KEY);
let customer = null;
let accountWriting = false;
let demoAccounts = null;
// Compare edits to the actual values shown in the controls (some inputs normalize text).
let profileBaseline = null;
// Each write, logout, and newer read invalidates older in-flight profile reads.
let profileReadVersion = 0;

function feedback(prefix) {
  return {
    status: document.getElementById(`${prefix}-status`),
    errors: document.getElementById(`${prefix}-errors`),
  };
}

function resetErrors(form, errorElement) {
  errorElement.replaceChildren();
  if (form) {
    for (const input of form.querySelectorAll("[aria-invalid]")) {
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");
    }
  }
}

function formValues(form) {
  return Object.fromEntries(
    [...new FormData(form).entries()].filter(([key]) => key !== "confirm")
  );
}

function validCustomer(value) {
  return value && ["id", "name", "email", "delivery_address"].every(
    key => typeof value[key] === "string"
  ) && ["active", "inactive"].includes(value.status);
}

// API validation objects are untrusted data. Render text, not HTML, and never
// repeat submitted password values in an error.
function showErrors(form, errorElement, status, body, action) {
  resetErrors(form, errorElement);
  if (status === 422 && Array.isArray(body?.detail) && body.detail.length) {
    const intro = document.createElement("p");
    intro.textContent = "Please correct the following fields.";
    const list = document.createElement("ul");
    let first = null;
    for (const problem of body.detail) {
      const name = problem.loc?.[1];
      const field = typeof name === "string" ? form?.elements.namedItem(name) : null;
      const label = field ? form.querySelector(`label[for="${field.id}"]`)?.textContent : "Form";
      const item = document.createElement("li");
      item.textContent = `${label || "Form"}: ${name === "password" ? "Check the password requirements." : problem.msg || "Invalid value."}`;
      if (field instanceof HTMLElement) {
        first ||= field;
        field.setAttribute("aria-invalid", "true");
        item.id = `${form.id}-${field.name}-error`;
        field.setAttribute("aria-describedby", item.id);
      }
      list.append(item);
    }
    errorElement.append(intro, list);
    first?.focus();
    return;
  }
  const detail = typeof body?.detail === "string" && body.detail
    ? body.detail
    : `Request failed (HTTP ${status}).`;
  errorElement.textContent = `Could not ${action}: ${detail}`;
}

function wireFieldCorrection(form, errorElement) {
  for (const field of form.querySelectorAll("input, textarea")) {
    field.addEventListener("input", () => {
      if (field.getAttribute("aria-invalid") !== "true") return;
      if (field.name === "password" ? !field.value : !field.value.trim()) return;
      field.removeAttribute("aria-invalid");
      field.removeAttribute("aria-describedby");
      document.getElementById(`${form.id}-${field.name}-error`)?.remove();
      if (!errorElement.querySelector("li")) errorElement.replaceChildren();
    });
  }
}

async function submitOnce(form, elements, progress, operation) {
  if (pendingForms.has(form) || !form.reportValidity()) return;
  const payload = formValues(form);
  pendingForms.add(form);
  const fieldset = form.querySelector("fieldset");
  fieldset.disabled = true;
  form.setAttribute("aria-busy", "true");
  setStatus(elements.status, progress, "loading");
  resetErrors(form, elements.errors);
  try {
    await operation(payload);
  } finally {
    pendingForms.delete(form);
    fieldset.disabled = false;
    form.removeAttribute("aria-busy");
  }
}

function setAccountEditingEnabled() {
  const active = customer?.status === "active";
  document.getElementById("profile-details").hidden = !customer;
  profileForm.hidden = !active;
  deactivateForm.hidden = !active;
  document.getElementById("account-state").textContent =
    customer?.status === "inactive"
      ? "This account is inactive. Profile editing and ordering are disabled."
      : customer ? "Account active." : "Loading your profile…";
}

function showSession() {
  signedOut.hidden = Boolean(token);
  signedIn.hidden = !token;
  setAccountEditingEnabled();
}

function clearAccountView() {
  ++profileReadVersion;
  customer = null;
  profileBaseline = null;
  for (const form of [signInForm, registerForm, profileForm, deactivateForm]) {
    form.reset();
  }
  for (const [form, elements] of [
    [signInForm, signin], [registerForm, register],
    [profileForm, profile], [deactivateForm, deactivate],
    [null, feedback("refresh")],
  ]) {
    setStatus(elements.status, "");
    resetErrors(form, elements.errors);
  }
  for (const id of ["profile-email", "saved-name", "saved-address"]) {
    document.getElementById(id).textContent = "";
  }
  setAccountEditingEnabled();
}

function forgetSession(message) {
  token = null;
  sessionStorage.removeItem(TOKEN_KEY);
  clearAccountView();
  showSession();
  sessionStatus.textContent = message;
}

function displayCustomer(value, replaceFields = false) {
  // An untouched field follows fresh server data; a locally edited field keeps
  // the draft. Capture the browser-normalized value after assigning it.
  const baseline = profileBaseline ?? {};
  for (const name of ["name", "delivery_address"]) {
    const field = profileForm.elements.namedItem(name);
    if (replaceFields || profileBaseline === null || field.value === baseline[name]) {
      field.value = value[name];
      baseline[name] = field.value;
    }
  }
  profileBaseline = baseline;
  customer = value;
  document.getElementById("profile-email").textContent = value.email;
  document.getElementById("saved-name").textContent = value.name;
  document.getElementById("saved-address").textContent = value.delivery_address;
  setAccountEditingEnabled();
}

async function loadProfile(fillForm = false) {
  if (!token) return;
  const currentToken = token;
  const readVersion = ++profileReadVersion;
  const message = feedback("refresh");
  message.status.textContent = "Checking your saved profile…";
  message.errors.textContent = "";
  refreshButton.disabled = true;
  try {
    const result = await requestJson("/customers/me", {
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (token !== currentToken || readVersion !== profileReadVersion) return;
    if (result.status === 401) {
      forgetSession("Your session is missing, invalid or expired. Sign in again.");
      return;
    }
    if (!result.ok) {
      showErrors(null, message.errors, result.status, result.body, "load profile");
      return;
    }
    if (!validCustomer(result.body)) {
      message.errors.textContent = "The profile response was unexpected. Check again before editing.";
      return;
    }
    const firstRead = profileBaseline === null;
    displayCustomer(result.body, fillForm);
    message.status.textContent = fillForm || firstRead
      ? "Profile loaded."
      : "Saved profile checked. Unsaved form entries have not been changed.";
  } catch {
    if (token === currentToken && readVersion === profileReadVersion) {
      message.errors.textContent = "Could not reach the server to check your profile. Try checking again.";
    }
  } finally {
    if (token === currentToken && readVersion === profileReadVersion) {
      refreshButton.disabled = accountWriting;
    }
  }
}

async function protectedRequest(path, options = {}) {
  return requestJson(path, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });
}

function authFailure(result, errors, action) {
  if (result.status === 401) {
    forgetSession("Your session is missing, invalid or expired. Sign in again.");
    return true;
  }
  if (result.status === 403) {
    errors.textContent = "This account is not allowed to make that change. Check the saved profile for its current status.";
    // A status change may have happened on the server. Reading is still allowed.
    void loadProfile(false);
    return true;
  }
  return false;
}

function lockAccountWrites(locked) {
  if (locked) {
    ++profileReadVersion; // A GET issued before this write is stale.
    feedback("refresh").status.textContent = "";
  }
  accountWriting = locked;
  profileForm.querySelector("fieldset").disabled = locked;
  deactivateForm.querySelector("fieldset").disabled = locked;
  refreshButton.disabled = locked;
  signOutButton.disabled = locked;
}

const signin = feedback("signin");
const register = feedback("register");
const profile = feedback("profile");
const deactivate = feedback("deactivate");
for (const [form, elements] of [
  [signInForm, signin], [registerForm, register],
  [profileForm, profile], [deactivateForm, deactivate],
]) wireFieldCorrection(form, elements.errors);

async function loadDemoAccounts() {
  try {
    const result = await requestJson("/demo-accounts");
    if (!result.ok) return;
    const group = document.getElementById("demo-accounts");
    demoAccounts = result.body;
    for (const button of group.querySelectorAll("[data-demo-role]")) {
      const preset = demoAccounts?.[button.dataset.demoRole];
      if (typeof preset?.email !== "string" || typeof preset.password !== "string") continue;
      button.addEventListener("click", () => {
        signInForm.elements.namedItem("email").value = preset.email;
        signInForm.elements.namedItem("password").value = preset.password;
        resetErrors(signInForm, signin.errors);
        setStatus(signin.status, "Demo credentials filled. Select Sign in to continue.");
      });
      button.hidden = false;
      group.hidden = false;
    }
  } catch {
    // Manual sign-in remains available if the optional demo data cannot load.
  }
}

function openDemoStaffPage(body, email) {
  const preset = demoAccounts?.[body.role];
  if (preset?.email !== email.toLowerCase()) return false;
  const destination = body.role === "administrator"
    ? "create-restaurant.html"
    : `edit-restaurant.html?id=${encodeURIComponent(preset.restaurant_id)}`;
  saveStaffToken(body.access_token, body.role);
  signInForm.reset();
  window.location.assign(destination);
  return true;
}

signInForm.addEventListener("submit", async event => {
  event.preventDefault();
  await submitOnce(signInForm, signin, "Signing in…", async values => {
    try {
      const result = await requestJson("/auth/login", {
        method: "POST", payload: values,
      });
      signin.status.textContent = "";
      if (!result.ok) {
        showErrors(signInForm, signin.errors, result.status, result.body, "sign in");
        return;
      }
      const body = result.body;
      if (result.status !== 200 || typeof body?.access_token !== "string" ||
          !body.access_token || body.token_type !== "bearer" || typeof body.role !== "string") {
        signin.errors.textContent = "Sign-in response was unexpected. Try signing in again.";
        return;
      }
      if (body.role !== "customer") {
        if (openDemoStaffPage(body, values.email)) return;
        signin.errors.textContent = "This page is for customer accounts. Use the staff interface for a staff account.";
        return;
      }
      clearAccountView(); // Never carry another session's data or consent forward.
      token = body.access_token;
      sessionStorage.setItem(TOKEN_KEY, token);
      setStatus(sessionStatus, "Signed in.", "success");
      showSession();
      await loadProfile(true);
    } catch {
      signin.status.textContent = "";
      signin.errors.textContent = "Could not confirm sign-in. Check your connection before trying again.";
    }
  });
});

registerForm.addEventListener("submit", async event => {
  event.preventDefault();
  await submitOnce(registerForm, register, "Registering…", async values => {
    try {
      const result = await requestJson("/customers", {
        method: "POST", payload: values,
      });
      setStatus(register.status, "");
      if (!result.ok) {
        showErrors(registerForm, register.errors, result.status, result.body, "register");
        return;
      }
      if (result.status !== 201 || !validCustomer(result.body)) {
        register.errors.textContent = "Could not confirm registration. Try signing in to verify before registering again.";
        return;
      }
      const email = registerForm.elements.namedItem("email").value;
      registerForm.reset();
      signInForm.elements.namedItem("email").value = email;
      setStatus(register.status, "Account created. Sign in using your email and password.", "success");
      signInForm.elements.namedItem("password").focus();
    } catch {
      setStatus(register.status, "");
      register.errors.textContent = "Could not confirm registration. Try signing in to verify before registering again. Your entries are preserved.";
    }
  });
});

profileForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (accountWriting || !customer || !profileBaseline ||
      customer.status !== "active" || !token || !profileForm.reportValidity()) return;
  const changes = {};
  for (const [name, value] of Object.entries(formValues(profileForm))) {
    if (value !== profileBaseline[name]) changes[name] = value;
  }
  if (!Object.keys(changes).length) {
    profile.status.textContent = "No changes to save.";
    profile.errors.replaceChildren();
    return;
  }
  lockAccountWrites(true);
  try {
    await submitOnce(profileForm, profile, "Saving changes…", async () => {
      try {
        const result = await protectedRequest("/customers/me", {
          method: "PATCH", payload: changes,
        });
        setStatus(profile.status, "");
        if (authFailure(result, profile.errors, "save profile")) return;
        if (!result.ok) {
          showErrors(profileForm, profile.errors, result.status, result.body, "save profile");
          return;
        }
        if (result.status !== 200 || !validCustomer(result.body)) {
          profile.errors.textContent = "Could not confirm the update. Check saved profile before submitting again.";
          return;
        }
        displayCustomer(result.body, true);
        setStatus(profile.status, "Profile updated.", "success");
      } catch {
        setStatus(profile.status, "");
        profile.errors.textContent = "Could not confirm the update. Check saved profile before submitting again. Your edits are preserved.";
      }
    });
  } finally {
    lockAccountWrites(false);
    // A denied write may have changed the displayed state while the request ran.
    setAccountEditingEnabled();
  }
});

deactivateForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (accountWriting || !customer || customer.status !== "active" || !token || !deactivateForm.reportValidity()) return;
  lockAccountWrites(true);
  try {
    await submitOnce(deactivateForm, deactivate, "Deactivating account…", async () => {
      try {
        const result = await protectedRequest("/customers/me/deactivate", { method: "POST" });
        setStatus(deactivate.status, "");
        if (authFailure(result, deactivate.errors, "deactivate account")) return;
        if (!result.ok) {
          showErrors(deactivateForm, deactivate.errors, result.status, result.body, "deactivate account");
          return;
        }
        if (result.status !== 200 || !validCustomer(result.body) || result.body.status !== "inactive") {
          deactivate.errors.textContent = "Could not confirm deactivation. Check saved profile before trying again.";
          return;
        }
        displayCustomer(result.body, false);
        document.getElementById("account-state").textContent =
          "Account deactivated. You can still view your profile, but cannot edit it or place orders.";
        setStatus(deactivate.status, "Account deactivated.", "success");
      } catch {
        setStatus(deactivate.status, "");
        deactivate.errors.textContent = "Could not confirm deactivation. Check saved profile before trying again.";
      }
    });
  } finally {
    lockAccountWrites(false);
    setAccountEditingEnabled();
  }
});

refreshButton.addEventListener("click", () => {
  if (!accountWriting) void loadProfile(false);
});
signOutButton.addEventListener("click", () => {
  if (!accountWriting) {
    forgetSession("Signed out of this tab.");
    profileForm.reset();
  }
});

// A failed module import leaves sensitive forms disabled and unable to submit.
signInForm.querySelector("fieldset").disabled = false;
registerForm.querySelector("fieldset").disabled = false;

showSession();
if (token) void loadProfile(true);
else sessionStatus.textContent = "Sign in or create an account below.";
void loadDemoAccounts();
