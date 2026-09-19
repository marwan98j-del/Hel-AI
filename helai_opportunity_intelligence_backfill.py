"""Fail-closed exact intelligence backfill for the 15 reviewed opportunities.

Default mode is a SELECT-only dry run.  ``--backup-only`` also remains
SELECT-only and writes a verified local JSON backup.  ``--apply`` is the only
mode capable of updating Supabase; it never writes matches or notifications.
"""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from helai_applicant_ai_audit import load_rows
from helai_maintenance import duplicate_groups
from helai_opportunity_intelligence_backfill_preview import simulate_safe_subset
from supabase_client import supabase


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXPECTED_OPPORTUNITIES = 122
EXPECTED_MATCHES = 224
EXPECTED_APPROVED = 15
EXPECTED_NON_OPPORTUNITIES = 2
EXPECTED_INDIVIDUALS = 13
EXPECTED_IMPACT = {
    "eligibility_true_to_false": 2,
    "eligibility_false_to_true": 0,
    "score_changes": 2,
    "readiness_changes": 2,
}
PREVIEW_PATH = Path(__file__).with_name("helai_opportunity_intelligence_backfill_preview_report.json")
BACKUP_DIRECTORY = Path(__file__).with_name("helai_opportunity_intelligence_backfill_backups")

NON_OPPORTUNITY_IDS = {
    "afcc85f3-91fd-4b7c-8bf2-27876c80355b",
    "82a18662-c566-418c-9e40-6e40fcd086be",
}
D_PRIZE_ID = "8138445d-ec17-4ca6-aef4-7c3508781cd0"
OPEN_NOTEBOOK_ID = "b79833ba-f682-40cf-9cd4-33dbae385e9a"
INTELLIGENCE_FIELDS = (
    "applicant_type", "eligible_applicant_types", "applicant_type_reviewed",
    "record_kind", "record_kind_reviewed",
)
UNCHANGED_FIELDS = (
    "title", "organization", "source", "source_name", "source_url", "external_id",
    "fingerprint", "original_text", "summary_en", "summary_ku", "status", "active",
    "deadline", "open_date", "created_at", "discovered_at", "updated_at",
)

# Immutable identity/content snapshot approved with the reviewed preview.  The
# digest covers every field explicitly required to remain unchanged.
APPROVED_IDENTITY_DIGESTS = {
    "afcc85f3-91fd-4b7c-8bf2-27876c80355b": "64fa21407aa17163c69899178760ca6909890a006a4b12f3f8bc47d1327c1e8e",
    "82a18662-c566-418c-9e40-6e40fcd086be": "bdebd7b2efe846b4ed13944d87f679d5c5378570641c4191fb93ca1234836907",
    "49a62059-2428-4f53-9f8a-1e4b98e3b2c1": "48b8693c2fae5aa80abc6d2acee2d6421b8b28f877c6695cc54ffaea026f1b61",
    "85389c1a-1592-46c6-9137-fffc05d6393c": "e9d8dd98c9906f0060333fb33c2aee7ffdd44ed3556f79077fa44fb315039df7",
    "6cbb02df-e653-406c-9603-4694e890fd22": "58edfa87791491ecb0d59424c6307966090faf8ade1297f4b1e1e107ddc0a2f4",
    "7f472825-3767-4434-aec3-698475f4983a": "ca2ba8375369d58a3592f8fd714b769f41547e76fecd0258be7b267b5d12588e",
    "454698a9-be87-48f0-bbf9-17acd7b305a5": "76d94c3fa9d9a6dd1d1bbe73d3cfa8e9d1eb244225166ffeea1ba6113dde3c83",
    "d336206b-3984-4b7c-a29d-a660f3c36016": "478b4c1cca1762b0040fb723633abfaa9da66923d1ab871827231e44d628a3e1",
    "93f8b7ed-dce3-4f0b-a0a8-497785494faa": "6862b2261207d8052d56144e50d7087851850e4fb8efa622136d9d3f42de9d05",
    "80396480-626a-4625-b386-850cf7125dc9": "d19dc149da6935886cfd1c48b4fafff1bbfae0062d884ac9af0e177e85efb745",
    "82b6d9c0-3184-46f0-bc50-1a13a7355b97": "cc8da1c254ffd5d7e764add0ac9bf44fca2b7b39b5d8c73cafeee508795036d1",
    "bd922ef3-bbec-4804-b387-6d74e9991cf9": "55f14955726431c875640a418d26cb622b2fd27731a1023f0272ef3f64170d86",
    "e9ef1a0b-00c7-4502-babf-f25cb586bdd4": "8c10440ce121380040422057d61b48e8b3400b548148fe5b1699471b0a74faf7",
    "15346abe-d279-4bb4-a90f-3e6f4f9532b4": "553893c66ff33fabcf3984ea1a16efeae12ad50d24b570383b5038bfd32a0307",
    "4fda1241-7012-48b7-84d4-939383ba6726": "df9e40120fe6e524a6bf898bb691da4c4cf935d9a31855ba8aa5ea50c4be3fe6",
}


class SafetyError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def identity_digest(row):
    payload = {field: row.get(field) for field in UNCHANGED_FIELDS}
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def load_approved_manifest(path=PREVIEW_PATH):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    groups = report.get("groups") or {}
    approved = copy.deepcopy(groups.get("SAFE_REVIEWED_BACKFILL") or [])
    if len(approved) != EXPECTED_APPROVED or len({row.get("id") for row in approved}) != EXPECTED_APPROVED:
        raise SafetyError(f"approved set must contain exactly {EXPECTED_APPROVED} unique rows")
    approved_ids = {row["id"] for row in approved}
    if set(APPROVED_IDENTITY_DIGESTS) != approved_ids:
        raise SafetyError("approved IDs differ from immutable reviewed identity manifest")
    # Selection is exclusively from SAFE_REVIEWED_BACKFILL.  The preview's
    # broad deterministic scan also reports the reviewed roundup because its
    # stored text triggers an applicant rule; that does not make the
    # deterministic group an approval source.  No row is ever unioned in from
    # any review-required/unreviewed group.
    if D_PRIZE_ID in approved_ids or OPEN_NOTEBOOK_ID in approved_ids:
        raise SafetyError("D-Prize or Open Notebook entered approved set")
    non_opportunities = [row for row in approved if set(row.get("patch", {})) == {"record_kind", "record_kind_reviewed"}]
    individuals = [row for row in approved if set(row.get("patch", {})) == {
        "applicant_type", "eligible_applicant_types", "applicant_type_reviewed"
    }]
    if {row["id"] for row in non_opportunities} != NON_OPPORTUNITY_IDS:
        raise SafetyError("reviewed non-opportunity set differs from exact approval")
    if len(individuals) != EXPECTED_INDIVIDUALS:
        raise SafetyError("reviewed individual count differs from exact approval")
    for row in non_opportunities:
        expected_kind = "informational" if row["id"].startswith("afcc") else "roundup"
        if row["patch"] != {"record_kind": expected_kind, "record_kind_reviewed": True}:
            raise SafetyError(f"invalid non-opportunity patch: {row['id']}")
    for row in individuals:
        if row["patch"] != {
            "applicant_type": "individual", "eligible_applicant_types": ["individual"],
            "applicant_type_reviewed": True,
        }:
            raise SafetyError(f"invalid individual patch: {row['id']}")
        if "record_kind" in row["patch"] or "record_kind_reviewed" in row["patch"]:
            raise SafetyError(f"individual patch changes record_kind: {row['id']}")
    return report, approved


def duplicate_match_count(matches):
    counts = Counter((row.get("user_id"), row.get("opportunity_id")) for row in matches)
    return sum(count > 1 for count in counts.values())


def check_runtime_guards():
    if sys.platform != "win32":
        raise SafetyError("scheduled-task/process guard is only supported on Windows")
    command = (
        "$t=Get-ScheduledTask -TaskName 'HelAI Automatic Collector' -ErrorAction Stop;"
        "$p=Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and "
        "$_.CommandLine -match 'helai_agent\\.py|run_collector\\.bat|automatic_collector\\.py|helai_pipeline\\.py' };"
        "[pscustomobject]@{TaskName=$t.TaskName;Enabled=$t.Settings.Enabled;State=[string]$t.State;"
        "Processes=@($p|ForEach-Object {[pscustomobject]@{Id=$_.ProcessId;CommandLine=$_.CommandLine}})}|ConvertTo-Json -Depth 4"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise SafetyError(f"cannot verify scheduled task/process state: {result.stderr.strip()}")
    state = json.loads(result.stdout)
    if state.get("TaskName") != "HelAI Automatic Collector" or state.get("Enabled") is not False:
        raise SafetyError(f"scheduled collector is not disabled: {state}")
    if str(state.get("State")).casefold() == "running" or state.get("Processes"):
        raise SafetyError(f"collector/agent process guard failed: {state}")
    return state


def validate_preflight(opportunities, matches, approved, check_runtime=True):
    state = {
        "opportunities": len(opportunities), "matches": len(matches),
        "duplicate_opportunity_groups": len(duplicate_groups(opportunities)),
        "duplicate_match_keys": duplicate_match_count(matches),
    }
    expected = (EXPECTED_OPPORTUNITIES, EXPECTED_MATCHES, 0, 0)
    actual = tuple(state[key] for key in (
        "opportunities", "matches", "duplicate_opportunity_groups", "duplicate_match_keys"
    ))
    if actual != expected:
        raise SafetyError(f"live count/duplicate preflight drift: {state}")
    by_id = {row.get("id"): row for row in opportunities}
    for proposal in approved:
        row = by_id.get(proposal["id"])
        if not row or row.get("title") != proposal.get("title"):
            raise SafetyError(f"approved ID/title drift: {proposal['id']}")
        for field, change in proposal.get("old_to_new", {}).items():
            if row.get(field) != change.get("old"):
                raise SafetyError(
                    f"old-value drift for {proposal['id']} {field}: "
                    f"expected {change.get('old')!r}, found {row.get(field)!r}"
                )
        if identity_digest(row) != APPROVED_IDENTITY_DIGESTS[proposal["id"]]:
            raise SafetyError(f"identity/content drift: {proposal['id']}")
    runtime = check_runtime_guards() if check_runtime else None
    return state, by_id, runtime


def load_notifications(approved_ids):
    # SELECT only. Filtering in memory avoids depending on PostgREST `in_` variations.
    rows = supabase.table("notifications").select("*").execute().data or []
    return [row for row in rows if row.get("opportunity_id") in approved_ids]


def build_backup_payload(opportunities, matches, notifications, approved, preflight):
    approved_ids = {row["id"] for row in approved}
    selected = [copy.deepcopy(row) for row in opportunities if row.get("id") in approved_ids]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "INTELLIGENCE_BACKFILL_BACKUP",
        "live_preflight": copy.deepcopy(preflight),
        "approved": copy.deepcopy(approved),
        "opportunities": selected,
        "matches": [copy.deepcopy(row) for row in matches if row.get("opportunity_id") in approved_ids],
        "notifications": [copy.deepcopy(row) for row in notifications if row.get("opportunity_id") in approved_ids],
        "related_counts": {
            "matches": sum(row.get("opportunity_id") in approved_ids for row in matches),
            "notifications": sum(row.get("opportunity_id") in approved_ids for row in notifications),
        },
    }


def verify_backup_payload(payload, approved, live_matches, live_notifications):
    expected_ids = {row["id"] for row in approved}
    rows = payload.get("opportunities") or []
    if len(rows) != EXPECTED_APPROVED or {row.get("id") for row in rows} != expected_ids:
        raise SafetyError("backup does not contain the exact 15 approved opportunities")
    titles = {row["id"]: row["title"] for row in approved}
    if any(row.get("title") != titles[row["id"]] for row in rows):
        raise SafetyError("backup title drift")
    for row in rows:
        if any(field not in row for field in INTELLIGENCE_FIELDS):
            raise SafetyError(f"backup lacks complete intelligence values: {row.get('id')}")
    backed_approved = payload.get("approved") or []
    if canonical(backed_approved) != canonical(approved):
        raise SafetyError("backup approved patches differ from reviewed preview")
    approved_ids = expected_ids
    expected_matches = [row for row in live_matches if row.get("opportunity_id") in approved_ids]
    expected_notifications = [row for row in live_notifications if row.get("opportunity_id") in approved_ids]
    if canonical(payload.get("matches") or []) != canonical(expected_matches):
        raise SafetyError("backup match rows/count differ from live preflight")
    if canonical(payload.get("notifications") or []) != canonical(expected_notifications):
        raise SafetyError("backup notification rows/count differ from live preflight")
    return True


def create_verified_backup(opportunities, matches, notifications, approved, preflight):
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUP_DIRECTORY / f"helai_opportunity_intelligence_{stamp}.json"
    payload = build_backup_payload(opportunities, matches, notifications, approved, preflight)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    try:
        reread = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SafetyError(f"backup read-back failed: {error}") from error
    verify_backup_payload(reread, approved, matches, notifications)
    return path, reread


def verify_impact(impact):
    actual = {field: impact.get(field) for field in EXPECTED_IMPACT}
    if actual != EXPECTED_IMPACT:
        raise SafetyError(f"hypothetical impact differs from reviewed preview: {actual}")
    false_to_true = [
        row for row in impact.get("all_effects", []) if row.get("evaluated")
        and not row["before"]["eligible"] and row["after"]["eligible"]
    ]
    if false_to_true:
        raise SafetyError("hypothetical False→True must equal zero")
    true_to_false = [
        row for row in impact.get("all_effects", []) if row.get("evaluated")
        and row["before"]["eligible"] and not row["after"]["eligible"]
    ]
    if len(true_to_false) != 2 or any(row["opportunity_id"] not in NON_OPPORTUNITY_IDS for row in true_to_false):
        raise SafetyError("True→False rows are not exactly the reviewed non-opportunity effect")
    return true_to_false


def dry_run_rows(approved, by_id, matches, notifications):
    match_counts = Counter(row.get("opportunity_id") for row in matches)
    notification_counts = Counter(row.get("opportunity_id") for row in notifications)
    output = []
    for proposal in approved:
        row = by_id[proposal["id"]]
        output.append({
            "id": row["id"], "title": row["title"],
            "current_intelligence_fields": {field: copy.deepcopy(row.get(field)) for field in INTELLIGENCE_FIELDS},
            "approved_old_to_new": copy.deepcopy(proposal["old_to_new"]),
            "approved_patch": copy.deepcopy(proposal["patch"]),
            "fields_proven_unchanged": {field: copy.deepcopy(row.get(field)) for field in UNCHANGED_FIELDS},
            "match_count": match_counts[row["id"]], "notification_count": notification_counts[row["id"]],
        })
    return output


def apply_exact(approved, backup, original_matches, original_notifications):
    raise SafetyError(
        "sequential Python apply is disabled to prevent partial writes; "
        "use the reviewed helai_opportunity_intelligence_backfill_transaction.sql transaction"
    )


def run(mode):
    preview, approved = load_approved_manifest()
    opportunities, matches, profiles = load_rows()
    # Runtime checks are repeated by every invocation, including eventual apply.
    preflight, by_id, runtime = validate_preflight(opportunities, matches, approved)
    approved_ids = {row["id"] for row in approved}
    notifications = load_notifications(approved_ids)
    profiles_by_id = {row.get("id"): row for row in profiles}
    impact = simulate_safe_subset(approved, by_id, matches, profiles_by_id)
    true_to_false = verify_impact(impact)
    rows = dry_run_rows(approved, by_id, matches, notifications)
    backup_path = None
    backup = None
    if mode == "backup-only":
        backup_path, backup = create_verified_backup(
            opportunities, matches, notifications, approved, preflight
        )
    if mode == "apply":
        apply_exact(approved, None, matches, notifications)
    report = {
        "mode": mode.upper().replace("-", "_"), "preflight": preflight,
        "runtime_guard": runtime, "approved_rows": len(approved),
        "reviewed_non_opportunities": EXPECTED_NON_OPPORTUNITIES,
        "reviewed_individuals": EXPECTED_INDIVIDUALS,
        "rows": rows, "hypothetical_impact": impact,
        "true_to_false_rows": true_to_false,
        "backup_path": str(backup_path.resolve()) if backup_path else None,
        "supabase_writes": 0 if mode != "apply" else EXPECTED_APPROVED,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--backup-only", action="store_true")
    modes.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    mode = "apply" if args.apply else "backup-only" if args.backup_only else "dry-run"
    run(mode)


if __name__ == "__main__":
    try:
        main()
    except SafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
