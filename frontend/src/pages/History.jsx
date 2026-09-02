import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";

export default function History() {
  const navigate = useNavigate();
  const [scans, setScans] = useState([]);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const handle = setTimeout(() => {
      api.listScans(filter || undefined, search || undefined).then(setScans).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(handle);
  }, [filter, search]);

  return (
    <div>
      <h2 className="page-title">Scan History</h2>
      <p className="page-subtitle">Repository of previously scanned products and their compliance status.</p>

      <div className="card">
        <div className="grid grid-2">
          <div>
            <label>Search by product, category or label text</label>
            <input
              type="text"
              placeholder="e.g. sunflower oil, potato chips…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div>
            <label>Filter by status</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">All</option>
              <option value="pass">Compliant</option>
              <option value="violation">Violations</option>
              <option value="needs_review">Needs Review</option>
            </select>
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Product</th>
              <th>Category</th>
              <th>Status</th>
              <th>Score</th>
              <th>Rule Version</th>
              <th>Scanned At</th>
            </tr>
          </thead>
          <tbody>
            {scans.map((s) => (
              <tr key={s.id} className="clickable" onClick={() => navigate(`/scan/${s.id}`)}>
                <td>#{s.id}</td>
                <td>{s.product_name || "—"}</td>
                <td>{s.category || "—"}</td>
                <td><span className={`badge ${s.status}`}>{s.status.replace("_", " ")}</span></td>
                <td>{s.compliance_score != null ? `${Math.round(s.compliance_score * 100)}%` : "—"}</td>
                <td>{s.rule_version}</td>
                <td>{s.created_at ? new Date(s.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
            {scans.length === 0 && (
              <tr><td colSpan={7} style={{ color: "#64748b", textAlign: "center", padding: 20 }}>No scans yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
