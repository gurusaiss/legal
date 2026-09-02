import React, { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, getSession } from "../api/client.js";

const STATUS_LABEL = {
  pass: "Compliant",
  violation: "Violations Found",
  needs_review: "Needs Manual Review",
  processing: "Processing",
};

const FONT_CHECK_LABEL = {
  checked: "performed",
  skipped_no_calibration: "skipped (no calibration)",
  skipped_no_pack_dimensions: "skipped (marker found, but pack dimensions missing)",
};

const CALIBRATION_METHOD_LABEL = {
  marker: "auto-calibrated via marker",
  manual_edge_assumption: "manual estimate (frame-edge assumption)",
  none: null,
};

function confidenceColor(c) {
  if (c >= 0.75) return { background: "#dcfce7", color: "#166534" };
  if (c >= 0.5) return { background: "#fef3c7", color: "#92400e" };
  return { background: "#fee2e2", color: "#991b1b" };
}

export default function ScanResult() {
  const { id } = useParams();
  const session = getSession();
  const canAddEvidence = session?.role === "inspector" || session?.role === "admin";
  const evidenceInputRef = useRef(null);

  const [scan, setScan] = useState(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(null); // "pdf" | "docx" | null
  const [imageBlobUrl, setImageBlobUrl] = useState(null);
  const [evidenceBlobUrls, setEvidenceBlobUrls] = useState({});
  const [caption, setCaption] = useState("");
  const [uploadingEvidence, setUploadingEvidence] = useState(false);

  function load() {
    api.getScan(id).then(setScan).catch((e) => setError(e.message));
  }

  useEffect(load, [id]);

  useEffect(() => {
    if (!scan?.image_url) return;
    let revoke;
    api.fetchImageBlobUrl(scan.image_url).then((url) => {
      revoke = url;
      setImageBlobUrl(url);
    }).catch(() => {});
    return () => revoke && URL.revokeObjectURL(revoke);
  }, [scan?.image_url]);

  useEffect(() => {
    if (!scan?.evidence?.length) return;
    const urls = {};
    Promise.all(
      scan.evidence.map((e) =>
        api.fetchImageBlobUrl(e.image_url).then((url) => { urls[e.id] = url; })
      )
    ).then(() => setEvidenceBlobUrls({ ...urls }));
  }, [scan?.evidence]);

  async function handleAddEvidence(file) {
    if (!file) return;
    setUploadingEvidence(true);
    try {
      await api.addEvidence(scan.id, file, caption);
      setCaption("");
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadingEvidence(false);
    }
  }

  if (error) return <div className="error-banner">{error}</div>;
  if (!scan) return <p>Loading…</p>;

  const fieldEntries = Object.entries(scan.extracted_fields || {});

  return (
    <div>
      <h2 className="page-title">Scan #{scan.id} Result</h2>
      <p className="page-subtitle">
        {scan.product_name || "Unnamed product"} {scan.category ? `· ${scan.category}` : ""}
      </p>

      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <div>
          <span className={`badge ${scan.status}`}>{STATUS_LABEL[scan.status] || scan.status}</span>
          <span style={{ marginLeft: 14, color: "#64748b", fontSize: 13 }}>
            Compliance score: <strong>{Math.round((scan.compliance_score || 0) * 100)}%</strong>
          </span>
          <span style={{ marginLeft: 14, color: "#64748b", fontSize: 13 }}>
            Rule version applied: <strong>{scan.rule_version}</strong>
          </span>
          <span style={{ marginLeft: 14, color: "#64748b", fontSize: 13 }}>
            Font-size check:{" "}
            <strong>{FONT_CHECK_LABEL[scan.font_check_status] || scan.font_check_status}</strong>
            {scan.calibration_method && CALIBRATION_METHOD_LABEL[scan.calibration_method] && (
              <> ({CALIBRATION_METHOD_LABEL[scan.calibration_method]})</>
            )}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn secondary"
            disabled={downloading === "pdf"}
            onClick={async () => {
              setDownloading("pdf");
              try { await api.downloadReport(scan.id); } finally { setDownloading(null); }
            }}
          >
            {downloading === "pdf" ? "Preparing…" : "Download PDF"}
          </button>
          <button
            className="btn secondary"
            disabled={downloading === "docx"}
            onClick={async () => {
              setDownloading("docx");
              try { await api.downloadEditableReport(scan.id); } finally { setDownloading(null); }
            }}
          >
            {downloading === "docx" ? "Preparing…" : "Download Editable (DOCX)"}
          </button>
        </div>
      </div>

      {scan.quality_flags?.length > 0 && (
        <div className="card" style={{ borderColor: "#fbbf24" }}>
          <strong style={{ fontSize: 13 }}>Image quality notice:</strong>{" "}
          <span style={{ fontSize: 13, color: "#92400e" }}>
            {scan.quality_flags.join(", ")} — results may be less reliable; consider retaking the photo.
          </span>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 15 }}>Scanned Label</h3>
        {imageBlobUrl ? (
          <img src={imageBlobUrl} alt="Scanned label" style={{ maxWidth: "100%", maxHeight: 360, borderRadius: 8, border: "1px solid #e2e8f0" }} />
        ) : (
          <p style={{ color: "#64748b", fontSize: 13 }}>Loading image…</p>
        )}
      </div>

      {scan.violations?.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Violations & Flags ({scan.violations.length})</h3>
          {scan.violations.map((v, i) => (
            <div className={`violation-item ${v.severity}`} key={i}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{v.label}</div>
              <div className="rule-ref">{v.rule_ref} · {v.issue_type.replace("_", " ")}</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>{v.detail}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 15 }}>Extracted Declarations</h3>
        {fieldEntries.map(([key, f]) => (
          <div className="field-row" key={key}>
            <div className="field-name">{key.replace(/_/g, " ")}</div>
            <div className="field-value">
              {f.found ? (f.value?.length > 70 ? f.value.slice(0, 70) + "…" : f.value) : "— not detected —"}
              {f.found && (
                <span className="confidence-pill" style={confidenceColor(f.confidence)}>
                  {Math.round(f.confidence * 100)}%
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, fontSize: 15 }}>Supporting Evidence ({scan.evidence?.length || 0})</h3>
        {scan.evidence?.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: canAddEvidence ? 16 : 0 }}>
            {scan.evidence.map((e) => (
              <div key={e.id} style={{ width: 160 }}>
                {evidenceBlobUrls[e.id] ? (
                  <img src={evidenceBlobUrls[e.id]} alt={e.caption || "evidence"} style={{ width: "100%", borderRadius: 6, border: "1px solid #e2e8f0" }} />
                ) : (
                  <div style={{ width: "100%", height: 100, background: "#f1f5f9", borderRadius: 6 }} />
                )}
                {e.caption && <p style={{ fontSize: 12, color: "#64748b", margin: "4px 0 0" }}>{e.caption}</p>}
              </div>
            ))}
          </div>
        )}
        {canAddEvidence && (
          <div>
            <label>Add supporting photo (optional caption)</label>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <input type="text" placeholder="e.g. Close-up of missing MRP" value={caption} onChange={(e) => setCaption(e.target.value)} style={{ marginBottom: 0 }} />
              <button className="btn secondary" type="button" disabled={uploadingEvidence} onClick={() => evidenceInputRef.current?.click()}>
                {uploadingEvidence ? "Uploading…" : "Attach Photo"}
              </button>
            </div>
            <input
              ref={evidenceInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: "none" }}
              onChange={(e) => handleAddEvidence(e.target.files?.[0])}
            />
          </div>
        )}
      </div>

      <Link to="/scan" className="btn secondary">Scan another product</Link>
    </div>
  );
}
