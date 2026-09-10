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
    "deadline": "",
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

6. Use null for an age limit that is not stated.

7. Use 0 for minimum grade if no grade requirement is stated.

8. Use 0 for work experience if no experience requirement
is stated.

9. Only mark passport, IELTS, portfolio, or CV as true
when the announcement explicitly requires it.

10. Do not mark IELTS as required just because English
language ability is required.

11. Translate extracted labels and descriptions into English,
even when the source announcement is Kurdish or Arabic.

12. Keep notes short and factual.

13. "status" should normally be:

Open

unless the announcement clearly indicates that it is
closed or expired.

14. Never invent a residency, degree, age, language,
document, grade or work-experience requirement.

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