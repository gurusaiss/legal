import React, { useState } from "react";
import { Routes, Route, Navigate, NavLink, useNavigate } from "react-router-dom";
import { getSession, clearSession } from "./api/client.js";
import Login from "./pages/Login.jsx";
import UploadScan from "./pages/UploadScan.jsx";
import ScanResult from "./pages/ScanResult.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import History from "./pages/History.jsx";

function RequireAuth({ children }) {
  const session = getSession();
  if (!session) return <Navigate to="/login" replace />;
  return children;
}

function Shell({ children }) {
  const navigate = useNavigate();
  const session = getSession();

  function handleLogout() {
    clearSession();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Legal Metrology Scanner</h1>
        <p className="sub">Packaged Commodities Compliance</p>
        {session?.role !== "auditor" && (
          <NavLink to="/scan" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
            + New Scan
          </NavLink>
        )}
        <NavLink to="/dashboard" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
          Dashboard
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
          Scan History
        </NavLink>
        <div className="sidebar-footer">
          {session?.name} <br />
          <span style={{ textTransform: "capitalize" }}>{session?.role}</span>
          <div style={{ marginTop: 10 }}>
            <a href="#" onClick={(e) => { e.preventDefault(); handleLogout(); }} style={{ color: "#93c5fd" }}>
              Sign out
            </a>
          </div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

export default function App() {
  const [, forceRerender] = useState(0);

  return (
    <Routes>
      <Route path="/login" element={<Login onAuth={() => forceRerender((n) => n + 1)} />} />
      <Route
        path="/scan"
        element={
          <RequireAuth>
            <Shell>
              <UploadScan />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/scan/:id"
        element={
          <RequireAuth>
            <Shell>
              <ScanResult />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Shell>
              <Dashboard />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/history"
        element={
          <RequireAuth>
            <Shell>
              <History />
            </Shell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to={getSession() ? "/dashboard" : "/login"} replace />} />
    </Routes>
  );
}
