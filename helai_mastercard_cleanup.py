"""One-pair cleanup for the approved Mastercard Foundation duplicate.

DRY-RUN is the default.  Supabase writes require the explicit ``--apply``
flag.  This module does not import or call any email-delivery code.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from helai_duplicate_cleanup import (
    SafetyError,
    build_pair_plan,
    checked_execute,
    fetch_rows,
)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEEP_ID = "645502b0-78a1-4720-b263-80e2569acaf4"
REMOVE_ID = "5ab6f8b0-efa4-4ecf-8cfc-8bf830c2f68f"
EXPECTED_TITLE = (
    "Mastercard Foundation Scholars Program at Arizona State University "
    "2027-2028"
)
EXPECTED_DEADLINE = "2026-09-27"
APPROVED_PAIR = (KEEP_ID, REMOVE_ID, EXPECTED_TITLE)
BACKUP_DIRECTORY = Path(__file__).with_name("helai_duplicate_cleanup_backups")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect, back up, or apply the approved Mastercard duplicate cleanup."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--apply",
        action="store_true",
        help="Create and verify a fresh backup, then apply this one approved merge.",
    )
    modes.add_argument(
        "--backup-only",
        action="store_true",
        help="Run preflight and create/verify a backup without Supabase mutations.",
    )
    return parser.parse_args(argv)


def load_and_plan(client):
    opportunity_ids = [KEEP_ID, REMOVE_ID]
    opportunities = (
        client.table("opportunities")
        .select("*")
        .in_("id", opportunity_ids)
        .execute()
        .data
        or []
    )
    by_id = {row.get("id"): row for row in opportunities}
    if len(opportunities) != 2 or set(by_id) != set(opportunity_ids):
        missing = sorted(set(opportunity_ids) - set(by_id))
        raise SafetyError(f"expected both approved opportunities; missing={missing}")

    keep = by_id[KEEP_ID]
    remove = by_id[REMOVE_ID]
    if keep.get("title") != EXPECTED_TITLE or remove.get("title") != EXPECTED_TITLE:
        raise SafetyError("title does not exactly match the approved Mastercard title")
    if keep.get("deadline") != EXPECTED_DEADLINE or remove.get("deadline") != EXPECTED_DEADLINE:
        raise SafetyError("deadline changed from the approved value")

    matches = fetch_rows(client, "matches", opportunity_ids)
    keep_match_count = sum(row.get("opportunity_id") == KEEP_ID for row in matches)
    remove_match_count = sum(row.get("opportunity_id") == REMOVE_ID for row in matches)
    if keep_match_count != 2 or remove_match_count != 2:
        raise SafetyError(
            "unexpected match counts: "
            f"KEEP={keep_match_count}, REMOVE={remove_match_count}; expected 2 and 2"
        )

    notifications_by_opportunity = fetch_rows(client, "notifications", opportunity_ids)
    match_ids = [row["id"] for row in matches if row.get("id")]
    notifications_by_match = (
        client.table("notifications")
        .select("*")
        .in_("match_id", match_ids)
        .execute()
        .data
        or []
    )
    notifications_by_id = {
        row.get("id"): row
        for row in notifications_by_opportunity + notifications_by_match
    }
    if None in notifications_by_id:
        raise SafetyError("notification row is missing id")
    notifications = list(notifications_by_id.values())

    plan = build_pair_plan(
        keep,
        remove,
        matches,
        notifications,
        EXPECTED_TITLE,
    )
    if plan["opportunity_patch"]:
        raise SafetyError(
            "unexpected opportunity backfills proposed: "
            f"{sorted(plan['opportunity_patch'])}; expected none"
        )
    if len(plan["match_moves"]) != 0 or len(plan["match_conflicts"]) != 2:
        raise SafetyError(
            "unexpected match topology: expected 0 direct moves and 2 conflicts"
        )
    return plan, opportunities, matches, notifications


def backup_rows(opportunities, matches, notifications):
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUP_DIRECTORY / f"helai_mastercard_cleanup_{stamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_pair": APPROVED_PAIR,
        "opportunities": opportunities,
        "matches": matches,
        "notifications": notifications,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def verify_backup(path, expected_notification_count):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SafetyError(f"backup JSON could not be read and parsed: {error}") from error

    opportunities = payload.get("opportunities")
    matches = payload.get("matches")
    notifications = payload.get("notifications")
    if not all(isinstance(rows, list) for rows in (opportunities, matches, notifications)):
        raise SafetyError("backup JSON is missing required record arrays")
    counts = {
        "opportunities": len(opportunities),
        "matches": len(matches),
        "notifications": len(notifications),
        "pairs": 1,
    }
    expected_counts = {
        "opportunities": 2,
        "matches": 4,
        "notifications": expected_notification_count,
        "pairs": 1,
    }
    if counts != expected_counts:
        raise SafetyError(f"backup counts differ: actual={counts}, expected={expected_counts}")
    if {row.get("id") for row in opportunities} != {KEEP_ID, REMOVE_ID}:
        raise SafetyError("backup does not contain both expected opportunity IDs")
    if tuple(payload.get("approved_pair") or ()) != APPROVED_PAIR:
        raise SafetyError("backup does not contain the exact approved pair")
    return counts


def print_plan(plan):
    print("# HelAI Mastercard Duplicate Cleanup")
    print("Mode: DRY-RUN (read-only)")
    print(f"title validation: PASS ({EXPECTED_TITLE})")
    print(
        "source validation: PASS "
        f"(normalized URLs match={plan['identity']['same_source_url']})"
    )
    print(f"deadline validation: PASS ({EXPECTED_DEADLINE})")
    print(f"KEEP ID: {KEEP_ID}")
    print(f"REMOVE ID: {REMOVE_ID}")
    print(f"match count KEEP: {len(plan['keep_matches'])}")
    print(f"match count REMOVE: {len(plan['remove_matches'])}")
    print(f"match direct moves: {len(plan['match_moves'])}")
    print(f"match conflict count: {len(plan['match_conflicts'])}")
    for conflict in plan["match_conflicts"]:
        print(
            "match conflict: "
            f"user={conflict['user_id']}, "
            f"keep_match={conflict['survivor_id']}, "
            f"remove_match={conflict['remove_match_id']}"
        )
    print(f"notification count KEEP: {len(plan['keep_notifications'])}")
    print(f"notification count REMOVE: {len(plan['remove_notifications'])}")
    print("proposed opportunity backfills: none")
    print("canonical derived matching fields preserved: yes")
    print("No Supabase rows were updated or deleted.")


def print_backup(path, counts):
    print("# HelAI Mastercard Cleanup Backup")
    print("Mode: BACKUP-ONLY (no Supabase mutations)")
    print(f"backup file: {path.resolve()}")
    print(f"opportunity count: {counts['opportunities']}")
    print(f"match count: {counts['matches']}")
    print(f"notification count: {counts['notifications']}")
    print(f"pair count: {counts['pairs']}")
    print("backup verification: PASS")
    print("No Supabase rows were updated or deleted.")


def apply_plan(client, plan, opportunities, matches, notifications):
    backup = backup_rows(opportunities, matches, notifications)
    verify_backup(backup, len(notifications))
    print(f"Local rollback backup: {backup.resolve()}")
    now = datetime.now(timezone.utc).isoformat()

    for action in plan["notification_actions"]:
        for notification_id in action["delete_ids"]:
            checked_execute(
                client.table("notifications").delete().eq("id", notification_id),
                f"deduplicate notification {notification_id}",
            )
        checked_execute(
            client.table("notifications")
            .update(
                {
                    "opportunity_id": KEEP_ID,
                    "match_id": action["target_match_id"],
                    "updated_at": now,
                }
            )
            .eq("id", action["survivor_id"]),
            f"migrate notification {action['survivor_id']}",
        )

    canonical_match_ids = {
        row["id"] for row in plan["keep_matches"]
    }
    derived_fields = (
        "match_score",
        "eligible",
        "readiness",
        "reasons",
        "eligibility_gaps",
        "readiness_gaps",
    )
    canonical_derived = {
        row["id"]: {field: row.get(field) for field in derived_fields}
        for row in plan["keep_matches"]
    }
    for conflict in plan["match_conflicts"]:
        if conflict["merged_fields"]:
            checked_execute(
                client.table("matches")
                .update(dict(conflict["merged_fields"], updated_at=now))
                .eq("id", conflict["survivor_id"]),
                f"preserve notification metadata on match {conflict['survivor_id']}",
            )
        checked_execute(
            client.table("matches").delete().eq("id", conflict["remove_match_id"]),
            f"deduplicate match {conflict['remove_match_id']}",
        )

    if fetch_rows(client, "matches", [REMOVE_ID]) or fetch_rows(
        client, "notifications", [REMOVE_ID]
    ):
        raise SafetyError("related rows remain on REMOVE after migration")
    canonical_matches = fetch_rows(client, "matches", [KEEP_ID])
    if {row.get("id") for row in canonical_matches} != canonical_match_ids:
        raise SafetyError("canonical match IDs changed unexpectedly")
    for row in canonical_matches:
        if any(
            row.get(field) != canonical_derived[row["id"]][field]
            for field in derived_fields
        ):
            raise SafetyError("canonical derived matching result changed unexpectedly")

    if not (
        client.table("opportunities")
        .select("id")
        .eq("id", KEEP_ID)
        .limit(1)
        .execute()
        .data
    ):
        raise SafetyError("KEEP opportunity disappeared before deletion")
    checked_execute(
        client.table("opportunities").delete().eq("id", REMOVE_ID),
        f"delete duplicate opportunity {REMOVE_ID}",
    )
    if (
        client.table("opportunities")
        .select("id")
        .eq("id", REMOVE_ID)
        .limit(1)
        .execute()
        .data
    ):
        raise SafetyError("REMOVE opportunity still exists after deletion")
    if not (
        client.table("opportunities")
        .select("id")
        .eq("id", KEEP_ID)
        .limit(1)
        .execute()
        .data
    ):
        raise SafetyError("KEEP opportunity missing after deletion")
    print("Apply completed. No email delivery function was called.")


def main(argv=None):
    args = parse_args(argv)
    from collector_client import collector_supabase

    plan, opportunities, matches, notifications = load_and_plan(collector_supabase)
    if args.backup_only:
        path = backup_rows(opportunities, matches, notifications)
        counts = verify_backup(path, len(notifications))
        print_backup(path, counts)
        return 0
    if not args.apply:
        print_plan(plan)
        return 0
    print("Mode: APPLY (explicit --apply received)")
    apply_plan(collector_supabase, plan, opportunities, matches, notifications)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
