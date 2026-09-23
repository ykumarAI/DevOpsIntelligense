import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "../components/Modal.jsx";

const EMPTY = {
  name: "",
  environment: "",
  base_url: "",
  project: "",
  ref: "main",
  job_name: "",
  artifact_path: "devops-report.json",
  token: "",
  enabled: true,
};

export default function GitLabSourcesPage() {
  const [sources, setSources] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try {
      setSources(await api.listGitlab());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (editing) {
      setForm({ ...editing, token: "" });
    } else {
      setForm(EMPTY);
    }
  }, [editing]);

  const openNew = () => {
    setEditing(null);
    setError("");
    setPreview(null);
    setShowForm(true);
  };

  const openEdit = (s) => {
    setEditing(s);
    setError("");
    setPreview(null);
    setShowForm(true);
  };

  const submit = async () => {
    setError("");
    try {
      const payload = { ...form, environment: form.environment || null };
      if (!payload.token) delete payload.token; // blank = keep existing
      const saved = editing
        ? await api.updateGitlab(editing.id, payload)
        : await api.createGitlab(payload);
      setEditing(saved);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const test = async () => {
    setError("");
    setPreview(null);
    try {
      // Ensure it is saved first so the backend has the token/config.
      if (!editing) {
        await submit();
      }
      const target = editing || sources.find((s) => s.name === form.name);
      if (!target) throw new Error("Save the source first, then test.");
      setPreview(await api.previewGitlab(target.id));
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (s) => {
    if (!confirm(`Delete GitLab source "${s.name}"?`)) return;
    await api.deleteGitlab(s.id);
    load();
  };

  return (
    <>
      <div className="header-row">
        <div>
          <div className="breadcrumb">Sources // GitLab</div>
          <h1>GitLab Sources</h1>
          <div className="subtitle">
            Pull environment status from a read-only CI job artifact — no personal AWS
            access needed. The pipeline collects (via OIDC role); the dashboard only reads.
          </div>
        </div>
        <button className="btn" onClick={openNew}>
          + Add GitLab source
        </button>
      </div>

      {error && !showForm && <div className="error-box">{error}</div>}

      {sources.length === 0 ? (
        <div className="empty">
          No GitLab sources yet. Add one that points at your collector job’s artifact.
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Environment</th>
              <th>Project</th>
              <th>Ref</th>
              <th>Job</th>
              <th>Artifact</th>
              <th>Token</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.environment || "—"}</td>
                <td className="mono">{s.project}</td>
                <td>{s.ref}</td>
                <td className="mono">{s.job_name}</td>
                <td className="mono">{s.artifact_path}</td>
                <td>{s.has_token ? "set" : "—"}</td>
                <td>{s.enabled ? "yes" : "no"}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <button className="btn ghost sm" onClick={() => openEdit(s)}>
                    Edit
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => remove(s)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showForm && (
        <Modal
          title={editing ? "Edit GitLab source" : "Add GitLab source"}
          onClose={() => {
            setShowForm(false);
            load();
          }}
        >
          {error && <div className="error-box">{error}</div>}
          {preview && (
            <div
              className={preview.ok ? "" : "error-box"}
              style={
                preview.ok
                  ? {
                      background: "rgba(22,163,74,.08)",
                      color: "var(--healthy)",
                      border: "1px solid rgba(22,163,74,.25)",
                      borderRadius: 9,
                      padding: "10px 12px",
                      fontSize: 13,
                      marginBottom: 14,
                    }
                  : undefined
              }
            >
              {preview.ok
                ? `✓ Fetched ${preview.resource_count} resources${
                    preview.environment ? ` for ${preview.environment}` : ""
                  }${preview.generated_at ? ` (generated ${preview.generated_at})` : ""}`
                : `Test failed: ${preview.error}`}
            </div>
          )}
          <div className="field">
            <label>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. UAT (via GitLab)"
            />
          </div>
          <div className="form-row">
            <div className="field">
              <label>Environment label (optional)</label>
              <input
                value={form.environment}
                onChange={(e) => setForm({ ...form, environment: e.target.value })}
                placeholder="UAT, PROD…"
              />
            </div>
            <div className="field">
              <label>Ref (branch/tag)</label>
              <input
                value={form.ref}
                onChange={(e) => setForm({ ...form, ref: e.target.value })}
              />
            </div>
          </div>
          <div className="field">
            <label>GitLab base URL</label>
            <input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://gitlab.company.com"
            />
          </div>
          <div className="field">
            <label>Project (numeric ID or group/subgroup/project path)</label>
            <input
              value={form.project}
              onChange={(e) => setForm({ ...form, project: e.target.value })}
              placeholder="1234  or  platform/devops/collector"
            />
          </div>
          <div className="form-row">
            <div className="field">
              <label>Collector job name</label>
              <input
                value={form.job_name}
                onChange={(e) => setForm({ ...form, job_name: e.target.value })}
                placeholder="collect:uat"
              />
            </div>
            <div className="field">
              <label>Artifact path</label>
              <input
                value={form.artifact_path}
                onChange={(e) => setForm({ ...form, artifact_path: e.target.value })}
                placeholder="devops-report-uat.json"
              />
            </div>
          </div>
          <div className="field">
            <label>
              Personal Access Token (read_api)
              {editing?.has_token && (
                <span className="subtitle" style={{ display: "inline" }}>
                  {" "}
                  (stored — leave blank to keep)
                </span>
              )}
            </label>
            <input
              type="password"
              value={form.token}
              onChange={(e) => setForm({ ...form, token: e.target.value })}
              placeholder={editing?.has_token ? "•••••• (leave blank to keep)" : "glpat-..."}
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                style={{ width: "auto", marginRight: 8 }}
              />
              Enabled
            </label>
          </div>
          <div className="modal-actions">
            <button className="btn ghost" onClick={test}>
              Save & test
            </button>
            <button
              className="btn ghost"
              onClick={() => {
                setShowForm(false);
                load();
              }}
            >
              Close
            </button>
            <button className="btn" onClick={submit}>
              {editing ? "Save" : "Create"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
