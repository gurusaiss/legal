import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!stats) return <p>Loading…</p>;

  return (
    <div>
      <h2 className="page-title">Enforcement Dashboard</h2>
      <p className="page-subtitle">Overview of scans, compliance rate and the most common violations.</p>

      <div className="grid grid-4">
        <div className="stat-card">
          <div className="stat-value">{stats.total_scans}</div>
          <div className="stat-label">Total Scans</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "#16a34a" }}>{stats.passed}</div>
          <div className="stat-label">Compliant</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "#dc2626" }}>{stats.violations}</div>
          <div className="stat-label">Violations</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "#d97706" }}>{stats.needs_review}</div>
          <div className="stat-label">Needs Review</div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Most Common Violations</h3>
          {stats.top_violations.length === 0 && <p style={{ color: "#64748b", fontSize: 13 }}>No violations recorded yet.</p>}
          {stats.top_violations.map((v, i) => (
            <div className="field-row" key={i}>
              <div className="field-name">{v.label}</div>
              <div className="field-value">{v.count}</div>
            </div>
          ))}
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Scans by Category</h3>
          {stats.by_category.length === 0 && <p style={{ color: "#64748b", fontSize: 13 }}>No categorized scans yet.</p>}
          {stats.by_category.map((c, i) => (
            <div className="field-row" key={i}>
              <div className="field-name">{c.category}</div>
              <div className="field-value">{c.count}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
