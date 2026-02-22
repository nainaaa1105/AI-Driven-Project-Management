import React, { useState, useEffect } from "react";
import { predictRisk, fetchWorkspaceRisk } from "../services/api";

export default function RiskPage({ workspace, wsEpoch }) {
  const [form, setForm] = useState({
    task_complexity: 0.5,
    dependency_count: 0.3,
    sentiment_score: 0.5,
    is_blocked: 0,
    idle_time_days: 30,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [wsRisk, setWsRisk] = useState(null);

  /* Load workspace-level risk overview when a workspace is selected */
  useEffect(() => {
    if (workspace?.id) {
      fetchWorkspaceRisk(workspace.id).then(setWsRisk).catch(() => setWsRisk(null));
    } else {
      setWsRisk(null);
    }
  }, [workspace?.id, wsEpoch]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: Number(value) }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await predictRisk(form);
      setResult(res);
    } catch (err) {
      console.error(err);
      setResult({ risk_score: -1, risk_level: "Error", reason: err.message });
    } finally {
      setLoading(false);
    }
  };

  const RISK_COLORS = {
    Low: "var(--green)", Medium: "var(--yellow)", High: "var(--orange)", Critical: "var(--red)",
  };

  return (
    <>
      <h2 style={{ fontSize: "1.1rem", marginBottom: 4, fontWeight: 600, letterSpacing: "0.02em" }}>Risk Predictor</h2>
      <p style={{ color: "var(--text-dim)", fontSize: "0.82rem", marginBottom: 16, lineHeight: 1.6 }}>
        Risk reflects likelihood of failure, not urgency. It increases when blockers, delays, or unresolved issues persist.
      </p>

      {/* ── Workspace Risk Overview ── */}
      {wsRisk && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: "0.9rem", color: "var(--accent-light)", fontWeight: 600, marginBottom: 10 }}>
            Workspace Risk: {workspace?.name}
          </h3>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: "0.85rem" }}>
            {wsRisk.avg_risk_score != null && (
              <div><strong>Avg Risk:</strong> {(wsRisk.avg_risk_score * 100).toFixed(0)}%</div>
            )}
            {wsRisk.high_risk_count != null && (
              <div><strong>High-Risk Tasks:</strong> {wsRisk.high_risk_count}</div>
            )}
            {wsRisk.total_tasks != null && (
              <div><strong>Total Tasks:</strong> {wsRisk.total_tasks}</div>
            )}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* ── Form ── */}
        <div className="card">
          <form className="risk-form" onSubmit={handleSubmit}>
            <div>
              <label>Task Complexity (0–1)</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={form.task_complexity}
                onChange={(e) => handleChange("task_complexity", e.target.value)}
              />
            </div>
            <div>
              <label>Dependency Count (0–1)</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={form.dependency_count}
                onChange={(e) => handleChange("dependency_count", e.target.value)}
              />
            </div>
            <div>
              <label>Sentiment Score (0–1)</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={form.sentiment_score}
                onChange={(e) => handleChange("sentiment_score", e.target.value)}
              />
            </div>
            <div>
              <label>Blocked?</label>
              <select
                value={form.is_blocked}
                onChange={(e) => handleChange("is_blocked", e.target.value)}
              >
                <option value={0}>No</option>
                <option value={1}>Yes</option>
              </select>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label>Idle Time (days)</label>
              <input
                type="number" step="1" min="0"
                value={form.idle_time_days}
                onChange={(e) => handleChange("idle_time_days", e.target.value)}
              />
            </div>
            <button type="submit" disabled={loading}>
              {loading ? "Predicting…" : "Predict Risk"}
            </button>
          </form>
        </div>

        {/* ── Result ── */}
        <div className="card risk-result">
          {!result ? (
            <p style={{ color: "var(--text-dim)", marginTop: 40 }}>
              Fill in features and click Predict Risk.
            </p>
          ) : (
            <>
              <div
                className="score"
                style={{ color: RISK_COLORS[result.risk_level] || "var(--text)", marginTop: 20 }}
              >
                {result.risk_score >= 0
                  ? `${(result.risk_score * 100).toFixed(0)}%`
                  : "N/A"}
              </div>
              <div style={{ marginTop: 8 }}>
                <span className={`risk-badge ${result.risk_level}`} style={{ fontSize: "1rem", padding: "6px 18px" }}>
                  {result.risk_level}
                </span>
              </div>
              <p style={{ marginTop: 16, fontSize: "0.9rem", color: "var(--text-dim)" }}>
                {result.reason}
              </p>
              {result.shap_values && (
                <div style={{ marginTop: 20, textAlign: "left" }}>
                  <h4 style={{ fontSize: "0.8rem", color: "var(--accent-light)", marginBottom: 8 }}>
                    SHAP Feature Contributions
                  </h4>
                  {Object.entries(result.shap_values).map(([feat, val]) => (
                    <div
                      key={feat}
                      style={{
                        display: "flex", justifyContent: "space-between",
                        fontSize: "0.8rem", padding: "4px 0",
                        borderBottom: "1px solid var(--border)",
                      }}
                    >
                      <span>{feat}</span>
                      <span style={{ color: val > 0 ? "var(--red)" : "var(--green)", fontWeight: 600 }}>
                        {val > 0 ? "+" : ""}{val.toFixed(4)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
