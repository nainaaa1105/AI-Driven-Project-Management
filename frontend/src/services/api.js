/**
 * api.js — Axios client for the FastAPI backend.
 *
 * Endpoints:
 *   POST /messages        — send chat message → ML pipeline
 *   GET  /tasks           — list all tasks
 *   GET  /dashboard       — aggregated stats
 *   POST /risk/predict    — standalone risk prediction
 */

import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE });

/* ── Chat ──────────────────────────────────────────────────────────── */

export async function sendMessage(content) {
  const res = await api.post("/messages", { content });
  return res.data;
}

/* ── Tasks ─────────────────────────────────────────────────────────── */

export async function fetchTasks(status) {
  const params = status ? { status } : {};
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

export async function fetchDashboard() {
  const res = await api.get("/dashboard");
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

/* ── WebSocket helper ─────────────────────────────────────────────── */

export function connectWebSocket(onMessage) {
  const wsUrl =
    (API_BASE.replace(/^http/, "ws")) + "/ws/chat";
  const ws = new WebSocket(wsUrl);
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
