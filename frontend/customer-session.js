// Share the customer bearer session between Food4Thought's menu and cart pages.
// The token stays in the current tab, while the backend enforces identity and roles.
import { requestJson } from "./api-client.js";

const TOKEN_KEY = "food4thought.customer.token";

export function customerToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function customerRequest(path, options = {}) {
  const token = customerToken();
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  return requestJson(path, { ...options, headers });
}

export function customerError(status, body) {
  if (status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    return "Your session is missing or expired. Sign in again from My account.";
  }
  if (status === 422) {
    return "Invalid input. Use a positive whole-number quantity.";
  }
  return typeof body?.detail === "string" && body.detail
    ? body.detail : `Request failed (HTTP ${status}).`;
}
