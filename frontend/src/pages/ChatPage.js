import React, { useState, useRef, useEffect, useCallback } from "react";
import { sendMessage, fetchTasks, updateTask, fetchCustomDomains, createCustomDomain, fetchWorkspaceMembers, addWorkspaceMember, connectWebSocket } from "../services/api";

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

/* Helper: extract initials from a name */
function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

/* Deterministic hue from a string */
function nameHue(str) {
  let h = 0;
  for (let i = 0; i < (str || "").length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  return Math.abs(h) % 360;
}

export default function ChatPage({ onNavigate, user, workspace, wsEpoch }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  const bottomRef = useRef(null);

  /* ── Voice UI state (visual only — no real audio) ── */
  const [isInVoice, setIsInVoice] = useState(false);

  /* ── Add Member modal state ── */
  const [showAddMember, setShowAddMember] = useState(false);
  const [addMemberUserId, setAddMemberUserId] = useState("");
  const [addMemberRole, setAddMemberRole] = useState("member");
  const [addMemberLoading, setAddMemberLoading] = useState(false);
  const [addMemberError, setAddMemberError] = useState("");
  const [addMemberSuccess, setAddMemberSuccess] = useState("");

  /* Clear messages + result when workspace changes */
  const prevWsId = useRef(workspace?.id);
  useEffect(() => {
    if (workspace?.id !== prevWsId.current) {
      setMessages([]);
      setLastResult(null);
      prevWsId.current = workspace?.id;
    }
  }, [workspace]);

  /* ── editable sidebar state ── */
  const [sidebarDomains, setSidebarDomains] = useState([]);
  const [sidebarUrgency, setSidebarUrgency] = useState("normal");
  const [customDomains, setCustomDomains] = useState([]);
  const [showAddDomain, setShowAddDomain] = useState(false);
  const [newDomainInput, setNewDomainInput] = useState("");

  /* ── workspace members ── */
  const [members, setMembers] = useState([]);
  const [onlineUsers, setOnlineUsers] = useState([]);

  /* ── WebSocket ref ── */
  const wsRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* Load custom domains on mount */
  useEffect(() => {
    fetchCustomDomains().then(setCustomDomains).catch(() => {});
  }, []);

  /* Load workspace members — reload when workspace or wsEpoch changes */
  useEffect(() => {
    if (workspace && workspace.id) {
      fetchWorkspaceMembers(workspace.id)
        .then(setMembers)
        .catch(() => {
          // Fallback: show current user as member
          setMembers([{ user_id: user?.id, role: "admin", name: user?.name }]);
        });
    } else {
      // No workspace — show current user
      setMembers(user ? [{ user_id: user.id, role: "admin", name: user.name }] : []);
    }
  }, [workspace, user, wsEpoch]);

  /* ── WebSocket connection for real-time messages ── */
  const handleWsMessage = useCallback((data) => {
    if (!data || !data.type) return;

    if (data.type === "chat_message") {
      // Don't show own messages (we already add them optimistically)
      if (data.sender_id === user?.id) return;
      setMessages((prev) => [...prev, {
        role: "user",
        text: data.content,
        sender: data.sender || "User",
        fromWs: true,
      }]);
    } else if (data.type === "ai_response") {
      // Only show AI responses from other users' messages
      if (data.sender_id === user?.id) return;
      const parts = [];
      if (data.summary) parts.push(`**Summary:** ${data.summary}`);
      if (data.task_id) {
        parts.push(`Task #${data.task_id} ${data.task_created ? "created" : "updated"} (${data.similarity_label || ""})`);
      }
      if (data.risk_score !== undefined) {
        parts.push(`Risk: ${(data.risk_score * 100).toFixed(0)}% (${data.risk_level})`);
      }
      if (data.alert) parts.push(data.alert);
      if (parts.length > 0) {
        setMessages((prev) => [...prev, {
          role: "ai",
          text: parts.join("\n"),
          sender: "AI Bot",
          fromWs: true,
        }]);
      }
    } else if (data.type === "presence_update") {
      setOnlineUsers(data.online_users || []);
    } else if (data.type === "member_joined" || data.type === "member_left") {
      // Reload member list
      if (workspace?.id) {
        fetchWorkspaceMembers(workspace.id).then(setMembers).catch(() => {});
      }
    } else if (data.type === "workspace_deleted") {
      // Dispatch custom event so App.js can clear activeWs for all users
      window.dispatchEvent(new CustomEvent("workspace:deleted", {
        detail: { workspace_id: data.workspace_id, workspace_name: data.workspace_name },
      }));
      setMessages((prev) => [...prev, {
        role: "ai",
        text: `Workspace "${data.workspace_name || "this workspace"}" has been deleted.`,
        sender: "System",
      }]);
    }
  }, [user?.id, workspace?.id]);

  useEffect(() => {
    if (!workspace?.id) return;

    const ws = connectWebSocket(workspace.id, handleWsMessage);
    wsRef.current = ws;

    ws.onclose = () => {
      console.log(`[WS] Disconnected from workspace ${workspace.id}`);
      wsRef.current = null;
      setOnlineUsers([]);   // clear stale presence dots on disconnect
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [workspace?.id, handleWsMessage]);

  /* Load recent tasks as "activity" — scoped to workspace */
  useEffect(() => {
    fetchTasks(undefined, workspace?.id)
      .then((tasks) => {
        const items = tasks.slice(0, 3).map((t) => ({
          icon: t.risk_level === "High" || t.risk_level === "Critical" ? "!" : "#",
          text: `Task #${t.id}: ${t.title.slice(0, 50)}${t.title.length > 50 ? "\u2026" : ""}`,
          sub: `${t.status} \u00b7 ${t.risk_level} risk`,
        }));
        setRecentActivity(items);
      })
      .catch(() => {});
  }, [messages.length, workspace?.id]);

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

  /* ── Check if current user is admin of active workspace ── */
  const isAdmin = members.some((m) => m.user_id === user?.id && m.role === "admin");

  /* ── Add member handler ── */
  const handleAddMember = async (e) => {
    e.preventDefault();
    const uid = parseInt(addMemberUserId, 10);
    if (!uid || !workspace?.id) return;
    setAddMemberLoading(true);
    setAddMemberError("");
    setAddMemberSuccess("");
    try {
      await addWorkspaceMember(workspace.id, uid, addMemberRole);
      setAddMemberSuccess(`User #${uid} added as ${addMemberRole}`);
      setAddMemberUserId("");
      setAddMemberRole("member");
      // Reload members
      try {
        const updated = await fetchWorkspaceMembers(workspace.id);
        setMembers(updated);
      } catch { /* best effort */ }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setAddMemberError(typeof detail === "string" ? detail : "Failed to add member");
    } finally {
      setAddMemberLoading(false);
    }
  };

  const handleSend = async (override) => {
    const text = (override || input).trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text, sender: user?.name || "You" }]);
    setInput("");
    setLoading(true);

    // REST-only: the backend broadcasts to WS after processing
    // so other workspace users see messages in real time.

    try {
      const result = await sendMessage(text, workspace?.id);

      if (result.action) {
        const icon = result.ok ? "[OK]" : "[FAIL]";
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: `${icon} ${result.message}`, sender: "AI Bot" },
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
        setMessages((prev) => [...prev, { role: "ai", text: parts.join("\n"), sender: "AI Bot" }]);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMsg = typeof detail === "string" ? detail : (err.message || "Something went wrong");
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: `Error: ${errMsg}`, sender: "AI Bot" },
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
      {/* ── Members sidebar ── */}
      <div className="members-panel">
        <h4 className="members-heading">Members ({members.length})</h4>
        <div className="members-list">
          {members.map((m, i) => {
            const mName = m.name || `User #${m.user_id}`;
            const isMe = user && m.user_id === user.id;
            return (
              <div className="member-item" key={m.user_id || i}>
                <span
                  className="member-avatar"
                  style={{ background: `hsl(${nameHue(mName)}, 55%, 45%)` }}
                >
                  {getInitials(mName)}
                </span>
                <div className="member-info">
                  <span className="member-name">{mName}{isMe ? " (you)" : ""}</span>
                  <span className="member-role">{m.role || "member"}</span>
                </div>
                {/* Voice indicator — show headphone icon if this user is in voice */}
                {isMe && isInVoice && <span className="member-voice-icon" title="In voice"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg></span>}
                <span className={`presence-dot ${isMe ? "online" : onlineUsers.includes(m.user_id) ? "online" : ""}`} />
              </div>
            );
          })}
        </div>

        {/* ── Admin: Add Member button ── */}
        {isAdmin && workspace && (
          <div className="add-member-section">
            <button className="add-member-btn" onClick={() => { setShowAddMember(true); setAddMemberError(""); setAddMemberSuccess(""); }}>
              + Add Member
            </button>
          </div>
        )}

        {/* ── Add Member modal ── */}
        {showAddMember && (
          <div className="add-member-modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowAddMember(false); }}>
            <div className="add-member-modal">
              <div className="modal-header">
                <h3>Add Member</h3>
                <button className="modal-close" onClick={() => setShowAddMember(false)}>×</button>
              </div>
              <p className="add-member-hint">Enter the user ID of the person you want to add to this workspace.</p>
              <form onSubmit={handleAddMember}>
                <label className="modal-label">User ID</label>
                <input
                  className="ws-create-input add-member-input"
                  type="number"
                  placeholder="e.g. 2"
                  value={addMemberUserId}
                  onChange={(e) => setAddMemberUserId(e.target.value)}
                  autoFocus
                />
                <label className="modal-label">Role</label>
                <select className="modal-select" value={addMemberRole} onChange={(e) => setAddMemberRole(e.target.value)}>
                  <option value="member">Member</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
                <div className="ws-create-actions" style={{ marginTop: 14 }}>
                  <button type="submit" className="ws-create-btn" disabled={addMemberLoading || !addMemberUserId}>
                    {addMemberLoading ? "Adding…" : "Add"}
                  </button>
                  <button type="button" className="ws-cancel-btn" onClick={() => setShowAddMember(false)}>
                    Cancel
                  </button>
                </div>
              </form>
              {addMemberError && <div className="ws-error" style={{ marginTop: 8 }}>{String(addMemberError)}</div>}
              {addMemberSuccess && <div className="add-member-success">{String(addMemberSuccess)}</div>}
            </div>
          </div>
        )}

        {/* ── Voice UI section ── */}
        <div className="voice-section">
          <div className="voice-divider" />
          {!isInVoice ? (
            <button className="voice-btn" onClick={() => setIsInVoice(true)} disabled={!workspace}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 5}}><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
              Join Voice
            </button>
          ) : (
            <button className="voice-btn voice-btn-active" onClick={() => setIsInVoice(false)}>
              <span className="voice-pulse" /> In Voice · Leave
            </button>
          )}
          {isInVoice && (
            <div className="voice-badge">Voice connected (not recorded)</div>
          )}
          <div className="voice-privacy">Voice is live only. No recording. No transcription.</div>
        </div>
      </div>

      {/* ── Chat panel ── */}
      <div className="chat-panel">
        <div className="chat-messages">
          {messages.length === 0 && <EmptyState />}
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              <div className="msg-sender">
                <span
                  className={`msg-avatar ${m.role === "ai" ? "ai-avatar" : ""}`}
                  style={m.role !== "ai" ? { background: `hsl(${nameHue(m.sender)}, 55%, 45%)` } : {}}
                >
                  {m.role === "ai" ? "AI" : getInitials(m.sender)}
                </span>
                <span className="msg-sender-name">{m.sender || (m.role === "ai" ? "AI Bot" : "You")}</span>
              </div>
              {m.text.split("\n").map((line, j) => (
                <div key={j}>{line}</div>
              ))}
            </div>
          ))}
          {loading && (
            <div className="chat-bubble ai">
              <div className="msg-sender">
                <span className="msg-avatar ai-avatar">AI</span>
                <span className="msg-sender-name">AI Bot</span>
              </div>
              <span className="spinner" /> Analyzing...
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-row">
          {!workspace ? (
            <div className="chat-no-ws-hint">Select or create a workspace to start chatting.</div>
          ) : (
            <>
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
            </>
          )}
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
