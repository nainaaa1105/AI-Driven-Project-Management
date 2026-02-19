import React, { useState, useRef, useEffect } from "react";
import { sendMessage, fetchTasks, updateTask, fetchCustomDomains, createCustomDomain } from "../services/api";

const EXAMPLE_MSGS = [
  "Started backend implementation",
  "Blocked due to API issue",
  "Mark task 3 as resolved",
  "delete task 5",
  "update task 2: Added auth middleware",
];

const DEFAULT_DOMAIN_OPTIONS = [
  "frontend", "backend", "devops", "design", "security",
  "database", "testing", "mobile", "infrastructure", "General",
];
const URGENCIES = ["normal", "low", "medium", "high"];

export default function ChatPage({ onNavigate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const bottomRef = useRef(null);

  /* ── editable sidebar state ── */
  const [sidebarDomains, setSidebarDomains] = useState([]);
  const [sidebarUrgency, setSidebarUrgency] = useState("normal");
  const [customDomains, setCustomDomains] = useState([]);
  const [showAddDomain, setShowAddDomain] = useState(false);
  const [newDomainInput, setNewDomainInput] = useState("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* Load custom domains on mount */
  useEffect(() => {
    fetchCustomDomains().then(setCustomDomains).catch(() => {});
  }, []);

  /* Load recent tasks as "activity" on mount */
  useEffect(() => {
    fetchTasks()
      .then((tasks) => {
        const items = tasks.slice(0, 3).map((t) => ({
          icon: t.risk_level === "High" || t.risk_level === "Critical" ? "!" : "#",
          text: `Task #${t.id}: ${t.title.slice(0, 50)}${t.title.length > 50 ? "\u2026" : ""}`,
          sub: `${t.status} \u00b7 ${t.risk_level} risk`,
        }));
        setRecentActivity(items);
      })
      .catch(() => {});
  }, [messages.length]);

  /* Sync sidebar state when lastResult changes */
  useEffect(() => {
    if (lastResult) {
      const d = lastResult.domain || "General";
      setSidebarDomains(d.split(",").map((s) => s.trim()).filter(Boolean));
      setSidebarUrgency(lastResult.urgency || "normal");
    }
  }, [lastResult]);

  /* ── persist sidebar edits to backend ── */
  const handleSidebarDomainToggle = async (d) => {
    if (!lastResult?.task_id) return;
    const next = sidebarDomains.includes(d)
      ? sidebarDomains.filter((x) => x !== d)
      : [...sidebarDomains, d];
    setSidebarDomains(next);
    try { await updateTask(lastResult.task_id, { domains: next }); }
    catch { /* best effort */ }
  };

  const handleSidebarUrgencyChange = async (val) => {
    if (!lastResult?.task_id) return;
    setSidebarUrgency(val);
    try { await updateTask(lastResult.task_id, { urgency: val }); }
    catch { /* best effort */ }
  };

  const handleAddCustomDomain = async () => {
    const name = newDomainInput.trim();
    if (!name) return;
    // Case-insensitive duplicate check locally
    const allDomains = [...DEFAULT_DOMAIN_OPTIONS, ...customDomains];
    if (allDomains.some((d) => d.toLowerCase() === name.toLowerCase())) {
      setNewDomainInput("");
      setShowAddDomain(false);
      return;
    }
    try {
      await createCustomDomain(name);
      setCustomDomains((prev) => [...prev, name]);
    } catch { /* duplicate on server */ }
    setNewDomainInput("");
    setShowAddDomain(false);
  };

  const allDomainOptions = [...DEFAULT_DOMAIN_OPTIONS, ...customDomains];

  const handleSend = async (override) => {
    const text = (override || input).trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendMessage(text);

      if (result.action) {
        const icon = result.ok ? "[OK]" : "[FAIL]";
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: `${icon} ${result.message}` },
        ]);
        /* Clear AI panel if the deleted task was shown */
        if (result.action === "delete" && lastResult && String(lastResult.task_id) === String(result.task_id)) {
          setLastResult(null);
        }
      } else {
        setLastResult(result);
        const parts = [`**Summary:** ${result.summary || "N/A"}`];
        if (result.task_created) {
          parts.push(`Task #${result.task_id} created (${result.similarity_label})`);
        } else {
          parts.push(`Task #${result.task_id} updated (${result.similarity_label})`);
        }
        parts.push(`Risk: ${(result.risk_score * 100).toFixed(0)}% (${result.risk_level})`);
        if (result.alert) parts.push(result.alert);
        setMessages((prev) => [...prev, { role: "ai", text: parts.join("\n") }]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: `Error: ${err.response?.data?.detail || err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  /* ── Empty state: help panel ── */
  const EmptyState = () => (
    <div className="chat-empty-state">
      <div className="chat-empty-icon"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
      <h3>AI Chat Assistant</h3>
      <p>Send a message to create tasks, detect risks, and get AI insights automatically.</p>

      <div className="chat-help-section">
        <h4>Try these examples</h4>
        <div className="example-chips">
          {EXAMPLE_MSGS.map((msg, i) => (
            <button key={i} className="example-chip" onClick={() => { setInput(msg); }}>
              {msg}
            </button>
          ))}
        </div>
      </div>

      {recentActivity.length > 0 && (
        <div className="chat-help-section">
          <h4>Recent Activity</h4>
          <div className="recent-list">
            {recentActivity.map((item, i) => (
              <div key={i} className="recent-item">
                <span className="recent-icon activity-icon-badge">{item.icon}</span>
                <div>
                  <div className="recent-text">{item.text}</div>
                  <div className="recent-sub">{item.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="chat-help-section">
        <h4>Quick Actions</h4>
        <div className="quick-actions">
          <button className="quick-btn" onClick={() => onNavigate && onNavigate("Tasks")}>View Tasks</button>
          <button className="quick-btn" onClick={() => onNavigate && onNavigate("Dashboard")}>Dashboard</button>
          <button className="quick-btn" onClick={() => onNavigate && onNavigate("Risk")}>Risks</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="chat-layout">
      {/* ── Chat panel ── */}
      <div className="chat-panel">
        <div className="chat-messages">
          {messages.length === 0 && <EmptyState />}
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.text.split("\n").map((line, j) => (
                <div key={j}>{line}</div>
              ))}
            </div>
          ))}
          {loading && (
            <div className="chat-bubble ai">
              <span className="spinner" /> Analyzing...
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-row">
          <input
            placeholder="Type a project update\u2026"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button onClick={() => handleSend()} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>

      {/* ── AI Result sidebar ── */}
      <div className="ai-result-panel">
        <h3>AI Analysis Result</h3>
        {!lastResult ? (
          <p style={{ color: "var(--text-dim)", fontSize: "0.85rem" }}>
            Results will appear here after sending a message.
          </p>
        ) : (
          <>
            <div className="ai-field">
              <div className="lbl">Summary</div>
              <div className="val">{lastResult.summary}</div>
            </div>
            <div className="ai-field">
              <div className="lbl">Task</div>
              <div className="val">
                {lastResult.task_created ? "Created" : "Updated"} <strong>Task #{lastResult.task_id}</strong>{" "}
                ({lastResult.similarity_label})
              </div>
            </div>

            {/* ── Editable Domain chips ── */}
            <div className="ai-field">
              <div className="lbl">Domain <span className="ai-user-label">AI Suggested · User Controlled</span></div>
              <div className="domain-chips sidebar-chips">
                {allDomainOptions.map((d) => (
                  <button
                    key={d}
                    className={`chip ${sidebarDomains.includes(d) ? "active" : ""}`}
                    onClick={() => handleSidebarDomainToggle(d)}
                  >{d}</button>
                ))}
                {!showAddDomain ? (
                  <button className="chip chip-add" onClick={() => setShowAddDomain(true)}>+ Add</button>
                ) : (
                  <span className="custom-domain-input-wrap">
                    <input
                      className="custom-domain-input"
                      placeholder="New domain"
                      value={newDomainInput}
                      onChange={(e) => setNewDomainInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleAddCustomDomain(); if (e.key === "Escape") setShowAddDomain(false); }}
                      autoFocus
                    />
                    <button className="chip chip-confirm" onClick={handleAddCustomDomain}>Add</button>
                  </span>
                )}
              </div>
            </div>

            {/* ── Editable Urgency dropdown ── */}
            <div className="ai-field">
              <div className="lbl">Urgency <span className="ai-user-label">AI Suggested · User Controlled</span></div>
              <select
                className="sidebar-urgency-select"
                value={sidebarUrgency}
                onChange={(e) => handleSidebarUrgencyChange(e.target.value)}
              >
                {URGENCIES.map((u) => (
                  <option key={u} value={u}>{u.charAt(0).toUpperCase() + u.slice(1)}</option>
                ))}
              </select>
            </div>

            <div className="ai-field">
              <div className="lbl">Risk Score <span className="ai-risk-hint">(AI-predicted)</span></div>
              <div className="val">
                {(lastResult.risk_score * 100).toFixed(0)}%{" "}
                <span className={`risk-badge ${lastResult.risk_level}`}>
                  {lastResult.risk_level}
                </span>
              </div>
              <div className="risk-helper-text">Risk reflects likelihood of failure, not urgency.</div>
            </div>
            {lastResult.risk_reason && (
              <div className="ai-field">
                <div className="lbl">Risk Reason</div>
                <div className="val">{lastResult.risk_reason}</div>
              </div>
            )}
            {lastResult.alert && (
              <div className="alert-banner">{lastResult.alert}</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
