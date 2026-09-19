"""Fail-closed cleanup for one explicitly approved UKRI duplicate pair.

Default mode is a read-only dry-run. ``--backup-only`` writes and verifies a
local JSON backup. Supabase mutations require the explicit ``--apply`` flag.
This module imports no notification or email delivery service.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from collector_service import identity_match_reasons
from opportunity_rules import normalize_url


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEEP_ID = "719d68ce-e8c6-43a9-826d-dd59fd45e654"
REMOVE_ID = "5a1a4a9a-2788-4bc7-a313-e252fddd6306"
EXPECTED_TITLE = "Small Molecule High Throughput Screen Using AstraZeneca Facilities"
EXPECTED_SOURCE_NAME = "UK Research and Innovation (UKRI)"
EXPECTED_NORMALIZED_URL = (
    "https://www.ukri.org/opportunity/"
    "small-molecule-high-throughput-screen-using-astrazeneca-facilities"
)
EXPECTED_KEEP_EXTERNAL_ID = (
    "small-molecule-high-throughput-screen-using-astrazeneca-facilities"
)
EXPECTED_KEEP_FINGERPRINT = (
    "6603ad5557d17156092afd0ccbeae616273ba4814bb04b2e89edc2afb085709c"
)
EXPECTED_REMOVE_FINGERPRINT = (
    "31d8d54c5e646ce3775faa98f5cab17b4d49c883903b06285c12a5b456a47906"
)
EXPECTED_MATCHES_PER_SIDE = 2
EXPECTED_NOTIFICATIONS = 0
BACKUP_DIRECTORY = Path(__file__).with_name("helai_ukri_duplicate_cleanup_backups")


class SafetyError(RuntimeError):
    pass


def has_value(value):
    return value is not None and value != "" and value != [] and value != {}


def normalized_title(value):
    return " ".join(str(value or "").split()).casefold()


def verify_approved_ids(keep, remove):
    if keep.get("id") != KEEP_ID or remove.get("id") != REMOVE_ID:
        raise SafetyError("records do not match the one approved KEEP/REMOVE pair")


def verify_identity(keep, remove):
    verify_approved_ids(keep, remove)
    if normalized_title(keep.get("title")) != normalized_title(EXPECTED_TITLE):
        raise SafetyError("KEEP title drifted from the approved opportunity")
    if normalized_title(remove.get("title")) != normalized_title(EXPECTED_TITLE):
        raise SafetyError("REMOVE title no longer corresponds to the approved opportunity")
    if keep.get("source") != "UKRI" or remove.get("source") != "UKRI":
        raise SafetyError("both opportunity records must remain UKRI records")
    if (
        keep.get("source_name") != EXPECTED_SOURCE_NAME
        or remove.get("source_name") != EXPECTED_SOURCE_NAME
    ):
        raise SafetyError("UKRI source_name drifted")

    keep_url = normalize_url(keep.get("source_url"))
    remove_url = normalize_url(remove.get("source_url"))
    if keep_url != EXPECTED_NORMALIZED_URL or remove_url != EXPECTED_NORMALIZED_URL:
        raise SafetyError("normalized source URL drifted from the approved UKRI identity")
    if keep_url != remove_url:
        raise SafetyError("normalized source URLs are no longer identical")
    if str(keep.get("external_id") or "").strip() != EXPECTED_KEEP_EXTERNAL_ID:
        raise SafetyError("KEEP external_id drifted")
    if str(remove.get("external_id") or "").strip():
        raise SafetyError("REMOVE external_id is unexpectedly populated")
    if keep.get("fingerprint") != EXPECTED_KEEP_FINGERPRINT:
        raise SafetyError("KEEP fingerprint drifted")
    if remove.get("fingerprint") != EXPECTED_REMOVE_FINGERPRINT:
        raise SafetyError("REMOVE fingerprint drifted")
    if keep.get("original_text") != remove.get("original_text"):
        raise SafetyError("original source text is no longer identical")
    return {
        "normalized_source_url": keep_url,
        "keep_external_id": keep.get("external_id"),
        "remove_external_id": remove.get("external_id"),
        "keep_fingerprint": keep.get("fingerprint"),
        "remove_fingerprint": remove.get("fingerprint"),
        "original_text_identical": True,
        "identity_match_reasons": identity_match_reasons(keep, remove),
    }


def proposed_opportunity_patch(keep, remove):
    system_fields = {"id", "created_at", "updated_at", "discovered_at"}
    candidates = {
        field: remove.get(field)
        for field in sorted(set(keep) | set(remove))
        if field not in system_fields
        and not has_value(keep.get(field))
        and has_value(remove.get(field))
    }
    if candidates:
        raise SafetyError(
            "unexpected possible backfills appeared; KEEP must remain unchanged: "
            + ", ".join(candidates)
        )
    return {}


def build_plan(keep, remove, matches, notifications):
    identity = verify_identity(keep, remove)
    keep_matches = [row for row in matches if row.get("opportunity_id") == KEEP_ID]
    remove_matches = [row for row in matches if row.get("opportunity_id") == REMOVE_ID]
    if len(keep_matches) != EXPECTED_MATCHES_PER_SIDE:
        raise SafetyError(f"expected 2 KEEP matches, found {len(keep_matches)}")
    if len(remove_matches) != EXPECTED_MATCHES_PER_SIDE:
        raise SafetyError(f"expected 2 REMOVE matches, found {len(remove_matches)}")
    if any(not row.get("id") or not row.get("user_id") for row in keep_matches + remove_matches):
        raise SafetyError("a related match is missing id or user_id")
    keep_by_user = {row["user_id"]: row for row in keep_matches}
    remove_by_user = {row["user_id"]: row for row in remove_matches}
    if len(keep_by_user) != 2 or len(remove_by_user) != 2:
        raise SafetyError("unexpected duplicate user match rows exist within one side")
    if set(keep_by_user) != set(remove_by_user):
        raise SafetyError("REMOVE users do not exactly match canonical KEEP users")
    if notifications:
        raise SafetyError(
            "unexpected notification rows exist: "
            + ", ".join(str(row.get("id")) for row in notifications)
        )

    conflicts = [
        {
            "user_id": user_id,
            "keep_match_id": keep_by_user[user_id]["id"],
            "remove_match_id": remove_by_user[user_id]["id"],
        }
        for user_id in sorted(keep_by_user)
    ]
    return {
        "keep": keep,
        "remove": remove,
        "identity": identity,
        "opportunity_patch": proposed_opportunity_patch(keep, remove),
        "keep_matches": keep_matches,
        "remove_matches": remove_matches,
        "notifications": notifications,
        "match_conflicts": conflicts,
        "delete_match_ids": [row["id"] for row in remove_matches],
        "keep_match_snapshots": {row["id"]: row for row in keep_matches},
    }


def fetch_related(client):
    ids = [KEEP_ID, REMOVE_ID]
    opportunities = (
        client.table("opportunities").select("*").in_("id", ids).execute().data or []
    )
    by_id = {row.get("id"): row for row in opportunities}
    if set(by_id) != set(ids) or len(opportunities) != 2:
        raise SafetyError(
            f"approved opportunities missing or duplicated; found={sorted(by_id)}"
        )
    matches = (
        client.table("matches").select("*").in_("opportunity_id", ids).execute().data or []
    )
    by_opportunity = (
        client.table("notifications").select("*").in_("opportunity_id", ids).execute().data or []
    )
    match_ids = [row.get("id") for row in matches if row.get("id")]
    by_match = (
        client.table("notifications").select("*").in_("match_id", match_ids).execute().data or []
        if match_ids else []
    )
    notification_map = {row.get("id"): row for row in by_opportunity + by_match}
    if None in notification_map:
        raise SafetyError("notification row is missing id")
    return (
        by_id[KEEP_ID],
        by_id[REMOVE_ID],
        matches,
        list(notification_map.values()),
    )


def load_plan(client):
    keep, remove, matches, notifications = fetch_related(client)
    return build_plan(keep, remove, matches, notifications)


def backup_plan(plan, directory=BACKUP_DIRECTORY):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"helai_ukri_duplicate_cleanup_{stamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_pair": {"keep": KEEP_ID, "remove": REMOVE_ID},
        "preflight_identity": plan["identity"],
        "opportunities": [plan["keep"], plan["remove"]],
        "matches": plan["keep_matches"] + plan["remove_matches"],
        "notifications": plan["notifications"],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def verify_backup(path, expected_plan):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SafetyError(f"backup JSON could not be read and parsed: {error}") from error
    pair = payload.get("approved_pair")
    opportunities = payload.get("opportunities")
    matches = payload.get("matches")
    notifications = payload.get("notifications")
    identity = payload.get("preflight_identity")
    if pair != {"keep": KEEP_ID, "remove": REMOVE_ID}:
        raise SafetyError("backup does not contain the approved pair")
    if not isinstance(opportunities, list) or {row.get("id") for row in opportunities} != {KEEP_ID, REMOVE_ID}:
        raise SafetyError("backup opportunity IDs differ from the approved pair")
    if not isinstance(matches, list) or len(matches) != 4:
        raise SafetyError("backup must contain exactly four related matches")
    if not isinstance(notifications, list) or len(notifications) != len(expected_plan["notifications"]):
        raise SafetyError("backup notification count differs from live preflight")
    expected_match_ids = {
        row["id"] for row in expected_plan["keep_matches"] + expected_plan["remove_matches"]
    }
    if {row.get("id") for row in matches} != expected_match_ids:
        raise SafetyError("backup match IDs differ from live preflight")
    if identity != expected_plan["identity"]:
        raise SafetyError("backup identity information differs from live preflight")
    return {
        "opportunities": 2,
        "matches": 4,
        "notifications": len(notifications),
        "approved_pair": True,
    }


def duplicate_scan(client):
    rows = client.table("opportunities").select("*").execute().data or []
    groups = []
    for first, second in combinations(rows, 2):
        reasons = identity_match_reasons(first, second)
        if reasons:
            groups.append({
                "ids": [first.get("id"), second.get("id")],
                "titles": [first.get("title"), second.get("title")],
                "reasons": reasons,
            })
    return groups


def checked_delete(query, expected_id, description):
    rows = query.execute().data
    if not isinstance(rows, list) or {row.get("id") for row in rows} != {expected_id}:
        raise SafetyError(f"unexpected delete result for {description}")


def apply_plan(client):
    # Repeat preflight immediately before any mutation.
    plan = load_plan(client)
    backup = backup_plan(plan)
    verify_backup(backup, plan)
    keep_snapshot = plan["keep"]
    keep_match_snapshots = plan["keep_match_snapshots"]

    for match_id in plan["delete_match_ids"]:
        checked_delete(
            client.table("matches").delete().eq("id", match_id),
            match_id,
            f"REMOVE-side match {match_id}",
        )
    if client.table("matches").select("id").eq("opportunity_id", REMOVE_ID).execute().data:
        raise SafetyError("a match still references REMOVE after match cleanup")

    live_keep_matches = (
        client.table("matches").select("*").eq("opportunity_id", KEEP_ID).execute().data or []
    )
    if {row["id"]: row for row in live_keep_matches} != keep_match_snapshots:
        raise SafetyError("KEEP-side match rows changed during cleanup")

    checked_delete(
        client.table("opportunities").delete().eq("id", REMOVE_ID),
        REMOVE_ID,
        "approved duplicate opportunity",
    )
    live_keep = client.table("opportunities").select("*").eq("id", KEEP_ID).execute().data or []
    if len(live_keep) != 1 or live_keep[0] != keep_snapshot:
        raise SafetyError("KEEP opportunity changed or disappeared during cleanup")
    if client.table("opportunities").select("id").eq("id", REMOVE_ID).execute().data:
        raise SafetyError("REMOVE opportunity still exists after cleanup")
    groups = duplicate_scan(client)
    print(f"Post-cleanup duplicate groups: {len(groups)}")
    print(f"Verified backup: {backup.resolve()}")


def print_plan(plan):
    print("# HelAI UKRI Duplicate Cleanup")
    print("Mode: DRY-RUN (read-only)")
    print(f"KEEP: {KEEP_ID}")
    print(f"REMOVE: {REMOVE_ID}")
    print(f"normalized source URL: {plan['identity']['normalized_source_url']}")
    print(f"KEEP matches: {len(plan['keep_matches'])}")
    print(f"REMOVE matches: {len(plan['remove_matches'])}")
    print(f"notifications: {len(plan['notifications'])}")
    print("opportunity backfills proposed: none")
    print("REMOVE-side match deletions proposed: " + ", ".join(plan["delete_match_ids"]))
    print("KEEP opportunity mutation proposed: none")
    print("KEEP match mutations proposed: none")
    print("Supabase mutations performed: 0")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--backup-only", action="store_true")
    modes.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    from collector_client import collector_supabase
    plan = load_plan(collector_supabase)
    if args.backup_only:
        path = backup_plan(plan)
        counts = verify_backup(path, plan)
        print("# HelAI UKRI Duplicate Cleanup Backup")
        print("Mode: BACKUP-ONLY (no Supabase mutations)")
        print(f"backup file: {path.resolve()}")
        print(json.dumps(counts, indent=2))
        print("backup verification: PASS")
        return 0
    if args.apply:
        print("Mode: APPLY (explicit --apply received)")
        apply_plan(collector_supabase)
        return 0
    print_plan(plan)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
