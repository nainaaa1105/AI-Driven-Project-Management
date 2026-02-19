import React, { useState } from "react";
import LandingPage from "./pages/LandingPage";
import ChatPage from "./pages/ChatPage";
import TasksPage from "./pages/TasksPage";
import DashboardPage from "./pages/DashboardPage";
import RiskPage from "./pages/RiskPage";

const TABS = ["Chat", "Tasks", "Dashboard", "Risk"];

export default function App() {
  const [tab, setTab] = useState("Landing");

  if (tab === "Landing") {
    return <LandingPage onEnter={() => setTab("Chat")} onDashboard={() => setTab("Dashboard")} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 onClick={() => setTab("Landing")} style={{ cursor: "pointer" }}>Horizon</h1>
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
        </nav>
      </header>

      <main className="page">
        {tab === "Chat" && <ChatPage onNavigate={setTab} />}
        {tab === "Tasks" && <TasksPage />}
        {tab === "Dashboard" && <DashboardPage />}
        {tab === "Risk" && <RiskPage />}
      </main>
    </div>
  );
}
