// Same-origin browser module for Jonathan's Django review screen.
// Import from a <script type="module">. Render returned data with textContent, never innerHTML.
let csrfToken;
async function request(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (response.redirected) throw new Error("Sign in to the Django application first.");
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status}).`);
  return data;
}
export async function initializeAI() {
  const session = await request("/api/ai/session/");
  csrfToken = session.csrf_token;
  return session.permissions;
}
export async function extractConference(url, year, options = {}) {
  if (!csrfToken) await initializeAI();
  return request("/api/ai/extract/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
    body: JSON.stringify({ url, ...(year == null ? {} : { year }), ...options })
  });
}
export function listCandidates({ status = "needs_review", page = 1, page_size = 20 } = {}) {
  return request("/api/ai/candidates/?" + new URLSearchParams({ status, page, page_size }));
}
export function getCandidate(id) {
  if (!Number.isSafeInteger(id) || id < 1) throw new Error("A positive candidate ID is required.");
  return request("/api/ai/candidates/" + id + "/");
}
