// Keep a staff session in this browser tab and attach its bearer token only to
// explicit restaurant-management writes. The backend alone decides permissions.
import { requestJson } from "./api-client.js";

const TOKEN_KEY = "food4thought.staff.token";
const ROLE_KEY = "food4thought.staff.role";

export function staffToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveStaffToken(token, role) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(ROLE_KEY, role);
}

export function staffRestriction(requiredRole) {
  if (!staffToken()) return "Sign in with a staff account to make changes.";
  const role = sessionStorage.getItem(ROLE_KEY);
  // Older tabs may have a token without a role. The API still checks every write.
  if (!role || role === requiredRole) return "";
  return requiredRole === "administrator"
    ? "Only an administrator can create restaurants."
    : "Only a restaurant manager can change restaurant details and availability.";
}

export function forgetStaffToken() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROLE_KEY);
}

export function staffRequest(path, options = {}) {
  const token = staffToken();
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  return requestJson(path, { ...options, headers });
}

export function managementError(status, body) {
  if (status === 401) {
    forgetStaffToken();
    return "Your staff session is missing or expired; sign in again.";
  }
  if (status === 403) return "Operation not permitted.";
  return typeof body?.detail === "string" && body.detail
    ? body.detail : `Request failed (HTTP ${status}).`;
}

export function staffSignInHref() {
  const current = window.location.pathname.split("/").pop();
  const destination = ["create-restaurant.html", "edit-restaurant.html"].includes(current)
    ? current + window.location.search : "create-restaurant.html";
  return `staff-sign-in.html?next=${encodeURIComponent(destination)}`;
}
