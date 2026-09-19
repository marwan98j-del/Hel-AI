import sys
from collections import defaultdict

from collector_client import collector_supabase
from helai_maintenance import duplicate_groups, normalized_patch


sys.stdout.reconfigure(
    encoding="utf-8",
    errors="replace",
)


def has_value(value):
    return bool(str(value or "").strip())


def count_related(table_name, opportunity_id):
    result = (
        collector_supabase
        .table(table_name)
        .select("id")
        .eq("opportunity_id", opportunity_id)
        .execute()
    )

    return len(result.data or [])


def completeness_score(opportunity):
    scalar_fields = [
        "title",
        "organization",
        "type",
        "location",
        "status",
        "deadline",
        "open_date",
        "education",
        "notes",
        "summary_en",
        "source_url",
        "external_id",
        "fingerprint",
    ]

    list_fields = [
        "languages",
        "interests",
        "skills",
        "eligible_applicant_types",
    ]

    return (
        sum(
            1
            for field in scalar_fields
            if has_value(opportunity.get(field))
        )
        + sum(
            1
            for field in list_fields
            if (
                isinstance(opportunity.get(field), list)
                and len(opportunity.get(field)) > 0
            )
        )
        + (
            1
            if has_value(opportunity.get("summary_ku"))
            else 0
        )
        + (
            1
            if has_value(opportunity.get("original_text"))
            else 0
        )
    )


def canonical_score(
    opportunity,
    match_counts,
    notification_counts,
):
    opportunity_id = opportunity["id"]

    return (
        (
            20
            if has_value(opportunity.get("source_url"))
            else 0
        )
        + completeness_score(opportunity) * 3
        + (
            15
            if has_value(opportunity.get("summary_ku"))
            else 0
        )
        + (
            10
            if has_value(opportunity.get("original_text"))
            else 0
        )
        + (
            8
            if (
                has_value(opportunity.get("deadline"))
                or has_value(opportunity.get("open_date"))
            )
            else 0
        )
        + min(
            match_counts[opportunity_id],
            5,
        )
        * 2
        + min(
            notification_counts[opportunity_id],
            3,
        )
        * 3
        + (
            2
            if has_value(opportunity.get("external_id"))
            else 0
        )
    )


def classify_patch(patch):
    categories = []

    if (
        "applicant_type" in patch
        or "eligible_applicant_types" in patch
    ):
        categories.append("applicant type backfill")

    if "source_url" in patch:
        categories.append("URL normalization")

    if "fingerprint" in patch:
        categories.append("fingerprint replacement")

    if "status" in patch:
        categories.append("status correction")

    if (
        "deadline" in patch
        or "open_date" in patch
        or "close_date" in patch
    ):
        categories.append("deadline/open-date correction")

    other_keys = set(patch) - {
        "applicant_type",
        "eligible_applicant_types",
        "source_url",
        "fingerprint",
        "status",
        "deadline",
        "open_date",
        "close_date",
        "updated_at",
    }

    if other_keys:
        categories.append("other")

    return categories


def risky_changes(opportunity, patch):
    risks = []

    if (
        "applicant_type" in patch
        or "eligible_applicant_types" in patch
    ):
        risks.append("eligibility")

    if "status" in patch:
        risks.append("notification behavior")

        after = patch["status"]
        before = opportunity.get("status")

        if before != after:
            risks.append("status from Open to Upcoming/Closed")

    if (
        "deadline" in patch
        or "open_date" in patch
        or "close_date" in patch
    ):
        risks.append("deadline")

    if (
        "source_url" in patch
        or "fingerprint" in patch
    ):
        risks.append("source identity")

    return sorted(set(risks))


def print_duplicate_plan(
    duplicates,
    match_counts,
    notification_counts,
):
    kept_ids = []
    removed_ids = []

    for index, ((key, value), group) in enumerate(
        duplicates.items(),
        start=1,
    ):
        ranked = sorted(
            group,
            key=lambda opportunity: (
                canonical_score(
                    opportunity,
                    match_counts,
                    notification_counts,
                ),
                has_value(opportunity.get("summary_ku")),
                has_value(opportunity.get("original_text")),
                (
                    opportunity.get("updated_at")
                    or opportunity.get("discovered_at")
                    or opportunity.get("created_at")
                    or ""
                ),
            ),
            reverse=True,
        )

        keep = ranked[0]
        kept_ids.append(keep["id"])

        print(f"## Duplicate Group {index}")
        print(f"- duplicate_key: {key}")
        print(f"- duplicate_value: {value}")
        print(
            "- recommended_keep: "
            f"{keep['id']} | {keep.get('title')}"
        )
        print(
            "- keep_reason: "
            f"score={canonical_score(keep, match_counts, notification_counts)}, "
            f"structured_fields={completeness_score(keep)}, "
            f"has_summary_ku={has_value(keep.get('summary_ku'))}, "
            f"has_original_text={has_value(keep.get('original_text'))}, "
            f"matches={match_counts[keep['id']]}, "
            f"notifications={notification_counts[keep['id']]}"
        )
        print()

        for opportunity in sorted(
            group,
            key=lambda item: item.get("id", ""),
        ):
            opportunity_id = opportunity["id"]

            print(f"### Record {opportunity_id}")

            for field in [
                "title",
                "source",
                "source_name",
                "source_url",
                "external_id",
                "fingerprint",
                "status",
                "deadline",
                "open_date",
                "created_at",
                "discovered_at",
                "updated_at",
            ]:
                print(
                    f"- {field}: {opportunity.get(field)}"
                )

            print(
                "- has_summary_ku: "
                f"{has_value(opportunity.get('summary_ku'))}"
            )
            print(
                "- has_original_text: "
                f"{has_value(opportunity.get('original_text'))}"
            )
            print(
                "- matching_records: "
                f"{match_counts[opportunity_id]}"
            )
            print(
                "- notification_records: "
                f"{notification_counts[opportunity_id]}"
            )
            print(
                "- structured_completeness_score: "
                f"{completeness_score(opportunity)}"
            )

            if opportunity_id == keep["id"]:
                print("- proposed_action: KEEP")
            else:
                removed_ids.append(opportunity_id)

                reasons = []

                if (
                    str(
                        opportunity.get("source_url") or ""
                    ).rstrip("/")
                    == str(
                        keep.get("source_url") or ""
                    ).rstrip("/")
                ):
                    reasons.append(
                        "same normalized official source URL as canonical"
                    )

                if completeness_score(
                    opportunity
                ) <= completeness_score(keep):
                    reasons.append(
                        "not more structurally complete than canonical"
                    )

                if (
                    not has_value(
                        opportunity.get("summary_ku")
                    )
                    and has_value(keep.get("summary_ku"))
                ):
                    reasons.append(
                        "canonical has Kurdish translation and this record does not"
                    )

                if match_counts[opportunity_id] == 0:
                    reasons.append(
                        "no match records to migrate"
                    )

                if notification_counts[opportunity_id] == 0:
                    reasons.append(
                        "no notification records to migrate"
                    )

                if (
                    match_counts[opportunity_id] > 0
                    or notification_counts[opportunity_id] > 0
                ):
                    reasons.append(
                        "requires related match/notification migration before deletion"
                    )

                print(
                    "- proposed_action: REMOVE after approval"
                )
                print(
                    "- safe_removal_reason: "
                    + "; ".join(reasons)
                )

            print()

    return kept_ids, removed_ids


def print_normalization_plan(opportunities):
    candidates = []
    category_counts = defaultdict(int)
    risky = []

    for opportunity in opportunities:
        patch = normalized_patch(opportunity)

        if not patch:
            continue

        categories = classify_patch(patch)
        risks = risky_changes(
            opportunity,
            patch,
        )

        candidates.append(
            (
                opportunity,
                patch,
                categories,
                risks,
            )
        )

        for category in categories:
            category_counts[category] += 1

        if risks:
            risky.append(
                (
                    opportunity,
                    patch,
                    risks,
                )
            )

    print("## Normalization Candidate Summary")

    for category in [
        "applicant type backfill",
        "URL normalization",
        "fingerprint replacement",
        "status correction",
        "deadline/open-date correction",
        "other",
    ]:
        print(
            f"- {category}: "
            f"{category_counts.get(category, 0)}"
        )

    print(
        f"- total normalization candidates: {len(candidates)}"
    )
    print(
        f"- risky normalization candidates: {len(risky)}"
    )
    print()

    print("## Risky Normalization Details")

    for opportunity, patch, risks in risky:
        print(
            "### "
            f"{opportunity.get('id')} | "
            f"{opportunity.get('title')}"
        )
        print("- risks: " + ", ".join(risks))

        for key in sorted(patch):
            if key == "updated_at":
                continue

            print(
                f"- {key}: "
                f"{opportunity.get(key)!r} -> {patch[key]!r}"
            )

        print()

    return candidates, risky


def main():
    opportunities = (
        collector_supabase
        .table("opportunities")
        .select("*")
        .execute()
        .data
        or []
    )

    duplicates = duplicate_groups(opportunities)

    duplicate_ids = sorted(
        {
            opportunity["id"]
            for group in duplicates.values()
            for opportunity in group
        }
    )

    match_counts = {}
    notification_counts = {}

    for opportunity_id in duplicate_ids:
        match_counts[opportunity_id] = count_related(
            "matches",
            opportunity_id,
        )
        notification_counts[opportunity_id] = count_related(
            "notifications",
            opportunity_id,
        )

    print("# HelAI Read-Only Cleanup Plan")
    print()
    print(
        "No Supabase records were deleted, merged, updated, "
        "or moved by this report."
    )
    print()

    kept_ids, removed_ids = print_duplicate_plan(
        duplicates,
        match_counts,
        notification_counts,
    )

    candidates, risky = print_normalization_plan(
        opportunities,
    )

    print("## Orphan And Migration Check")
    print(
        "Deleting duplicate opportunities directly would orphan "
        "or discard related rows where matching_records or "
        "notification_records are non-zero."
    )
    print(
        "Safe migration plan: for each approved removal, pause "
        "notification sending, update matches.opportunity_id and "
        "notifications.opportunity_id to the canonical opportunity, "
        "deduplicate any user_id/opportunity_id match conflicts by "
        "keeping the newest/highest-confidence match, verify counts, "
        "then delete only the duplicate opportunity record."
    )
    print(
        "Kurdish translations and original source text are stored "
        "on opportunity rows, so preserve the canonical row with the "
        "best summary_ku/original_text or copy missing non-conflicting "
        "fields before any approved delete."
    )
    print()

    print("## Final Counts")
    print(f"- duplicate groups: {len(duplicates)}")
    print(f"- records proposed to keep: {len(kept_ids)}")
    print(f"- records proposed to remove: {len(removed_ids)}")
    print(
        f"- normalization candidates: {len(candidates)}"
    )
    print(
        f"- risky normalization candidates: {len(risky)}"
    )
    print(
        "- cleanup can be performed safely without schema changes: "
        "yes, for merge/delete of duplicates; structured "
        "applicant/open_date fields only persist if existing columns "
        "are present, otherwise current code falls back safely."
    )


if __name__ == "__main__":
    main()
