# CogniTrace — Intelligent Project Knowledge Handover

CogniTrace converts scattered software project artifacts (documents, Git history, chat exports, and task records) into an evidence-linked, human-verified project handover report.

## Implemented Features (Phases 1–4)

- **Document Ingestion (Phase 1):** Upload and parse `PDF`, `DOCX`, `TXT`, `MD`, `CSV`, and `JSON` files (up to 20 MB) into indexed `EvidenceChunk` records with page, line, and JSON path references.
- **Evidence-Linked Claim Generation & Human Verification (Phase 2):** Deterministic rule-based claim extraction across 8 categories (`technology`, `architecture_decision`, `completed_feature`, `pending_feature`, `blocker_risk`, `dependency`, `todo_fixme`, `project_decision`), strict citation linking, contradiction & insufficient-evidence detection, and human approve/reject/edit workflow with `ReviewHistory` persistence.
- **Handover Report Generation (Phase 3 & 3.1/3.2):** 10-section Markdown and PyMuPDF PDF handover reports built strictly from human-approved claims, preserving citations, implementation-status labels, and an explicit Unresolved Evidence & Conflicts section.
- **Multi-Source Ingestion (Phase 4):** Dedicated importers for Git activity logs (`TXT`, `CSV`, `JSON`), chat exports (`TXT`, `JSON`), and task records (`CSV`, `JSON`) with SHA-256 file and per-record duplicate prevention.

## Project Structure

```text
CogniTrace/
├── backend/
│   ├── app/
│   │   ├── api/            # files.py, claims.py, reports.py, imports.py
│   │   ├── core/           # config.py (Pydantic Settings)
│   │   ├── db/             # __init__.py (SQLite engine + additive migrations)
│   │   ├── schemas/        # Pydantic v2 schemas
│   │   ├── services/       # parser.py, claim_extractor.py, report_generator.py, multi_source_importer.py
│   │   ├── main.py         # FastAPI app & CORS
│   │   └── models.py       # SQLAlchemy models
│   ├── tests/              # End-to-end API tests
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/            # client.js (VITE_API_BASE_URL support)
│   │   ├── components/     # Layout, Sidebar, MultiSourceImport, StatCard, StatusBadge
│   │   └── pages/          # DashboardOverview, UploadDocuments, EvidenceExplorer, ClaimVerification, HandoverReports, Settings
│   ├── .env.example
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## Local Development Setup

### 1. Backend (FastAPI + SQLite)
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/health`

### 2. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
- Dashboard URL: `http://localhost:5174` (Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`).

## Environment Variables

### Backend (`backend/.env.example`)
| Variable | Default | Description |
|---|---|---|
| `SQLITE_DB_PATH` | `sqlite:///./cognitrace.db` | SQLAlchemy SQLite connection string |
| `UPLOAD_DIR` | `uploads` | Directory for uploaded source files |
| `REPORTS_DIR` | `reports` | Directory for generated `.md` and `.pdf` reports |
| `CORS_ORIGINS` | `http://localhost:5174,...` | Comma-separated allowed frontend origins |
| `MAX_UPLOAD_SIZE_MB` | `20` | Maximum upload size per file |
| `ALLOWED_TYPES` | `pdf,docx,txt,md,csv,json` | Allowed document extensions |
| `GEMINI_API_KEY` | *(empty)* | Optional Gemini API key (rule-based fallback always active) |

### Frontend (`frontend/.env.example`)
| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | *(empty)* | Production backend origin (e.g. `https://api.example.com`) |

## Production Build & Deployment

### Recommended Hosting Architecture
Because CogniTrace persists state in **SQLite** and stores uploaded/generated files on disk, deploy the backend on a container/VM platform with a **persistent disk/volume** (e.g., **Render Web Service + Persistent Disk**, **Railway + Volume**, or **Fly.io + Volume**). Do not use stateless serverless functions for the backend.

### Backend Production Start Command
Never use `--reload` in production:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
Set environment variables pointing to your mounted persistent volume (e.g. `/data`):
```env
SQLITE_DB_PATH=sqlite:////data/cognitrace.db
UPLOAD_DIR=/data/uploads
REPORTS_DIR=/data/reports
CORS_ORIGINS=https://your-frontend-domain.com
```

### Frontend Production Build
```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://your-backend-domain.com npm run build
```
Deploy `frontend/dist/` to a static host (Vercel, Netlify, or Render Static Site) with an SPA rewrite rule directing unmatched routes to `/index.html`.

## Render Deployment Guide

A Render Blueprint is included at [`render.yaml`](./render.yaml) defining both services:

1. **Initialize Git & Push to GitHub** (`.gitignore` already excludes `*.db`, `backend/uploads/`, `backend/reports/`, `frontend/dist/`, and `.env` files):
   ```bash
   git init
   git add .
   git commit -m "Prepare CogniTrace for Render deployment"
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. **Deploy via Render Blueprint:**
   - In Render Dashboard, select **New + → Blueprint** and connect your GitHub repository.
   - Render reads `render.yaml` and provisions:
     - **`cognitrace-backend`** (`rootDir: backend`, `buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /health`, Persistent Disk mounted at `/data`).
     - **`cognitrace-frontend`** (`rootDir: frontend`, `buildCommand: npm ci && npm run build`, `staticPublishPath: dist`, SPA rewrite `/* -> /index.html` so `/upload`, `/evidence`, `/claims`, and `/reports` work on page refresh).
3. **Connect Frontend & Backend Environment Variables:**
   - On **`cognitrace-frontend`**, set `VITE_API_BASE_URL` to your deployed backend URL (e.g. `https://cognitrace-backend.onrender.com`), then trigger a rebuild so Vite bakes the URL into `dist/`.
   - On **`cognitrace-backend`**, set `CORS_ORIGINS` to your deployed frontend URL (e.g. `https://cognitrace-frontend.onrender.com`).
4. **Persistent Storage Environment Variables (Pre-configured in `render.yaml`):**
   - `SQLITE_DB_PATH=sqlite:////data/cognitrace.db`
   - `UPLOAD_DIR=/data/uploads`
   - `REPORTS_DIR=/data/reports`
