# HelAI

## Mission Statement

HelAI is an AI-powered opportunity agent that automatically discovers global opportunities, understands their requirements, matches them with each user’s profile, and delivers personalized guidance on what they qualify for and what they need to apply.

In practice, HelAI discovers scholarships, grants, fellowships, competitions, internships, training programs, exchange programs, and other opportunities from public web sources, uses OpenAI to understand the requirements, stores structured data in Supabase, creates Kurdish Sorani summaries, matches opportunities with user profiles, and emails users when a strong eligible match is found.

Built as a prototype for AI Olympiad Kurdistan 2026.

## Current Architecture

```text
Web sources
  -> automatic discovery
  -> duplicate check by source URL and fingerprint
  -> full announcement reader
  -> OpenAI requirement extraction
  -> Supabase opportunities table
  -> Kurdish Sorani summary
  -> matching against complete profiles
  -> notification queue
  -> Resend email delivery
```

The Streamlit website is the user interface. The background opportunity agent is a separate process and does not require Streamlit to be open.

## Working Sources

HelAI currently supports these source connectors:

- Opportunity Desk
- UK Research and Innovation (UKRI)
- Grants.gov
- U.S. National Science Foundation (NSF)

Each source adapter returns a consistent candidate structure with title, URL, source, and source name. Imported opportunities preserve `source`, `source_name`, and `source_url`.

## OpenAI Extraction

`ai_extractor.py` reads unstructured opportunity announcements and extracts structured fields such as title, organization, type, location, status, deadline, age limits, education level, residency requirements, languages, interests, skills, required documents, and notes.

Unknown requirements should stay empty or unknown. The extractor is instructed not to invent eligibility conditions.

## Supabase

Supabase stores:

- user profiles
- opportunities
- match records
- notification records

The Streamlit app uses `SUPABASE_KEY` for user-facing auth and profile actions. Trusted background automation uses `SUPABASE_SECRET_KEY` for collection, matching, notification queueing, and email status updates.

## Kurdish Sorani Translation

`translation_service.py` creates concise Kurdish Sorani summaries in Arabic-script Kurdish and stores them in `summary_ku`. English notes or summaries are kept in `summary_en` where available.

The website interface remains English. Opportunity summaries can be shown in Kurdish Sorani when the user's preferred language is Kurdish Sorani and a Kurdish summary exists.

## Matching And Eligibility

`matcher.py` keeps three ideas separate:

- Match: how relevant the opportunity is to the user.
- Eligibility: whether mandatory requirements are satisfied.
- Readiness: whether required application documents are available.

`matching_service.py` automatically compares open opportunities against all complete profiles and upserts records into the `matches` table. Incomplete profiles are skipped safely.

HelAI uses an effective status check at match and notification time: an opportunity stored as open is treated as closed after its application deadline, while the deadline date itself remains actionable. Reviewed informational or roundup records are not treated as actionable opportunities.

The Streamlit Opportunity Booster explains readiness gaps and simulates profile improvements so users can see which changes may unlock additional eligible matches or improve application readiness. These simulations do not change the user's profile automatically.

## Notifications

`notification_service.py` creates email notification records only when:

- the opportunity is open
- the user is eligible
- the match score is at or above `HELAI_MATCH_THRESHOLD`
- email notifications are enabled
- the user has an email address
- the exact match has not already been notified

This prevents repeated notifications for the same user and opportunity.

## Resend Email

`email_service.py` sends queued notifications through Resend.

Email messages include the opportunity title, organization, type, location, deadline, match score, readiness, a short summary, and a direct link to the original source.

If the user's preferred language is Kurdish Sorani and a Kurdish summary exists, HelAI sends the Kurdish email. Otherwise it sends English.

Resend may require a verified sending domain before emailing arbitrary recipients. Keep test mode enabled until production email sending is configured.

## Automation Files

- `helai_pipeline.py` runs one full end-to-end automation cycle.
- `helai_agent.py` runs the continuous background monitor and sleeps between cycles.
- `run_collector.bat` runs one complete automation cycle on Windows.
- `run_agent.bat` starts continuous monitoring on Windows.

The local agent architecture keeps source discovery, extraction, translation, matching, notification queueing, and email delivery in explicit pipeline stages. It runs on the local machine; this repository does not claim a public production deployment.

## Environment Variables

Create `.env` locally. Do not commit it. Use placeholders only in examples:

```text
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SECRET_KEY=
RESEND_API_KEY=
EMAIL_TEST_MODE=true
EMAIL_TEST_RECIPIENT=
EMAIL_FROM=HelAI <onboarding@resend.dev>
HELAI_CHECK_INTERVAL_MINUTES=180
HELAI_MATCH_THRESHOLD=70
HELAI_SOURCE_LIMIT=10
HELAI_MAX_NEW_PER_SOURCE=3
HELAI_REQUEST_TIMEOUT_SECONDS=30
HELAI_REQUEST_DELAY_SECONDS=1
```

`.env.example` contains the same variable names with safe placeholders.

## Start The Streamlit Website

```bat
cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"
.venv\Scripts\activate
streamlit run app.py
```

## Run One Automation Cycle

```bat
cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"
run_collector.bat
```

This runs discovery, duplicate checks, AI extraction for new opportunities, Supabase saving, Kurdish translation, matching, notification queueing, and email delivery once.

## Start Continuous Monitoring

```bat
cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"
run_agent.bat
```

The agent checks sources every `HELAI_CHECK_INTERVAL_MINUTES` minutes. The default is 180 minutes. Stop it with `Ctrl+C`.

## Email Test Mode Vs Production Mode

When `EMAIL_TEST_MODE=true`, all outgoing emails are sent only to `EMAIL_TEST_RECIPIENT`.

When `EMAIL_TEST_MODE=false`, emails are sent to the matched user's profile email.

Do not turn off test mode until `EMAIL_FROM` is configured with a Resend sender or verified domain that can email real recipients.

## Logs

The one-cycle runner appends to:

```text
collector.log
```

The Streamlit app reads `helai_source_status.json` when present to show real source connector status. This file is runtime state and is ignored by Git.

## Current Limitations

- Source websites and APIs can change or go offline.
- One failed source is logged and does not stop the rest of the pipeline.
- OpenAI is called only for newly discovered opportunities, but API calls may still cost money.
- Email production delivery depends on Resend sender/domain configuration.
- This project uses the existing Supabase tables and fields. No destructive database migration is included.
