import os
import json

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# API SETUP
# =========================================================

load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        "OPENAI_API_KEY was not found in the .env file."
    )

client = OpenAI(
    api_key=api_key
)


# =========================================================
# AI OPPORTUNITY EXTRACTION
# =========================================================

def extract_opportunity(announcement_text):

    if not announcement_text.strip():
        raise ValueError(
            "Opportunity announcement cannot be empty."
        )

    prompt = f"""
You are the AI extraction engine for Opportunity AI,
an opportunity-discovery platform designed for Kurdistan
and Iraq.

Your job is to read unstructured opportunity announcements
written in Kurdish Sorani, Kurdish Kurmanji, Arabic, English,
Persian, Turkish, or a mixture of these languages.

Extract the important opportunity, eligibility, residency,
education and document requirements.

Return ONLY valid JSON.

Do not use markdown.
Do not use ```json.
Do not add commentary.
Do not invent information that is not present.

Use exactly this JSON structure:

{{
    "title": "",
    "organization": "",
    "type": "",
    "location": "",
    "status": "",
    "open_date": null,
    "deadline": "",
    "close_date": null,
    "record_kind": "unknown",
    "eligible_applicant_types": [],
    "applicant_type": "",
    "minimum_age": null,
    "maximum_age": null,
    "education": "Any",
    "education_rule": "minimum",
    "minimum_grade": 0,
    "minimum_work_experience_years": 0,
    "residency_requirement": "",
    "languages": [],
    "interests": [],
    "skills": [],
    "requires_passport": false,
    "requires_ielts": false,
    "requires_portfolio": false,
    "requires_cv": false,
    "notes": ""
}}

RULES:

1. "type" must be exactly one of:

Scholarships
Internships
Competitions
Training Programs
Grants
Fellowships
Volunteering
Exchange Programs

2. "education" must be exactly one of:

Any
High School
Diploma
Bachelor's Degree
Master's Degree
PhD

3. "education_rule" must be:

minimum

when the announcement means the applicant needs
AT LEAST that education level.

Example:
"Applicants must have a bachelor's degree"
usually means Bachelor's Degree with rule "minimum".

Use:

exact

only when the opportunity specifically targets people
currently at or graduating from that education stage.

Examples:

"Only Grade 12 graduates may apply"
=> education = "High School"
=> education_rule = "exact"

"This programme is for current master's students"
=> education = "Master's Degree"
=> education_rule = "exact"

4. "residency_requirement" represents where the APPLICANT
must live or be resident.

Examples:

"Applicants must live in the Kurdistan Region"
=> "Kurdistan Region"

"Only residents of Erbil may apply"
=> "Erbil"

"Applicants must be residents of Iraq"
=> "Iraq"

If there is no residency requirement:
=> ""

Do NOT confuse the location where the programme takes place
with the applicant residency requirement.

Example:

"The programme takes place in Sulaymaniyah"
does NOT automatically mean the applicant must live
in Sulaymaniyah.

5. Convert deadlines to:

YYYY-MM-DD

whenever enough information is provided.

Only use "deadline" or "close_date" for an explicitly
labeled closing date, deadline, due date, or applications
close date.

If a date is only an opening date, start date, posted date,
forecasted date, or "applications accepted anytime starting"
date, put it in "open_date" and leave "deadline" and
"close_date" null or empty.

Do not choose the first date you see.

6. "eligible_applicant_types" must use only these values:

individual
organization/institution
company/business
government entity
university/research institution
NGO/nonprofit
mixed/both/unknown

Use these only when the announcement explicitly states who
may apply.

Examples:

"Students may apply"
=> ["individual"]

"Research organisations eligible to apply"
=> ["university/research institution"]

"State, territorial, and tribal organizations"
=> ["government entity", "organization/institution"]

"Small businesses may apply"
=> ["company/business"]

"Nonprofit organizations may apply"
=> ["NGO/nonprofit"]

If both individuals and organizations can apply:
=> ["mixed/both/unknown"]

If the announcement does not clearly say who may apply:
=> []

Set "applicant_type" to the single primary value, "mixed" when both
individuals and entities may apply, or "" when unknown.

7. "record_kind" must be exactly one of:

application_opportunity
informational
roundup
unknown

Use "informational" for articles, guides, advice posts, or news pages.
Use "roundup" for pages aggregating multiple separate opportunities.
Use "application_opportunity" only when the page content demonstrates a
direct application. A title containing grant, scholarship, fellowship, or
competition is not sufficient evidence. Use "unknown" when evidence is
insufficient. Do not guess.

8. Use null for an age limit that is not stated.

9. Use 0 for minimum grade if no grade requirement is stated.

10. Use 0 for work experience if no experience requirement
is stated.

11. Only mark passport, IELTS, portfolio, or CV as true
when the announcement explicitly requires it.

12. Do not mark IELTS as required just because English
language ability is required.

13. Translate extracted labels and descriptions into English,
even when the source announcement is Kurdish or Arabic.

14. Keep notes short and factual. Include clear organization
or entity-only applicant restrictions when explicitly stated.

15. "status" should be:

Open

only when the announcement is posted, active, or currently
accepting applications.

Use:

Upcoming

when the announcement says forecasted, forecast, upcoming,
planned, or not yet accepting applications.

Use:

Closed

when it is closed or expired.

16. Never invent a residency, degree, age, language,
document, grade, work-experience, applicant-type, opening
date, or deadline requirement.

ANNOUNCEMENT:

{announcement_text}
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt
    )

    raw_output = response.output_text.strip()

    try:
        opportunity = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "The AI returned invalid JSON."
        ) from error

    return opportunity
