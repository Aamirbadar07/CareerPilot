# 0001: Licensed job APIs and pasted text, no scraping

## Context
The largest job sites for the target market (LinkedIn, Naukri, Indeed) forbid scraping in
their terms. Scrapers also break whenever the markup changes.

## Decision
Jobs come only from sources that publish an API or feed for this purpose: JSearch (a licensed
Google for Jobs feed), Remotive, and public Greenhouse boards. For anything else the user
pastes the job description. The app never fetches a page the user links to.

The same rule covers the other direction: the app never applies to a job and never posts or
edits anything on LinkedIn. It prepares text; the human submits it.

## Consequences
- Coverage is narrower than a scraper's. Pasting a description is the escape hatch.
- Each source's terms are followed in code: Remotive is cached for six hours and every job
  links back to its source URL with the source named.
- The project can be deployed publicly without risking anyone's account.
