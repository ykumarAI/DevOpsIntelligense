import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function SettingsPage({ accounts, onSaved }) {
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setForm(await api.getSettings());
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const save = async () => {
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateSettings({
        default_account_id: form.default_account_id
          ? Number(form.default_account_id)
          : null,
        refresh_interval_seconds: Number(form.refresh_interval_seconds),
        default_status_filter: form.default_status_filter || "all",
        image_check_interval_seconds: Number(form.image_check_interval_seconds),
      });
      setForm(updated);
      setSaved(true);
      onSaved?.(updated);
    } catch (e) {
      setError(e.message);
    }
  };

  if (!form) {
    return (
      <>
        <div className="header-row">
          <div>
            <div className="breadcrumb">Preferences // Settings</div>
            <h1>Settings</h1>
          </div>
        </div>
        {error ? <div className="error-box">{error}</div> : <div className="subtitle">Loading…</div>}
      </>
    );
  }

  return (
    <>
      <div className="header-row">
        <div>
          <div className="breadcrumb">Preferences // Settings</div>
          <h1>Settings</h1>
          <div className="subtitle">Personalize defaults for the dashboard.</div>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {saved && (
        <div
          style={{
            background: "rgba(22,163,74,.08)",
            color: "var(--healthy)",
            border: "1px solid rgba(22,163,74,.25)",
            borderRadius: 9,
            padding: "10px 12px",
            fontSize: 13,
            marginBottom: 14,
          }}
        >
          ✓ Settings saved.
        </div>
      )}

      <div style={{ maxWidth: 560 }}>
        <div className="card" style={{ padding: 20 }}>
          <div className="field">
            <label>Default environment / account</label>
            <select
              value={form.default_account_id ?? ""}
              onChange={(e) =>
                setForm({ ...form, default_account_id: e.target.value || null })
              }
            >
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="field">
              <label>Auto-refresh interval (seconds)</label>
              <input
                type="number"
                min={5}
                max={3600}
                value={form.refresh_interval_seconds}
                onChange={(e) =>
                  setForm({ ...form, refresh_interval_seconds: e.target.value })
                }
              />
            </div>
            <div className="field">
              <label>Default status filter</label>
              <select
                value={form.default_status_filter || "all"}
                onChange={(e) =>
                  setForm({ ...form, default_status_filter: e.target.value })
                }
              >
                <option value="all">All statuses</option>
                <option value="critical">Critical only</option>
                <option value="warning">Warning only</option>
                <option value="healthy">Healthy only</option>
                <option value="unknown">Unknown only</option>
              </select>
            </div>
          </div>

          <div className="field">
            <label>Image monitor check interval (seconds)</label>
            <input
              type="number"
              min={60}
              max={86400}
              value={form.image_check_interval_seconds ?? 1800}
              onChange={(e) =>
                setForm({
                  ...form,
                  image_check_interval_seconds: e.target.value,
                })
              }
            />
            <div className="subtitle" style={{ marginTop: 6 }}>
              How often the background scheduler evaluates production image
              monitors (ECS → ECR → GitLab).
            </div>
          </div>

          <div className="modal-actions">
            <button className="btn" onClick={save}>
              Save settings
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
