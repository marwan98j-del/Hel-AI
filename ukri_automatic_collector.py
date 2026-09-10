import hashlib
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from supabase import create_client

from ai_extractor import extract_opportunity
from ukri_discovery import discover_ukri_opportunities
from ukri_article import read_ukri_opportunity


load_dotenv(override=True)


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


SOURCE = "UKRI"
SOURCE_NAME = "UK Research and Innovation (UKRI)"

DISCOVERY_LIMIT = 10
MAX_NEW_IMPORTS = 2
DELAY_SECONDS = 1


SKIP_TITLE_PHRASES = [
    "invite only",
    "pre-announcement",
    "cbrn",
    "chemical, biological, radiological and nuclear",
]


def get_supabase():
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


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def clean_integer(value):
    if value is None:
        return None

    try:
        return int(value)
    except Exception:
        return None


def clean_number(value, default=0):
    if value is None:
        return default

    try:
        return float(value)
    except Exception:
        return default


def clean_list(value):
    if not value:
        return []

    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def clean_date(value):
    value = clean_text(value)

    if not value:
        return None

    return value


def create_fingerprint(
    title,
    source_url
):
    raw = (
        clean_text(title).lower()
        + "|"
        + clean_text(source_url).lower()
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def get_external_id(url):
    path = (
        urlparse(url)
        .path
        .strip("/")
    )

    if not path:
        return url

    return path.split("/")[-1]


def should_skip_title(title):
    title_lower = clean_text(
        title
    ).lower()

    for phrase in SKIP_TITLE_PHRASES:
        if phrase in title_lower:
            return True

    return False


def already_exists(
    supabase,
    source_url
):
    result = (
        supabase
        .table("opportunities")
        .select("id,title")
        .eq(
            "source_url",
            source_url
        )
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def normalize_status(value):
    value = clean_text(value)

    allowed = {
        "Open",
        "Closed",
        "Upcoming",
        "Unknown",
    }

    if value in allowed:
        return value

    return "Unknown"


def normalize_education_rule(value):
    value = clean_text(
        value
    ).lower()

    if value == "exact":
        return "exact"

    return "minimum"


def build_record(
    extracted,
    article_text,
    source_url
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    title = clean_text(
        extracted.get("title")
    )

    if not title:
        raise ValueError(
            "AI extraction returned no title."
        )

    opportunity_type = clean_text(
        extracted.get("type")
    )

    if not opportunity_type:
        opportunity_type = "Grants"

    record = {
        "title": title,

        "organization": clean_text(
            extracted.get("organization")
        ),

        "type": opportunity_type,

        "location": clean_text(
            extracted.get("location")
        ),

        "status": normalize_status(
            extracted.get("status")
        ),

        "deadline": clean_date(
            extracted.get("deadline")
        ),

        "minimum_age": clean_integer(
            extracted.get("minimum_age")
        ),

        "maximum_age": clean_integer(
            extracted.get("maximum_age")
        ),

        "education": (
            clean_text(
                extracted.get("education")
            )
            or "Any"
        ),

        "education_rule":
            normalize_education_rule(
                extracted.get(
                    "education_rule"
                )
            ),

        "minimum_grade": clean_number(
            extracted.get("minimum_grade"),
            0
        ),

        "minimum_work_experience_years":
            clean_number(
                extracted.get(
                    "minimum_work_experience_years"
                ),
                0
            ),

        "residency_requirement":
            clean_text(
                extracted.get(
                    "residency_requirement"
                )
            ),

        "languages": clean_list(
            extracted.get("languages")
        ),

        "interests": clean_list(
            extracted.get("interests")
        ),

        "skills": clean_list(
            extracted.get("skills")
        ),

        "requires_passport": bool(
            extracted.get(
                "requires_passport",
                False
            )
        ),

        "requires_ielts": bool(
            extracted.get(
                "requires_ielts",
                False
            )
        ),

        "requires_portfolio": bool(
            extracted.get(
                "requires_portfolio",
                False
            )
        ),

        "requires_cv": bool(
            extracted.get(
                "requires_cv",
                False
            )
        ),

        "notes": clean_text(
            extracted.get("notes")
        ),

        "summary_en": clean_text(
            extracted.get("notes")
        ),

        "summary_ku": None,

        "original_text": article_text,

        "source_language": "English",

        "ai_processed": True,

        "source": SOURCE,

        "source_name": SOURCE_NAME,

        "source_url": source_url,

        "external_id": get_external_id(
            source_url
        ),

        "fingerprint":
            create_fingerprint(
                title,
                source_url
            ),

        "active": True,

        "discovered_at": now,

        "updated_at": now,
    }

    return record


def run_collector():
    print()
    print(
        "========================================"
    )
    print(
        "       HelAI UKRI Collector"
    )
    print(
        "========================================"
    )
    print()

    supabase = get_supabase()

    print(
        "Discovering UKRI opportunities..."
    )
    print()

    opportunities = (
        discover_ukri_opportunities(
            limit=DISCOVERY_LIMIT
        )
    )

    print()
    print(
        "Discovered:",
        len(opportunities)
    )
    print()

    imported = 0
    existing = 0
    filtered = 0
    failures = 0

    for candidate in opportunities:

        if imported >= MAX_NEW_IMPORTS:
            break

        title = clean_text(
            candidate.get("title")
        )

        source_url = clean_text(
            candidate.get("url")
        )

        print(
            "----------------------------------------"
        )
        print(
            "Candidate:",
            title
        )
        print(
            "URL:",
            source_url
        )

        if should_skip_title(title):
            print(
                "Result: Filtered by HelAI. Skipped."
            )
            filtered += 1
            print()
            continue

        try:
            found = already_exists(
                supabase,
                source_url
            )

            if found:
                print(
                    "Result: Already in Supabase. Skipped."
                )
                existing += 1
                print()
                continue

            print(
                "Reading official UKRI page..."
            )

            article_text = (
                read_ukri_opportunity(
                    source_url
                )
            )

            print(
                "AI is understanding "
                "the opportunity..."
            )

            extracted = extract_opportunity(
                article_text
            )

            record = build_record(
                extracted,
                article_text,
                source_url
            )

            result = (
                supabase
                .table("opportunities")
                .insert(record)
                .execute()
            )

            if not result.data:
                raise ValueError(
                    "Supabase did not return "
                    "the inserted opportunity."
                )

            print(
                "Result: created"
            )

            print(
                "AI title:",
                record["title"]
            )

            print(
                "Type:",
                record["type"]
            )

            print(
                "Deadline:",
                record["deadline"]
            )

            imported += 1

            time.sleep(
                DELAY_SECONDS
            )

        except Exception as error:
            print(
                "Result: FAILED"
            )
            print(
                "Error:",
                str(error)
            )

            failures += 1

        print()

    print()
    print(
        "========================================"
    )
    print(
        "             RUN SUMMARY"
    )
    print(
        "========================================"
    )

    print(
        "New UKRI opportunities imported:",
        imported
    )

    print(
        "Existing opportunities skipped:",
        existing
    )

    print(
        "Filtered opportunities skipped:",
        filtered
    )

    print(
        "Failures:",
        failures
    )

    print(
        "========================================"
    )
    print()


if __name__ == "__main__":
    run_collector()