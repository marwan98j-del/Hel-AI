"""Read-only AI audit of applicant types for currently unclassified opportunities.

There is deliberately no apply mode. This module only SELECTs rows from Supabase,
calls OpenAI, and calculates hypothetical match effects in memory.
"""

import argparse
import copy
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

from matcher import calculate_match
from matching_service import prepare_profile, profile_is_matchable
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    ENTITY_APPLICANT_TYPES,
    get_eligible_applicant_types,
)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MODEL = "gpt-5.6-luna"
EXPECTED_OPPORTUNITY_COUNT = 102
EXPECTED_UNCLASSIFIED_COUNT = 45
EXPECTED_MATCH_COUNT = 196
# The user-verified snapshot predates rows collected on the task date. The live
# preflight may contain later rows, which must not silently expand this audit.
VERIFIED_SNAPSHOT_BEFORE = "2026-09-18"
SOURCE_FIELDS = ("title", "summary_en", "notes", "original_text", "organization")
EVIDENCE_FIELDS = ("title", "summary_en", "notes", "original_text")
REPORT_PATH = Path(__file__).with_name("helai_applicant_ai_audit_report.json")

CLASSIFICATIONS = ("individual", "entity", "mixed", "unknown", "non_opportunity")
APPLICANT_TYPES = (
    "individual",
    "organization/institution",
    "company/business",
    "government entity",
    "university/research institution",
    "NGO/nonprofit",
)
RECORD_KINDS = ("application_opportunity", "informational", "roundup", "unknown")
CONFIDENCES = ("high", "medium", "low")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "record_kind": {"type": "string", "enum": list(RECORD_KINDS)},
        "applicant_types": {
            "type": "array",
            "items": {"type": "string", "enum": list(APPLICANT_TYPES)},
        },
        "classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": [
        "record_kind", "applicant_types", "classification", "confidence",
        "evidence", "reason",
    ],
}

INSTRUCTIONS = """You are conducting a conservative applicant-type evidence audit.
Use only the supplied stored fields. Never use outside knowledge.
Return the required JSON and nothing else.

Rules:
1. Evidence entries must be exact short verbatim phrases from the supplied stored text.
2. Never infer applicant type from the sponsor, publisher, host, or organization name.
3. Distinguish sponsor/host from who may submit and who is legally eligible to apply.
4. Insufficient evidence means classification=unknown and confidence=low. Do not guess.
5. Articles, guides, roundups, advice, and news are not direct applications; identify their
   record_kind and use classification=non_opportunity.
6. An affiliation requirement does not by itself make an institution the applicant. Read
   the complete surrounding eligibility context.
7. Entity requires evidence that an organization, company, government, university/research
   institution, or NGO/nonprofit is the legal applicant or submitting party.
8. Individual requires evidence that a person, student, researcher, professional, or similar
   person is directly eligible to apply.
9. Mixed requires explicit evidence that both individuals and entities can apply.
10. applicant_types must identify the explicitly eligible types. Use [] for unknown and for
    non-opportunities when the page does not itself accept applications.
11. For entity do not include individual. For individual use only individual. For mixed include
    individual plus at least one entity type.
"""

BENCHMARKS = (
    ("Innovation & Growth Pitch Competition 2026", "entity"),
    ("Medicines Manufacturing Data Institute: Phase 1", "entity"),
    ("Engineering Biology Access to Infrastructure Pilot", "entity"),
    ("Single Source: Scalable and Systematic Neurobiology of Psychiatric and Neurodevelopmental Disorder Risk Genes: Data Resource and Administrative Coordination Center (U24 Clinical Trial Not Allowed)", "entity"),
    ("Core Research in Biological Sciences (BIO Core)", "entity"),
    ("NSF Graduate Research Fellowship Program", "individual"),
    ("NSF IAIFI Fellowship", "individual"),
    ("AWARD Women in Agriculture Leadership Program Fellowship", "individual"),
    ("UBA National Essay Competition", "individual"),
    ("Global Entrepreneurship Festival EIP", "mixed"),
    ("iProBono Accelerate", "mixed"),
    ("How to Write a Winning Mastercard Foundation Scholarship Essay", "non_opportunity"),
    ("30 Masters, Ph.D and Other Scholarship Opportunities Currently Open", "non_opportunity"),
)


class SafetyStop(RuntimeError):
    pass


def compact_text(value):
    return " ".join(str(value or "").split())


def source_payload(row):
    return {field: row.get(field) for field in SOURCE_FIELDS if row.get(field)}


def source_haystack(row):
    return "\n".join(str(row.get(field) or "") for field in SOURCE_FIELDS)


def evidence_is_verbatim(phrase, row):
    phrase = str(phrase or "").strip()
    if not phrase or len(phrase) > 400:
        return False
    # Organization is context only: it can never independently satisfy evidence.
    evidence_text = "\n".join(str(row.get(field) or "") for field in EVIDENCE_FIELDS)
    return phrase.casefold() in evidence_text.casefold()


def validate_result(result, row):
    problems = []
    classification = result["classification"]
    types = set(result["applicant_types"])
    entity_types = types & ENTITY_APPLICANT_TYPES
    if any(not evidence_is_verbatim(item, row) for item in result["evidence"]):
        problems.append("evidence is not a verbatim substring of stored content")
    if classification == "unknown" and result["confidence"] != "low":
        problems.append("unknown must have low confidence")
    if classification == "individual" and types != {APPLICANT_INDIVIDUAL}:
        problems.append("individual has inconsistent applicant_types")
    if classification == "entity" and (APPLICANT_INDIVIDUAL in types or not entity_types):
        problems.append("entity has inconsistent applicant_types")
    if classification == "mixed" and not (APPLICANT_INDIVIDUAL in types and entity_types):
        problems.append("mixed lacks explicit individual and entity types")
    if classification in {"individual", "entity", "mixed"} and not result["evidence"]:
        problems.append("opportunity classification lacks evidence")
    if classification == "non_opportunity" and result["record_kind"] == "application_opportunity":
        problems.append("non-opportunity has application record_kind")
    if classification != "non_opportunity" and result["record_kind"] in {"informational", "roundup"}:
        problems.append("informational/roundup record is not non_opportunity")
    return problems


def classify(client, row):
    payload = source_payload(row)
    response = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "applicant_type_audit",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    )
    result = json.loads(response.output_text)
    problems = validate_result(result, row)
    if problems:
        # Invalid evidence is never trusted. Preserve the model output for diagnosis but
        # force the decision to the safe state used by summaries and impact calculations.
        result["validation_errors"] = problems
        result["classification"] = "unknown"
        result["confidence"] = "low"
        result["applicant_types"] = []
    return result


def title_key(value):
    return compact_text(value).casefold().replace("–", "-").replace("—", "-")


def find_benchmark(rows, requested_title):
    needle = title_key(requested_title)
    exact = [row for row in rows if title_key(row.get("title")) == needle]
    if len(exact) == 1:
        return exact[0]
    partial = [
        row for row in rows
        if needle in title_key(row.get("title")) or title_key(row.get("title")) in needle
    ]
    if len(partial) == 1:
        return partial[0]
    # The user supplied descriptive shorthand for these two records.
    words = [word for word in needle.replace("-", " ").split() if len(word) >= 3]
    scored = sorted(
        ((sum(word in title_key(row.get("title")) for word in words), row) for row in rows),
        key=lambda item: item[0], reverse=True,
    )
    if scored and scored[0][0] >= 2 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    raise SafetyStop(f"benchmark not found uniquely: {requested_title}")


def benchmark_is_sensible(results):
    correct = sum(item["agrees"] for item in results)
    non_opportunities_ok = all(
        item["agrees"] for item in results if item["expected"] == "non_opportunity"
    )
    group_coverage = all(
        any(item["agrees"] for item in results if item["expected"] == group)
        for group in ("entity", "individual", "mixed")
    )
    return correct >= 10 and non_opportunities_ok and group_coverage


def hypothetical_impact(matches, profiles, opportunities_by_id, audits_by_id):
    profiles_by_id = {row.get("id"): row for row in profiles}
    changes = []
    for match in matches:
        audit = audits_by_id.get(match.get("opportunity_id"))
        if not audit or audit["confidence"] != "high" or audit["classification"] == "unknown":
            continue
        opportunity = opportunities_by_id.get(match.get("opportunity_id"))
        profile = profiles_by_id.get(match.get("user_id"))
        if not opportunity or not profile or not profile_is_matchable(profile)[0]:
            continue
        prepared = prepare_profile(profile)
        before = bool(match.get("eligible"))
        simulated = copy.deepcopy(opportunity)
        classification = audit["classification"]
        if classification == "non_opportunity":
            after = False
        else:
            simulated["eligible_applicant_types"] = list(audit["applicant_types"])
            simulated["applicant_type"] = ""
            after = bool(calculate_match(prepared, simulated).get("eligible"))
        if before != after:
            changes.append({
                "match_id": match.get("id"),
                "opportunity_id": match.get("opportunity_id"),
                "title": opportunity.get("title"),
                "before": before,
                "after": after,
                "classification": classification,
                "evidence": audit["evidence"],
            })
    return changes


def load_rows():
    load_dotenv(override=True)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise SafetyStop("Supabase read credentials are not configured")
    db = create_client(url, key)
    # SELECT is the only database operation in this program.
    opportunities = db.table("opportunities").select("*").execute().data or []
    matches = db.table("matches").select("*").execute().data or []
    profiles = db.table("profiles").select("*").execute().data or []
    return opportunities, matches, profiles


def select_verified_cohort(opportunities):
    if len(opportunities) == EXPECTED_OPPORTUNITY_COUNT:
        return opportunities, []
    cohort = [
        row for row in opportunities
        if str(row.get("created_at") or "")[:10] < VERIFIED_SNAPSHOT_BEFORE
    ]
    excluded = [row for row in opportunities if row not in cohort]
    if len(cohort) != EXPECTED_OPPORTUNITY_COUNT:
        raise SafetyStop(
            f"cannot reconstruct verified {EXPECTED_OPPORTUNITY_COUNT}-row snapshot: "
            f"live={len(opportunities)}, before {VERIFIED_SNAPSHOT_BEFORE}={len(cohort)}"
        )
    return cohort, excluded


def print_section(label, items, individual=False):
    print(f"\n## {label}")
    if not items:
        print("- None")
        return
    for item in items:
        result = item["ai"]
        evidence = "; ".join(f'\"{phrase}\"' for phrase in result["evidence"]) or "none"
        if individual:
            print(f"- {item['title']} | {result['confidence']} | {evidence}")
        else:
            print(
                f"- {item['title']} | {result['confidence']} | "
                f"types={result['applicant_types']} | evidence={evidence} | {result['reason']}"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    live_opportunities, live_matches, profiles = load_rows()
    opportunities, excluded_opportunities = select_verified_cohort(live_opportunities)
    cohort_ids = {row.get("id") for row in opportunities}
    matches = [row for row in live_matches if row.get("opportunity_id") in cohort_ids]
    if len(matches) != EXPECTED_MATCH_COUNT:
        raise SafetyStop(
            f"expected {EXPECTED_MATCH_COUNT} snapshot matches, found {len(matches)} "
            f"(live total={len(live_matches)})"
        )
    unclassified = [row for row in opportunities if not get_eligible_applicant_types(row)]
    if len(unclassified) != EXPECTED_UNCLASSIFIED_COUNT:
        raise SafetyStop(
            f"expected {EXPECTED_UNCLASSIFIED_COUNT} unclassified opportunities, "
            f"found {len(unclassified)}"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SafetyStop("OpenAI is not configured")
    ai = OpenAI(api_key=api_key)

    benchmark_results = []
    for requested_title, expected in BENCHMARKS:
        # Benchmarks are an independent validation set and may include a newer
        # known record; they never expand the verified 45-row audit cohort.
        row = find_benchmark(live_opportunities, requested_title)
        result = classify(ai, row)
        benchmark_results.append({
            "requested_title": requested_title,
            "title": row.get("title"),
            "opportunity_id": row.get("id"),
            "expected": expected,
            "actual": result["classification"],
            "agrees": result["classification"] == expected,
            "ai": result,
        })

    sensible = benchmark_is_sensible(benchmark_results)
    if not sensible:
        audited = []
    else:
        audited = [
            {"opportunity_id": row.get("id"), "title": row.get("title"), "ai": classify(ai, row)}
            for row in unclassified
        ]

    counts = Counter(item["ai"]["classification"] for item in audited)
    confidence_counts = Counter(item["ai"]["confidence"] for item in audited)
    audits_by_id = {item["opportunity_id"]: item["ai"] for item in audited}
    changes = hypothetical_impact(
        matches,
        profiles,
        {row.get("id"): row for row in opportunities},
        audits_by_id,
    ) if sensible else []
    disagreements = [item for item in benchmark_results if not item["agrees"]]
    recommendation = (
        "A. enough high-confidence information exists to prepare a safe applicant-type normalization plan"
        if sensible and confidence_counts["high"] > 0
        else "B. more source data is required before normalization"
    )
    report = {
        "mode": "READ_ONLY_AI_AUDIT",
        "model": MODEL,
        "scope": {
            "verified_opportunities": len(opportunities),
            "live_opportunities": len(live_opportunities),
            "excluded_newer_rows": len(excluded_opportunities),
            "snapshot_before": VERIFIED_SNAPSHOT_BEFORE if excluded_opportunities else None,
            "existing_matches": len(matches),
            "live_matches": len(live_matches),
            "excluded_newer_match_rows": len(live_matches) - len(matches),
        },
        "benchmark_sensible": sensible,
        "benchmarks": benchmark_results,
        "summary": {
            "total_audited": len(audited),
            "individual": counts["individual"],
            "entity": counts["entity"],
            "mixed": counts["mixed"],
            "informational_non_opportunity": counts["non_opportunity"],
            "unknown": counts["unknown"],
            "high_confidence": confidence_counts["high"],
            "medium_confidence": confidence_counts["medium"],
            "low_confidence": confidence_counts["low"],
        },
        "audited": audited,
        "hypothetical_matching_impact": {
            "changed_rows": len(changes),
            "true_to_false": sum(item["before"] and not item["after"] for item in changes),
            "false_to_true": sum(not item["before"] and item["after"] for item in changes),
            "false_to_true_details": [item for item in changes if not item["before"] and item["after"]],
        },
        "recommendation": recommendation,
        "safety_confirmation": {
            "supabase_opportunity_writes": 0,
            "supabase_match_updates": 0,
            "supabase_match_inserts": 0,
            "supabase_match_deletes": 0,
            "notifications": 0,
            "emails": 0,
            "matching_apply": "not run",
            "normalization_candidates_modified": 0,
            "commit": "none",
            "push": "none",
        },
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("# HelAI Applicant-Type AI Audit")
    print("Mode: READ ONLY; benchmark gate:", "PASS" if sensible else "STOP")
    print(json.dumps(report["summary"], ensure_ascii=False))
    for classification, label in (
        ("entity", "Entity classifications"),
        ("mixed", "Mixed classifications"),
        ("non_opportunity", "Non-opportunity classifications"),
        ("unknown", "Unknown classifications"),
        ("individual", "Individual classifications"),
    ):
        print_section(label, [item for item in audited if item["ai"]["classification"] == classification], classification == "individual")
    print_section("AI-vs-rule benchmark disagreements", disagreements)
    print("\n## Hypothetical matching impact (high confidence only)")
    print(json.dumps(report["hypothetical_matching_impact"], ensure_ascii=False, indent=2))
    print("\n## Recommendation")
    print(recommendation)
    print("\n## Safety confirmation")
    print(json.dumps(report["safety_confirmation"], ensure_ascii=False, indent=2))
    return 0 if sensible else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyStop as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
