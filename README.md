# Legal Metrology Compliance Scanner (SIH26034)

Software system to check compliance of packaged commodities under the **Legal
Metrology (Packaged Commodities) Rules, 2011** by scanning product labels and
images. Built for enforcement officers to get an automated first-pass
compliance read instead of manually cross-referencing every declaration.

## What's working right now

- **Full pipeline**: image upload → quality gate (blur/glare/resolution) →
  deskew/enhance → OCR (Tesseract) → structured field extraction (regex +
  keyword-window NLP) → **versioned rule engine** → pass/violation/needs-review
  result → PDF report.
- **Versioned rule database** (`backend/rules/*.json`): base 2011 rules plus a
  2017 and 2022 amendment layer, selected automatically by the product's
  declared packing date so a 2017-packed product isn't judged against 2022
  rules.
- **Confidence scoring**: every extracted field carries a confidence score;
  low-confidence hits route to `needs_review` instead of being silently
  trusted as a pass or auto-failed as a violation.
- **Auth + roles**: JWT login/signup, `inspector` / `auditor` / `admin` roles.
- **Repository**: every scan (image, OCR text, extracted fields, violations,
  score) is persisted in SQLite via SQLAlchemy.
- **Dashboard**: total scans, compliance rate, most common violations, scans
  by category.
- **PDF compliance report**: per-scan, downloadable, cites the exact rule
  clause violated.
- **React frontend**: login/signup, upload-and-scan, scan result view,
  history/repository search, dashboard.
- **Scanned image + evidence photos**: the processed label image is shown on
  the scan result page (served via an authenticated endpoint, not a public
  static mount), and inspectors/admins can attach additional supporting
  photos to an existing scan (`POST /scans/{id}/evidence`).
- **Search**: history page supports free-text search across product name,
  category and the raw OCR text (`GET /scans?q=...`), plus the existing
  status filter.
- **Role enforcement**: `inspector`/`admin` can create scans and attach
  evidence; `auditor` is read-only (dashboard, history, scan detail, both
  report formats) — enforced server-side via `require_role`, not just hidden
  in the UI.
- **Editable report export**: `GET /scans/{id}/report/editable` generates a
  `.docx` version of the same compliance report, alongside the PDF.

## What's intentionally simplified for the hackathon MVP (see `backend/rules/*.json` `verification_note` fields)

- OCR is Tesseract, not PaddleOCR — swappable later, see `app/services/ocr.py`
  (interface is provider-agnostic on purpose).
- Font-size compliance checking is wired in with two calibration sources,
  in priority order: (1) the printed ArUco reference marker
  (`GET /calibration/marker.pdf`, auto-detected via `preprocessing.detect_reference_marker`)
  gives a ground-truth px-per-mm ratio regardless of framing/angle; (2) if no
  marker is found, a manual fallback assumes the pack fills the photo's
  width edge-to-edge (`calibration_confirmed` checkbox, deliberately
  labelled as a rougher estimate). Either way, the Second Schedule's area
  band still needs the pack's physical width/height entered separately —
  the marker fixes the *scale*, not the *pack size*.
- Perspective correction handles skew, not full curved-can unwrapping.
- Amendment rule text (2017/2022) is summarized for prototyping and is
  flagged in each JSON file as needing cross-verification against the
  official gazette notification before any real enforcement use.
- `common_name` extraction falls back to "largest text block on the label"
  when no explicit "Common Name:" keyword is present — flagged at low
  confidence for manual confirmation, since most real labels just print the
  product name without a label prefix.
- Signup lets anyone self-select `admin`/`auditor`/`inspector` — fine for a
  hackathon demo, not for real deployment. A real rollout needs an
  invite/approval flow so role assignment isn't self-service.

## Architecture

```
Image → Preprocessing (OpenCV: quality gate, deskew, CLAHE)
      → OCR (Tesseract, word-level bboxes)
      → Field Extraction (regex/keyword NLP → MRP, net qty, dates, mfr, consumer care...)
      → Rule Engine (versioned Rules JSON → validation → pass/violation/needs_review)
      → Repository (SQLite) + PDF Report (ReportLab) + Dashboard (FastAPI + React)
```

- `backend/app/services/preprocessing.py` — image quality gate + deskew/enhance
- `backend/app/services/ocr.py` — OCR wrapper (Tesseract, swappable)
- `backend/app/services/field_extractor.py` — OCR text → structured declarations
- `backend/app/services/rule_engine.py` — versioned rule selection + compliance evaluation
- `backend/app/services/report_generator.py` — PDF report
- `backend/rules/*.json` — the actual legal rule database, versioned by effective date
- `backend/app/routers/` — FastAPI endpoints (auth, scans, dashboard)
- `frontend/src/pages/` — Login, UploadScan, ScanResult, Dashboard, History

## Running it locally

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # Windows; use venv/bin on Linux/Mac
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Requires the Tesseract OCR binary installed separately (already detected on
this machine at `C:\Program Files\Tesseract-OCR\tesseract.exe`).

Quick pipeline sanity check without the HTTP layer:
```bash
./venv/Scripts/python scripts/smoke_test.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, talks to the backend on `http://127.0.0.1:8000`.

### Deployment — live link (Render + Vercel)

This is the path used for the actual hosted demo.

1. **Push this repo to GitHub** (`git remote add origin <url> && git push -u origin master`).
2. **Backend → Render**: New → Blueprint → point it at the GitHub repo. Render
   reads [`render.yaml`](render.yaml) automatically — it builds
   `backend/Dockerfile`, mounts a persistent Disk at `/data`, and generates
   `LM_JWT_SECRET` for you. `LM_DATABASE_URL`, `LM_UPLOADS_DIR` and
   `LM_REPORTS_DIR` all point at that disk (see `backend/app/paths.py`) so
   scans, images and reports survive restarts and redeploys — the `starter`
   plan is required for this (Render's free tier has no persistent disk, so
   the DB and uploads would reset on every redeploy). Note the resulting
   backend URL, e.g. `https://legal-metrology-backend.onrender.com`.
3. **Frontend → Vercel**: import the repo, set the root directory to
   `frontend`, and set the env var `VITE_API_BASE` to the Render URL from
   step 2. Vercel auto-detects the Vite build. Deploy — this is the link you
   actually share.
4. **Close the loop**: back on Render, set `LM_ALLOWED_ORIGINS` to the Vercel
   URL from step 3 (comma-separated if there's more than one, e.g. a preview
   + production URL) and redeploy the backend — otherwise the browser blocks
   every API call from the frontend as a CORS violation. See
   `backend/app/main.py` for how this is read.

### Deployment (Docker, self-hosted / local)

```bash
docker compose up --build
```

Brings up both services: backend on `http://localhost:8000` (FastAPI +
Tesseract baked into the image), frontend on `http://localhost:5173` (static
build served by nginx). The SQLite database, uploaded images and generated
reports persist in named Docker volumes (`backend_db`, `backend_data`,
`backend_reports`) across container restarts.

Two things to override for anything beyond a local demo:
- `LM_JWT_SECRET` — set a real secret (`LM_JWT_SECRET=... docker compose up`);
  the default in `docker-compose.yml` is explicitly a dev-only placeholder.
- `VITE_API_BASE` (frontend build arg) — defaults to `http://localhost:8000`,
  which only works when the browser and backend share the same host. Point it
  at wherever the backend is actually reachable from the browser for any
  multi-host deployment.

The frontend is a static SPA build — `VITE_API_BASE` is baked in at `docker
build` time, not read at container start. Changing it means rebuilding the
frontend image.

## Who buys this (positioning, not just tech)

Framed as a B2B compliance-audit backend, not a self-check tool sellers would
avoid:
- **E-commerce marketplaces** — auto-vet seller listings before they go live,
  reducing penalty exposure and listing disputes.
- **Legal Metrology enforcement departments** — the actual target buyer named
  in the problem statement, for market-surveillance audits at scale.
- **Compliance consultancies** (Product Label Guru, Vincular-style firms) —
  as a 10x-faster first-pass tool ahead of their manual review.

## Next steps

1. Collect real product-label photos (curved, glare, poor quality — not just
   clean samples) to benchmark OCR accuracy honestly.
2. Verify 2017/2022 amendment text against the official e-Gazette notifications.
3. Expand category-specific conditional rules (imported goods, loose/multipack units).
4. Consider detecting the pack's own outline (not just the calibration
   marker) so pack width/height could be estimated automatically instead of
   manually entered — would close the last manual-input gap in the font check.
