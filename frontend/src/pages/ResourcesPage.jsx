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

const EMPTY = {
  account_id: "",
  resource_type: "ec2",
  identifier: "",
  display_name: "",
  region: "",
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
              <th>Account</th>
              <th>Region</th>
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
                <td>{accountName(r.account_id)}</td>
                <td>{r.region || "—"}</td>
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
                onChange={(e) => setForm({ ...form, resource_type: e.target.value })}
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
