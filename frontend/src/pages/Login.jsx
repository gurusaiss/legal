import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, saveSession } from "../api/client.js";

export default function Login({ onAuth }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("inspector");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result =
        mode === "login"
          ? await api.login(email, password)
          : await api.signup({ email, password, full_name: fullName, role });
      saveSession(result);
      onAuth();
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Legal Metrology Compliance Scanner</h1>
        <p className="subtitle">
          {mode === "login" ? "Sign in to continue" : "Create an enforcement officer account"}
        </p>

        {error && <div className="error-banner">{error}</div>}

        {mode === "signup" && (
          <>
            <label>Full name</label>
            <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="inspector">Inspector</option>
              <option value="auditor">Auditor</option>
              <option value="admin">Admin</option>
            </select>
          </>
        )}

        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />

        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />

        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        <div className="toggle-link">
          {mode === "login" ? (
            <>
              No account?{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); setMode("signup"); }}>
                Sign up
              </a>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); setMode("login"); }}>
                Sign in
              </a>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
