import React, { useEffect, useState } from "react";
import { fetchDashboard } from "../services/api";

const RISK_COLORS = { Low: "#34d399", Medium: "#fbbf24", High: "#fb923c", Critical: "#f87171" };

/* Alert system explanation SVG icon */
const AlertSystemIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle", marginRight: 6 }}>
    <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
  </svg>
);

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "var(--text-dim)" }}>Loading dashboard...</p>;
  if (!data) return <p style={{ color: "var(--red)" }}>Failed to load dashboard.</p>;

  const maxRisk = Math.max(...Object.values(data.tasks_by_risk || {}), 1);

  return (
    <>
      <h2 style={{ fontSize: "1.1rem", marginBottom: 16, fontWeight: 600, letterSpacing: "0.02em" }}>Dashboard</h2>

      {/* ── Stat cards ── */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="value">{data.total_messages}</div>
          <div className="label">Messages</div>
        </div>
        <div className="stat-card">
          <div className="value">{data.total_tasks}</div>
          <div className="label">Tasks</div>
        </div>
        <div className="stat-card">
          <div className="value">{data.total_alerts}</div>
          <div className="label">Alerts</div>
        </div>
        <div className="stat-card">
          <div className="value">{(data.avg_risk_score * 100).toFixed(0)}%</div>
          <div className="label">Avg Risk</div>
        </div>
      </div>

      <div className="dash-grid">
        {/* ── Risk breakdown bar chart ── */}
        <div className="card">
          <h3 style={{ fontSize: "0.9rem", marginBottom: 14, color: "var(--accent-light)", fontWeight: 600 }}>
            Tasks by Risk Level
          </h3>
          <div className="bar-chart">
            {Object.entries(data.tasks_by_risk || {}).map(([level, count]) => (
              <div className="bar-item" key={level}>
                <div className="bar-value">{count}</div>
                <div
                  className="bar"
                  style={{
                    height: `${(count / maxRisk) * 120}px`,
                    background: RISK_COLORS[level] || "var(--accent)",
                  }}
                />
                <div className="bar-label">{level}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Recent alerts ── */}
        <div className="card">
          <h3 style={{ fontSize: "0.9rem", marginBottom: 14, color: "var(--accent-light)", fontWeight: 600 }}>
            Recent Alerts
          </h3>
          {(data.recent_alerts || []).length === 0 && (
            <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
              <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
                <AlertSystemIcon />
                <span style={{ fontWeight: 500 }}>Alert system active</span>
              </div>
              <p style={{ lineHeight: 1.6, margin: 0 }}>
                No alerts yet -- alerts trigger when risk is high, tasks are blocked, or deadlines are missed.
              </p>
            </div>
          )}
          {(data.recent_alerts || []).map((a) => (
            <div
              key={a.id}
              style={{
                padding: "8px 12px",
                marginBottom: 8,
                background: "var(--surface2)",
                borderRadius: 8,
                borderLeft: `3px solid ${RISK_COLORS[a.level] || "var(--accent)"}`,
                fontSize: "0.85rem",
              }}
            >
              <span className={`risk-badge ${a.level}`} style={{ marginRight: 8 }}>
                {a.level}
              </span>
              {a.message}
            </div>
          ))}
        </div>
      </div>

      {/* ── Recent tasks table ── */}
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: "0.9rem", marginBottom: 14, color: "var(--accent-light)", fontWeight: 600 }}>
          Recent Tasks
        </h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ color: "var(--text-dim)", textAlign: "left" }}>
              <th style={{ padding: "8px" }}>#</th>
              <th style={{ padding: "8px" }}>Title</th>
              <th style={{ padding: "8px" }}>Status</th>
              <th style={{ padding: "8px" }}>Risk</th>
              <th style={{ padding: "8px" }}>Domain</th>
            </tr>
          </thead>
          <tbody>
            {(data.recent_tasks || []).map((t) => (
              <tr key={t.id} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ padding: "8px" }}>{t.id}</td>
                <td style={{ padding: "8px" }}>{t.title}</td>
                <td style={{ padding: "8px" }}>{t.status}</td>
                <td style={{ padding: "8px" }}>
                  <span className={`risk-badge ${t.risk_level || "Low"}`}>
                    {t.risk_level} ({((t.risk_score || 0) * 100).toFixed(0)}%)
                  </span>
                </td>
                <td style={{ padding: "8px" }}>{t.domain}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
