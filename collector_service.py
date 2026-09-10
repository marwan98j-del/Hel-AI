import hashlib
from datetime import datetime, timezone

from ai_extractor import extract_opportunity
from collector_client import collector_supabase


# =========================================================
# CREATE UNIQUE FINGERPRINT
# =========================================================

def create_fingerprint(title, source_url=""):

    raw_value = (
        f"{title.strip().lower()}|"
        f"{source_url.strip().lower()}"
    )

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()


# =========================================================
# PROCESS ANNOUNCEMENT WITH AI
# =========================================================

def process_announcement(
    announcement_text,
    source_name="Manual Import",
    source_url=""
):

    if not announcement_text.strip():
        raise ValueError(
            "Announcement text cannot be empty."
        )

    extracted = extract_opportunity(
        announcement_text
    )

    title = extracted.get(
        "title",
        "Untitled Opportunity"
    )

    fingerprint = create_fingerprint(
        title,
        source_url
    )

    opportunity = {
        "title": title,
        "organization": extracted.get(
            "organization"
        ),
        "type": extracted.get(
            "type"
        ),
        "location": extracted.get(
            "location"
        ),
        "status": extracted.get(
            "status",
            "Unknown"
        ),
        "deadline": (
            extracted.get("deadline")
            or None
        ),
        "minimum_age": extracted.get(
            "minimum_age"
        ),
        "maximum_age": extracted.get(
            "maximum_age"
        ),
        "education": extracted.get(
            "education",
            "Any"
        ),
        "education_rule": extracted.get(
            "education_rule",
            "minimum"
        ),
        "minimum_grade": extracted.get(
            "minimum_grade",
            0
        ) or 0,
        "minimum_work_experience_years": extracted.get(
            "minimum_work_experience_years",
            0
        ) or 0,
        "residency_requirement": extracted.get(
            "residency_requirement",
            ""
        ),
        "languages": extracted.get(
            "languages",
            []
        ),
        "interests": extracted.get(
            "interests",
            []
        ),
        "skills": extracted.get(
            "skills",
            []
        ),
        "requires_passport": extracted.get(
            "requires_passport",
            False
        ),
        "requires_ielts": extracted.get(
            "requires_ielts",
            False
        ),
        "requires_portfolio": extracted.get(
            "requires_portfolio",
            False
        ),
        "requires_cv": extracted.get(
            "requires_cv",
            False
        ),
        "notes": extracted.get(
            "notes",
            ""
        ),
        "original_text": announcement_text,
        "source": source_name,
        "source_name": source_name,
        "source_url": source_url or None,
        "source_language": None,
        "ai_processed": True,
        "active": True,
        "discovered_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "fingerprint": fingerprint
    }

    return opportunity


# =========================================================
# SAVE TO SUPABASE
# =========================================================

def save_opportunity(
    opportunity
):

    fingerprint = opportunity[
        "fingerprint"
    ]

    existing = (
        collector_supabase
        .table("opportunities")
        .select("id,title")
        .eq(
            "fingerprint",
            fingerprint
        )
        .execute()
    )

    if existing.data:

        opportunity_id = existing.data[0][
            "id"
        ]

        response = (
            collector_supabase
            .table("opportunities")
            .update(opportunity)
            .eq(
                "id",
                opportunity_id
            )
            .execute()
        )

        return {
            "success": True,
            "action": "updated",
            "data": response.data
        }

    response = (
        collector_supabase
        .table("opportunities")
        .insert(opportunity)
        .execute()
    )

    return {
        "success": True,
        "action": "created",
        "data": response.data
    }


# =========================================================
# COMPLETE AI PIPELINE
# =========================================================

def analyze_and_save(
    announcement_text,
    source_name="Manual Import",
    source_url=""
):

    opportunity = process_announcement(
        announcement_text=announcement_text,
        source_name=source_name,
        source_url=source_url
    )

    result = save_opportunity(
        opportunity
    )

    return {
        "success": result["success"],
        "action": result["action"],
        "opportunity": opportunity,
        "database_result": result["data"]
    }