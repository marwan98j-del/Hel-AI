import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client


load_dotenv(override=True)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


MODEL = "gpt-5.6-luna"

MAX_TRANSLATIONS_PER_RUN = 5
MAX_SOURCE_CHARACTERS = 9000


def get_openai_client():
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY was not found in .env"
        )

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


def get_supabase_client():
    if not SUPABASE_URL:
        raise ValueError(
            "SUPABASE_URL was not found in .env"
        )

    if not SUPABASE_SECRET_KEY:
        raise ValueError(
            "SUPABASE_SECRET_KEY was not found in .env"
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_SECRET_KEY
    )


def clean_value(value):
    if value is None:
        return ""

    return str(value).strip()


def console_text(value):
    encoding = (
        sys.stdout.encoding
        or "utf-8"
    )

    return (
        str(value)
        .encode(
            encoding,
            errors="replace",
        )
        .decode(
            encoding,
            errors="replace",
        )
    )


def build_source_text(opportunity):
    title = clean_value(
        opportunity.get("title")
    )

    organization = clean_value(
        opportunity.get("organization")
    )

    opportunity_type = clean_value(
        opportunity.get("type")
    )

    location = clean_value(
        opportunity.get("location")
    )

    deadline = clean_value(
        opportunity.get("deadline")
    )

    education = clean_value(
        opportunity.get("education")
    )

    residency = clean_value(
        opportunity.get(
            "residency_requirement"
        )
    )

    notes = clean_value(
        opportunity.get("notes")
    )

    summary_en = clean_value(
        opportunity.get("summary_en")
    )

    original_text = clean_value(
        opportunity.get("original_text")
    )

    if len(original_text) > MAX_SOURCE_CHARACTERS:
        original_text = original_text[
            :MAX_SOURCE_CHARACTERS
        ]

    sections = [
        f"Title: {title}",
        f"Organization: {organization}",
        f"Type: {opportunity_type}",
        f"Location: {location}",
        f"Deadline: {deadline}",
        f"Education: {education}",
        f"Residency requirement: {residency}",
    ]

    if notes:
        sections.append(
            f"Notes: {notes}"
        )

    if summary_en:
        sections.append(
            f"English summary:\n{summary_en}"
        )

    if original_text:
        sections.append(
            f"Original announcement:\n"
            f"{original_text}"
        )

    return "\n\n".join(sections)


def translate_opportunity(
    openai_client,
    opportunity
):
    source_text = build_source_text(
        opportunity
    )

    prompt = f"""
You are the Kurdish Sorani translation and
opportunity-information agent for HelAI.

Your task is to read the opportunity information
below and produce a clear, accurate Kurdish Sorani
summary.

LANGUAGE REQUIREMENTS:

- Write only in Kurdish Sorani.
- Use the Arabic-based Kurdish Sorani script.
- Use natural, professional Kurdish.
- Do not use Kurmanji.
- Do not answer in English.
- Proper names of organizations, universities,
  programs, and people may remain in their
  official form when necessary.

ACCURACY REQUIREMENTS:

- Do not invent information.
- Do not add eligibility requirements that are
  not present in the source.
- Preserve important numbers, dates, ages,
  amounts, countries, and deadlines accurately.
- Clearly explain who the opportunity is for.
- Clearly explain what the opportunity offers.
- Mention the deadline when available.
- Mention important eligibility requirements
  when available.
- If information is missing, simply leave it out.
- Do not claim that a person is eligible.
  Eligibility is handled separately by HelAI.

STYLE:

- Clear and easy to understand.
- Professional but not overly formal.
- Suitable for a Kurdish-speaking student or
  young professional.
- Approximately 120 to 220 Kurdish words.
- Use short paragraphs.
- Do not use Markdown headings.
- Do not use bullet points.
- Do not include explanations about translation.
- Return only the final Kurdish Sorani text.

OPPORTUNITY INFORMATION:

{source_text}
"""

    response = openai_client.responses.create(
        model=MODEL,
        input=prompt,
        max_output_tokens=1000
    )

    translation = (
        response.output_text or ""
    ).strip()

    if not translation:
        raise ValueError(
            "OpenAI returned an empty translation."
        )

    return translation


def save_translation(
    supabase,
    opportunity_id,
    translation
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    (
        supabase
        .table("opportunities")
        .update({
            "summary_ku": translation,
            "updated_at": now
        })
        .eq("id", opportunity_id)
        .execute()
    )


def needs_translation(opportunity):
    summary_ku = clean_value(
        opportunity.get("summary_ku")
    )

    if summary_ku:
        return False

    if not opportunity.get(
        "active",
        True
    ):
        return False

    status = clean_value(
        opportunity.get("status")
    ).lower()

    if status == "closed":
        return False

    return True


def run_translation_service():
    print()
    print(
        "========================================"
    )
    print(
        "       HELAI KURDISH TRANSLATION"
    )
    print(
        "========================================"
    )
    print()

    openai_client = get_openai_client()
    supabase = get_supabase_client()

    result = (
        supabase
        .table("opportunities")
        .select("*")
        .eq("active", True)
        .execute()
    )

    opportunities = (
        result.data or []
    )

    candidates = [
        opportunity
        for opportunity in opportunities
        if needs_translation(opportunity)
    ]

    candidates = candidates[
        :MAX_TRANSLATIONS_PER_RUN
    ]

    print(
        "Opportunities needing translation:",
        len(candidates)
    )

    print()

    translated_count = 0
    failed_count = 0

    for opportunity in candidates:
        title = (
            opportunity.get("title")
            or "Untitled opportunity"
        )

        opportunity_id = (
            opportunity.get("id")
        )

        print(
            "----------------------------------------"
        )

        print(
            "Opportunity:",
            title
        )

        try:
            print(
                "AI is translating to Kurdish Sorani..."
            )

            translation = translate_opportunity(
                openai_client,
                opportunity
            )

            save_translation(
                supabase,
                opportunity_id,
                translation
            )

            print(
                "Saved Kurdish translation: True"
            )

            print()
            print(
                "Preview:"
            )
            print(
                console_text(
                    translation[:350]
                )
            )

            if len(translation) > 350:
                print("...")

            translated_count += 1

        except Exception as error:
            print(
                "Translation failed:",
                str(error)
            )

            failed_count += 1

        print()

    print(
        "========================================"
    )
    print(
        "                 SUMMARY"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Translated:",
        translated_count
    )
    print(
        "Failed:",
        failed_count
    )
    print()

    return {
        "translated": translated_count,
        "failed": failed_count,
        "candidates": len(candidates),
    }


if __name__ == "__main__":
    run_translation_service()
