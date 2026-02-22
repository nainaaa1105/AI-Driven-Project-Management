import React, { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { fetchWorkspaces, createWorkspace, leaveWorkspace, fetchWorkspaceById, joinWorkspace, deleteWorkspace } from "./services/api";
import LandingPage from "./pages/LandingPage";
import AuthPage from "./pages/AuthPage";
import ChatPage from "./pages/ChatPage";
import TasksPage from "./pages/TasksPage";
import DashboardPage from "./pages/DashboardPage";
import RiskPage from "./pages/RiskPage";

const TABS = ["Chat", "Tasks", "Dashboard", "Risk"];

/* Helper: extract initials from a name */
function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

export default function App() {
  const [tab, setTab] = useState("Landing");
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    const token = localStorage.getItem("token");
    if (stored && token) {
      try { return JSON.parse(stored); } catch { /* ignore */ }
    }
    return null;
  });
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWs, setActiveWs] = useState(null);
  const [wsDropdown, setWsDropdown] = useState(false);

  /* ── Create-workspace inline form state ─────────────────────────── */
  const [showCreateWs, setShowCreateWs] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newWsDesc, setNewWsDesc] = useState("");
  const [newWsAccess, setNewWsAccess] = useState("private");
  const [wsCreating, setWsCreating] = useState(false);
  const [wsError, setWsError] = useState("");

  /* ── Join-workspace inline form state ──────────────────────────── */
  const [showJoinWs, setShowJoinWs] = useState(false);
  const [joinWsId, setJoinWsId] = useState("");
  const [joinWsLoading, setJoinWsLoading] = useState(false);
  const [joinWsResult, setJoinWsResult] = useState(null);   // { id, name, description }
  const [joinWsError, setJoinWsError] = useState(""); //changes made here

  /* ── Workspace epoch — bumped on switch so children reload ──────── */
  const [wsEpoch, setWsEpoch] = useState(0);

  /* ── Delete workspace confirmation ─────────────────────────────── */
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  /* ── Join loading state ────────────────────────────────────────── */
  const [joinLoading, setJoinLoading] = useState(false);

  /* ── Pending join from /join/:id invite link ────────────────────── */
  const [pendingJoinId, setPendingJoinId] = useState(null);

  /* ── Copy-to-clipboard feedback ────────────────────────────────── */
  const [copiedField, setCopiedField] = useState("");   // "id" | "link" | ""

  const copyToClipboard = useCallback((text, field) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(""), 2000);
    }).catch(() => { /* clipboard unavailable */ });
  }, []);

  /* ── Portal positioning for dropdown ───────────────────────────── */
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 240 });

  const selectorRef = useRef(null);   // the clickable toggle element
  const dropdownRef = useRef(null);   // the portal dropdown panel

  /* ── Detect /join/:id invite link on mount ─────────────────────── */
  useEffect(() => {
    const match = window.location.pathname.match(/^\/join\/(.+)$/);
    if (match) {
      const wsId = decodeURIComponent(match[1]).trim();
      if (wsId) {
        setPendingJoinId(wsId);
        // Clean up the URL so it doesn't stick around
        window.history.replaceState(null, "", "/");
      }
    }
  }, []);

  /* ── Process pending invite-link join once user is authenticated ── */
  useEffect(() => {
    if (!pendingJoinId || !user) return;
    const id = pendingJoinId;
    setPendingJoinId(null);  // consume it
    // Open the dropdown with the join form pre-filled & auto-lookup
    setTab("Chat");
    setShowJoinWs(true);
    setJoinWsId(id);
    setJoinWsResult(null);
    setJoinWsError("");
    // Auto-lookup the workspace
    (async () => {
      setJoinWsLoading(true);
      try {
        const ws = await fetchWorkspaceById(id);
        setJoinWsResult(ws);
      } catch (err) {
        const status = err?.response?.status;
        if (status === 404 || status === 403) {
          setJoinWsError("Workspace not found. Check the ID and try again.");
        } else {
          const detail = err?.response?.data?.detail;
          setJoinWsError(typeof detail === "string" ? detail : "Could not look up workspace");
        }
      } finally {
        setJoinWsLoading(false);
      }
    })();
    // Open the dropdown so the user sees the join panel
    if (selectorRef.current) {
      const rect = selectorRef.current.getBoundingClientRect();
      setDropdownPos({ top: rect.bottom + 8, left: rect.left, width: Math.max(rect.width, 260) });
    }
    setWsDropdown(true);
  }, [pendingJoinId, user]);

  // Close dropdown on outside click (works with portal)
  useEffect(() => {
    function handleClickOutside(e) {
      const clickedInSelector = selectorRef.current && selectorRef.current.contains(e.target);
      const clickedInDropdown = dropdownRef.current && dropdownRef.current.contains(e.target);
      if (!clickedInSelector && !clickedInDropdown) {
        setWsDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Listen for 401 logouts triggered by the API interceptor
  const handleLogout = useCallback(() => {
    setUser(null);
    setTab("Landing");
  }, []);

  useEffect(() => {
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, [handleLogout]);

  /* ── Load workspaces when user logs in ─────────────────────────── */
  const loadWorkspaces = useCallback(async () => {
    if (!user) { setWorkspaces([]); setActiveWs(null); return; }
    try {
      const ws = await fetchWorkspaces();
      setWorkspaces(ws);
      // Restore last-used workspace from localStorage if it still exists
      const savedWsId = localStorage.getItem("activeWsId");
      const saved = savedWsId ? ws.find((w) => String(w.id) === savedWsId) : null;
      if (saved) {
        setActiveWs(saved);
      } else if (ws.length > 0) {
        setActiveWs(ws[0]);
        localStorage.setItem("activeWsId", String(ws[0].id));
      } else {
        setActiveWs(null);
        localStorage.removeItem("activeWsId");
      }
    } catch {
      setWorkspaces([]);
    }
  }, [user]);

  useEffect(() => { loadWorkspaces(); }, [loadWorkspaces]);

  /* ── Listen for workspace:deleted from ChatPage WS ─────────────── */
  useEffect(() => {
    function handleWsDeleted(e) {
      const deletedId = e.detail?.workspace_id;
      if (deletedId && activeWs && String(activeWs.id) === String(deletedId)) {
        setActiveWs(null);
        localStorage.removeItem("activeWsId");
      }
      // Reload workspace list regardless
      loadWorkspaces();
    }
    window.addEventListener("workspace:deleted", handleWsDeleted);
    return () => window.removeEventListener("workspace:deleted", handleWsDeleted);
  }, [activeWs, loadWorkspaces]);

  /* ── Switch workspace ──────────────────────────────────────────── */
  const switchWorkspace = (ws) => {
    setActiveWs(ws);
    localStorage.setItem("activeWsId", String(ws.id));
    setWsDropdown(false);
    setWsEpoch((e) => e + 1); // trigger children to reload
  };

  /* ── Create workspace ──────────────────────────────────────────── */
  const handleCreateWorkspace = async (e) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setWsCreating(true);
    setWsError("");
    try {
      const ws = await createWorkspace(newWsName.trim(), newWsDesc.trim(), newWsAccess);
      setShowCreateWs(false);
      setNewWsName("");
      setNewWsDesc("");
      setNewWsAccess("private");
      await loadWorkspaces();
      switchWorkspace(ws);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setWsError(typeof detail === "string" ? detail : "Failed to create workspace");
    } finally {
      setWsCreating(false);
    }
  };

  /* ── Leave workspace ───────────────────────────────────────────── */
  const handleLeaveWorkspace = async () => {
    if (!activeWs || !user) return;
    const confirm = window.confirm(
      `Leave workspace "${activeWs.name}"? You may need an admin to re-add you.`
    );
    if (!confirm) return;
    try {
      await leaveWorkspace(activeWs.id, user.id);
      localStorage.removeItem("activeWsId");
      await loadWorkspaces();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : "Cannot leave workspace";
      alert(msg);
    }
  };

  /* ── Join workspace lookup ─────────────────────────────────────── */
  const handleJoinLookup = async (e) => {
    e.preventDefault();
    const id = joinWsId.trim();
    if (!id) return;
    setJoinWsLoading(true);
    setJoinWsError("");
    setJoinWsResult(null);
    try {
      const ws = await fetchWorkspaceById(id);
      setJoinWsResult(ws);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 404 || status === 403) {
        setJoinWsError("Workspace not found. Check the ID and try again.");
      } else {
        const detail = err?.response?.data?.detail;
setJoinWsError(
  typeof detail === "string"
    ? detail
    : "Could not look up workspace"
);
      }
    } finally {
      setJoinWsLoading(false);
    }
  };

  // Called after successful login/register
  const handleAuth = (data) => {
    setUser({ id: data.user_id, name: data.name, email: data.email });
    // If a pending join ID exists, the pendingJoinId effect will handle navigation
    if (!pendingJoinId) setTab("Chat");
  };

  /* ── Join open workspace ───────────────────────────────────────── */
  const handleJoinOpenWorkspace = async () => {
    if (!joinWsResult || joinLoading) return;
    setJoinLoading(true);
    try {
      await joinWorkspace(joinWsResult.id);
      setShowJoinWs(false);
      setJoinWsResult(null);
      setJoinWsId("");
      await loadWorkspaces();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setJoinWsError(typeof detail === "string" ? detail : "Failed to join workspace");
    } finally {
      setJoinLoading(false);
    }
  };

  /* ── Delete workspace (admin only) ─────────────────────────────── */
  const handleDeleteWorkspace = async () => {
    if (!activeWs || deleteLoading) return;
    setDeleteLoading(true);
    try {
      await deleteWorkspace(activeWs.id);
      setShowDeleteConfirm(false);
      setWsDropdown(false);
      localStorage.removeItem("activeWsId");
      setActiveWs(null);
      await loadWorkspaces();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : "Failed to delete workspace";
      alert(msg);
    } finally {
      setDeleteLoading(false);
    }
  };

  const doLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("activeWsId");
    setUser(null);
    setTab("Landing");
  };

  // Landing page is always public — but skip it if arriving via invite link
  if (tab === "Landing" && !pendingJoinId) {
    return (
      <LandingPage
        onEnter={() => setTab(user ? "Chat" : "Auth")}
        onDashboard={() => setTab(user ? "Dashboard" : "Auth")}
      />
    );
  }

  // Auth gate: show login/register if not authenticated
  if (!user) {
    return <AuthPage onAuth={handleAuth} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 onClick={() => setTab("Landing")} style={{ cursor: "pointer" }}>Horizon</h1>
          {/* ── Workspace selector ──────────────────────────────────── */}
          <div
            className="workspace-selector"
            ref={selectorRef}
            onClick={() => {
              if (!wsDropdown && selectorRef.current) {
                const rect = selectorRef.current.getBoundingClientRect();
                setDropdownPos({
                  top: rect.bottom + 8,
                  left: rect.left,
                  width: Math.max(rect.width, 260),
                });
              }
              setWsDropdown((v) => !v);
            }}
          >
            <span className="ws-label">Workspace:</span>
            <span className="ws-name">{activeWs ? activeWs.name : "None"}</span>
            <span className="ws-chevron">{wsDropdown ? "\u25B4" : "\u25BE"}</span>
          </div>

          {/* ── Dropdown rendered via Portal into document.body ────── */}
          {wsDropdown && createPortal(
            <div
              className="ws-dropdown ws-dropdown-portal"
              ref={dropdownRef}
              style={{
                position: "fixed",
                top: dropdownPos.top,
                left: dropdownPos.left,
                width: dropdownPos.width,
                zIndex: 99999,
              }}
            >
              <div className="ws-dropdown-content">
                {/* Workspace info — shows ID + copy buttons when a workspace is active */}
                {activeWs && (
                  <div className="ws-info-section">
                    <div className="ws-info-header">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 6}}><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                      Workspace Info
                    </div>
                    <div className="ws-info-row">
                      <span className="ws-info-label">Name</span>
                      <span className="ws-info-value">{activeWs.name}</span>
                    </div>
                    <div className="ws-info-row">
                      <span className="ws-info-label">ID</span>
                      <span className="ws-info-value ws-info-id">{activeWs.id}</span>
                    </div>
                    <div className="ws-info-actions">
                      <button className="ws-copy-btn" onClick={(e) => { e.stopPropagation(); copyToClipboard(String(activeWs.id), "id"); }}>
                        {copiedField === "id" ? (
                          <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.5" style={{verticalAlign:"middle", marginRight: 4}}><polyline points="20 6 9 17 4 12"/></svg> Copied!</>
                        ) : (
                          <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 4}}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy ID</>
                        )}
                      </button>
                      <button className="ws-copy-btn" onClick={(e) => { e.stopPropagation(); copyToClipboard(`${window.location.origin}/join/${activeWs.id}`, "link"); }}>
                        {copiedField === "link" ? (
                          <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.5" style={{verticalAlign:"middle", marginRight: 4}}><polyline points="20 6 9 17 4 12"/></svg> Copied!</>
                        ) : (
                          <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 4}}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg> Copy Invite Link</>
                        )}
                      </button>
                    </div>
                    <div className="ws-divider" />
                  </div>
                )}

                {/* Workspace list */}
                {workspaces.length === 0 && (
                  <div className="ws-empty-hint">No workspaces yet</div>
                )}

                {workspaces.length > 0 && (
                  <div className="ws-list">
                    {workspaces.map((ws) => (
                      <div
                        key={ws.id}
                        className={`ws-option ${activeWs && activeWs.id === ws.id ? "active" : ""}`}
                        onClick={() => switchWorkspace(ws)}
                      >
                        <span className="ws-option-name">
                          <span className="ws-icon-inline">{ws.access_type === "open" ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>}</span>
                          {ws.name}
                        </span>
                        {ws.description && <span className="ws-desc">{ws.description}</span>}
                      </div>
                    ))}
                  </div>
                )}

                <div className="ws-divider" />

                {/* ALWAYS visible — Create workspace toggle / form */}
                {!showCreateWs ? (
                  <div className="ws-action ws-create" onClick={() => setShowCreateWs(true)}>
                    ＋ Create Workspace
                  </div>
                ) : (
                  <form className="ws-create-form" onSubmit={handleCreateWorkspace}>
                    <input
                      className="ws-create-input"
                      placeholder="Workspace name"
                      value={newWsName}
                      onChange={(e) => setNewWsName(e.target.value)}
                      autoFocus
                    />
                    <input
                      className="ws-create-input ws-create-desc"
                      placeholder="Description (optional)"
                      value={newWsDesc}
                      onChange={(e) => setNewWsDesc(e.target.value)}
                    />
                    <div className="ws-access-selector">
                      <label className="ws-access-option">
                        <input type="radio" name="ws-access" value="private" checked={newWsAccess === "private"} onChange={() => setNewWsAccess("private")} />
                        <span className="ws-access-label"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign: "middle", marginRight: 4}}><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Private</span>
                        <span className="ws-access-hint">Admin approval required</span>
                      </label>
                      <label className="ws-access-option">
                        <input type="radio" name="ws-access" value="open" checked={newWsAccess === "open"} onChange={() => setNewWsAccess("open")} />
                        <span className="ws-access-label"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign: "middle", marginRight: 4}}><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Open</span>
                        <span className="ws-access-hint">Anyone with the workspace ID can join</span>
                      </label>
                    </div>
                    <div className="ws-create-actions">
                      <button type="submit" className="ws-create-btn" disabled={wsCreating || !newWsName.trim()}>
                        {wsCreating ? "Creating…" : "Create"}
                      </button>
                      <button type="button" className="ws-cancel-btn" onClick={() => { setShowCreateWs(false); setWsError(""); }}>
                        Cancel
                      </button>
                    </div>
                    {wsError && <div className="ws-error">{String(wsError)}</div>}
                  </form>
                )}

                <div className="ws-divider" />

                {/* Join workspace — lookup by ID */}
                {!showJoinWs ? (
                  <div className="ws-action ws-join" onClick={() => { setShowJoinWs(true); setJoinWsResult(null); setJoinWsError(""); setJoinWsId(""); }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 6}}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    Join Workspace
                  </div>
                ) : (
                  <div className="ws-join-section">
                    <form className="ws-join-form" onSubmit={handleJoinLookup}>
                      <input
                        className="ws-create-input"
                        placeholder="Enter Workspace ID (shared by an admin)"
                        value={joinWsId}
                        onChange={(e) => setJoinWsId(e.target.value)}
                        autoFocus
                      />
                      <div className="ws-create-actions">
                        <button type="submit" className="ws-create-btn" disabled={joinWsLoading || !joinWsId.trim()}>
                          {joinWsLoading ? "Looking up\u2026" : "Look up"}
                        </button>
                        <button type="button" className="ws-cancel-btn" onClick={() => { setShowJoinWs(false); setJoinWsResult(null); setJoinWsError(""); }}>
                          Cancel
                        </button>
                      </div>
                    </form>

                    {joinWsError && <div className="ws-error" style={{ padding: "6px 10px" }}>{String(joinWsError)}</div>}

                    {joinWsResult && (
                      <div className="ws-join-result">
                        <div className="ws-join-found">
                          <span className="ws-join-found-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                          </span>
                          <div>
                            <div className="ws-join-found-name">{joinWsResult.name}</div>
                            {joinWsResult.description && <div className="ws-join-found-desc">{joinWsResult.description}</div>}
                            <div className="ws-join-access-badge">
                              {joinWsResult.access_type === "open"
                                ? <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 4}}><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Open workspace</>
                                : <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 4}}><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Private workspace</>}
                            </div>
                          </div>
                        </div>
                        {joinWsResult.access_type === "open" ? (
                          <button
                            className="ws-create-btn ws-join-btn"
                            onClick={handleJoinOpenWorkspace}
                            disabled={joinLoading}
                          >
                            {joinLoading ? "Joining\u2026" : "Join Workspace"}
                          </button>
                        ) : (
                          <div className="ws-join-admin-msg">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 5}}><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
                            This workspace is private. Ask an admin to add you as a member.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Leave & Delete workspace */}
                {activeWs && (
                  <>
                    <div className="ws-divider" />
                    <div className="ws-action ws-action-danger" onClick={handleLeaveWorkspace}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 6}}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                      Leave "{activeWs.name}"
                    </div>
                    <div className="ws-action ws-action-danger ws-delete-action" onClick={() => setShowDeleteConfirm(true)}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{verticalAlign:"middle", marginRight: 6}}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                      Delete Workspace
                    </div>
                  </>
                )}
              </div>
            </div>,
            document.body
          )}
        </div>
        <nav className="app-nav">
          {TABS.map((t) => (
            <button
              key={t}
              className={t === tab ? "active" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
          <button
            className="logout-btn"
            onClick={doLogout}
            title={`Logged in as ${user.name || "User"} (${user.email || ""})`}
          >
            <span className="user-avatar-sm">{getInitials(user.name)}</span>
            {user.name || "User"} · Logout
          </button>
        </nav>
      </header>

      <main className="page">
        {tab === "Chat" && <ChatPage onNavigate={setTab} user={user} workspace={activeWs} wsEpoch={wsEpoch} />}
        {tab === "Tasks" && <TasksPage user={user} workspace={activeWs} wsEpoch={wsEpoch} />}
        {tab === "Dashboard" && <DashboardPage workspace={activeWs} wsEpoch={wsEpoch} />}
        {tab === "Risk" && <RiskPage workspace={activeWs} wsEpoch={wsEpoch} />}
      </main>

      {/* ── Delete Workspace Confirmation Modal ── */}
      {showDeleteConfirm && activeWs && createPortal(
        <div className="delete-modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowDeleteConfirm(false); }}>
          <div className="delete-modal">
            <div className="delete-modal-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
            </div>
            <h3>Delete Workspace</h3>
            <p>Are you sure you want to delete <strong>"{activeWs.name}"</strong>? This will permanently remove all channels, messages, tasks, and members. This action cannot be undone.</p>
            <div className="delete-modal-actions">
              <button className="ws-cancel-btn" onClick={() => setShowDeleteConfirm(false)} disabled={deleteLoading}>Cancel</button>
              <button className="delete-confirm-btn" onClick={handleDeleteWorkspace} disabled={deleteLoading}>
                {deleteLoading ? "Deleting\u2026" : "Delete Permanently"}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
