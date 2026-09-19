from datetime import datetime, timezone

from ai_extractor import extract_opportunity
from collector_client import collector_supabase
from opportunity_rules import (
    create_fingerprint,
    get_eligible_applicant_types,
    normalize_applicant_types,
    normalize_deadline,
    normalize_open_date,
    normalize_record_kind,
    normalize_status,
    normalize_url,
    primary_applicant_type,
    RECORD_KIND_APPLICATION,
)


def normalize_list(value):
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    return []


# =========================================================
# PROCESS ANNOUNCEMENT WITH AI
# =========================================================

def process_announcement(
    announcement_text,
    source_name="Manual Import",
    source_url="",
    source=None,
    external_id=None
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

    normalized_source_url = normalize_url(
        source_url
    )

    fingerprint = create_fingerprint(
        title,
        normalized_source_url,
        external_id,
    )

    source_text = "\n".join(
        value
        for value in [
            extracted.get("deadline") or "",
            extracted.get("close_date") or "",
            extracted.get("open_date") or "",
            announcement_text,
        ]
        if value
    )

    applicant_types = normalize_applicant_types(
        extracted.get("eligible_applicant_types")
        or extracted.get("applicant_type")
    )

    record_kind = normalize_record_kind(
        extracted.get("record_kind")
    )

    if record_kind != RECORD_KIND_APPLICATION:
        applicant_types = []

    if (
        not applicant_types
        and record_kind == RECORD_KIND_APPLICATION
    ):
        applicant_types = get_eligible_applicant_types(
            {
                "title": title,
                "organization": extracted.get(
                    "organization"
                ),
                "type": extracted.get("type"),
                "notes": extracted.get("notes"),
                "summary_en": extracted.get("notes"),
                "original_text": announcement_text,
            }
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
        "status": normalize_status(
            extracted.get("status")
        ),
        "open_date": normalize_open_date(
            extracted.get("open_date"),
            source_text,
        ),
        "deadline": normalize_deadline(
            (
                extracted.get("close_date")
                or extracted.get("deadline")
            ),
            source_text,
        ),
        "close_date": normalize_deadline(
            extracted.get("close_date"),
            source_text,
        ),
        "record_kind": record_kind,
        "eligible_applicant_types": (
            applicant_types or None
        ),
        "applicant_type": primary_applicant_type(
            applicant_types
        ),
        "applicant_type_reviewed": False,
        "record_kind_reviewed": False,
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
        "languages": normalize_list(
            extracted.get("languages")
        ),
        "interests": normalize_list(
            extracted.get("interests")
        ),
        "skills": normalize_list(
            extracted.get("skills")
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
        "summary_en": extracted.get(
            "notes",
            ""
        ),
        "summary_ku": None,
        "original_text": announcement_text,
        "source": source or source_name,
        "source_name": source_name,
        "source_url": normalized_source_url or None,
        "external_id": external_id,
        "source_language": None,
        "ai_processed": True,
        "active": True,
        "discovered_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "fingerprint": fingerprint
    }

    return opportunity


OPTIONAL_SCHEMA_KEYS = {
    "open_date",
    "close_date",
    "eligible_applicant_types",
    "applicant_type",
    "record_kind",
    "applicant_type_reviewed",
    "record_kind_reviewed",
}


def opportunity_identity(opportunity):
    return {
        "source_url": normalize_url(
            opportunity.get("source_url")
            or opportunity.get("url")
        ),
        "external_id": str(
            opportunity.get("external_id") or ""
        ).strip(),
        "fingerprint": str(
            opportunity.get("fingerprint") or ""
        ).strip(),
    }


def identity_match_reasons(incoming, stored):
    """Return exact reliable identities shared by two opportunity records."""
    incoming_identity = opportunity_identity(incoming)
    stored_identity = opportunity_identity(stored)
    return [
        key
        for key in ("source_url", "external_id", "fingerprint")
        if incoming_identity[key]
        and incoming_identity[key] == stored_identity[key]
    ]


def find_matching_opportunity(incoming, stored_rows):
    for stored in stored_rows:
        if identity_match_reasons(incoming, stored):
            return stored
    return None


def find_existing_opportunity(opportunity, client=None):
    client = client or collector_supabase
    response = (
        client
        .table("opportunities")
        .select("*")
        .execute()
    )
    return find_matching_opportunity(
        opportunity,
        response.data or [],
    )


def protect_reviewed_intelligence(incoming, existing):
    """Apply reviewed > automated > empty precedence without mutating inputs."""
    record = dict(incoming)

    if existing.get("applicant_type_reviewed"):
        record["applicant_type"] = existing.get("applicant_type")
        record["eligible_applicant_types"] = existing.get(
            "eligible_applicant_types"
        )
        record["applicant_type_reviewed"] = True
    elif not record.get("applicant_type") and existing.get("applicant_type"):
        record["applicant_type"] = existing.get("applicant_type")
        record["eligible_applicant_types"] = existing.get(
            "eligible_applicant_types"
        )

    if existing.get("record_kind_reviewed"):
        record["record_kind"] = existing.get("record_kind")
        record["record_kind_reviewed"] = True
    elif (
        normalize_record_kind(record.get("record_kind")) == "unknown"
        and normalize_record_kind(existing.get("record_kind")) != "unknown"
    ):
        record["record_kind"] = existing.get("record_kind")

    return record


def remove_optional_schema_keys(opportunity):
    return {
        key: value
        for key, value in opportunity.items()
        if key not in OPTIONAL_SCHEMA_KEYS
    }


def execute_with_schema_fallback(query_factory, opportunity):
    try:
        return query_factory(opportunity)
    except Exception as error:
        message = str(error).lower()

        if not any(
            key in message
            for key in OPTIONAL_SCHEMA_KEYS
        ):
            raise

        fallback = remove_optional_schema_keys(
            opportunity
        )

        return query_factory(fallback)


# =========================================================
# SAVE TO SUPABASE
# =========================================================

def save_opportunity(
    opportunity
):

    existing = find_existing_opportunity(
        opportunity
    )

    if existing:

        opportunity_id = existing[
            "id"
        ]

        opportunity = protect_reviewed_intelligence(
            opportunity,
            existing,
        )

        response = execute_with_schema_fallback(
            lambda record: (
                collector_supabase
                .table("opportunities")
                .update(record)
                .eq(
                    "id",
                    opportunity_id
                )
                .execute()
            ),
            opportunity,
        )

        return {
            "success": True,
            "action": "updated",
            "data": response.data
        }

    response = execute_with_schema_fallback(
        lambda record: (
            collector_supabase
            .table("opportunities")
            .insert(record)
            .execute()
        ),
        opportunity,
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
    source_url="",
    source=None,
    external_id=None
):

    opportunity = process_announcement(
        announcement_text=announcement_text,
        source_name=source_name,
        source_url=source_url,
        source=source,
        external_id=external_id
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
