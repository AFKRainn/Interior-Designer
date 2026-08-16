const jsonHeaders = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const res = await fetch(path, options);
  const raw = await res.text();
  let body = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    if (body && body.detail != null) {
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } else if (raw) {
      detail = raw;
    }
    throw new Error(detail);
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),
  createSession: () => request("/api/session", { method: "POST" }),
  demo: () => request("/api/session/demo", { method: "POST" }),
  get: (id) => request(`/api/session/${id}`),
  briefStart: (id, text, images = []) =>
    request(`/api/session/${id}/brief/start`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ text, images }),
    }),
  briefReply: (id, text, images = []) =>
    request(`/api/session/${id}/brief/reply`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ text, images }),
    }),
  buildSpec: (id) =>
    request(`/api/session/${id}/spec/build`, { method: "POST" }),
  patchSpec: (id, text) =>
    request(`/api/session/${id}/spec/patch`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ text }),
    }),
  bayWidth: (id, wall_id, bay_id, width) =>
    request(`/api/session/${id}/spec/bay-width`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ wall_id, bay_id, width }),
    }),
  divider: (id, wall_id, left_bay_id, delta_cm) =>
    request(`/api/session/${id}/spec/divider`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ wall_id, left_bay_id, delta_cm }),
    }),
  lock: (id) => request(`/api/session/${id}/lock`, { method: "POST" }),
  renderAll: (id) => request(`/api/session/${id}/render`, { method: "POST" }),
  renderShot: (id, shotId) =>
    request(`/api/session/${id}/render/${shotId}`, { method: "POST" }),
};
