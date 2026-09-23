import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Modal from "../components/Modal.jsx";
import Sparkline from "../components/Sparkline.jsx";

const REFRESH_MS = 20000;
const STATUS_ORDER = { critical: 0, warning: 1, unknown: 2, healthy: 3 };

// Distinct colour per tile, stable per resource id.
const PALETTE = [
  "#7c5cff", "#12b5a5", "#ff5c8a", "#3b82f6",
  "#f59e0b", "#22c55e", "#ec4899", "#06b6d4",
  "#8b5cf6", "#ef4444", "#0ea5e9", "#84cc16",
];

const TYPE_ABBR = {
  ec2: "EC2",
  ecs: "ECS",
  ecr: "ECR",
  eks: "EKS",
  s3: "S3",
  cloudwatch: "CW",
  gitlab: "GL",
};

const colorFor = (id) => PALETTE[Math.abs(id) % PALETTE.length];
const fmt = (v) => (typeof v === "number" ? v.toLocaleString() : String(v));
const humanize = (k) => k.replace(/_/g, " ");

export default function DashboardPage({ accounts, settings }) {
  const [accountId, setAccountId] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const refreshMs = (settings?.refresh_interval_seconds ?? 20) * 1000 || REFRESH_MS;

  // Apply personalization defaults once settings arrive.
  useEffect(() => {
    if (!settings) return;
    if (settings.default_account_id != null)
      setAccountId(String(settings.default_account_id));
    if (settings.default_status_filter)
      setStatusFilter(settings.default_status_filter);
  }, [settings]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSummary(await api.summary(accountId || undefined));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    load();
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);

  const s = summary?.by_status || {};
  const total = summary?.total_resources ?? 0;
  const healthyPct = total ? Math.round(((s.healthy || 0) / total) * 100) : 0;
  const resources = [...(summary?.resources || [])]
    .filter((r) => statusFilter === "all" || r.status === statusFilter)
    .sort((a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9));

  return (
    <>
      <div className="header-row">
        <div>
          <div className="breadcrumb">Dashboard // Fleet</div>
          <h1>Resource Fleet · Live Status</h1>
          <div className="subtitle">
            Auto-refresh every {Math.round(refreshMs / 1000)}s · {total} resources across{" "}
            {summary?.accounts ?? 0} accounts
          </div>
        </div>
        <div className="header-badges">
          <span className="chip">
            <span className="dot" /> {healthyPct}% healthy
          </span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: 150 }}
          >
            <option value="all">All statuses</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="healthy">Healthy</option>
            <option value="unknown">Unknown</option>
          </select>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            style={{ width: 190 }}
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <button className="btn ghost" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="cards">
        <div className="card">
          <div className="value">{total}</div>
          <div className="label">Total resources</div>
        </div>
        <div className="card healthy">
          <div className="value">{s.healthy || 0}</div>
          <div className="label">Healthy</div>
        </div>
        <div className="card warning">
          <div className="value">{s.warning || 0}</div>
          <div className="label">Warning</div>
        </div>
        <div className="card critical">
          <div className="value">{s.critical || 0}</div>
          <div className="label">Critical</div>
        </div>
        <div className="card">
          <div className="value">{s.unknown || 0}</div>
          <div className="label">Unknown</div>
        </div>
      </div>

      <h2>Monitored resources</h2>
      {resources.length === 0 ? (
        <div className="empty">
          No resources yet. Add AWS resources from the “Monitored Resources” tab.
        </div>
      ) : (
        <div className="grid">
          {resources.map((r) => {
            const color = colorFor(r.resource_id);
            const metricEntries = Object.entries(r.metrics || {}).slice(0, 3);
            const detailEntries = Object.entries(r.details || {}).slice(0, 3);
            return (
              <div
                key={r.resource_id}
                className="tile"
                style={{ "--c": color }}
                onClick={() => setSelected(r)}
              >
                <div className="tile-head">
                  <div className="tile-id">
                    <div className="tile-icon">
                      {TYPE_ABBR[r.resource_type] || r.resource_type}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div className="tile-code">{r.identifier}</div>
                      <div className="tile-name">
                        {r.display_name || r.identifier}
                      </div>
                    </div>
                  </div>
                  <div className="tile-badges">
                    <span className="online">
                      <span
                        className="dot"
                        style={{
                          background:
                            r.status === "unknown" ? "var(--unknown)" : undefined,
                        }}
                      />
                      {r.source}
                    </span>
                    <span className={`pill ${r.status}`}>{r.status}</span>
                  </div>
                </div>

                <div className="now">
                  <span className="now-tag">NOW</span>
                  <span className="now-text">{r.summary || "—"}</span>
                </div>

                <Sparkline seed={r.resource_id + 1} color={color} />

                {metricEntries.length > 0 && (
                  <div className="tile-metrics">
                    {metricEntries.map(([k, v]) => (
                      <div className="metric" key={k}>
                        <div className="m-value">{fmt(v)}</div>
                        <div className="m-label">{humanize(k)}</div>
                      </div>
                    ))}
                  </div>
                )}

                {detailEntries.length > 0 && (
                  <div className="tile-activity">
                    {detailEntries.map(([k, v]) => (
                      <div className="act" key={k}>
                        <span className="tick">✓</span>
                        <span className="k">{humanize(k)}:</span>
                        <span className="v">{fmt(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <Modal
          title={selected.display_name || selected.identifier}
          onClose={() => setSelected(null)}
        >
          <div style={{ marginBottom: 14 }}>
            <span className={`pill ${selected.status}`}>{selected.status}</span>
          </div>
          {selected.error && <div className="error-box">{selected.error}</div>}
          <div className="kv">
            <div className="k">Account</div>
            <div className="v">{selected.account_name}</div>
            <div className="k">Type</div>
            <div className="v">{selected.resource_type}</div>
            <div className="k">Identifier</div>
            <div className="v mono">{selected.identifier}</div>
            <div className="k">Region</div>
            <div className="v">{selected.region || "—"}</div>
            <div className="k">Source</div>
            <div className="v">{selected.source}</div>
            <div className="k">Summary</div>
            <div className="v">{selected.summary || "—"}</div>
          </div>

          {Object.keys(selected.metrics || {}).length > 0 && (
            <>
              <h2 style={{ marginTop: 18 }}>Metrics</h2>
              <div className="kv">
                {Object.entries(selected.metrics).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <div className="k">{humanize(k)}</div>
                    <div className="v">{fmt(v)}</div>
                  </React.Fragment>
                ))}
              </div>
            </>
          )}

          {Object.keys(selected.details || {}).length > 0 && (
            <>
              <h2 style={{ marginTop: 18 }}>Details</h2>
              <div className="kv">
                {Object.entries(selected.details).map(([k, v]) => (
                  <React.Fragment key={k}>
                    <div className="k">{humanize(k)}</div>
                    <div className="v">{fmt(v)}</div>
                  </React.Fragment>
                ))}
              </div>
            </>
          )}

          <div className="modal-actions">
            <button className="btn ghost" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
