# Privacy

What CareerPilot does with a visitor's data. The same points appear in the app under
Settings.

## What is kept, and for how long

| Data | Kept? | For how long |
|---|---|---|
| The resume or certificate file you upload | No. It is read in memory and discarded when the request ends. | Never stored |
| The profile built from your resume | Yes | 24 hours (`PROFILE_TTL_HOURS`), then deleted |
| Jobs, fit reports, tailored resumes, LinkedIn text, coaching plan | Yes, linked to that profile | Deleted with the profile |
| Cached model responses | Yes, tagged with the profile they were computed for | Deleted with the profile |
| The sample profile | Yes | Permanent. It is a fictional candidate. |

**Delete my data** in Settings removes all of the above for your profile immediately.
Expired profiles are purged whenever a new resume is uploaded.

## What is sent to the AI model

- The resume analyzer receives the full resume text, including contact details, once.
- Every later agent receives the profile with the email address and phone number removed.
- LinkedIn text and certificate text you paste or upload are sent to the model as given.

The deployed service sends them to Google's Gemini API, so Google's API terms govern what
is retained. The app can also run on Anthropic's API (`LLM_PROVIDER=anthropic`): a copy you
host yourself sends them to whichever provider its key belongs to.

## What is never done

- No resume text, email address or phone number is written to logs. A log filter redacts
  both patterns, and error messages are built from field positions, never from content.
- No scraping. Jobs come from licensed feeds or from text you paste. A link you give for a
  credential is recorded, not opened.
- Nothing is sent on your behalf: no job applications, no LinkedIn posts or edits.

## Accounts and access

There are no accounts. Your browser stores one random profile id. Anyone who has that id
can read the profile until it expires, so do not share links that contain it. This is a
deliberate trade-off for a demo (see `docs/decisions/0004-demo-mode.md`); a production
service would add sign-in.
