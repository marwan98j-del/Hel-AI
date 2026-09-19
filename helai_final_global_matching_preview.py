"""SELECT-only final global matching preview. There is no apply mode."""

import json
import sys
from collections import Counter
from pathlib import Path

from helai_applicant_ai_audit import load_rows
from helai_maintenance import duplicate_groups
from helai_matching_preview import build_preview
from matching_service import opportunity_is_actionable
from opportunity_rules import (
    effective_status,
    get_eligible_applicant_types,
    normalize_status,
    record_kind_is_non_actionable,
)
from supabase_client import supabase


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUTPUT = Path(__file__).with_name("helai_final_global_matching_preview_report.json")
EXPECTED_OPPORTUNITIES = 122
EXPECTED_MATCHES = 224


class SafetyStop(RuntimeError):
    pass


def match_key_duplicates(matches):
    counts = Counter((row.get("user_id"), row.get("opportunity_id")) for row in matches)
    return sum(count > 1 for count in counts.values())


def build_global_report(profiles, opportunities, matches, notifications):
    duplicate_opportunities = len(duplicate_groups(opportunities))
    duplicate_matches = match_key_duplicates(matches)
    if (len(opportunities), len(matches), duplicate_opportunities, duplicate_matches) != (122, 224, 0, 0):
        raise SafetyStop("live count or duplicate preflight drift")

    preview = build_preview(profiles, opportunities, matches)
    opportunities_by_id = {row.get("id"): row for row in opportunities}
    comparisons = {
        row["match_id"]: row for row in preview["changed_matches"]
    }
    # build_preview exposes changed rows only; reconstruct unchanged count from
    # the number of existing rows actually evaluated.
    changed_count = len(preview["changed_matches"])
    unchanged_count = preview["existing_matches_evaluated"] - changed_count

    expired_opportunities = {
        row["id"]: row for row in opportunities
        if normalize_status(row.get("status")) == "Open" and effective_status(row) == "Closed"
    }
    expired_matches = []
    for old in matches:
        opportunity = expired_opportunities.get(old.get("opportunity_id"))
        if not opportunity:
            continue
        change = comparisons.get(old.get("id"))
        new = change["new"] if change else {
            "eligible": old.get("eligible"), "match_score": old.get("match_score"),
            "readiness": old.get("readiness"),
        }
        expired_matches.append({
            "match_id": old.get("id"), "user_id": old.get("user_id"),
            "opportunity_id": opportunity.get("id"), "title": opportunity.get("title"),
            "deadline": opportunity.get("deadline"),
            "stored_status": normalize_status(opportunity.get("status")),
            "effective_status": effective_status(opportunity),
            "before_eligible": bool(old.get("eligible")), "after_eligible": bool(new.get("eligible")),
            "before_score": old.get("match_score"), "after_score": new.get("match_score"),
            "before_readiness": old.get("readiness"), "after_readiness": new.get("readiness"),
        })

    non_opportunity_ids = {
        "afcc85f3-91fd-4b7c-8bf2-27876c80355b",
        "82a18662-c566-418c-9e40-6e40fcd086be",
    }
    non_opportunity_matches = []
    for old in matches:
        if old.get("opportunity_id") not in non_opportunity_ids:
            continue
        opportunity = opportunities_by_id[old["opportunity_id"]]
        change = comparisons.get(old.get("id"))
        new = change["new"] if change else {
            "eligible": old.get("eligible"), "match_score": old.get("match_score"),
            "readiness": old.get("readiness"),
        }
        non_opportunity_matches.append({
            "match_id": old.get("id"), "user_id": old.get("user_id"),
            "opportunity_id": opportunity["id"], "title": opportunity.get("title"),
            "record_kind": opportunity.get("record_kind"),
            "before": {"eligible": old.get("eligible"), "score": old.get("match_score"), "readiness": old.get("readiness")},
            "after": {"eligible": new.get("eligible"), "score": new.get("match_score"), "readiness": new.get("readiness")},
        })

    false_to_true = []
    for row in preview["changed_matches"]:
        if row["old"]["eligible"] is not False or row["new"]["eligible"] is not True:
            continue
        opportunity = opportunities_by_id[row["opportunity_id"]]
        removed_gaps = [gap for gap in row["old"]["eligibility_gaps"] if gap not in row["new"]["eligibility_gaps"]]
        false_to_true.append({
            "match_id": row["match_id"], "user_id": row["user_id"],
            "opportunity_id": row["opportunity_id"], "title": row["title"],
            "applicant_type": opportunity.get("applicant_type"),
            "eligible_applicant_types": opportunity.get("eligible_applicant_types"),
            "record_kind": opportunity.get("record_kind"), "deadline": opportunity.get("deadline"),
            "stored_status": normalize_status(opportunity.get("status")),
            "effective_status": effective_status(opportunity),
            "previous": {"eligible": row["old"]["eligible"], "score": row["old"]["match_score"], "readiness": row["old"]["readiness"]},
            "proposed": {"eligible": row["new"]["eligible"], "score": row["new"]["match_score"], "readiness": row["new"]["readiness"]},
            "exact_reason": {"removed_eligibility_gaps": removed_gaps, "new_reasons": row["new"]["reasons"]},
        })

    new_matches = []
    for row in preview["missing_matches_to_create"]:
        opportunity = opportunities_by_id[row["opportunity_id"]]
        new_matches.append({
            "user_id": row["user_id"], "opportunity_id": row["opportunity_id"],
            "title": row["title"], "effective_status": effective_status(opportunity),
            "applicant_types": get_eligible_applicant_types(opportunity),
            "eligible": row["new"]["eligible"], "score": row["new"]["match_score"],
            "readiness": row["new"]["readiness"], "reasons": row["new"]["reasons"],
        })

    obsolete = [
        old for old in matches
        if not opportunity_is_actionable(opportunities_by_id[old["opportunity_id"]])
        or record_kind_is_non_actionable(opportunities_by_id[old["opportunity_id"]].get("record_kind"))
    ]
    reviewed_individual_ids = {
        row["id"] for row in opportunities
        if row.get("applicant_type_reviewed") is True
        and row.get("applicant_type") == "individual"
        and row.get("eligible_applicant_types") == ["individual"]
    }
    informational_ids = {
        row["id"] for row in opportunities if record_kind_is_non_actionable(row.get("record_kind"))
    }
    actionable_pairs = preview["existing_matches_total"] - len(obsolete)
    # The current APPLY implementation upserts actionable pairs and does not
    # delete historical/non-actionable rows, so total stored rows are existing + missing.
    report = {
        "mode": "READ_ONLY_FINAL_GLOBAL_MATCHING_PREVIEW",
        "live": {"opportunities": len(opportunities), "matches": len(matches),
                 "duplicate_opportunity_groups": duplicate_opportunities,
                 "duplicate_match_keys": duplicate_matches},
        "effective_open": sum(effective_status(row) == "Open" for row in opportunities),
        "stored_open_effectively_closed": len(expired_opportunities),
        "existing_matches": len(matches),
        "proposed_total_matches_after_upsert": len(matches) + len(new_matches),
        "actionable_relationships_recomputed": actionable_pairs + len(new_matches),
        "unchanged_matches": unchanged_count,
        "eligibility_true_to_false": preview["eligible_true_to_false"],
        "eligibility_false_to_true": preview["eligible_false_to_true"],
        "score_changes": preview["score_changes"], "readiness_changes": preview["readiness_changes"],
        "new_matches_proposed": new_matches,
        "obsolete_non_actionable_matches": len(obsolete),
        "expired_opportunity_matches": expired_matches,
        "non_opportunity_matches": non_opportunity_matches,
        "explicit_informational_roundup_match_count": sum(row.get("opportunity_id") in informational_ids for row in matches),
        "applicant_reviewed_individual_match_count": sum(row.get("opportunity_id") in reviewed_individual_ids for row in matches),
        "false_to_true_changes": false_to_true,
        "unexpected_false_to_true_changes": len(false_to_true),
        "related_expired_notifications": sum(row.get("opportunity_id") in expired_opportunities for row in notifications),
        "errors": preview["errors"],
    }
    return report


def main():
    opportunities, matches, profiles = load_rows()
    notifications = supabase.table("notifications").select("*").execute().data or []
    report = build_global_report(profiles, opportunities, matches, notifications)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except SafetyStop as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
