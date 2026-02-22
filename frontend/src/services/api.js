/**
 * api.js — Axios client for the FastAPI backend.
 *
 * Endpoints:
 *   POST /auth/register   — create account → JWT
 *   POST /auth/login      — login → JWT
 *   POST /messages        — send chat message → ML pipeline
 *   GET  /tasks           — list all tasks
 *   GET  /dashboard       — aggregated stats
 *   POST /risk/predict    — standalone risk prediction
 *   GET  /workspaces/     — list user workspaces
 *   POST /workspaces/     — create workspace
 *   GET  /workspaces/:id/members — list members
 *   DELETE /workspaces/:id/members/:uid — remove member
 */

import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE });

/* ── JWT interceptors ──────────────────────────────────────────────── */

// Attach token to every outgoing request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear token & redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      // Dispatch a custom event so App.js can react
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(err);
  }
);

/* ── Auth ──────────────────────────────────────────────────────────── */

export async function registerUser({ name, email, password }) {
  const res = await api.post("/auth/register", { name, email, password });
  return res.data; // { access_token, user_id, name, email }
}

export async function loginUser({ email, password }) {
  const res = await api.post("/auth/login", { email, password });
  return res.data; // { access_token, user_id, name, email }
}

/* ── Chat ──────────────────────────────────────────────────────────── */

export async function sendMessage(content, workspaceId) {
  const body = { content };
  if (workspaceId) body.workspace_id = workspaceId;
  const res = await api.post("/messages", body);
  return res.data;
}

/* ── Tasks ─────────────────────────────────────────────────────────── */

export async function fetchTasks(status, workspaceId) {
  const params = {};
  if (status) params.status = status;
  if (workspaceId) params.workspace_id = workspaceId;
  const res = await api.get("/tasks", { params });
  return res.data;
}

export async function updateTaskStatus(taskId, newStatus) {
  const res = await api.patch(`/tasks/${taskId}/status`, null, {
    params: { new_status: newStatus },
  });
  return res.data;
}

export async function deleteTask(taskId) {
  const res = await api.delete(`/tasks/${taskId}`);
  return res.data;
}

export async function updateTask(taskId, payload) {
  const res = await api.patch(`/tasks/${taskId}`, payload);
  return res.data;
}

/* ── Dashboard ─────────────────────────────────────────────────────── */

export async function fetchDashboard(workspaceId) {
  const params = {};
  if (workspaceId) params.workspace_id = workspaceId;
  const res = await api.get("/dashboard", { params });
  return res.data;
}

/* ── Custom Domains ────────────────────────────────────────────────── */

export async function fetchCustomDomains() {
  const res = await api.get("/domains");
  return res.data;
}

export async function createCustomDomain(name) {
  const res = await api.post("/domains", null, { params: { name } });
  return res.data;
}

/* ── Risk ──────────────────────────────────────────────────────────── */

export async function predictRisk(features) {
  const res = await api.post("/risk/predict", features);
  return res.data;
}

export async function fetchWorkspaceRisk(workspaceId) {
  const res = await api.get(`/risk/workspace/${workspaceId}`);
  return res.data;
}

/* ── Workspaces ────────────────────────────────────────────────────── */

export async function fetchWorkspaces() {
  const res = await api.get("/workspaces/");
  return res.data; // [{ id, name, description, created_by, created_at }]
}

export async function fetchWorkspaceById(id) {
  const res = await api.get(`/workspaces/${id}/lookup`);
  return res.data; // { id, name, description, access_type }
}

export async function createWorkspace(name, description, accessType) {
  const res = await api.post("/workspaces/", {
    name,
    description: description || "",
    access_type: accessType || "private",
  });
  return res.data; // { id, name, description, access_type, created_by, created_at }
}

export async function fetchWorkspaceMembers(workspaceId) {
  const res = await api.get(`/workspaces/${workspaceId}/members`);
  return res.data; // [{ id, workspace_id, user_id, role, name, email, joined_at }]
}

export async function addWorkspaceMember(workspaceId, userId, role) {
  const res = await api.post(`/workspaces/${workspaceId}/members`, {
    user_id: userId,
    role: role || "member",
  });
  return res.data;
}

export async function joinWorkspace(workspaceId) {
  const res = await api.post(`/workspaces/${workspaceId}/join`);
  return res.data;
}

export async function deleteWorkspace(workspaceId) {
  const res = await api.delete(`/workspaces/${workspaceId}`);
  return res.data;
}

export async function leaveWorkspace(workspaceId, userId) {
  const res = await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
  return res.data;
}

/* ── Users ─────────────────────────────────────────────────────────── */

export async function fetchMe() {
  const res = await api.get("/auth/me");
  return res.data;
}

/* ── WebSocket helper ─────────────────────────────────────────────── */

export function connectWebSocket(workspaceId, onMessage) {
  const token = localStorage.getItem("token");
  const wsUrl =
    (API_BASE.replace(/^http/, "ws")) + `/ws/workspace/${workspaceId}?token=${encodeURIComponent(token || "")}`;
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    console.log(`[WS] Connected to workspace ${workspaceId}`);
  };
  ws.onerror = (err) => {
    console.error(`[WS] Error on workspace ${workspaceId}:`, err);
  };
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      onMessage({ raw: event.data });
    }
  };
  return ws;
}
