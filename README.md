# HelAI

HelAI is a multilingual AI opportunity agent that discovers global opportunities, understands eligibility requirements, translates them into Kurdish Sorani, matches them with user profiles, and prepares personalized notifications for relevant users.

Built as a prototype for AI Olympiad Kurdistan 2026.

## What HelAI does

- Discovers opportunities automatically from multiple sources
- Reads full opportunity pages and extracts structured requirements with AI
- Supports multilingual announcements
- Stores opportunities and user profiles in Supabase
- Calculates relevance, eligibility, and application readiness
- Translates opportunity summaries into Kurdish Sorani
- Creates notification records for strong matches
- Includes an email-delivery pipeline for user alerts
- Provides a Streamlit web interface for profiles, matching, eligibility, and opportunity analysis

## Current sources

- Opportunity Desk
- UK Research and Innovation (UKRI)

## AI pipeline

```text
Global Sources
      ↓
Automatic Collectors
      ↓
AI Opportunity Extraction
      ↓
Structured Requirements
      ↓
Supabase Database
      ↓
Kurdish Sorani Translation
      ↓
User Profile Matching
      ↓
Eligibility + Match Score + Readiness
      ↓
Notification Queue
      ↓
Email Alert Pipeline
```

## Main components

- `app.py` — Streamlit web application
- `ai_extractor.py` — AI extraction of opportunity requirements
- `matcher.py` — matching, eligibility, readiness, and booster logic
- `matching_service.py` — automated profile-to-opportunity matching
- `automatic_collector.py` — Opportunity Desk collector
- `ukri_automatic_collector.py` — UKRI collector
- `translation_service.py` — Kurdish Sorani translation service
- `notification_service.py` — notification queue generation
- `email_service.py` — email delivery pipeline
- `auth_service.py` — authentication and profile management
- `opportunity_service.py` — cloud opportunity loading

## Tech stack

- Python
- Streamlit
- OpenAI API
- Supabase
- Requests / BeautifulSoup
- Resend email API
- Windows Task Scheduler for recurring local automation

## Local setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file locally with the required environment variables:

```text
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SECRET_KEY=
RESEND_API_KEY=
```

Do not commit the `.env` file. It is excluded through `.gitignore`.

Run the web app:

```bash
streamlit run app.py
```

Run the automated matching service:

```bash
python matching_service.py
```

Run the full Windows collector pipeline:

```text
run_collector.bat
```

## Prototype status

HelAI currently has working AI extraction, cloud storage, profile matching, eligibility scoring, readiness scoring, Kurdish Sorani translation, automatic opportunity collection from two sources, and a notification/email pipeline.

The prototype is still being improved for broader deployment and production use.
