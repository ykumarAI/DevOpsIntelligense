const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // accounts
  listAccounts: () => request("/accounts"),
  createAccount: (data) =>
    request("/accounts", { method: "POST", body: JSON.stringify(data) }),
  updateAccount: (id, data) =>
    request(`/accounts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAccount: (id) => request(`/accounts/${id}`, { method: "DELETE" }),

  // resources
  listResources: (accountId) =>
    request(`/resources${accountId ? `?account_id=${accountId}` : ""}`),
  createResource: (data) =>
    request("/resources", { method: "POST", body: JSON.stringify(data) }),
  updateResource: (id, data) =>
    request(`/resources/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteResource: (id) => request(`/resources/${id}`, { method: "DELETE" }),

  // monitor
  summary: (accountId) =>
    request(`/monitor/summary${accountId ? `?account_id=${accountId}` : ""}`),
  resourceStatus: (id) => request(`/monitor/resource/${id}`),

  // settings
  getSettings: () => request("/settings"),
  updateSettings: (data) =>
    request("/settings", { method: "PUT", body: JSON.stringify(data) }),

  // gitlab sources
  listGitlab: () => request("/gitlab"),
  createGitlab: (data) =>
    request("/gitlab", { method: "POST", body: JSON.stringify(data) }),
  updateGitlab: (id, data) =>
    request(`/gitlab/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteGitlab: (id) => request(`/gitlab/${id}`, { method: "DELETE" }),
  previewGitlab: (id) => request(`/gitlab/${id}/preview`, { method: "POST" }),
};
