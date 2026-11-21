// Keep a staff session in this browser tab and attach its bearer token only to
// explicit restaurant-management writes. The backend alone decides permissions.
import { requestJson } from "./api-client.js";

const TOKEN_KEY = "food4thought.staff.token";

export function staffToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveStaffToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function forgetStaffToken() {
  sessionStorage.removeItem(TOKEN_KEY);
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
