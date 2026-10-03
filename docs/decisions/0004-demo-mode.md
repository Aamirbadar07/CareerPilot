# 0004: Demo mode is a sample profile plus self-deleting uploads

## Context
A public site must not run on the author's personal profile. Visitors need something to
look at immediately, and people who upload their own resume need to know it will not linger.

## Decision
- The app ships one built-in **sample profile** (a fictional candidate). It never expires and
  is what a first-time visitor sees.
- A visitor may **upload their own resume**. The file is parsed in memory and never stored.
  The resulting profile gets `profiles.expires_at = now + PROFILE_TTL_HOURS` (default 24) and
  is purged, together with every cached LLM result derived from it, once that passes.
- **Delete my data** in settings runs the same purge immediately.
- There are no accounts. The random profile id is the only credential; the browser keeps it
  in local storage. Anyone holding the id can read that profile until it expires.

## Consequences
- The data model needs `profiles.expires_at` and a `profile_id` on every derived row.
- Nothing personal survives a day by default, so there is no account system to secure.
- A profile id leaked from the browser exposes that profile until expiry. Acceptable for a
  demo; a real product would add authentication.
