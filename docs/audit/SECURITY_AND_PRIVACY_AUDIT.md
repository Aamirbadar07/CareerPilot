# CareerPilot Security and Privacy Audit

**Date:** 2026-11-02  
**Target:** CareerPilot Application Security & Privacy Architecture  
**Evaluator:** Senior Application Security & Privacy Engineer  
**Classification Standard:** OWASP Top 10 / CVSS v3.1 Severity Rating

---

## 1. Executive Summary

CareerPilot processes highly sensitive candidate personally identifiable information (PII), employment histories, and career documents. The application was audited for data leakage, unauthorized access, injection vectors, upload processing risks, and secrets management.

---

## 2. Findings Matrix

| Finding ID | Title | Severity | Status | Remediation Summary |
|---|---|---|---|---|
| **SEC-01** | Unvalidated Profile ID Format in Route Parameters | **HIGH** | **RESOLVED** | Enforced strict `^[a-zA-Z0-9_\-]{1,36}$` regex validation in `get_profile`. |
| **SEC-02** | Absence of Rate Limiting on Sensitive Read & Mutation Endpoints | **MEDIUM** | **RESOLVED** | Implemented sliding-window rate limiters on `read_profile` (60/min), `update_preferences` (20/hr), and `delete_my_data` (10/hr). |
| **SEC-03** | Single-Origin Restriction in CORS Configuration | **LOW** | **RESOLVED** | Upgraded `Settings.frontend_origin` to parse comma-separated multi-origin lists. |
| **SEC-04** | Missing Null Guard on Profile Metadata Resolution | **LOW** | **RESOLVED** | Guarded `db.get(repo.Profile, id)` resolution to prevent unhandled 500 exceptions. |
| **SEC-05** | Capability-Based Profile Access Model | **MEDIUM** | **ANALYZED / DOCUMENTED** | Documented demo capability URL trade-off; isolated profile data with 24h automatic purge. |
| **SEC-06** | In-Memory Document Processing & Safe Upload Bounds | **INFORMATIONAL** | **VERIFIED** | 5 MB upload cap enforced; no disk persistence of raw resume files. |
| **SEC-07** | Automated PII Redaction in Logging Pipeline | **INFORMATIONAL** | **VERIFIED** | `RedactPII` filter scrubs emails and telephone numbers across all log channels. |

---

## 3. In-Depth Vulnerability Analysis & Mitigations

### 3.1 SEC-01: Profile ID Format & Injection Protection (HIGH)
- **Vulnerability:** Endpoint route parameters accepted untyped strings for `{profile_id}`. An attacker could pass malformed payloads, directory traversal indicators (`../`), or large strings directly into database query parameters.
- **Resolution:** Added regex validation in `app/api/deps.py`:
  ```python
  _VALID_ID = re.compile(r"^[a-zA-Z0-9_\-]{1,36}$")

  def get_profile(profile_id: str, db: Session = Depends(get_db)) -> MasterProfile:
      if not _VALID_ID.match(profile_id):
          raise HTTPException(400, "Invalid profile ID format.")
      profile = repo.get_profile(db, profile_id)
      if profile is None:
          raise HTTPException(404, "Profile not found. It may have expired.")
      return profile
  ```
- **Verification:** Unit tests confirm that paths like `../etc/passwd`, non-alphanumeric characters, and strings exceeding 36 characters are immediately rejected with HTTP 400.

### 3.2 SEC-02: Rate Limiting & Denial of Service Protection (MEDIUM)
- **Vulnerability:** While `upload_resume` was throttled at 5 calls/hour, `read_profile`, `update_preferences`, and `delete_my_data` had no rate limiting, leaving them susceptible to brute-force polling and resource exhaustion.
- **Resolution:** Attached `rate_limit` dependencies across all profile endpoints in `app/api/profiles.py`. Client IPs are resolved from the rightmost trusted proxy hop (`TRUSTED_PROXY_HOPS`) to prevent header spoofing.

### 3.3 SEC-05: Capability-Based Profile Access Model Analysis
- **Architecture:** The application operates without traditional username/password accounts for demo accessibility. The UUIDv4 profile ID serves as an unguessable capability secret held in `localStorage`.
- **Security Assessment:**
  - A UUIDv4 provides 122 bits of random entropy ($5.3 \times 10^{36}$ possible combinations). Brute-force enumeration across the public internet is computationally impossible.
  - Profiles carry a mandatory 24-hour time-to-live (`PROFILE_TTL_HOURS = 24`), after which `purge_expired` deletes the profile, all version rows, cached LLM entries, and derived artifacts.
  - "Delete my data" immediately executes full cascade purge.
  - **Production Recommendation:** If transitioned from demo mode to multi-user enterprise production, integrate OAuth2 / JWT authentication (e.g. Supabase Auth or Auth0) to bind profiles to authenticated user identities.

### 3.4 Data Privacy & PII Handling
- **Resume Files:** Processed entirely in memory via `io.BytesIO`. Zero temporary files are written to disk or cloud buckets.
- **Model Prompts:** Downstream agents (Job Discovery, Fit Scorer, Tailor, Coach) receive `profile_for_llm(profile)`, which explicitly sets `email` and `phone` to `None`.
- **Logs:** `app/core/logging.py` attaches `RedactPII` to all log handlers, stripping email addresses and telephone digit sequences before emission.
- **Secrets:** Environment variables are loaded via `pydantic-settings` from `.env`. Zero secrets or credentials are hardcoded in the codebase.

