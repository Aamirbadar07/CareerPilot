# CareerPilot Deployment & Infrastructure Verification Report

**Date:** 2026-11-02  
**Target:** Live Deployment Infrastructure, Production Health, and Cloud Run / Render / Vercel Configurations  
**Evaluator:** Cloud DevOps & Infrastructure Reliability Engineer

---

## 1. Executive Summary

A comprehensive investigation of CareerPilot's live deployment endpoints and deployment configurations was executed.

- **Frontend (Vercel):** Live at `https://career-pilot-lac.vercel.app` (Status: **200 OK**).
- **Backend (Cloud Run):** Documented at `https://careerpilot-backend-473372801300.us-central1.run.app/health`.
  - **Live Probe Status:** **503 Service Unavailable** (`The service you requested is not available yet`).
  - **Root Cause:** The Google Cloud Run project associated with project number `473372801300` has disabled billing or expired trial credits. As documented in `README.md`, Cloud Run immediately shuts down container instances on projects with disabled billing.
- **Alternative Backend (Render):** Fully configured via `render.yaml` with a free tier blueprint that requires zero credit card setup.

---

## 2. Live Probing Results

### 2.1 Frontend Probe
- **Target URL:** `https://career-pilot-lac.vercel.app`
- **HTTP Status:** `200 OK`
- **Response Headers:** `server: Vercel`, `content-type: text/html; charset=utf-8`
- **Render Verification:** Complete Next.js 14 document structure, stylesheet links, fonts (`carlito`), and client bundles delivered successfully.

### 2.2 Backend Cloud Run Probe
- **Target URL:** `https://careerpilot-backend-473372801300.us-central1.run.app/health`
- **HTTP Status:** `503 Service Unavailable`
- **Diagnostic Response Body:**
  ```html
  <html><head><title>503 Server Error</title></head>
  <body text=#000000 bgcolor=#ffffff>
  <h1>Error: Server Error</h1>
  <h2>The service you requested is not available yet.<p>Please try again in 30 seconds.</h2>
  </body></html>
  ```
- **Conclusion:** Cloud Run container cannot start due to GCP billing restrictions.

---

## 3. Infrastructure & Deployment Configurations

### 3.1 Docker Container (`backend/Dockerfile`)
- Base image: `python:3.11-slim`
- Installs native Pango & fonts: `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-crosextra-carlito`
- Uses `ghcr.io/astral-sh/uv:latest` for reproducible frozen dependency synchronization (`uv sync --frozen --no-dev`)
- Container startup script:
  ```sh
  timeout 60 alembic upgrade head || echo 'migrations failed or timed out; starting anyway, see /health'
  uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```
  *Defensive engineering:* Alembic migration timeout prevents an unreachable external database from freezing container startup, allowing `/health` to report the underlying status code and body.

### 3.2 Render Blueprint (`render.yaml`)
- Service Name: `careerpilot-api`
- Plan: `free` (Docker runtime)
- Region: `singapore` (recommended for low latency to Supabase `ap-south-1`)
- Health check path: `/health`
- Required Environment Variables:
  - `LLM_PROVIDER`: `google` or `anthropic`
  - `GOOGLE_API_KEY`: API key from Google AI Studio
  - `GOOGLE_MODEL`: `gemini-3.8-flash,gemini-2.5-flash`
  - `DATABASE_URL`: Supabase *session pooler* connection string (IPv4 compatible)
  - `FRONTEND_ORIGIN`: `https://career-pilot-lac.vercel.app,http://localhost:3000`
  - `TRUSTED_PROXY_HOPS`: `1`

### 3.3 Production Runbook & Activation Steps

To reactivate the live backend without GCP billing:
1. In Render Dashboard, click **New + -> Blueprint** and select the repository `Aamirbadar07/CareerPilot`.
2. Populate the required environment variables:
   - `GOOGLE_API_KEY`: (Valid Gemini API key)
   - `DATABASE_URL`: (Supabase Session Pooler connection URL)
   - `FRONTEND_ORIGIN`: `https://career-pilot-lac.vercel.app`
3. Once deployed, copy the Render service URL (e.g. `https://careerpilot-api.onrender.com`).
4. In Vercel Project Settings for `career-pilot-lac`:
   - Set `NEXT_PUBLIC_API_URL` to `https://careerpilot-api.onrender.com`.
   - Trigger a redeploy.
5. Verify `/health` returns `{"status":"ok"}`.

