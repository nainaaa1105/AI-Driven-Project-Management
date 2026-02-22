import React, { useEffect, useRef } from "react";
import "./LandingPage.css";

/* ── Abstract SVG icons (no emojis) ── */
const IconAutoTask = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 12l2 2 4-4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/>
  </svg>
);
const IconSmartLink = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
  </svg>
);
const IconRisk = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);
const IconSummary = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
  </svg>
);

/* Flow step icons */
const IconChat = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);
const IconBrain = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><path d="M2 12h20"/>
  </svg>
);
const IconChart = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
);

const FEATURES = [
  { Icon: IconAutoTask, title: "Auto Task Creation", desc: "Chat messages are parsed by AI into structured, tracked tasks automatically." },
  { Icon: IconSmartLink, title: "Smart Updates & Dependencies", desc: "Detects duplicates, links related tasks, and tracks dependency chains." },
  { Icon: IconRisk, title: "Risk Prediction & Alerts", desc: "ML-powered risk scoring with SHAP explanations and real-time alerts." },
  { Icon: IconSummary, title: "Executive AI Summaries", desc: "Every message produces a structured executive report with domains, urgency, and contacts." },
];

const FLOW_STEPS = [
  { Icon: IconChat, label: "Chat", desc: "Reads team conversations" },
  { Icon: IconBrain, label: "AI", desc: "Understands tasks, risks & intent" },
  { Icon: IconChart, label: "Insights", desc: "Creates tasks, alerts & dashboards" },
];

export default function LandingPage({ onEnter, onDashboard }) {
  const sectionsRef = useRef([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.15 }
    );
    sectionsRef.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const addRef = (el) => {
    if (el && !sectionsRef.current.includes(el)) sectionsRef.current.push(el);
  };

  return (
    <div className="landing">
      {/* Noise / grain overlay */}
      <div className="noise-overlay" aria-hidden="true" />

      {/* Geometric background shapes */}
      <div className="geo-shapes" aria-hidden="true">
        <div className="geo geo-1" />
        <div className="geo geo-2" />
        <div className="geo geo-3" />
      </div>

      {/* 1. HERO */}
      <section className="hero">
        <div className="hero-glow" />
        <div className="hero-glow-left" />
        <div className="hero-glow-right" />
        <div className="hero-horizon-line" />
        <div className="hero-content fade-up">
          <h1 className="hero-title">
            <span className="gradient-text">Horizon</span>
          </h1>
          <p className="hero-tagline">AI Project Intelligence</p>
          <p className="hero-sub">From conversations to clarity. Automatically.</p>
          <p className="hero-quote">"Great teams don't track work -- intelligence does."</p>
          <div className="hero-ctas">
            <button className="btn-glow" onClick={onEnter}>Get Started</button>
            <button className="btn-glass" onClick={onDashboard}>View Dashboard</button>
          </div>
        </div>
        <div className="hero-particles" aria-hidden="true">
          {[...Array(6)].map((_, i) => (
            <span key={i} className="particle" style={{ "--i": i }} />
          ))}
        </div>
      </section>

      {/* 2. HOW IT WORKS */}
      <section className="section how-it-works" ref={addRef}>
        <h2 className="section-title">How It Works</h2>
        <div className="flow-row">
          {FLOW_STEPS.map((step, i) => (
            <React.Fragment key={i}>
              <div className="flow-card" style={{ "--delay": `${i * 0.15}s` }}>
                <div className="flow-icon"><step.Icon /></div>
                <h3>{step.label}</h3>
                <p>{step.desc}</p>
              </div>
              {i < FLOW_STEPS.length - 1 && (
                <div className="flow-arrow">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--lp-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* 3. KEY FEATURES */}
      <section className="section features" ref={addRef}>
        <h2 className="section-title">Key Features</h2>
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div className="feature-card glass" key={i} style={{ "--delay": `${i * 0.1}s` }}>
              <div className="feature-icon"><f.Icon /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 4. LIVE PREVIEW */}
      <section className="section preview" ref={addRef}>
        <h2 className="section-title">Live Dashboard Preview</h2>
        <p className="section-sub">See your project thinking in real-time</p>
        <div className="mock-dashboard glass">
          <div className="mock-row">
            <div className="mock-stat"><div className="mock-value pulse-glow">12</div><div className="mock-label">Tasks</div></div>
            <div className="mock-stat"><div className="mock-value pulse-glow" style={{ color: "var(--yellow)" }}>3</div><div className="mock-label">At Risk</div></div>
            <div className="mock-stat"><div className="mock-value pulse-glow" style={{ color: "var(--green)" }}>72%</div><div className="mock-label">Health</div></div>
            <div className="mock-stat"><div className="mock-value pulse-glow" style={{ color: "var(--red)" }}>2</div><div className="mock-label">Alerts</div></div>
          </div>
          <div className="mock-bars">
            {[65, 40, 85, 30, 55, 75].map((h, i) => (
              <div key={i} className="mock-bar" style={{ "--h": `${h}%`, "--delay": `${i * 0.08}s` }} />
            ))}
          </div>
        </div>
      </section>

      {/* 5. FINAL CTA */}
      <section className="section final-cta" ref={addRef}>
        <p className="final-quote">"Don't manage projects. <span className="gradient-text">Predict them.</span>"</p>
        <button className="btn-glow large" onClick={onEnter}>Launch AI Intelligence</button>
      </section>

      <footer className="landing-footer">
        <span>Horizon -- AI Project Intelligence -- Built with FastAPI, React & ML</span>
      </footer>
    </div>
  );
}
