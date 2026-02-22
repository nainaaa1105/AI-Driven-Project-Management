import React, { useEffect, useState } from "react";
import { fetchDashboard } from "../services/api";

const RISK_COLORS = { Low: "#34d399", Medium: "#fbbf24", High: "#fb923c", Critical: "#f87171" };

/* SVG Icons */
const AlertSystemIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "middle", marginRight: 6 }}>
    <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
  </svg>
);

const MessagesIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
);
const TasksIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
);
const AlertsIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
);
const RiskIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
);

const STAT_ICONS = [<MessagesIcon />, <TasksIcon />, <AlertsIcon />, <RiskIcon />];

export default function DashboardPage({ workspace, wsEpoch }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchDashboard(workspace?.id)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [workspace?.id, wsEpoch]);

  if (loading) return <div className="dash-loading"><div className="dash-spinner" /><span>Loading dashboard...</span></div>;
  if (!data) return <p style={{ color: "var(--red)" }}>Failed to load dashboard.</p>;

  const maxRisk = Math.max(...Object.values(data.tasks_by_risk || {}), 1);
  const statData = [
    { value: data.total_messages, label: "Messages" },
    { value: data.total_tasks, label: "Tasks" },
    { value: data.total_alerts, label: "Alerts" },
    { value: `${(data.avg_risk_score * 100).toFixed(0)}%`, label: "Avg Risk" },
  ];

  return (
    <div className="dashboard-wrap">
      {/* Futuristic background layers */}
      <div className="dash-bg-grid" />
      <div className="dash-bg-glow dash-bg-glow-1" />
      <div className="dash-bg-glow dash-bg-glow-2" />
      <div className="dash-bg-glow dash-bg-glow-3" />
      <div className="dash-bg-noise" />
      <div className="dash-bg-scanlines" />

      <h2 className="dash-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" style={{verticalAlign:"middle", marginRight: 8}}>
          <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
        </svg>
        Dashboard
      </h2>

      {/* Stat cards */}
      <div className="stat-grid">
        {statData.map((s, i) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-card-icon">{STAT_ICONS[i]}</div>
            <div className="value">{s.value}</div>
            <div className="label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="dash-grid">
        {/* Risk breakdown bar chart */}
        <div className="card">
          <h3 className="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" style={{verticalAlign:"middle", marginRight: 6}}>
              <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
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
                    background: `linear-gradient(to top, ${RISK_COLORS[level] || "var(--accent)"}88, ${RISK_COLORS[level] || "var(--accent)"})`,
                    boxShadow: `0 0 12px ${RISK_COLORS[level] || "var(--accent)"}44`,
                  }}
                />
                <div className="bar-label">{level}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent alerts */}
        <div className="card">
          <h3 className="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" style={{verticalAlign:"middle", marginRight: 6}}>
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            Recent Alerts
          </h3>
          {(data.recent_alerts || []).length === 0 && (
            <div style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
              <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
                <AlertSystemIcon />
                <span style={{ fontWeight: 500 }}>Alert system active</span>
              </div>
              <p style={{ lineHeight: 1.6, margin: 0 }}>
                No alerts yet. Alerts trigger when risk is high, tasks are blocked, or deadlines are missed.
              </p>
            </div>
          )}
          {(data.recent_alerts || []).map((a) => (
            <div
              key={a.id}
              className="alert-row"
              style={{
                borderLeftColor: RISK_COLORS[a.level] || "var(--accent)",
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

      {/* Recent tasks table */}
      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="card-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5" style={{verticalAlign:"middle", marginRight: 6}}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
          </svg>
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
    </div>
  );
}
