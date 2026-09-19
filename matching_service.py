import os
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

from matcher import calculate_match
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    RECORD_KIND_APPLICATION,
    effective_status,
    normalize_record_kind,
)


load_dotenv(override=True)


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

# Compatibility stays enabled until record_kind has been backfilled and
# reviewed. Flip this only in a separately reviewed activation change.
REQUIRE_APPLICATION_RECORD_KIND = False


def opportunity_is_actionable(
    opportunity,
    require_application_record_kind=REQUIRE_APPLICATION_RECORD_KIND,
    reference_date=None,
):
    if not opportunity.get("active", True):
        return False
    if effective_status(opportunity, today=reference_date) != "Open":
        return False
    if require_application_record_kind:
        return (
            normalize_record_kind(opportunity.get("record_kind"))
            == RECORD_KIND_APPLICATION
        )
    return True


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


def safe_text(value):
    if value is None:
        return ""

    return str(value).strip()


def safe_float(value, default=0.0):
    if value is None:
        return default

    try:
        return float(value)
    except Exception:
        return default


def safe_list(value):
    if isinstance(value, list):
        return value

    return []


def calculate_age(date_of_birth):
    if not date_of_birth:
        return None

    try:
        if isinstance(date_of_birth, date):
            dob = date_of_birth
        else:
            dob = date.fromisoformat(
                str(date_of_birth)[:10]
            )

    except Exception:
        return None

    today = date.today()

    return (
        today.year
        - dob.year
        - (
            (today.month, today.day)
            <
            (dob.month, dob.day)
        )
    )


def profile_is_matchable(profile):
    if not profile:
        return False, "profile data is missing"

    if not profile.get("profile_complete"):
        return False, "profile is not complete"

    if not profile.get("date_of_birth"):
        return False, "date of birth is missing"

    age = calculate_age(
        profile.get("date_of_birth")
    )

    if age is None:
        return False, "date of birth is invalid"

    return True, ""


def prepare_profile(profile):
    age = calculate_age(
        profile.get("date_of_birth")
    )

    return {
        "full_name": safe_text(
            profile.get("full_name")
        ),

        "email": safe_text(
            profile.get("email")
        ),

        "age": age,

        "nationality": safe_text(
            profile.get("nationality")
        ),

        "country_of_residence": safe_text(
            profile.get(
                "country_of_residence"
            )
        ),

        "city": safe_text(
            profile.get("city")
        ),

        "education": (
            safe_text(
                profile.get("education")
            )
            or "Any"
        ),

        "field_of_study": safe_text(
            profile.get("field_of_study")
        ),

        "grade": safe_float(
            profile.get("grade"),
            0
        ),

        "work_experience_years":
            safe_float(
                profile.get(
                    "work_experience_years"
                ),
                0
            ),

        "languages": safe_list(
            profile.get("languages")
        ),

        "skills": safe_list(
            profile.get("skills")
        ),

        "interests": safe_list(
            profile.get("interests")
        ),

        "opportunity_types": safe_list(
            profile.get(
                "opportunity_types"
            )
        ),

        "has_passport": bool(
            profile.get(
                "has_passport",
                False
            )
        ),

        "has_ielts": bool(
            profile.get(
                "has_ielts",
                False
            )
        ),

        "has_portfolio": bool(
            profile.get(
                "has_portfolio",
                False
            )
        ),

        "has_cv": bool(
            profile.get(
                "has_cv",
                False
            )
        ),

        "applicant_type": APPLICANT_INDIVIDUAL,
    }


def load_profiles(client):
    result = (
        client
        .table("profiles")
        .select("*")
        .execute()
    )

    return result.data or []


def load_matchable_opportunities(client):
    result = (
        client
        .table("opportunities")
        .select("*")
        .eq("active", True)
        .execute()
    )

    return [
        opportunity
        for opportunity in (result.data or [])
        if opportunity_is_actionable(opportunity)
    ]


def save_match(
    client,
    profile,
    opportunity,
    result
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    record = {
        "user_id": profile["id"],

        "opportunity_id":
            opportunity["id"],

        "match_score": int(
            round(
                result.get(
                    "score",
                    0
                )
            )
        ),

        "eligible": bool(
            result.get(
                "eligible",
                False
            )
        ),

        "readiness": int(
            round(
                result.get(
                    "readiness",
                    0
                )
            )
        ),

        "reasons": (
            result.get("reasons")
            or []
        ),

        "eligibility_gaps": (
            result.get(
                "eligibility_gaps"
            )
            or []
        ),

        "readiness_gaps": (
            result.get(
                "readiness_gaps"
            )
            or []
        ),

        "updated_at": now,
    }

    (
        client
        .table("matches")
        .upsert(
            record,
            on_conflict=(
                "user_id,opportunity_id"
            )
        )
        .execute()
    )


def run_matching():
    print()
    print("====================================")
    print("       HelAI Matching Engine")
    print("====================================")
    print()

    client = get_supabase()

    profiles = load_profiles(
        client
    )

    opportunities = (
        load_matchable_opportunities(
            client
        )
    )

    matchable_profiles = []

    skipped_profiles = []

    for profile in profiles:

        matchable, reason = (
            profile_is_matchable(
                profile
            )
        )

        if matchable:
            matchable_profiles.append(
                profile
            )
        else:
            skipped_profiles.append(
                (
                    profile,
                    reason
                )
            )

    print(
        "Profiles found:",
        len(profiles)
    )

    print(
        "Matchable profiles:",
        len(matchable_profiles)
    )

    print(
        "Incomplete profiles skipped:",
        len(skipped_profiles)
    )

    print(
        "Matchable opportunities:",
        len(opportunities)
    )

    print()

    for profile, reason in skipped_profiles:

        email = (
            profile.get("email")
            or "Unknown account"
        )

        print(
            f"SKIPPED PROFILE: "
            f"{email} | {reason}"
        )

    if skipped_profiles:
        print()

    processed = 0
    failed = 0

    for cloud_profile in matchable_profiles:

        prepared_profile = (
            prepare_profile(
                cloud_profile
            )
        )

        email = (
            cloud_profile.get("email")
            or "Unknown user"
        )

        print(
            "User:",
            email
        )

        print(
            "Age:",
            prepared_profile["age"]
        )

        for opportunity in opportunities:

            title = (
                opportunity.get("title")
                or "Untitled opportunity"
            )

            try:
                result = calculate_match(
                    prepared_profile,
                    opportunity
                )

                save_match(
                    client,
                    cloud_profile,
                    opportunity,
                    result
                )

                print(
                    f"- {title}"
                    f" | Match: "
                    f"{result.get('score', 0)}%"
                    f" | Eligible: "
                    f"{result.get('eligible', False)}"
                    f" | Readiness: "
                    f"{result.get('readiness', 0)}%"
                )

                processed += 1

            except Exception as error:

                print(
                    f"- ERROR: {title}"
                )

                print(
                    f"  {type(error).__name__}: "
                    f"{error}"
                )

                failed += 1

        print()

    print("====================================")
    print(
        "Match records processed:",
        processed
    )
    print(
        "Match failures:",
        failed
    )
    print(
        "Profiles skipped:",
        len(skipped_profiles)
    )
    print("====================================")
    print()

    return {
        "profiles_found": len(profiles),
        "profiles_checked": len(matchable_profiles),
        "profiles_skipped": len(skipped_profiles),
        "opportunities": len(opportunities),
        "matches_processed": processed,
        "failures": failed,
    }


if __name__ == "__main__":
    run_matching()
