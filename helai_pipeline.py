import time
from datetime import datetime, timezone

from collector_client import collector_supabase
from collector_service import (
    analyze_and_save,
    create_fingerprint,
    find_existing_opportunity,
)
from email_service import send_pending_notifications
from helai_config import (
    HELAI_MAX_NEW_PER_SOURCE,
    HELAI_REQUEST_DELAY_SECONDS,
    HELAI_SOURCE_LIMIT,
)
from helai_source_status import update_source_status
from matching_service import run_matching
from notification_service import build_notification_queue
from source_adapters import (
    get_source_adapters,
    normalize_candidate_url,
)
from translation_service import run_translation_service


def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def already_imported(candidate):
    source_url = normalize_candidate_url(
        candidate
    )

    external_id = (
        candidate.get("external_id")
        or ""
    )

    title = (
        candidate.get("title")
        or ""
    )

    fingerprint = create_fingerprint(
        title,
        source_url,
        external_id,
    )

    return bool(
        find_existing_opportunity(
            {
                "title": title,
                "source_url": source_url,
                "external_id": external_id,
                "fingerprint": fingerprint,
            },
            client=collector_supabase,
        )
    )


def collect_from_source(source):
    print()
    print("========================================")
    print("SOURCE CHECK")
    print("Source:", source.source_name)
    print("========================================")

    discovered_count = 0
    existing_count = 0
    imported_count = 0
    failed_count = 0
    error_message = ""

    try:
        candidates = source.discover(
            HELAI_SOURCE_LIMIT
        )
        discovered_count = len(candidates)

        print(
            "Discovered:",
            discovered_count,
        )

    except Exception as error:
        error_message = str(error)
        print(
            "Source discovery failed:",
            error_message,
        )

        update_source_status(
            source.key,
            {
                "source": source.source,
                "source_name": source.source_name,
                "active": source.active,
                "last_status": "failed",
                "last_error": error_message,
                "discovered": 0,
                "existing": 0,
                "imported": 0,
                "failed": 1,
            },
        )

        return {
            "source": source.source,
            "source_name": source.source_name,
            "discovered": 0,
            "existing": 0,
            "imported": 0,
            "failed": 1,
            "error": error_message,
        }

    for candidate in candidates:
        if imported_count >= HELAI_MAX_NEW_PER_SOURCE:
            break

        title = (
            candidate.get("title")
            or "Untitled opportunity"
        )

        candidate["url"] = normalize_candidate_url(
            candidate
        )

        print("----------------------------------------")
        print("Candidate:", title)
        print("URL:", candidate["url"])

        try:
            if already_imported(candidate):
                existing_count += 1
                print("Result: Existing. Skipped.")
                continue

            print("Reading full announcement...")
            announcement_text = source.read(
                candidate
            )

            print("OpenAI is extracting requirements...")
            result = analyze_and_save(
                announcement_text=announcement_text,
                source=source.source,
                source_name=source.source_name,
                source_url=candidate["url"],
                external_id=candidate.get(
                    "external_id"
                ),
            )

            imported_count += 1
            opportunity = result["opportunity"]

            print("Result:", result["action"])
            print(
                "AI title:",
                opportunity.get("title"),
            )
            print(
                "Type:",
                opportunity.get("type"),
            )
            print(
                "Deadline:",
                opportunity.get("deadline"),
            )

            time.sleep(
                HELAI_REQUEST_DELAY_SECONDS
            )

        except Exception as error:
            failed_count += 1
            print("Result: FAILED")
            print("Error:", str(error))

    print("----------------------------------------")
    print("Discovered:", discovered_count)
    print("Existing:", existing_count)
    print("Imported:", imported_count)
    print("Failed:", failed_count)

    update_source_status(
        source.key,
        {
            "source": source.source,
            "source_name": source.source_name,
            "active": source.active,
            "last_status": (
                "ok"
                if failed_count == 0
                else "partial"
            ),
            "last_error": error_message,
            "discovered": discovered_count,
            "existing": existing_count,
            "imported": imported_count,
            "failed": failed_count,
        },
    )

    return {
        "source": source.source,
        "source_name": source.source_name,
        "discovered": discovered_count,
        "existing": existing_count,
        "imported": imported_count,
        "failed": failed_count,
        "error": error_message,
    }


def run_full_cycle():
    print()
    print("========================================")
    print("HELAI AUTOMATION CYCLE START")
    print("Started:", now_iso())
    print("========================================")

    source_results = []

    for source in get_source_adapters():
        if not source.active:
            continue

        source_results.append(
            collect_from_source(source)
        )

    print()
    print("========================================")
    print("TRANSLATION")
    print("========================================")

    translation_result = run_translation_service()

    print()
    print("========================================")
    print("MATCHING")
    print("========================================")

    matching_result = run_matching()

    print()
    print("========================================")
    print("NOTIFICATIONS")
    print("========================================")

    notification_result = build_notification_queue()

    print()
    print("========================================")
    print("EMAIL")
    print("========================================")

    email_result = send_pending_notifications()

    print()
    print("========================================")
    print("FINAL")
    print("HELAI AUTOMATION COMPLETED SUCCESSFULLY")
    print("Finished:", now_iso())
    print("========================================")

    return {
        "sources": source_results,
        "translation": translation_result,
        "matching": matching_result,
        "notifications": notification_result,
        "email": email_result,
    }
