import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "../components/Modal.jsx";

const EMPTY = {
  name: "",
  mode: "mock",
  profile_name: "",
  region: "us-east-1",
  access_key_id: "",
  secret_access_key: "",
  session_token: "",
};

export default function AccountsPage({ accounts, onChange }) {
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  useEffect(() => {
    if (editing) {
      setForm({
        name: editing.name,
        mode: editing.mode,
        profile_name: editing.profile_name || "",
        region: editing.region,
        access_key_id: "",
        secret_access_key: "",
        session_token: "",
      });
    } else {
      setForm(EMPTY);
    }
  }, [editing]);

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY);
    setError("");
    setShowForm(true);
  };

  const openEdit = (a) => {
    setEditing(a);
    setError("");
    setShowForm(true);
  };

  const submit = async () => {
    setError("");
    try {
      const payload = {
        name: form.name,
        mode: form.mode,
        region: form.region,
        profile_name: form.profile_name || null,
      };
      // Only send credential fields for keys mode; blank = leave unchanged on edit.
      if (form.mode === "keys") {
        if (form.access_key_id) payload.access_key_id = form.access_key_id;
        if (form.secret_access_key) payload.secret_access_key = form.secret_access_key;
        if (form.session_token) payload.session_token = form.session_token;
      }
      if (editing) {
        await api.updateAccount(editing.id, payload);
      } else {
        await api.createAccount(payload);
      }
      setShowForm(false);
      onChange();
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (a) => {
    if (!confirm(`Delete account "${a.name}" and all its resources?`)) return;
    await api.deleteAccount(a.id);
    onChange();
  };

  return (
    <>
      <div className="header-row">
        <div>
          <h1>AWS Accounts</h1>
          <div className="subtitle">
            Configure how the platform connects: mock, a named profile, or the default credential chain.
          </div>
        </div>
        <button className="btn" onClick={openNew}>
          + Add account
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="empty">No accounts yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Mode</th>
              <th>Profile</th>
              <th>Region</th>
              <th>Resources</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>{a.mode}</td>
                <td>{a.profile_name || "—"}</td>
                <td>{a.region}</td>
                <td>{a.resource_count}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <button className="btn ghost sm" onClick={() => openEdit(a)}>
                    Edit
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => remove(a)}>
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
          title={editing ? "Edit account" : "Add AWS account"}
          onClose={() => setShowForm(false)}
        >
          {error && <div className="error-box">{error}</div>}
          <div className="field">
            <label>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Production account"
            />
          </div>
          <div className="form-row">
            <div className="field">
              <label>Mode</label>
              <select
                value={form.mode}
                onChange={(e) => setForm({ ...form, mode: e.target.value })}
              >
                <option value="mock">mock (synthetic data)</option>
                <option value="profile">profile (named AWS profile)</option>
                <option value="env">env (default credential chain)</option>
                <option value="keys">keys (access key / token)</option>
              </select>
            </div>
            <div className="field">
              <label>Region</label>
              <input
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
              />
            </div>
          </div>
          {form.mode === "profile" && (
            <div className="field">
              <label>AWS profile name</label>
              <input
                value={form.profile_name}
                onChange={(e) => setForm({ ...form, profile_name: e.target.value })}
                placeholder="e.g. prod-readonly"
              />
            </div>
          )}
          {form.mode === "keys" && (
            <>
              <div className="field">
                <label>
                  Access key ID{" "}
                  {editing?.has_credentials && (
                    <span className="subtitle" style={{ display: "inline" }}>
                      (stored ****{editing.access_key_last4} — leave blank to keep)
                    </span>
                  )}
                </label>
                <input
                  value={form.access_key_id}
                  onChange={(e) => setForm({ ...form, access_key_id: e.target.value })}
                  placeholder="AKIA..."
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label>Secret access key</label>
                <input
                  type="password"
                  value={form.secret_access_key}
                  onChange={(e) =>
                    setForm({ ...form, secret_access_key: e.target.value })
                  }
                  placeholder={editing?.has_credentials ? "•••••• (leave blank to keep)" : ""}
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label>Session token (optional — for STS/temporary creds)</label>
                <textarea
                  rows={2}
                  value={form.session_token}
                  onChange={(e) => setForm({ ...form, session_token: e.target.value })}
                  autoComplete="off"
                />
              </div>
            </>
          )}
          <p className="subtitle">
            For higher environments (UAT/Prod) prefer a dedicated read-only role or the
            GitLab source (pipeline-collected), rather than personal keys. Credentials are
            stored locally under <span className="mono">~/.devops</span> and never returned
            by the API.
          </p>
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setShowForm(false)}>
              Cancel
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
