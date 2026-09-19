"""SELECT-only live applicant/schema/readiness audit. There is no apply mode."""

import copy
import json
import sys
from collections import Counter
from pathlib import Path

from helai_applicant_ai_audit import classify, load_rows
from helai_maintenance import duplicate_groups
from matcher import calculate_match
from matching_service import prepare_profile, profile_is_matchable
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    APPLICANT_MIXED,
    ENTITY_APPLICANT_TYPES,
    applicant_types_are_entity_only,
    get_eligible_applicant_types,
    normalize_status,
)
from openai import OpenAI
import os


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_REPORT = Path(__file__).with_name("helai_applicant_ai_audit_report.json")
OUTPUT = Path(__file__).with_name("helai_live_applicant_readiness_audit_report.json")
CUTOFF = "2026-09-18"
SCHEMA_FIELDS = ("applicant_type", "eligible_applicant_types", "record_kind", "active", "status")


def classify_type(types):
    values = set(types or [])
    if not values:
        return "unclassified"
    if APPLICANT_MIXED in values or (APPLICANT_INDIVIDUAL in values and values & ENTITY_APPLICANT_TYPES):
        return "mixed"
    if values == {APPLICANT_INDIVIDUAL}:
        return "individual"
    if applicant_types_are_entity_only(values):
        return "entity"
    return "mixed"


def pair_impact(opportunity, proposed_types, matches, profiles_by_id):
    changed = []
    relevant = [m for m in matches if m.get("opportunity_id") == opportunity.get("id")]
    proposed = copy.deepcopy(opportunity)
    proposed["eligible_applicant_types"] = proposed_types
    proposed["applicant_type"] = ", ".join(proposed_types)
    for match in relevant:
        profile = profiles_by_id.get(match.get("user_id"))
        if not profile or not profile_is_matchable(profile)[0]:
            continue
        prepared = prepare_profile(profile)
        before = calculate_match(prepared, opportunity)
        after = calculate_match(prepared, proposed)
        if bool(before.get("eligible")) != bool(after.get("eligible")):
            changed.append({
                "match_id": match.get("id"),
                "before": bool(before.get("eligible")),
                "after": bool(after.get("eligible")),
            })
    return {"existing_match_rows": len(relevant), "eligibility_changes": changed}


def main():
    base = json.loads(BASE_REPORT.read_text(encoding="utf-8"))
    opportunities, matches, profiles = load_rows()
    rows_by_id = {row.get("id"): row for row in opportunities}
    profiles_by_id = {row.get("id"): row for row in profiles}
    high_individuals = [
        item for item in base["audited"]
        if item["ai"]["classification"] == "individual" and item["ai"]["confidence"] == "high"
    ]
    plan = []
    for item in high_individuals:
        row = rows_by_id[item["opportunity_id"]]
        impact = pair_impact(row, [APPLICANT_INDIVIDUAL], matches, profiles_by_id)
        plan.append({
            "opportunity_id": row.get("id"),
            "title": row.get("title"),
            "current_applicant_type": row.get("applicant_type"),
            "current_eligible_applicant_types": row.get("eligible_applicant_types"),
            "proposed_applicant_type": APPLICANT_INDIVIDUAL,
            "evidence": item["ai"]["evidence"],
            "confidence": item["ai"]["confidence"],
            "deterministic_rules_infer_individual": get_eligible_applicant_types(row) == [APPLICANT_INDIVIDUAL],
            "matching_eligibility_would_change": bool(impact["eligibility_changes"]),
            "matching_impact": impact,
        })

    schema = {}
    all_keys = {key for row in opportunities for key in row}
    for field in SCHEMA_FIELDS:
        schema[field] = {
            "exists_in_select_results": field in all_keys,
            "non_null_rows": sum(row.get(field) is not None for row in opportunities) if field in all_keys else 0,
        }

    newer = [row for row in opportunities if str(row.get("created_at") or "")[:10] >= CUTOFF]
    if len(newer) != 20:
        raise RuntimeError(f"expected 20 newer opportunities, found {len(newer)}")
    match_counts = Counter(m.get("opportunity_id") for m in matches)
    ai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    newer_audit = []
    for row in newer:
        inferred = get_eligible_applicant_types(row)
        ai_result = None
        if not inferred:
            ai_result = classify(ai, row)
            if ai_result["classification"] == "non_opportunity":
                category = "NON_OPPORTUNITY_SUSPECT"
            elif ai_result["classification"] == "unknown":
                category = "AMBIGUOUS"
            else:
                category = "NEEDS_AI_AUDIT"
            evidence_quality = f"AI {ai_result['confidence']} confidence with verbatim validation"
        else:
            category = "RULE_CLASSIFIED_SAFE"
            evidence_quality = "deterministic stored-text rule classification"
        newer_audit.append({
            "id": row.get("id"),
            "title": row.get("title"),
            "source": row.get("source") or row.get("source_name"),
            "status": normalize_status(row.get("status")),
            "currently_inferred_applicant_types": inferred,
            "entity_only": applicant_types_are_entity_only(inferred),
            "match_rows": match_counts[row.get("id")],
            "has_match_rows": bool(match_counts[row.get("id")]),
            "applicant_type_evidence_quality": evidence_quality,
            "category": category,
            "ai": ai_result,
        })

    type_counts = Counter(classify_type(get_eligible_applicant_types(row)) for row in opportunities)
    status_counts = Counter(normalize_status(row.get("status")) for row in opportunities)
    duplicates = duplicate_groups(opportunities)
    duplicate_details = [
        {"key_type": key[0], "key_value": key[1], "ids": [row.get("id") for row in group], "titles": [row.get("title") for row in group]}
        for key, group in duplicates.items()
    ]
    match_key_counts = Counter((row.get("user_id"), row.get("opportunity_id")) for row in matches)
    duplicate_match_keys = [
        {"user_id": key[0], "opportunity_id": key[1], "count": count}
        for key, count in match_key_counts.items() if count > 1
    ]
    old_non_opportunities = [
        item for item in base["audited"] if item["ai"]["classification"] == "non_opportunity"
    ]
    new_non_opportunities = [item for item in newer_audit if item["category"] == "NON_OPPORTUNITY_SUSPECT"]
    complete_profiles = sum(profile_is_matchable(profile)[0] for profile in profiles)

    report = {
        "mode": "SELECT_ONLY_LIVE_AUDIT",
        "high_confidence_individual_normalization_plan": plan,
        "excluded_from_applicant_normalization": {
            "non_opportunity": [item for item in base["audited"] if item["ai"]["classification"] == "non_opportunity"],
            "medium_or_low_confidence": [item for item in base["audited"] if item["ai"]["confidence"] != "high"],
        },
        "schema_capability": schema,
        "newer_opportunities": newer_audit,
        "live_totals": {
            "opportunities": len(opportunities),
            "matches": len(matches),
            "profiles": len(profiles),
            "complete_profiles": complete_profiles,
            "individual_only_opportunities": type_counts["individual"],
            "entity_only_opportunities": type_counts["entity"],
            "mixed_opportunities": type_counts["mixed"],
            "unclassified_opportunities": type_counts["unclassified"],
            "informational_non_opportunity_suspects": len(old_non_opportunities) + len(new_non_opportunities),
            "duplicate_opportunity_groups": len(duplicates),
            "duplicate_match_keys": len(duplicate_match_keys),
            "Open": status_counts["Open"],
            "Upcoming": status_counts["Upcoming"],
            "Closed": status_counts["Closed"],
            "Unknown": status_counts["Unknown"],
        },
        "duplicate_opportunity_details": duplicate_details,
        "duplicate_match_key_details": duplicate_match_keys,
        "safety": {
            "supabase_opportunity_updates": 0, "supabase_opportunity_inserts": 0,
            "supabase_opportunity_deletes": 0, "supabase_match_updates": 0,
            "supabase_match_inserts": 0, "supabase_match_deletes": 0,
            "notifications": 0, "emails": 0, "matching_apply": "not run",
            "schema_changes": 0, "commit": "none", "push": "none",
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
