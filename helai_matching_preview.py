"""Read-only HelAI matching re-evaluation with verified local backup.

This tool intentionally has no apply mode and imports neither notification nor
email services.  It creates a local backup, then calculates a comparison plan.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from matcher import calculate_match
from matching_service import (
    opportunity_is_actionable,
    prepare_profile,
    profile_is_matchable,
)
from opportunity_rules import (
    applicant_types_are_entity_only,
    effective_status,
    get_eligible_applicant_types,
)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKUP_DIRECTORY = Path(__file__).with_name("helai_matching_backups")
DERIVED_FIELDS = (
    "match_score",
    "eligible",
    "readiness",
    "reasons",
    "eligibility_gaps",
    "readiness_gaps",
)
MAJOR_SCORE_DELTA = 20
PROBLEM_TITLES = (
    "Medicines Manufacturing Data Institute: Phase 1",
    "Engineering Biology Access to Infrastructure Pilot",
)


class PreviewSafetyError(RuntimeError):
    pass


def result_fields(result):
    return {
        "match_score": int(round(result.get("score", 0))),
        "eligible": bool(result.get("eligible", False)),
        "readiness": int(round(result.get("readiness", 0))),
        "reasons": result.get("reasons") or [],
        "eligibility_gaps": result.get("eligibility_gaps") or [],
        "readiness_gaps": result.get("readiness_gaps") or [],
    }


def changed_fields(old, new):
    return {
        field: {"old": old.get(field), "new": new.get(field)}
        for field in DERIVED_FIELDS
        if old.get(field) != new.get(field)
    }


def backup_matches(matches):
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUP_DIRECTORY / f"helai_matches_{stamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table": "matches",
        "matches": matches,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def verify_match_backup(path, expected_matches):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreviewSafetyError(f"match backup is not valid JSON: {error}") from error
    rows = payload.get("matches")
    if payload.get("table") != "matches" or not isinstance(rows, list):
        raise PreviewSafetyError("match backup structure is invalid")
    expected_ids = {row.get("id") for row in expected_matches}
    actual_ids = {row.get("id") for row in rows}
    if None in actual_ids or len(actual_ids) != len(rows):
        raise PreviewSafetyError("match backup contains missing or duplicate row IDs")
    if actual_ids != expected_ids or len(rows) != len(expected_matches):
        raise PreviewSafetyError("match backup rows differ from the live preflight rows")
    return {
        "total_matches": len(rows),
        "unique_users": len({row.get("user_id") for row in rows}),
        "unique_opportunities": len({row.get("opportunity_id") for row in rows}),
    }


def is_problem_example(opportunity):
    title = str(opportunity.get("title") or "")
    combined = " ".join(
        str(opportunity.get(field) or "")
        for field in ("title", "organization", "source", "source_name")
    ).lower()
    agency_record = bool(
        re.search(r"\bcdc\b|centers for disease control", combined)
        or re.search(r"\bnsf\b|national science foundation", combined)
    )
    applicant_types = get_eligible_applicant_types(opportunity)
    return title in PROBLEM_TITLES or (
        agency_record and applicant_types_are_entity_only(applicant_types)
    )


def build_preview(profiles, opportunities, matches):
    profiles_by_id = {row.get("id"): row for row in profiles}
    opportunities_by_id = {row.get("id"): row for row in opportunities}
    complete_profiles = []
    skipped_profiles = []
    for profile in profiles:
        matchable, reason = profile_is_matchable(profile)
        if matchable:
            complete_profiles.append(profile)
        else:
            skipped_profiles.append({"profile_id": profile.get("id"), "reason": reason})
    complete_ids = {row["id"] for row in complete_profiles}

    pair_counts = Counter(
        (row.get("user_id"), row.get("opportunity_id")) for row in matches
    )
    duplicate_match_keys = [list(key) for key, count in pair_counts.items() if count > 1]
    errors = []
    comparisons = []
    for old in matches:
        profile = profiles_by_id.get(old.get("user_id"))
        opportunity = opportunities_by_id.get(old.get("opportunity_id"))
        if profile is None:
            errors.append(f"match {old.get('id')} references missing profile")
            continue
        if opportunity is None:
            errors.append(f"match {old.get('id')} references missing opportunity")
            continue
        if profile.get("id") not in complete_ids:
            continue
        prepared = prepare_profile(profile)
        result = calculate_match(prepared, opportunity)
        new = result_fields(result)
        changes = changed_fields(old, new)
        applicant_types = get_eligible_applicant_types(opportunity)
        comparisons.append(
            {
                "match_id": old["id"],
                "user_id": old["user_id"],
                "opportunity_id": old["opportunity_id"],
                "title": opportunity.get("title"),
                "status": effective_status(opportunity),
                "applicant_types": applicant_types,
                "entity_only": applicant_types_are_entity_only(applicant_types),
                "old": {field: old.get(field) for field in DERIVED_FIELDS},
                "new": new,
                "changes": changes,
            }
        )

    existing_keys = set(pair_counts)
    missing_matches = []
    for profile in complete_profiles:
        prepared = prepare_profile(profile)
        for opportunity in opportunities:
            if not opportunity_is_actionable(opportunity):
                continue
            key = (profile["id"], opportunity["id"])
            if key in existing_keys:
                continue
            missing_matches.append(
                {
                    "user_id": profile["id"],
                    "opportunity_id": opportunity["id"],
                    "title": opportunity.get("title"),
                    "new": result_fields(calculate_match(prepared, opportunity)),
                }
            )

    entity_opportunities = []
    questionable = []
    for opportunity in opportunities:
        applicant_types = get_eligible_applicant_types(opportunity)
        entity_only = applicant_types_are_entity_only(applicant_types)
        if entity_only:
            entity_opportunities.append(
                {
                    "id": opportunity["id"],
                    "title": opportunity.get("title"),
                    "applicant_types": applicant_types,
                }
            )
        if not applicant_types:
            questionable.append(
                {
                    "id": opportunity["id"],
                    "title": opportunity.get("title"),
                    "issue": "applicant type could not be inferred",
                }
            )

    entity_eligible_errors = [
        row
        for row in comparisons
        if row["entity_only"] and row["new"]["eligible"]
    ]
    if entity_eligible_errors:
        errors.append(
            f"{len(entity_eligible_errors)} individual matches remained eligible for entity-only opportunities"
        )

    status_counts = Counter(effective_status(opportunity) for opportunity in opportunities)
    non_open_ready = [
        row
        for row in comparisons
        if row["status"] != "Open"
        and (row["new"]["eligible"] or row["new"]["match_score"] != 0 or row["new"]["readiness"] != 0)
    ]
    if non_open_ready:
        errors.append(f"{len(non_open_ready)} non-Open matches are still actionable")

    problem_examples = [
        {
            "opportunity_id": opportunity["id"],
            "title": opportunity.get("title"),
            "applicant_types": get_eligible_applicant_types(opportunity),
            "entity_only": applicant_types_are_entity_only(
                get_eligible_applicant_types(opportunity)
            ),
            "matches": [
                {
                    "user_id": row["user_id"],
                    "old_eligible": row["old"]["eligible"],
                    "new_eligible": row["new"]["eligible"],
                    "new_eligibility_gaps": row["new"]["eligibility_gaps"],
                }
                for row in comparisons
                if row["opportunity_id"] == opportunity["id"]
            ],
        }
        for opportunity in opportunities
        if is_problem_example(opportunity)
    ]

    return {
        "profiles_total": len(profiles),
        "profiles_complete": len(complete_profiles),
        "profiles_incomplete_skipped": len(skipped_profiles),
        "skipped_profiles": skipped_profiles,
        "opportunities_evaluated": len(opportunities),
        "existing_matches_total": len(matches),
        "existing_matches_evaluated": len(comparisons),
        "existing_matches_skipped_incomplete_profiles": sum(
            row.get("user_id") not in complete_ids for row in matches
        ),
        "eligible_true_to_false": sum(
            row["old"]["eligible"] is True and row["new"]["eligible"] is False
            for row in comparisons
        ),
        "eligible_false_to_true": sum(
            row["old"]["eligible"] is False and row["new"]["eligible"] is True
            for row in comparisons
        ),
        "score_changes": sum("match_score" in row["changes"] for row in comparisons),
        "major_score_changes": [
            row
            for row in comparisons
            if abs(row["new"]["match_score"] - (row["old"]["match_score"] or 0))
            >= MAJOR_SCORE_DELTA
        ],
        "readiness_changes": sum("readiness" in row["changes"] for row in comparisons),
        "changed_matches": [row for row in comparisons if row["changes"]],
        "entity_only_opportunities": entity_opportunities,
        "entity_only_count": len(entity_opportunities),
        "entity_eligible_errors": entity_eligible_errors,
        "status_counts": dict(status_counts),
        "non_open_actionable_errors": non_open_ready,
        "problem_examples": problem_examples,
        "missing_matches_to_create": missing_matches,
        "duplicate_match_keys": duplicate_match_keys,
        "questionable_results": questionable,
        "errors": errors,
    }


def main():
    from collector_client import collector_supabase

    matches = collector_supabase.table("matches").select("*").execute().data or []
    backup_path = backup_matches(matches)
    backup_summary = verify_match_backup(backup_path, matches)
    profiles = collector_supabase.table("profiles").select("*").execute().data or []
    opportunities = (
        collector_supabase.table("opportunities").select("*").execute().data or []
    )
    preview = build_preview(profiles, opportunities, matches)
    print("# HelAI Controlled Matching Re-evaluation")
    print("Mode: PREVIEW + VERIFIED LOCAL BACKUP (no Supabase writes)")
    print(f"backup file: {backup_path.resolve()}")
    print("backup verification: PASS")
    print(json.dumps({"backup": backup_summary, "preview": preview}, ensure_ascii=False, indent=2))
    print("Supabase match updates/inserts/deletes: 0/0/0")
    print("Notifications created: 0")
    print("Emails sent: 0")


if __name__ == "__main__":
    try:
        main()
    except PreviewSafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
