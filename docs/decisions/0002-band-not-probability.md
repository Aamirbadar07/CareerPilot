# 0002: A fit band, never a hire probability

## Context
Users ask "what are my chances?". A percentage looks precise and is easy to produce.

## Decision
The fit scorer returns a 0-100 match score built from six weighted dimensions and one of four
bands (Strong, Competitive, Stretch, Poor). It is forbidden to state a probability of being
hired, and code enforces it: output containing "N% chance", "odds of getting", and similar is
rejected and retried.

## Why
Whether someone is hired depends on who else applied, referrals and recruiter behaviour.
None of that is in the model's inputs, so any probability would be invented. A band says
what the inputs support: how well this profile covers this posting.

## Consequences
- The score is explainable: each dimension has a number and a one-line reason.
- Code, not the model, adds the dimensions, applies the cap (a missing must-have holds the
  score at 60) and derives the band, so the three can never disagree.
- The score measures match, not outcome. `docs/evaluation.md` reports agreement with
  hand-scored pairs, not offer rates.
