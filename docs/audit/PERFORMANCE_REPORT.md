# CareerPilot Performance & Concurrency Engineering Report

**Date:** 2026-11-02  
**Target:** Backend & Frontend Throughput, Concurrency, and Latency  
**Evaluator:** Principal Performance & Cloud Infrastructure Engineer

---

## 1. Executive Summary

A comprehensive performance analysis was conducted on CareerPilot's backend concurrency, database connection pooling, Server-Sent Events (SSE) streaming throughput, and Next.js frontend rendering performance.

Key improvements were made to thread isolation in SQLite, pool sizing in PostgreSQL, description payload streaming, and client-side iframe loading.

---

## 2. Backend Concurrency & Throughput

### 2.1 Multi-Threaded Batch Fit Scoring
- **Implementation:** `score_jobs` uses Python's `concurrent.futures.ThreadPoolExecutor` to score multiple jobs concurrently.
- **Provider-Aware Concurrency Tuning:**
  - `Anthropic`: `MAX_CONCURRENT = 10` worker threads. Anthropic's tier easily handles 10 parallel calls.
  - `Google Gemini`: `FREE_TIER_CONCURRENT = 4` worker threads. Throttled to 4 because the Gemini free tier enforces a strict 5–15 requests/minute quota per model. Sending 10 concurrent requests causes immediate 429 backoff sleeps.
- **DbCache Thread Safety:** `DbCache` utilizes a session factory (`SessionLocal`), opening and closing short-lived sessions per cache lookup/store to prevent session race conditions across threads.

### 2.2 Database Pool Configuration
- **SQLite (Local Development):**
  - Configured `connect_args={"check_same_thread": False, "timeout": 30}`.
  - Eliminates threading exceptions when background threads query or write to SQLite concurrently with active web requests.
- **PostgreSQL (Production):**
  - Configured `pool_size=10, max_overflow=20` to guarantee dedicated connections for all 10 worker threads during peak tailoring and scoring batches.
  - Configured `connect_timeout=5` so database connectivity failures fail fast without hanging container startup.

---

## 3. Frontend Performance & Bundle Optimization

*Evaluated via Next.js 14 production build (`npm run build`):*

```
Route (app)                              Size     First Load JS
┌ ○ / (Landing)                          5.97 kB         164 kB
├ ○ /_not-found                          873 B          88.2 kB
├ ○ /certifications                      5.09 kB         154 kB
├ ○ /coach                               96.5 kB         246 kB
├ ○ /dashboard                           1.97 kB         164 kB
├ ○ /jobs                                5.24 kB         168 kB
├ ƒ /jobs/[id]                           4.77 kB         163 kB
├ ○ /linkedin                            5.29 kB         155 kB
├ ○ /resume                              2.84 kB         156 kB
├ ○ /settings                            4.64 kB         154 kB
└ ƒ /tailor/[jobId]                      5.1 kB          163 kB
+ First Load JS shared by all            87.4 kB
```

### 3.1 Bundle Efficiency
- **Shared JavaScript:** Only **87.4 kB** across all routes.
- **Zero Heavy State Management:** No Redux, MobX, or Zustand overhead. Individual views leverage lightweight React hooks (`useApi`, `useProfileId`).
- **Smooth Scrolling:** Integrated with Lenis for hardware-accelerated 60 FPS scrolling.
- **CSS Architecture:** Zero hardcoded colors. Global CSS variables compiled by Tailwind into small utility classes without runtime CSS-in-JS overhead.

---

## 4. PDF Rendering Performance & Resource Usage

- **Engine:** WeasyPrint + Pango typography.
- **One-Page Fitting:** `render.fit_to_one_page` executes a deterministic trimming loop:
  1. Trims least relevant projects.
  2. Trims trailing project bullets.
  3. Trims trailing experience bullets.
  4. Never cuts core employer facts or dates.
- **Memory Footprint:** Output stream generated directly into a memory buffer and transmitted with `Content-Disposition: attachment`.
- **Operating System Compatibility:**
  - **Linux / Docker:** Fully supported with native Pango and Carlito font packages.
  - **Windows:** Gracefully handles missing `libgobject-2.0-0` with `PdfUnavailable`, returning HTTP 501 with clear instructions to use the browser print view.

