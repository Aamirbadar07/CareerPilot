# 0003: Layout lives in a template, not in the model

## Context
A resume must look the same every time and fit one page. Models asked to produce formatted
documents drift: spacing changes between runs, sections move, the page overflows.

## Decision
The tailor returns content JSON only. A Jinja2 template rendered by WeasyPrint produces the
PDF. Typography, spacing, section order and the page size are fixed in
`backend/app/templates/resume.html`. The renderer counts pages; an overflow asks the tailor
for a tighter cut once, then trims trailing content in code.

Facts that must not change (employer, role, dates, education, certifications) are read from
the master profile by the renderer and are never part of the model's output.

## Consequences
- Identical layout on every run, and the one-page rule is enforced by code.
- The model has fewer ways to fabricate: it cannot restate a date or an employer.
- A new look means editing one HTML file, with no prompt changes.
- One departure from a literal reading of the credentials rule: an unverified certification
  is labelled "unverified" everywhere in the app, but not on the resume document, because a
  candidate sends that document to employers. The app shows which certifications lack a
  credential id or URL so the user can add one.
- WeasyPrint needs Pango. The Docker image and CI install it; on Windows without it the PDF
  route answers 501 and the HTML preview still works.
