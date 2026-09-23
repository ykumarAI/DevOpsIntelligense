import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "../components/Modal.jsx";

const RESOURCE_TYPES = [
  { value: "ec2", label: "EC2 instance", hint: "instance id, e.g. i-0abc123..." },
  { value: "ecs", label: "ECS service", hint: "cluster/service, e.g. prod/orders" },
  { value: "ecr", label: "ECR repository", hint: "repository name" },
  { value: "eks", label: "EKS cluster", hint: "cluster name" },
  { value: "s3", label: "S3 bucket", hint: "bucket name" },
  { value: "cloudwatch", label: "CloudWatch alarm", hint: "alarm name" },
];

// Signals that can be collected per resource type (key must match the backend
// metric/detail keys). Users tick the ones they want; the collector returns
// only those. Empty selection is allowed (shows status only).
const SIGNALS = {
  ec2: [
    { key: "cpu_percent", label: "CPU %" },
    { key: "disk_percent", label: "Disk %" },
    { key: "memory_percent", label: "Memory %" },
    { key: "state", label: "State" },
    { key: "instance_type", label: "Instance type" },
    { key: "availability_zone", label: "Availability zone" },
    { key: "private_ip", label: "Private IP" },
    { key: "launch_days_ago", label: "Age (days)" },
  ],
  ecs: [
    { key: "desired_count", label: "Desired tasks" },
    { key: "running_count", label: "Running tasks" },
    { key: "pending_count", label: "Pending tasks" },
    { key: "launch_type", label: "Launch type" },
    { key: "deployment_status", label: "Deployment status" },
    { key: "task_definition", label: "Task definition" },
  ],
  ecr: [
    { key: "image_count", label: "Image count" },
    { key: "images_near_expiry", label: "Images near expiry" },
    { key: "days_since_last_push", label: "Days since last push" },
    { key: "scan_on_push", label: "Scan on push" },
    { key: "latest_tag", label: "Latest tag" },
    { key: "critical_vulnerabilities", label: "Critical vulnerabilities" },
  ],
  eks: [
    { key: "node_count", label: "Node count" },
    { key: "unhealthy_nodes", label: "Unhealthy nodes" },
    { key: "pending_pods", label: "Pending pods" },
    { key: "version", label: "K8s version" },
    { key: "status", label: "Cluster status" },
    { key: "crashloop_pods", label: "CrashLoop pods" },
  ],
  s3: [
    { key: "size_gb", label: "Size (GB)" },
    { key: "object_count", label: "Object count" },
    { key: "public_access", label: "Public access" },
    { key: "encrypted", label: "Encrypted" },
    { key: "versioning", label: "Versioning" },
  ],
  cloudwatch: [
    { key: "breaches_24h", label: "Breaches (24h)" },
    { key: "state", label: "Alarm state" },
    { key: "metric", label: "Metric" },
    { key: "threshold", label: "Threshold" },
  ],
};

const allSignalKeys = (type) => (SIGNALS[type] || []).map((s) => s.key);

const EMPTY = {
  account_id: "",
  resource_type: "ec2",
  identifier: "",
  display_name: "",
  region: "",
  group_name: "",
  collect_options: allSignalKeys("ec2"),
  enabled: true,
  notes: "",
};

export default function ResourcesPage({ accounts }) {
  const [resources, setResources] = useState([]);
  const [filterAccount, setFilterAccount] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setResources(await api.listResources(filterAccount || undefined));
    } catch (e) {
      setError(e.message);
    }
  }, [filterAccount]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (editing) {
      setForm({
        account_id: editing.account_id,
        resource_type: editing.resource_type,
        identifier: editing.identifier,
        display_name: editing.display_name || "",
        region: editing.region || "",
        group_name: editing.group_name || "",
        collect_options:
          editing.collect_options ?? allSignalKeys(editing.resource_type),
        enabled: editing.enabled,
        notes: editing.notes || "",
      });
    } else {
      setForm({ ...EMPTY, account_id: accounts[0]?.id || "" });
    }
  }, [editing, accounts]);

  const openNew = () => {
    setEditing(null);
    setError("");
    setShowForm(true);
  };

  const openEdit = (r) => {
    setEditing(r);
    setError("");
    setShowForm(true);
  };

  const submit = async () => {
    setError("");
    try {
      const payload = {
        ...form,
        account_id: Number(form.account_id),
        display_name: form.display_name || null,
        region: form.region || null,
        group_name: form.group_name || null,
        collect_options: form.collect_options,
        notes: form.notes || null,
      };
      if (editing) {
        await api.updateResource(editing.id, payload);
      } else {
        await api.createResource(payload);
      }
      setShowForm(false);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (r) => {
    if (!confirm(`Stop monitoring "${r.display_name || r.identifier}"?`)) return;
    await api.deleteResource(r.id);
    load();
  };

  const accountName = (id) => accounts.find((a) => a.id === id)?.name || id;
  const currentHint = RESOURCE_TYPES.find((t) => t.value === form.resource_type)?.hint;
  const currentSignals = SIGNALS[form.resource_type] || [];

  const onTypeChange = (type) => {
    // Reset the signal selection to the new type's full set.
    setForm((f) => ({ ...f, resource_type: type, collect_options: allSignalKeys(type) }));
  };

  const toggleSignal = (key) => {
    setForm((f) => {
      const set = new Set(f.collect_options || []);
      set.has(key) ? set.delete(key) : set.add(key);
      // Preserve catalog order.
      const ordered = allSignalKeys(f.resource_type).filter((k) => set.has(k));
      return { ...f, collect_options: ordered };
    });
  };

  const allChecked = currentSignals.length > 0 &&
    currentSignals.every((s) => (form.collect_options || []).includes(s.key));
  const toggleAll = () =>
    setForm((f) => ({
      ...f,
      collect_options: allChecked ? [] : allSignalKeys(f.resource_type),
    }));

  return (
    <>
      <div className="header-row">
        <div>
          <h1>Monitored Resources</h1>
          <div className="subtitle">Add the AWS objects you want the dashboard to watch.</div>
        </div>
        <button className="btn" onClick={openNew} disabled={accounts.length === 0}>
          + Add resource
        </button>
      </div>

      {accounts.length === 0 && (
        <div className="error-box">
          Create an AWS account first (AWS Accounts tab) before adding resources.
        </div>
      )}

      <div className="toolbar">
        <select
          value={filterAccount}
          onChange={(e) => setFilterAccount(e.target.value)}
          style={{ width: 220 }}
        >
          <option value="">All accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>

      {resources.length === 0 ? (
        <div className="empty">No resources configured.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Identifier</th>
              <th>Group</th>
              <th>Account</th>
              <th>Signals</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {resources.map((r) => (
              <tr key={r.id}>
                <td>{r.display_name || "—"}</td>
                <td>{r.resource_type}</td>
                <td className="mono">{r.identifier}</td>
                <td>{r.group_name || "—"}</td>
                <td>{accountName(r.account_id)}</td>
                <td>{r.collect_options == null ? "all" : `${r.collect_options.length} selected`}</td>
                <td>{r.enabled ? "yes" : "no"}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <button className="btn ghost sm" onClick={() => openEdit(r)}>
                    Edit
                  </button>{" "}
                  <button className="btn danger sm" onClick={() => remove(r)}>
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
          title={editing ? "Edit resource" : "Add resource"}
          onClose={() => setShowForm(false)}
        >
          {error && <div className="error-box">{error}</div>}
          <div className="form-row">
            <div className="field">
              <label>Account</label>
              <select
                value={form.account_id}
                onChange={(e) => setForm({ ...form, account_id: e.target.value })}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Resource type</label>
              <select
                value={form.resource_type}
                onChange={(e) => onTypeChange(e.target.value)}
              >
                {RESOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Identifier</label>
            <input
              value={form.identifier}
              onChange={(e) => setForm({ ...form, identifier: e.target.value })}
              placeholder={currentHint}
            />
          </div>
          <div className="form-row">
            <div className="field">
              <label>Display name (optional)</label>
              <input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Region override (optional)</label>
              <input
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
                placeholder="defaults to account region"
              />
            </div>
          </div>
          <div className="field">
            <label>Group (optional) — tiles with the same group are shown together</label>
            <input
              value={form.group_name}
              onChange={(e) => setForm({ ...form, group_name: e.target.value })}
              placeholder="e.g. Payments service, UAT web tier"
            />
          </div>
          <div className="field">
            <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Information to collect</span>
              <button type="button" className="btn ghost sm" onClick={toggleAll}>
                {allChecked ? "Clear all" : "Select all"}
              </button>
            </label>
            <div className="signal-grid">
              {currentSignals.map((s) => (
                <label key={s.key} className="signal-item">
                  <input
                    type="checkbox"
                    checked={(form.collect_options || []).includes(s.key)}
                    onChange={() => toggleSignal(s.key)}
                  />
                  {s.label}
                </label>
              ))}
            </div>
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
          <div className="field">
            <label>Notes (optional)</label>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setShowForm(false)}>
              Cancel
            </button>
            <button className="btn" onClick={submit}>
              {editing ? "Save" : "Add"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
