import argparse
from collections import defaultdict
from datetime import datetime, timezone

from collector_client import collector_supabase
from collector_service import execute_with_schema_fallback
from opportunity_rules import (
    create_fingerprint,
    get_eligible_applicant_types,
    normalize_deadline,
    normalize_open_date,
    normalize_status,
    normalize_url,
)


def load_opportunities():
    response = (
        collector_supabase
        .table("opportunities")
        .select("*")
        .execute()
    )

    return response.data or []


def normalized_patch(opportunity):
    original_text = opportunity.get(
        "original_text"
    ) or ""

    source_url = normalize_url(
        opportunity.get("source_url")
    )

    external_id = opportunity.get(
        "external_id"
    )

    applicant_types = get_eligible_applicant_types(
        opportunity
    )

    patch = {}

    normalized_status = normalize_status(
        opportunity.get("status")
    )

    if opportunity.get("status") != normalized_status:
        patch["status"] = normalized_status

    if opportunity.get("source_url") != (
        source_url or None
    ):
        patch["source_url"] = source_url or None

    current_fingerprint = opportunity.get(
        "fingerprint"
    )

    if (
        not current_fingerprint
        or str(current_fingerprint).startswith(
            "legacy-"
        )
    ):
        patch["fingerprint"] = create_fingerprint(
            opportunity.get("title"),
            source_url,
            external_id,
        )

    open_date = normalize_open_date(
        opportunity.get("open_date"),
        original_text,
    )

    if (
        open_date
        and opportunity.get("open_date") != open_date
    ):
        patch["open_date"] = open_date

    deadline = normalize_deadline(
        (
            opportunity.get("close_date")
            or opportunity.get("deadline")
        ),
        original_text,
    )

    if opportunity.get("deadline") != deadline:
        patch["deadline"] = deadline

    close_date = normalize_deadline(
        opportunity.get("close_date"),
        original_text,
    )

    if (
        close_date
        and opportunity.get("close_date") != close_date
    ):
        patch["close_date"] = close_date

    if applicant_types:
        patch["eligible_applicant_types"] = (
            applicant_types
        )
        patch["applicant_type"] = ", ".join(
            applicant_types
        )

    if patch:
        patch["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

    return {
        key: value
        for key, value in patch.items()
        if opportunity.get(key) != value
    }


def duplicate_groups(opportunities):
    groups = defaultdict(list)

    for opportunity in opportunities:
        checks = [
            (
                "source_url",
                normalize_url(
                    opportunity.get("source_url")
                ),
            ),
            (
                "external_id",
                opportunity.get("external_id"),
            ),
            (
                "fingerprint",
                opportunity.get("fingerprint"),
            ),
        ]

        for key, value in checks:
            if value:
                groups[(key, value)].append(
                    opportunity
                )

    return {
        key: value
        for key, value in groups.items()
        if len(value) > 1
    }


def apply_patch(opportunity_id, patch):
    return execute_with_schema_fallback(
        lambda record: (
            collector_supabase
            .table("opportunities")
            .update(record)
            .eq("id", opportunity_id)
            .execute()
        ),
        patch,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Safely re-evaluate HelAI opportunity status, "
            "dates, applicant type, and duplicate groups."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply non-destructive normalization updates.",
    )

    args = parser.parse_args()

    opportunities = load_opportunities()

    print("Opportunities loaded:", len(opportunities))
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print()

    changed = 0

    for opportunity in opportunities:
        patch = normalized_patch(opportunity)

        if not patch:
            continue

        changed += 1

        print("----------------------------------------")
        print("ID:", opportunity.get("id"))
        print("Title:", opportunity.get("title"))
        print("Proposed fields:", sorted(patch.keys()))

        for key in sorted(patch.keys()):
            if key == "updated_at":
                continue

            print(
                f"  {key}: "
                f"{opportunity.get(key)!r} -> {patch[key]!r}"
            )

        if args.apply:
            apply_patch(
                opportunity["id"],
                patch,
            )
            print("Applied: True")

    print()
    print("Records with proposed updates:", changed)
    print()

    duplicates = duplicate_groups(opportunities)

    print("Duplicate groups found:", len(duplicates))

    for (key, value), group in duplicates.items():
        print("----------------------------------------")
        print("Duplicate key:", key)
        print("Duplicate value:", value)

        for item in group:
            print(
                "-",
                item.get("id"),
                "|",
                item.get("title"),
                "|",
                item.get("source_name")
                or item.get("source"),
            )

    if duplicates:
        print()
        print(
            "No duplicate records were deleted. Review these "
            "groups and approve any cleanup before removal or merge."
        )


if __name__ == "__main__":
    main()
