import React, { useState } from "react";
import { registerUser, loginUser } from "../services/api";
import "./AuthPage.css";

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let data;
      if (mode === "register") {
        data = await registerUser({ name, email, password });
      } else {
        data = await loginUser({ email, password });
      }

      // Persist JWT & user info
      localStorage.setItem("token", data.access_token);
      localStorage.setItem(
        "user",
        JSON.stringify({ id: data.user_id, name: data.name, email: data.email })
      );

      onAuth(data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(", "));
      } else {
        setError(err.message || "Something went wrong");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card glass">
        <h1 className="auth-logo">
          <span className="gradient-text">Horizon</span>
        </h1>
        <p className="auth-tagline">AI Project Intelligence</p>

        <div className="auth-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Sign In
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <input
              type="text"
              placeholder="Full Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={1}
              autoComplete="name"
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
          />

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading
              ? "Please wait…"
              : mode === "login"
              ? "Sign In"
              : "Create Account"}
          </button>
        </form>

        <p className="auth-switch">
          {mode === "login" ? (
            <>
              Don't have an account?{" "}
              <button onClick={() => { setMode("register"); setError(""); }}>Register</button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button onClick={() => { setMode("login"); setError(""); }}>Sign In</button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
