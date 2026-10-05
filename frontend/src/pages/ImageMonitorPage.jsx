import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "../components/Modal.jsx";

const EMPTY = {
  name: "",
  application: "",
  account_id: "",
  ecs_cluster: "",
  ecs_service: "",
  ecr_repository: "",
  region: "",
  gitlab_source_id: "",
  image_tag_prefix: "",
  retention_count: "",
  warn_threshold: 3,
  webhook_url: "",
  enabled: true,
};

const humanize = (k) => k.replace(/_/g, " ");
const fmtDate = (s) => (s ? new Date(s).toLocaleString() : "—");

function RetentionBar({ position, retained }) {
  if (!position || !retained) return null;
  const slots = Array.from({ length: retained }, (_, i) => i + 1);
  return (
    <div className="retention-bar" title={`position ${position} of ${retained}`}>
      {slots.map((n) => {
        const isDeployed = n === position;
        const cls = isDeployed
          ? "slot deployed"
          : n > retained
          ? "slot gone"
          : "slot";
        return <span key={n} className={cls} />;
      })}
    </div>
  );
}

export default function ImageMonitorPage({ accounts }) {
  const [monitors, setMonitors] = useState([]);
  const [gitlabSources, setGitlabSources] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setMonitors(await api.listImageMonitors());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
    api
      .listGitlab()
      .then(setGitlabSources)
      .catch(() => setGitlabSources([]));
  }, [load]);

  useEffect(() => {
    if (editing) {
      setForm({
        ...EMPTY,
        ...editing,
        account_id: editing.account_id ?? "",
        gitlab_source_id: editing.gitlab_source_id ?? "",
        region: editing.region ?? "",
        image_tag_prefix: editing.image_tag_prefix ?? "",
        retention_count: editing.retention_count ?? "",
        webhook_url: "",
      });
    } else {
      setForm(EMPTY);
    }
  }, [editing]);

  const openNew = () => {
    setEditing(null);
    setError("");
    setShowForm(true);
  };

  const openEdit = (m) => {
    setEditing(m);
    setError("");
    setShowForm(true);
  };

  const submit = async () => {
    setError("");
    try {
      const payload = {
        ...form,
        account_id: form.account_id === "" ? null : Number(form.account_id),
        gitlab_source_id:
          form.gitlab_source_id === "" ? null : Number(form.gitlab_source_id),
        region: form.region || null,
        image_tag_prefix: form.image_tag_prefix || null,
        retention_count:
          form.retention_count === "" ? null : Number(form.retention_count),
        warn_threshold: Number(form.warn_threshold) || 3,
      };
      if (!payload.webhook_url) delete payload.webhook_url; // blank = keep existing
      const saved = editing
        ? await api.updateImageMonitor(editing.id, payload)
        : await api.createImageMonitor(payload);
      setEditing(saved);
      await load();
      setShowForm(false);
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (m) => {
    if (!confirm(`Delete image monitor "${m.name}"?`)) return;
    await api.deleteImageMonitor(m.id);
    load();
  };

  const check = async (m) => {
    setBusy(true);
    setError("");
    setResult(null);
    setAlerts([]);
    try {
      const res = await api.checkImageMonitor(m.id);
      setResult(res);
      try {
        setAlerts(await api.imageMonitorAlerts(m.id));
      } catch {
        /* ignore */
      }
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const checkAll = async () => {
    setBusy(true);
    setError("");
    try {
      await api.checkAllImageMonitors();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="header-row">
        <div>
          <div className="breadcrumb">Operations // Image Monitoring</div>
          <h1>Production Image Monitoring</h1>
          <div className="subtitle">
            Trace each production service's deployed image across ECS → ECR →
            GitLab and get an early warning before it is pruned by the ECR
            lifecycle policy.
          </div>
        </div>
        <div className="header-badges">
          <button className="btn ghost" onClick={checkAll} disabled={busy}>
            {busy ? "Checking…" : "Check all now"}
          </button>
          <button className="btn" onClick={openNew}>
            + Add monitor
          </button>
        </div>
      </div>

      {error && !showForm && <div className="error-box">{error}</div>}

      {monitors.length === 0 ? (
        <div className="empty">
          No image monitors yet. Add one that points at a production ECS service
          and its ECR repository.
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Application</th>
              <th>ECS service</th>
              <th>ECR repo</th>
              <th>Risk</th>
              <th>Position</th>
              <th>Last checked</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {monitors.map((m) => (
              <tr key={m.id}>
                <td>{m.name}</td>
                <td>{m.application}</td>
                <td className="mono">
                  {m.ecs_cluster}/{m.ecs_service}
                </td>
                <td className="mono">{m.ecr_repository}</td>
                <td>
                  {m.last_risk ? (
                    <span className={`pill ${m.last_risk}`}>{m.last_risk}</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{m.last_position ?? "—"}</td>
                <td>{fmtDate(m.last_checked_at)}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <button
                    className="btn ghost sm"
                    onClick={() => check(m)}
                    disabled={busy}
                  >
                    Check
                  </button>{" "}
                  <button className="btn ghost sm" onClick={() => openEdit(m)}>
                    Edit
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => remove(m)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {result && (
        <Modal
          title={`${result.name} · chain`}
          onClose={() => {
            setResult(null);
            setAlerts([]);
          }}
        >
          <div style={{ marginBottom: 14 }}>
            <span className={`pill ${result.risk}`}>{result.risk}</span>{" "}
            <span className="subtitle">{result.summary}</span>
          </div>
          {result.error && <div className="error-box">{result.error}</div>}

          <RetentionBar
            position={result.ecr.position}
            retained={result.ecr.retained}
          />

          <h2 style={{ marginTop: 18 }}>ECS production service</h2>
          <div className="kv">
            <div className="k">Cluster / service</div>
            <div className="v mono">
              {result.ecs.cluster}/{result.ecs.service}
            </div>
            <div className="k">Task definition</div>
            <div className="v mono">{result.ecs.task_definition || "—"}</div>
            <div className="k">Image tag</div>
            <div className="v mono">{result.ecs.image_tag || "—"}</div>
            <div className="k">Image digest</div>
            <div className="v mono">{result.ecs.image_digest || "—"}</div>
            <div className="k">Tasks</div>
            <div className="v">
              {result.ecs.running_count ?? "—"}/{result.ecs.desired_count ?? "—"}
            </div>
            {result.ecs.error && (
              <>
                <div className="k">Error</div>
                <div className="v">{result.ecs.error}</div>
              </>
            )}
          </div>

          <h2 style={{ marginTop: 18 }}>ECR lifecycle position</h2>
          <div className="kv">
            <div className="k">Repository</div>
            <div className="v mono">{result.ecr.repository}</div>
            <div className="k">Position</div>
            <div className="v">
              {result.ecr.position ?? "—"} of {result.ecr.retained ?? "—"} retained
            </div>
            <div className="k">Slots remaining</div>
            <div className="v">{result.ecr.slots_remaining ?? "—"}</div>
            <div className="k">Total images</div>
            <div className="v">{result.ecr.total_images ?? "—"}</div>
            <div className="k">Retention source</div>
            <div className="v">{result.ecr.lifecycle_source || "—"}</div>
            <div className="k">Pushed at</div>
            <div className="v">{fmtDate(result.ecr.pushed_at)}</div>
            {result.ecr.error && (
              <>
                <div className="k">Error</div>
                <div className="v">{result.ecr.error}</div>
              </>
            )}
          </div>

          <h2 style={{ marginTop: 18 }}>GitLab build</h2>
          {result.gitlab.found ? (
            <div className="kv">
              <div className="k">Pipeline</div>
              <div className="v">
                {result.gitlab.pipeline_url ? (
                  <a href={result.gitlab.pipeline_url} target="_blank" rel="noreferrer">
                    #{result.gitlab.pipeline_id}
                  </a>
                ) : (
                  `#${result.gitlab.pipeline_id ?? "—"}`
                )}{" "}
                {result.gitlab.pipeline_status && `(${result.gitlab.pipeline_status})`}
              </div>
              <div className="k">Created</div>
              <div className="v">{fmtDate(result.gitlab.created_at)}</div>
              <div className="k">Commit</div>
              <div className="v mono">
                {result.gitlab.commit_url ? (
                  <a href={result.gitlab.commit_url} target="_blank" rel="noreferrer">
                    {(result.gitlab.commit_id || "").slice(0, 12)}
                  </a>
                ) : (
                  (result.gitlab.commit_id || "—").slice(0, 12)
                )}
              </div>
              <div className="k">Ref</div>
              <div className="v mono">{result.gitlab.ref || "—"}</div>
            </div>
          ) : (
            <div className="subtitle">
              {result.gitlab.error || "No GitLab source linked to this monitor."}
            </div>
          )}

          {alerts.length > 0 && (
            <>
              <h2 style={{ marginTop: 18 }}>Recent alerts</h2>
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Risk</th>
                    <th>Position</th>
                    <th>Message</th>
                    <th>Notified</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a) => (
                    <tr key={a.id}>
                      <td>{fmtDate(a.created_at)}</td>
                      <td>
                        <span className={`pill ${a.risk_level}`}>{a.risk_level}</span>
                      </td>
                      <td>
                        {a.position ?? "—"}/{a.retention_count ?? "—"}
                      </td>
                      <td>{a.message}</td>
                      <td>{a.notified ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <div className="modal-actions">
            <button
              className="btn ghost"
              onClick={() => {
                setResult(null);
                setAlerts([]);
              }}
            >
              Close
            </button>
          </div>
        </Modal>
      )}

      {showForm && (
        <Modal
          title={editing ? "Edit image monitor" : "Add image monitor"}
          onClose={() => setShowForm(false)}
        >
          {error && <div className="error-box">{error}</div>}
          <div className="field">
            <label>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. orders-service (prod)"
            />
          </div>
          <div className="form-row">
            <div className="field">
              <label>Application / service name</label>
              <input
                value={form.application}
                onChange={(e) => setForm({ ...form, application: e.target.value })}
                placeholder="orders-service"
              />
            </div>
            <div className="field">
              <label>AWS account</label>
              <select
                value={form.account_id}
                onChange={(e) => setForm({ ...form, account_id: e.target.value })}
              >
                <option value="">Mock (no account)</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="field">
              <label>ECS cluster</label>
              <input
                value={form.ecs_cluster}
                onChange={(e) => setForm({ ...form, ecs_cluster: e.target.value })}
                placeholder="prod-cluster"
              />
            </div>
            <div className="field">
              <label>ECS service</label>
              <input
                value={form.ecs_service}
                onChange={(e) => setForm({ ...form, ecs_service: e.target.value })}
                placeholder="orders-service"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="field">
              <label>ECR repository</label>
              <input
                value={form.ecr_repository}
                onChange={(e) =>
                  setForm({ ...form, ecr_repository: e.target.value })
                }
                placeholder="orders-service"
              />
            </div>
            <div className="field">
              <label>Region (optional)</label>
              <input
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
                placeholder="us-east-1"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="field">
              <label>GitLab source (optional)</label>
              <select
                value={form.gitlab_source_id}
                onChange={(e) =>
                  setForm({ ...form, gitlab_source_id: e.target.value })
                }
              >
                <option value="">None</option>
                {gitlabSources.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Image tag prefix (optional)</label>
              <input
                value={form.image_tag_prefix}
                onChange={(e) =>
                  setForm({ ...form, image_tag_prefix: e.target.value })
                }
                placeholder="orders-service-prod"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="field">
              <label>Retention count (blank = from policy)</label>
              <input
                type="number"
                value={form.retention_count}
                onChange={(e) =>
                  setForm({ ...form, retention_count: e.target.value })
                }
                placeholder="20"
              />
            </div>
            <div className="field">
              <label>Warn threshold (slots from boundary)</label>
              <input
                type="number"
                value={form.warn_threshold}
                onChange={(e) =>
                  setForm({ ...form, warn_threshold: e.target.value })
                }
                placeholder="3"
              />
            </div>
          </div>
          <div className="field">
            <label>Notification webhook (Slack/Teams, optional)</label>
            <input
              value={form.webhook_url}
              onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
              placeholder={
                editing?.has_webhook
                  ? "•••• (leave blank to keep existing)"
                  : "https://hooks.slack.com/services/…"
              }
            />
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />{" "}
              Enabled (included in periodic checks)
            </label>
          </div>
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
