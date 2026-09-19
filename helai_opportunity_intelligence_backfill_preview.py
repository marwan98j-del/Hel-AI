"""Read-only reviewed opportunity-intelligence backfill preview.

This program has deliberately no apply mode.  Its database access is SELECT-only;
all proposed rows and matching effects are calculated on deep copies in memory.
"""

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

from helai_applicant_ai_audit import load_rows
from helai_maintenance import duplicate_groups
from matcher import calculate_match
from matching_service import prepare_profile, profile_is_matchable
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    ENTITY_APPLICANT_TYPES,
    get_eligible_applicant_types,
    infer_applicant_types_from_text,
    normalize_record_kind,
    normalize_status,
    primary_applicant_type,
)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXPECTED_OPPORTUNITIES = 122
EXPECTED_MATCHES = 224
AUDIT_PATH = Path(__file__).with_name("helai_applicant_ai_audit_report.json")
NEW_AUDIT_PATH = Path(__file__).with_name("helai_live_applicant_readiness_audit_report.json")
REPORT_PATH = Path(__file__).with_name("helai_opportunity_intelligence_backfill_preview_report.json")

INTELLIGENCE_COLUMNS = (
    "applicant_type",
    "eligible_applicant_types",
    "record_kind",
    "applicant_type_reviewed",
    "record_kind_reviewed",
)

NON_OPPORTUNITIES = {
    "afcc85f3-91fd-4b7c-8bf2-27876c80355b": {
        "title": "How to Write a Winning Mastercard Foundation Scholarship Essay",
        "record_kind": "informational",
    },
    "82a18662-c566-418c-9e40-6e40fcd086be": {
        "title": "30 Masters, Ph.D and Other Scholarship Opportunities Currently Open – September 16, 2026",
        "record_kind": "roundup",
    },
}

NEW_HIGH_CONFIDENCE_TITLES = (
    "OpenAI AI & Teen Development Research Grant Program 2026",
    "Cornell University AI for Sustainability (AI4S) Visiting Professorship Program 2027",
    "Interactivity Foundation Collaborative Discussion Emerging Fellowship 2027",
)
D_PRIZE_TITLE = "D-Prize Global Competition 2026 for Entrepreneurs"
SOURCE_FIELDS = ("title", "notes", "summary_en", "original_text")
MATCH_FIELDS = ("match_score", "eligible", "readiness", "reasons", "eligibility_gaps", "readiness_gaps")


class SafetyStop(RuntimeError):
    pass


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def duplicate_match_keys(matches):
    counts = Counter((row.get("user_id"), row.get("opportunity_id")) for row in matches)
    return [key for key, count in counts.items() if count > 1]


def validate_preflight(opportunities, matches):
    duplicate_opportunities = duplicate_groups(opportunities)
    duplicate_matches = duplicate_match_keys(matches)
    all_keys = {key for row in opportunities for key in row}
    missing_columns = [field for field in INTELLIGENCE_COLUMNS if field not in all_keys]
    state = {
        "opportunities": len(opportunities),
        "matches": len(matches),
        "duplicate_opportunity_groups": len(duplicate_opportunities),
        "duplicate_match_keys": len(duplicate_matches),
        "intelligence_columns": {field: field in all_keys for field in INTELLIGENCE_COLUMNS},
    }
    expected = (EXPECTED_OPPORTUNITIES, EXPECTED_MATCHES, 0, 0)
    actual = (
        state["opportunities"], state["matches"],
        state["duplicate_opportunity_groups"], state["duplicate_match_keys"],
    )
    if actual != expected or missing_columns:
        raise SafetyStop(f"live preflight differs; state={json.dumps(state, ensure_ascii=False)}")
    return state


def exact_title(row, expected):
    return row is not None and row.get("title") == expected


def stored_match_rows(opportunity_id, matches):
    return [copy.deepcopy(row) for row in matches if row.get("opportunity_id") == opportunity_id]


def source_text(row):
    return "\n".join(str(row.get(field) or "") for field in SOURCE_FIELDS)


def evidence_context(row, terms, radius=190):
    """Return exact stored-text windows around requested terms, without paraphrasing."""
    text = source_text(row)
    results = []
    for term in terms:
        match = re.search(re.escape(term), text, re.IGNORECASE)
        if not match:
            continue
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        excerpt = text[start:end].strip()
        if excerpt not in results:
            results.append(excerpt)
    return results


def audit_item_by_id(report, opportunity_id):
    candidates = list(report.get("audited", [])) + list(report.get("benchmarks", []))
    return next((item for item in candidates if item.get("opportunity_id") == opportunity_id), None)


def select_previous_individuals(report):
    selected = [
        item for item in report.get("audited", [])
        if item.get("ai", {}).get("classification") == "individual"
        and item.get("ai", {}).get("confidence") == "high"
    ]
    if len(selected) != 13:
        raise SafetyStop(f"expected 13 prior high-confidence individuals, found {len(selected)}")
    return selected


def select_new_high_confidence(report):
    by_title = {item.get("title"): item for item in report.get("newer_opportunities", [])}
    selected = []
    for title in NEW_HIGH_CONFIDENCE_TITLES:
        item = by_title.get(title)
        if not item:
            raise SafetyStop(f"new applicant-audit record missing: {title}")
        ai = item.get("ai") or {}
        if ai.get("classification") != "individual" or ai.get("confidence") != "high":
            raise SafetyStop(f"new applicant-audit result changed: {title}")
        selected.append(item)
    return selected


def result_fields(result):
    return {
        "match_score": int(round(result.get("score", 0))),
        "eligible": bool(result.get("eligible", False)),
        "readiness": int(round(result.get("readiness", 0))),
        "reasons": result.get("reasons") or [],
        "eligibility_gaps": result.get("eligibility_gaps") or [],
        "readiness_gaps": result.get("readiness_gaps") or [],
    }


def opportunity_match_effect(opportunity, patch, matches, profiles_by_id):
    before_row = copy.deepcopy(opportunity)
    after_row = copy.deepcopy(opportunity)
    after_row.update(copy.deepcopy(patch))
    effects = []
    relevant = [row for row in matches if row.get("opportunity_id") == opportunity.get("id")]
    for match in relevant:
        profile = profiles_by_id.get(match.get("user_id"))
        if not profile or not profile_is_matchable(profile)[0]:
            effects.append({"match_id": match.get("id"), "evaluated": False, "reason": "profile not matchable"})
            continue
        prepared = prepare_profile(profile)
        before = result_fields(calculate_match(prepared, before_row))
        after = result_fields(calculate_match(prepared, after_row))
        effects.append({
            "match_id": match.get("id"), "user_id": match.get("user_id"), "evaluated": True,
            "before": before, "after": after,
            "changed_fields": [field for field in MATCH_FIELDS if before[field] != after[field]],
        })
    return {"existing_match_rows": len(relevant), "effects": effects}


def deterministic_evidence(row, inferred):
    text = source_text(row)
    pieces = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if piece.strip()]
    evidence = []
    wanted = set(inferred)
    for piece in pieces:
        if set(infer_applicant_types_from_text(piece)) & wanted and piece not in evidence:
            evidence.append(piece)
    if evidence:
        return evidence
    # Some rules span adjacent clauses. Return exact nearby stored text, never invented text.
    return evidence_context(row, ("eligible", "applicant", "apply", "open to"))


def deterministic_candidates(opportunities, matches, profiles_by_id):
    results = []
    for row in opportunities:
        if row.get("applicant_type") is not None or row.get("eligible_applicant_types") is not None:
            continue
        inferred = get_eligible_applicant_types(row)
        if not inferred:
            continue
        values = set(inferred)
        if values == {APPLICANT_INDIVIDUAL}:
            classification = "deterministic individual"
        elif APPLICANT_INDIVIDUAL in values and values & ENTITY_APPLICANT_TYPES:
            classification = "deterministic mixed"
        else:
            classification = "deterministic entity"
        patch = {
            "applicant_type": primary_applicant_type(inferred),
            "eligible_applicant_types": inferred,
            "applicant_type_reviewed": False,
        }
        impact = opportunity_match_effect(row, patch, matches, profiles_by_id)
        false_to_true = [
            effect for effect in impact["effects"] if effect.get("evaluated")
            and not effect["before"]["eligible"] and effect["after"]["eligible"]
        ]
        results.append({
            "id": row.get("id"), "title": row.get("title"), "classification": classification,
            "inferred_types": inferred, "inference_evidence": deterministic_evidence(row, inferred),
            "current_status": normalize_status(row.get("status")),
            "current_record_kind": normalize_record_kind(row.get("record_kind")),
            "match_count": impact["existing_match_rows"], "hypothetical_matching_effect": impact,
            "false_to_true_warning": bool(false_to_true),
        })
    return results


def safe_patch_for_individual():
    return {
        "applicant_type": "individual",
        "eligible_applicant_types": ["individual"],
        "applicant_type_reviewed": True,
    }


def old_to_new(row, patch):
    return {field: {"old": copy.deepcopy(row.get(field)), "new": copy.deepcopy(value)} for field, value in patch.items()}


def simulate_safe_subset(safe_rows, opportunities_by_id, matches, profiles_by_id):
    effects = []
    for proposal in safe_rows:
        row = opportunities_by_id[proposal["id"]]
        impact = opportunity_match_effect(row, proposal["patch"], matches, profiles_by_id)
        for effect in impact["effects"]:
            effect.update({"opportunity_id": row.get("id"), "title": row.get("title")})
            effects.append(effect)
    evaluated = [item for item in effects if item.get("evaluated")]
    false_to_true = [item for item in evaluated if not item["before"]["eligible"] and item["after"]["eligible"]]
    true_to_false = [item for item in evaluated if item["before"]["eligible"] and not item["after"]["eligible"]]
    return {
        "existing_match_rows_evaluated": len(evaluated),
        "eligibility_true_to_false": len(true_to_false),
        "eligibility_false_to_true": len(false_to_true),
        "score_changes": sum(item["before"]["match_score"] != item["after"]["match_score"] for item in evaluated),
        "readiness_changes": sum(item["before"]["readiness"] != item["after"]["readiness"] for item in evaluated),
        "informational_records_becoming_non_actionable": sum(
            proposal["patch"].get("record_kind") == "informational" for proposal in safe_rows
        ),
        "roundup_records_becoming_non_actionable": sum(
            proposal["patch"].get("record_kind") == "roundup" for proposal in safe_rows
        ),
        "false_to_true_details": false_to_true,
        "all_effects": effects,
    }


def build_preview(opportunities, matches, profiles, old_audit, new_audit):
    preflight = validate_preflight(opportunities, matches)
    by_id = {row.get("id"): row for row in opportunities}
    profiles_by_id = {row.get("id"): row for row in profiles}

    non_opportunity_rows = []
    safe_rows = []
    for opportunity_id, expected in NON_OPPORTUNITIES.items():
        row = by_id.get(opportunity_id)
        if not exact_title(row, expected["title"]):
            raise SafetyStop(f"known non-opportunity ID/title mismatch: {opportunity_id}")
        audit = audit_item_by_id(old_audit, opportunity_id)
        if not audit:
            raise SafetyStop(f"previous audit evidence missing: {opportunity_id}")
        patch = {"record_kind": expected["record_kind"], "record_kind_reviewed": True}
        details = {
            "id": opportunity_id, "title": row.get("title"),
            "current_values": {field: copy.deepcopy(row.get(field)) for field in INTELLIGENCE_COLUMNS},
            "proposed_values": {**patch, "applicant_type": None, "eligible_applicant_types": None},
            "stored_text_evidence_from_previous_ai_audit": copy.deepcopy(audit["ai"]["evidence"]),
            "current_match_rows": stored_match_rows(opportunity_id, matches),
            "current_eligible_state": [m.get("eligible") for m in matches if m.get("opportunity_id") == opportunity_id],
            "status_not_used_as_substitute": True,
        }
        non_opportunity_rows.append(details)
        safe_rows.append({"id": opportunity_id, "title": row.get("title"), "patch": patch, "old_to_new": old_to_new(row, patch)})

    prior_rows = []
    for item in select_previous_individuals(old_audit):
        row = by_id.get(item["opportunity_id"])
        if not row or row.get("title") != item.get("title"):
            raise SafetyStop(f"prior individual ID/title mismatch: {item.get('opportunity_id')}")
        patch = safe_patch_for_individual()
        impact = opportunity_match_effect(row, patch, matches, profiles_by_id)
        changes_eligibility = any(
            e.get("evaluated") and e["before"]["eligible"] != e["after"]["eligible"] for e in impact["effects"]
        )
        prior_rows.append({
            "id": row.get("id"), "title": row.get("title"),
            "current_applicant_type": row.get("applicant_type"),
            "current_eligible_applicant_types": row.get("eligible_applicant_types"),
            "proposed_applicant_type": "individual", "proposed_eligible_applicant_types": ["individual"],
            "proposed_applicant_type_reviewed": True,
            "verbatim_evidence": copy.deepcopy(item["ai"]["evidence"]),
            "current_record_kind": normalize_record_kind(row.get("record_kind")),
            "current_record_kind_reviewed": row.get("record_kind_reviewed"),
            "existing_match_rows": stored_match_rows(row.get("id"), matches),
            "applicant_backfill_changes_current_eligibility_in_memory": changes_eligibility,
            "record_kind_proposed": False,
        })
        safe_rows.append({"id": row.get("id"), "title": row.get("title"), "patch": patch, "old_to_new": old_to_new(row, patch)})

    review_required = []
    for item in select_new_high_confidence(new_audit):
        row = by_id.get(item["id"])
        if not exact_title(row, item["title"]):
            raise SafetyStop(f"new high-confidence ID/title mismatch: {item.get('id')}")
        proposed = safe_patch_for_individual()
        review_required.append({
            "id": row.get("id"), "title": row.get("title"),
            "verbatim_eligibility_evidence": copy.deepcopy(item["ai"]["evidence"]),
            "ai_classification": item["ai"]["classification"], "confidence": item["ai"]["confidence"],
            "proposed_applicant_fields": proposed, "reviewed_automatically": False,
            "current_match_state": stored_match_rows(row.get("id"), matches),
            "hypothetical_matching_effect": opportunity_match_effect(row, proposed, matches, profiles_by_id),
        })

    d_item = next((item for item in new_audit.get("newer_opportunities", []) if item.get("title") == D_PRIZE_TITLE), None)
    d_row = by_id.get(d_item.get("id")) if d_item else None
    if not d_row:
        raise SafetyStop("D-Prize live/audit record missing")
    d_prize = {
        "id": d_row.get("id"), "title": d_row.get("title"),
        "stored_source_evidence": evidence_context(
            d_row, ("entrepreneurs", "new organizations", "for-profit ventures", "NGOs", "charities", "apply", "submit")
        ),
        "assessment": "D. insufficient evidence",
        "reason": "Stored wording describes entrepreneurs and organizations receiving support, but does not explicitly identify the legal applicant/submitting party.",
        "human_review_required": True, "reviewed_backfill_proposed": False,
    }

    deterministic = deterministic_candidates(opportunities, matches, profiles_by_id)
    deterministic_ids = {row["id"] for row in deterministic}
    excluded_ids = {row["id"] for row in safe_rows} | {row["id"] for row in review_required} | deterministic_ids | {d_row["id"]}
    ambiguous = [
        {"id": row.get("id"), "title": row.get("title"), "current_applicant_type": row.get("applicant_type"),
         "current_eligible_applicant_types": row.get("eligible_applicant_types")}
        for row in opportunities if row.get("id") not in excluded_ids
        and row.get("applicant_type") is None and row.get("eligible_applicant_types") is None
    ]

    safe_impact = simulate_safe_subset(safe_rows, by_id, matches, profiles_by_id)
    deterministic_warnings = [row for row in deterministic if row["false_to_true_warning"]]
    false_to_true_warnings = copy.deepcopy(safe_impact["false_to_true_details"])
    false_to_true_warnings.extend({
        "opportunity_id": row["id"], "title": row["title"], "source": "deterministic_unreviewed"
    } for row in deterministic_warnings)

    coverage = Counter(normalize_record_kind(row.get("record_kind")) for row in opportunities)
    open_unknown = sum(
        normalize_status(row.get("status")) == "Open" and normalize_record_kind(row.get("record_kind")) == "unknown"
        for row in opportunities
    )
    report = {
        "mode": "READ_ONLY_REVIEWED_INTELLIGENCE_BACKFILL_PREVIEW",
        "live_preflight": preflight,
        "known_non_opportunities": non_opportunity_rows,
        "previously_validated_individuals": prior_rows,
        "d_prize_review": d_prize,
        "record_kind_coverage": {
            kind: coverage[kind] for kind in ("application_opportunity", "informational", "roundup", "unknown")
        },
        "open_opportunities_with_record_kind_unknown": open_unknown,
        "strict_record_kind_matching_enabled": False,
        "hypothetical_matching_impact": safe_impact,
        "future_apply_tool_plan": {
            "create_timestamped_json_backup": True,
            "backup_complete_old_values_for_every_affected_opportunity": True,
            "verify_backup_before_updates": True,
            "update_only_explicitly_approved_fields": True,
            "never_alter_unrelated_fields": ["title", "source", "source_url", "original_text", "status", "etc."],
            "match_writes_during_backfill": 0, "notifications": 0, "emails": 0,
            "matching_rerun": "separate later step only",
        },
        "groups": {
            "SAFE_REVIEWED_BACKFILL": safe_rows,
            "REVIEW_REQUIRED_HIGH_CONFIDENCE": review_required,
            "DETERMINISTIC_UNREVIEWED": deterministic,
            "AMBIGUOUS_OR_UNKNOWN": ambiguous + [d_prize],
            "NON_OPPORTUNITY_REVIEWED": non_opportunity_rows,
            "FALSE_TO_TRUE_WARNINGS": false_to_true_warnings,
        },
        "safety_confirmation": {
            "supabase_opportunity_updates": 0, "supabase_opportunity_inserts": 0,
            "supabase_opportunity_deletes": 0, "supabase_match_writes": 0,
            "matching_apply": "not run", "collector_pipeline": "not run",
            "notifications": 0, "emails": 0, "commit": "none", "push": "none",
        },
    }
    return report


def final_summary(report):
    live = report["live_preflight"]
    groups = report["groups"]
    impact = report["hypothetical_matching_impact"]
    lines = [
        f"live opportunities: {live['opportunities']}",
        f"live matches: {live['matches']}",
        f"duplicate opportunity groups: {live['duplicate_opportunity_groups']}",
        f"duplicate match keys: {live['duplicate_match_keys']}", "",
        f"SAFE_REVIEWED_BACKFILL count: {len(groups['SAFE_REVIEWED_BACKFILL'])}",
        f"reviewed non-opportunity count: {len(groups['NON_OPPORTUNITY_REVIEWED'])}",
        f"reviewed individual count: {len(report['previously_validated_individuals'])}", "",
        f"REVIEW_REQUIRED_HIGH_CONFIDENCE count: {len(groups['REVIEW_REQUIRED_HIGH_CONFIDENCE'])}",
        f"DETERMINISTIC_UNREVIEWED count: {len(groups['DETERMINISTIC_UNREVIEWED'])}",
        f"AMBIGUOUS_OR_UNKNOWN count: {len(groups['AMBIGUOUS_OR_UNKNOWN'])}", "",
        f"Open opportunities with record_kind unknown: {report['open_opportunities_with_record_kind_unknown']}", "",
        f"hypothetical True→False: {impact['eligibility_true_to_false']}",
        f"hypothetical False→True: {impact['eligibility_false_to_true']}",
        f"score changes: {impact['score_changes']}",
        f"readiness changes: {impact['readiness_changes']}", "",
        "safe to create exact backfill APPLY tool: yes", "",
        "Supabase opportunity updates = 0", "Supabase opportunity inserts = 0",
        "Supabase opportunity deletes = 0", "Supabase match writes = 0",
        "matching APPLY = not run", "collector/pipeline = not run", "notifications = 0",
        "emails = 0", "commit = none", "push = none",
    ]
    return "\n".join(lines)


def main():
    opportunities, matches, profiles = load_rows()
    report = build_preview(opportunities, matches, profiles, load_json(AUDIT_PATH), load_json(NEW_AUDIT_PATH))
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nFINAL REPORT\n")
    print(final_summary(report))


if __name__ == "__main__":
    try:
        main()
    except SafetyStop as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
