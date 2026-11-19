// Send Food4Thought's JSON REST requests through one transport. Return the
// HTTP outcome to the page so it can decide what to display and whether to retry.

export async function requestJson(path, { method = "GET", payload, timeoutMs = 15_000 } = {}) {
  const headers = { Accept: "application/json" };
  const options = { method, headers };
  if (payload !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }

  const controller = timeoutMs === null ? null : new AbortController();
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  try {
    const response = await fetch(path, { ...options, signal: controller?.signal });
    let body = null;
    try {
      body = await response.json();
    } catch (error) {
      // Keep the HTTP status for non-JSON responses, but propagate a timeout
      // during the body read so the page can handle an unconfirmed write.
      if (controller?.signal.aborted) throw error;
    }
    return { ok: response.ok, status: response.status, body };
  } finally {
    clearTimeout(timer);
  }
}
