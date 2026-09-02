import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";

export default function UploadScan() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [productName, setProductName] = useState("");
  const [category, setCategory] = useState("");
  const [packDate, setPackDate] = useState("");
  const [packWidthMm, setPackWidthMm] = useState("");
  const [packHeightMm, setPackHeightMm] = useState("");
  const [calibrationConfirmed, setCalibrationConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [downloadingMarker, setDownloadingMarker] = useState(false);

  function handleFile(f) {
    if (!f) return;
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) {
      setError("Please select or capture a product label image.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const result = await api.uploadScan({
        file,
        productName,
        category,
        packDateHint: packDate,
        packWidthMm,
        packHeightMm,
        calibrationConfirmed,
      });
      navigate(`/scan/${result.id}`);
    } catch (err) {
      setError(err.message || "Scan failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 className="page-title">New Compliance Scan</h2>
      <p className="page-subtitle">
        Upload or capture a photo of the product label. The system will detect mandatory declarations and
        check them against the Legal Metrology (Packaged Commodities) Rules, 2011 — using the rule version
        applicable to the product's packing date.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="card">
          <div
            className="dropzone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              handleFile(e.dataTransfer.files?.[0]);
            }}
          >
            {previewUrl ? (
              <img src={previewUrl} alt="preview" />
            ) : (
              <>
                <p style={{ fontSize: 15, margin: 0 }}>Click to upload or drag a label photo here</p>
                <p style={{ fontSize: 12, margin: "6px 0 0" }}>JPG, PNG or WEBP — up to 15MB</p>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            style={{ display: "none" }}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>

        <div className="card">
          <div className="grid grid-2">
            <div>
              <label>Product name (optional)</label>
              <input type="text" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="e.g. Refined Sunflower Oil 1L" />
            </div>
            <div>
              <label>Category (optional)</label>
              <input type="text" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Edible Oil" />
            </div>
          </div>
          <label>Manufacture / packing date (if known — determines which rule version applies)</label>
          <input type="date" value={packDate} onChange={(e) => setPackDate(e.target.value)} />
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Font-Size Check (optional)</h3>
          <p style={{ fontSize: 13, color: "#64748b", marginTop: -8, marginBottom: 14 }}>
            Rule 7 / Second Schedule sets a minimum character height for the net quantity and MRP
            declarations, scaled to the pack's surface area. Checking this needs (1) an accurate
            pixels-to-millimetres scale, and (2) the pack's physical size to pick the right minimum.
          </p>

          <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: 12, marginBottom: 16 }}>
            <strong style={{ fontSize: 13 }}>Best accuracy: use the calibration marker</strong>
            <p style={{ fontSize: 12.5, color: "#334155", margin: "6px 0 10px" }}>
              Print the marker sheet at actual size (100% scale, not "fit to page"), place it flat next
              to the product, and include it in the photo. The system detects it automatically and reads
              the true pixel-to-mm scale from it — no assumptions about how the photo was framed, and it
              works even if the shot isn't perfectly straight-on.
            </p>
            <button
              type="button"
              className="btn secondary"
              disabled={downloadingMarker}
              onClick={async () => {
                setDownloadingMarker(true);
                try { await api.downloadCalibrationMarker(); } catch (e) { setError(e.message); } finally { setDownloadingMarker(false); }
              }}
            >
              {downloadingMarker ? "Preparing…" : "Download Calibration Marker (PDF)"}
            </button>
          </div>

          <div className="grid grid-2">
            <div>
              <label>Pack width (mm)</label>
              <input
                type="text"
                inputMode="decimal"
                value={packWidthMm}
                onChange={(e) => setPackWidthMm(e.target.value)}
                placeholder="e.g. 80"
              />
            </div>
            <div>
              <label>Pack height (mm)</label>
              <input
                type="text"
                inputMode="decimal"
                value={packHeightMm}
                onChange={(e) => setPackHeightMm(e.target.value)}
                placeholder="e.g. 150"
              />
            </div>
          </div>
          <p style={{ fontSize: 12, color: "#64748b", marginTop: -8 }}>
            Needed either way — the marker fixes the pixel scale, but the legal minimum font size still
            depends on how big the pack itself is.
          </p>

          <label style={{ display: "flex", alignItems: "flex-start", gap: 8, fontWeight: 400, cursor: "pointer", marginTop: 4 }}>
            <input
              type="checkbox"
              checked={calibrationConfirmed}
              onChange={(e) => setCalibrationConfirmed(e.target.checked)}
              style={{ width: "auto", marginTop: 3 }}
            />
            <span>
              No marker in this photo — fall back to a rougher estimate by assuming the pack's outer
              edges reach the left and right edges of the frame (I confirm this photo is a straight-on,
              uncropped shot). If a marker is detected in the photo, it's used instead of this fallback
              automatically. Leave everything in this section blank/unchecked to skip the font-size
              check — every other check still runs.
            </span>
          </label>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Analyzing label…" : "Run Compliance Check"}
        </button>
      </form>
    </div>
  );
}
