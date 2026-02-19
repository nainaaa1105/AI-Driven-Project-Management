import React, { useEffect, useState } from "react";
import { fetchTasks, updateTaskStatus, deleteTask, updateTask, fetchCustomDomains, createCustomDomain } from "../services/api";

const STATUSES = ["open", "in-progress", "updated", "resolved"];
const URGENCIES = ["normal", "low", "medium", "high"];
const DEFAULT_DOMAIN_OPTIONS = [
  "frontend", "backend", "devops", "design", "security",
  "database", "testing", "mobile", "infrastructure", "General",
];

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingTask, setEditingTask] = useState(null);

  /* ── form state for the update modal ── */
  const [noteText, setNoteText] = useState("");
  const [selDomains, setSelDomains] = useState([]);
  const [selUrgency, setSelUrgency] = useState("normal");
  const [selStatus, setSelStatus] = useState("open");
  const [submitting, setSubmitting] = useState(false);

  /* ── custom domain state ── */
  const [customDomains, setCustomDomains] = useState([]);
  const [showAddDomain, setShowAddDomain] = useState(false);
  const [newDomainInput, setNewDomainInput] = useState("");

  const allDomainOptions = [...DEFAULT_DOMAIN_OPTIONS, ...customDomains];

  const load = async () => {
    setLoading(true);
    try { setTasks(await fetchTasks()); }
    catch (err) { console.error("Failed to load tasks", err); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { fetchCustomDomains().then(setCustomDomains).catch(() => {}); }, []);

  const handleStatusChange = async (taskId, newStatus) => {
    try { await updateTaskStatus(taskId, newStatus); load(); }
    catch (err) { console.error("Failed to update status", err); }
  };

  const handleDelete = async (taskId) => {
    if (!window.confirm(`Delete task #${taskId}? This cannot be undone.`)) return;
    try {
      await deleteTask(taskId);
      /* If the update modal is open for the deleted task, close it */
      if (editingTask && editingTask.id === taskId) setEditingTask(null);
      load();
    }
    catch (err) { console.error("Failed to delete task", err); }
  };

  /* ── open the update modal, pre-fill from task ── */
  const openUpdateModal = (task) => {
    setEditingTask(task);
    setNoteText("");
    setSelDomains(task.domain ? task.domain.split(",").map((d) => d.trim()).filter(Boolean) : []);
    setSelUrgency(task.urgency || "normal");
    setSelStatus(task.status || "open");
    setShowAddDomain(false);
    setNewDomainInput("");
  };

  const closeModal = () => setEditingTask(null);

  const handleUpdateSubmit = async () => {
    if (!editingTask) return;
    setSubmitting(true);
    try {
      const payload = {};
      if (noteText.trim()) payload.update_note = noteText.trim();
      if (selDomains.length) payload.domains = selDomains;
      if (selUrgency) payload.urgency = selUrgency;
      if (selStatus) payload.status = selStatus;
      await updateTask(editingTask.id, payload);
      closeModal();
      load();
    } catch (err) {
      console.error("Failed to update task", err);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleDomain = (d) => {
    setSelDomains((prev) => prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]);
  };

  const handleAddCustomDomain = async () => {
    const name = newDomainInput.trim();
    if (!name) return;
    if (allDomainOptions.some((d) => d.toLowerCase() === name.toLowerCase())) {
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

  /* ── group tasks by status for Kanban ── */
  const grouped = {};
  STATUSES.forEach((s) => (grouped[s] = []));
  tasks.forEach((t) => {
    const s = STATUSES.includes(t.status) ? t.status : "open";
    grouped[s].push(t);
  });

  if (loading) return <p style={{ color: "var(--text-dim)" }}>Loading tasks...</p>;

  return (
    <>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ fontSize: "1.1rem" }}>Task Board</h2>
        <button onClick={load} className="btn-outline">Refresh</button>
      </div>

      {/* Kanban board */}
      <div className="task-board">
        {STATUSES.map((status) => (
          <div className="task-column" key={status}>
            <h3>{status} ({grouped[status].length})</h3>
            {grouped[status].length === 0 && (
              <p style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>No tasks</p>
            )}
            {grouped[status].map((task) => (
              <div className="task-card" key={task.id}>
                <div className="task-id-label">Task #{task.id}</div>
                <div className="title">{task.title}</div>
                <div className="meta">
                  <span className={`risk-badge ${task.risk_level || "Low"}`} title="Risk reflects likelihood of failure, not urgency">
                    {task.risk_level || "Low"} ({((task.risk_score || 0) * 100).toFixed(0)}%)
                  </span>
                  <span>{task.domain}</span>
                  <span className="urgency-tag">{task.urgency || "normal"}</span>
                  {task.similarity_label !== "NEW" && (
                    <span style={{ color: "var(--yellow)" }}>{task.similarity_label}</span>
                  )}
                </div>

                {/* Notes preview */}
                {task.update_notes && (
                  <div className="task-notes-preview">{task.update_notes.split("\n").pop()}</div>
                )}

                <div className="actions">
                  <select
                    value={task.status}
                    onChange={(e) => handleStatusChange(task.id, e.target.value)}
                  >
                    {STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
                  </select>

                  <button className="btn-icon btn-update" title="Add Update" onClick={() => openUpdateModal(task)}>
                    Edit
                  </button>
                  <button className="btn-icon btn-delete" title="Delete task" onClick={() => handleDelete(task.id)}>
                    Del
                  </button>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* ── Update Modal ── */}
      {editingTask && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Update Task #{editingTask.id} &mdash; {editingTask.title}</h3>
              <button className="modal-close" onClick={closeModal}>&times;</button>
            </div>
            <p className="modal-task-title">{editingTask.description || editingTask.title}</p>

            {/* Update Note */}
            <label className="modal-label">Update Note</label>
            <textarea
              className="modal-textarea"
              rows={3}
              placeholder="What changed? Add a progress note..."
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />

            {/* Domains multi-select with custom domain */}
            <label className="modal-label">Domains</label>
            <div className="domain-chips">
              {allDomainOptions.map((d) => (
                <button
                  key={d}
                  className={`chip ${selDomains.includes(d) ? "active" : ""}`}
                  onClick={() => toggleDomain(d)}
                >{d}</button>
              ))}
              {!showAddDomain ? (
                <button className="chip chip-add" onClick={() => setShowAddDomain(true)}>+ Add Custom</button>
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

            {/* Urgency */}
            <label className="modal-label">Urgency</label>
            <select className="modal-select" value={selUrgency} onChange={(e) => setSelUrgency(e.target.value)}>
              {URGENCIES.map((u) => (<option key={u} value={u}>{u.charAt(0).toUpperCase() + u.slice(1)}</option>))}
            </select>

            {/* Status */}
            <label className="modal-label">Status</label>
            <select className="modal-select" value={selStatus} onChange={(e) => setSelStatus(e.target.value)}>
              {STATUSES.map((s) => (<option key={s} value={s}>{s}</option>))}
            </select>

            {/* Previous notes */}
            {editingTask.update_notes && (
              <>
                <label className="modal-label" style={{ marginTop: 14 }}>History</label>
                <div className="notes-history">
                  {editingTask.update_notes.split("\n").map((line, i) => (
                    <div key={i} className="note-entry">{line}</div>
                  ))}
                </div>
              </>
            )}

            <button className="btn-primary modal-submit" onClick={handleUpdateSubmit} disabled={submitting}>
              {submitting ? "Saving..." : "Save Update"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
