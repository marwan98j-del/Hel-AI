"""Safely inspect or apply the 10 approved HelAI duplicate merges.

The default mode is read-only.  ``--apply`` is deliberately required for
every update or delete.  This module never imports or calls email delivery.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APPROVED_PAIRS = [
    ("8c5dc682-a55e-47bc-a20a-3b7fb00ccfd7", "fafe12ed-8e1a-48b3-9dde-e7c05ce21968", "Medicines Manufacturing Data Institute: Phase 1"),
    ("e9ef1a0b-00c7-4502-babf-f25cb586bdd4", "b0f9211b-f29c-488d-884f-2387747e35a0", "Leaders of Africa Institute Research Communication Program 2026"),
    ("95598821-1fea-4818-bfb5-1ca2b066564f", "eb4d9ec0-33e0-4c64-8c36-2ffc0c10ceab", "EPSRC and MHCLG Fire Engineering Skills Hub"),
    ("719d68ce-e8c6-43a9-826d-dd59fd45e654", "6466bdb3-09d3-4c96-9c4f-52fe134b70e8", "Small Molecule High Throughput Screen Using AstraZeneca Facilities"),
    ("c221d3d5-fc25-47fd-96ed-fe683d645d9d", "b96abecb-37bb-4385-bdb5-4612a37ef55c", "Biodiversa+ 2026 to 2027: Novel Ecosystems (BiodivFuture)"),
    ("114b2305-7b19-4642-bd4e-b4152bf7af0c", "679349ba-bc36-462f-a8f6-d094cb09cf9f", "Engineering Biology Access to Infrastructure Pilot"),
    ("5456017e-aefb-49bb-99f9-9e8093e4647a", "e3ea2cbb-8ff0-4754-81ba-d21cc43c330f", "UBA National Essay Competition 2026"),
    ("80396480-626a-4625-b386-850cf7125dc9", "aa51a968-a133-414f-a8eb-00e845de7ad0", "LeadGreen Fellowship Cohort 4"),
    ("ef9247f0-d55a-45e1-aee8-743d5e1964b1", "3b67855f-2098-4a98-b71a-58fdd1c0a86e", "IIH SHIFT Programme 2026"),
    ("686831ca-ea8b-40b2-8229-dd0fc422143e", "2b661e45-23b0-4b95-a16f-58b0eb49d55c", "Democracy Group Podcast Fellowship 2026"),
]

# The approved plan used a shortened label for this group; both live records
# carry the same expanded title.  Keeping the one known alias explicit avoids
# fuzzy title matching while still failing closed on any future title change.
APPROVED_TITLE_ALIASES = {
    "IIH SHIFT Programme 2026": {
        "IIH SHIFT (Scaling Homegrown Innovations & Frontier Technologies) Programme 2026",
    },
}

SYSTEM_OPPORTUNITY_FIELDS = {"id", "created_at", "updated_at", "discovered_at"}
NOTIFICATION_STATUS_RANK = {"failed": 0, "pending": 1, "processing": 2, "sent": 3}
BACKUP_DIRECTORY = Path(__file__).with_name("helai_duplicate_cleanup_backups")


class SafetyError(RuntimeError):
    """Raised when current data does not exactly satisfy cleanup assumptions."""


def has_value(value):
    return value is not None and value != "" and value != [] and value != {}


def normalized_title(value):
    return " ".join(str(value or "").split()).casefold()


def normalized_url(value):
    if not has_value(value):
        return None
    parts = urlsplit(str(value).strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def verify_identity(keep, remove, expected_title):
    allowed_titles = {expected_title} | APPROVED_TITLE_ALIASES.get(expected_title, set())
    allowed = {normalized_title(title) for title in allowed_titles}
    if normalized_title(keep.get("title")) not in allowed or normalized_title(remove.get("title")) not in allowed:
        raise SafetyError("title changed or no longer matches the approved duplicate group")
    same_url = normalized_url(keep.get("source_url")) is not None and normalized_url(keep.get("source_url")) == normalized_url(remove.get("source_url"))
    keep_external = str(keep.get("external_id") or "").strip().casefold()
    remove_external = str(remove.get("external_id") or "").strip().casefold()
    same_external = bool(keep_external and keep_external == remove_external)
    if not (same_url or same_external):
        raise SafetyError("source URL/external ID no longer establishes duplicate identity")
    return {"same_source_url": same_url, "same_external_id": same_external}


def opportunity_patch(keep, remove):
    """Fill only genuinely missing canonical fields from the duplicate.

    The canonical extraction is authoritative.  This deliberately does not
    union semantic lists or replace non-empty text based on length.
    """
    patch = {}
    for field in sorted(set(keep) | set(remove)):
        if field in SYSTEM_OPPORTUNITY_FIELDS:
            continue
        current, candidate = keep.get(field), remove.get(field)
        if not has_value(current) and has_value(candidate):
            patch[field] = candidate
    return patch


def parse_time(row):
    return str(row.get("updated_at") or row.get("created_at") or "")


def merge_match_values(survivor, other):
    """Preserve only metadata that prevents duplicate notifications.

    Scores, eligibility, readiness, reasons, and gaps are derived values.  A
    later normal matching cycle must recompute them from canonical data.
    """
    patch = {}
    if bool(other.get("notified")) and not bool(survivor.get("notified")):
        patch["notified"] = True
    if str(other.get("notified_at") or "") > str(survivor.get("notified_at") or ""):
        patch["notified_at"] = other.get("notified_at")
    return patch


def notification_key(row):
    return (row.get("user_id"), row.get("channel") or "email")


def notification_quality(row):
    return (NOTIFICATION_STATUS_RANK.get(str(row.get("status") or "").lower(), -1), int(row.get("attempts") or 0), str(row.get("sent_at") or row.get("updated_at") or row.get("created_at") or ""))


def build_pair_plan(keep, remove, matches, notifications, expected_title):
    identity = verify_identity(keep, remove, expected_title)
    keep_matches = [row for row in matches if row.get("opportunity_id") == keep["id"]]
    remove_matches = [row for row in matches if row.get("opportunity_id") == remove["id"]]
    keep_by_user = {row.get("user_id"): row for row in keep_matches}
    if len(keep_by_user) != len(keep_matches):
        raise SafetyError("canonical record already has duplicate match rows for a user")
    remove_by_user = {row.get("user_id"): row for row in remove_matches}
    if len(remove_by_user) != len(remove_matches):
        raise SafetyError("remove candidate already has duplicate match rows for a user")
    match_moves, match_conflicts = [], []
    for row in remove_matches:
        if row.get("user_id") is None:
            raise SafetyError("match row has no user_id")
        existing = keep_by_user.get(row["user_id"])
        if existing:
            match_conflicts.append({"user_id": row["user_id"], "survivor_id": existing["id"], "remove_match_id": row["id"], "merged_fields": merge_match_values(existing, row)})
        else:
            match_moves.append({"match_id": row["id"], "user_id": row["user_id"]})
    pair_notifications = [row for row in notifications if row.get("opportunity_id") in {keep["id"], remove["id"]}]
    grouped = defaultdict(list)
    for row in pair_notifications:
        if row.get("user_id") is None or row.get("id") is None:
            raise SafetyError("notification row is missing id or user_id")
        grouped[notification_key(row)].append(row)
    notification_actions = []
    conflict_match_map = {item["remove_match_id"]: item["survivor_id"] for item in match_conflicts}
    for key, rows in grouped.items():
        winner = max(rows, key=notification_quality)
        losers = [row for row in rows if row["id"] != winner["id"]]
        target_match = conflict_match_map.get(winner.get("match_id"), winner.get("match_id"))
        notification_actions.append({"key": key, "survivor_id": winner["id"], "target_match_id": target_match, "delete_ids": [row["id"] for row in losers], "status": winner.get("status")})
    return {
        "keep": keep, "remove": remove, "title": expected_title, "identity": identity,
        "opportunity_patch": opportunity_patch(keep, remove),
        "keep_matches": keep_matches, "remove_matches": remove_matches,
        "match_moves": match_moves, "match_conflicts": match_conflicts,
        "keep_notifications": [row for row in notifications if row.get("opportunity_id") == keep["id"]],
        "remove_notifications": [row for row in notifications if row.get("opportunity_id") == remove["id"]],
        "notification_actions": notification_actions,
        "deletion_safe": True,
    }


def fetch_rows(client, table, ids):
    return client.table(table).select("*").in_("opportunity_id", ids).execute().data or []


def load_and_plan(client):
    ids = [item for pair in APPROVED_PAIRS for item in pair[:2]]
    opportunities = client.table("opportunities").select("*").in_("id", ids).execute().data or []
    by_id = {row.get("id"): row for row in opportunities}
    if len(opportunities) != len(ids) or set(by_id) != set(ids):
        missing = sorted(set(ids) - set(by_id))
        raise SafetyError(f"expected all 20 records; missing={missing}")
    matches = fetch_rows(client, "matches", ids)
    notifications_by_opportunity = fetch_rows(client, "notifications", ids)
    match_ids = [row.get("id") for row in matches if row.get("id")]
    notifications_by_match = (
        client.table("notifications").select("*").in_("match_id", match_ids).execute().data or []
        if match_ids
        else []
    )
    notifications_by_id = {
        row.get("id"): row
        for row in notifications_by_opportunity + notifications_by_match
    }
    if None in notifications_by_id:
        raise SafetyError("notification row is missing id")
    notifications = list(notifications_by_id.values())
    plans = [build_pair_plan(by_id[keep_id], by_id[remove_id], matches, notifications, title) for keep_id, remove_id, title in APPROVED_PAIRS]
    return plans, opportunities, matches, notifications


def print_plan(plans):
    print("# HelAI Approved Duplicate Cleanup")
    print("Mode: DRY-RUN (read-only)" if plans else "Mode: DRY-RUN")
    print("Conflict rule: retain the canonical user's match row and all canonical derived matching results. Do not merge score, eligibility, readiness, reasons, or gaps from REMOVE. Preserve only notified=True and the newest notified_at to prevent resends. Notifications are grouped by user/channel; the highest state (sent first), attempts, and recency survives. No email code is called.")
    for index, plan in enumerate(plans, 1):
        print(f"\n## Pair {index}: {plan['title']}")
        print(f"keep ID: {plan['keep']['id']}")
        print(f"remove ID: {plan['remove']['id']}")
        print(f"match count on keep: {len(plan['keep_matches'])}")
        print(f"match count on remove: {len(plan['remove_matches'])}")
        print(f"notification count on keep: {len(plan['keep_notifications'])}")
        print(f"notification count on remove: {len(plan['remove_notifications'])}")
        fields = sorted(plan["opportunity_patch"])
        print(f"fields copied remove -> keep: {', '.join(fields) if fields else 'none'}")
        print("match rows migrated: " + (", ".join(f"{row['match_id']} (user {row['user_id']})" for row in plan["match_moves"]) or "none"))
        print("match conflicts deduplicated: " + (", ".join(f"user {row['user_id']}: remove {row['remove_match_id']}, keep {row['survivor_id']}" for row in plan["match_conflicts"]) or "none"))
        moved_notifications = [row for row in plan["remove_notifications"]]
        print("notification rows migrated: " + (", ".join(str(row["id"]) for row in moved_notifications) or "none"))
        print(f"source identity: same URL={plan['identity']['same_source_url']}, same external ID={plan['identity']['same_external_id']}")
        print(f"deletion safe after planned migration and post-checks: {'yes' if plan['deletion_safe'] else 'no'}")
    print(f"\nTotals: pairs={len(plans)}, matches={sum(len(p['keep_matches']) + len(p['remove_matches']) for p in plans)}, match moves={sum(len(p['match_moves']) for p in plans)}, match conflicts={sum(len(p['match_conflicts']) for p in plans)}, notifications={sum(len(p['keep_notifications']) + len(p['remove_notifications']) for p in plans)}")
    print("No Supabase rows were updated or deleted.")


def checked_execute(query, description):
    result = query.execute()
    if result.data is None:
        raise SafetyError(f"mutation returned no data: {description}")
    return result.data


def backup_rows(opportunities, matches, notifications):
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUP_DIRECTORY / f"helai_duplicate_cleanup_{stamp}.json"
    payload = {"created_at": datetime.now(timezone.utc).isoformat(), "approved_pairs": APPROVED_PAIRS, "opportunities": opportunities, "matches": matches, "notifications": notifications}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def verify_backup(path, expected_opportunities, expected_matches, expected_notifications):
    """Read a backup back from disk and fail closed on any discrepancy."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SafetyError(f"backup JSON could not be read and parsed: {error}") from error

    opportunities = payload.get("opportunities")
    matches = payload.get("matches")
    notifications = payload.get("notifications")
    pairs = payload.get("approved_pairs")
    if not all(isinstance(rows, list) for rows in (opportunities, matches, notifications, pairs)):
        raise SafetyError("backup JSON is missing required record arrays")

    counts = {
        "opportunities": len(opportunities),
        "matches": len(matches),
        "notifications": len(notifications),
        "pairs": len(pairs),
    }
    expected_counts = {
        "opportunities": expected_opportunities,
        "matches": expected_matches,
        "notifications": expected_notifications,
        "pairs": len(APPROVED_PAIRS),
    }
    if counts != expected_counts:
        raise SafetyError(f"backup counts differ: actual={counts}, expected={expected_counts}")

    expected_ids = {item for pair in APPROVED_PAIRS for item in pair[:2]}
    actual_ids = {row.get("id") for row in opportunities}
    if actual_ids != expected_ids:
        raise SafetyError(
            "backup opportunity IDs differ: "
            f"missing={sorted(expected_ids - actual_ids)}, "
            f"unexpected={sorted(actual_ids - expected_ids)}"
        )

    expected_pairs = {tuple(pair) for pair in APPROVED_PAIRS}
    try:
        actual_pairs = {tuple(pair) for pair in pairs}
    except TypeError as error:
        raise SafetyError(f"backup approved-pair data is invalid: {error}") from error
    if actual_pairs != expected_pairs:
        raise SafetyError("backup does not contain all 10 approved keep/remove pairs")
    return counts


def print_backup_result(path, counts, passed):
    print("# HelAI Duplicate Cleanup Backup")
    print("Mode: BACKUP-ONLY (no Supabase mutations)")
    print(f"backup file: {path.resolve()}")
    print(f"opportunity count: {counts['opportunities']}")
    print(f"match count: {counts['matches']}")
    print(f"notification count: {counts['notifications']}")
    print(f"pair count: {counts['pairs']}")
    print(f"backup verification: {'PASS' if passed else 'FAIL'}")
    print("No Supabase rows were updated or deleted.")


def apply_plans(client, plans, opportunities, matches, notifications):
    # Preflight for every pair completed before this point. Backup is the first write.
    backup = backup_rows(opportunities, matches, notifications)
    verify_backup(
        backup,
        expected_opportunities=len(opportunities),
        expected_matches=len(matches),
        expected_notifications=len(notifications),
    )
    print(f"Local rollback backup: {backup}")
    now = datetime.now(timezone.utc).isoformat()
    for plan in plans:
        keep_id, remove_id = plan["keep"]["id"], plan["remove"]["id"]
        if plan["opportunity_patch"]:
            patch = dict(plan["opportunity_patch"], updated_at=now)
            checked_execute(client.table("opportunities").update(patch).eq("id", keep_id), f"enrich opportunity {keep_id}")
        for action in plan["notification_actions"]:
            for notification_id in action["delete_ids"]:
                checked_execute(client.table("notifications").delete().eq("id", notification_id), f"deduplicate notification {notification_id}")
            patch = {"opportunity_id": keep_id, "match_id": action["target_match_id"], "updated_at": now}
            checked_execute(client.table("notifications").update(patch).eq("id", action["survivor_id"]), f"migrate notification {action['survivor_id']}")
        for conflict in plan["match_conflicts"]:
            if conflict["merged_fields"]:
                patch = dict(conflict["merged_fields"], updated_at=now)
                checked_execute(client.table("matches").update(patch).eq("id", conflict["survivor_id"]), f"merge match {conflict['survivor_id']}")
            checked_execute(client.table("matches").delete().eq("id", conflict["remove_match_id"]), f"deduplicate match {conflict['remove_match_id']}")
        for move in plan["match_moves"]:
            checked_execute(client.table("matches").update({"opportunity_id": keep_id, "updated_at": now}).eq("id", move["match_id"]), f"migrate match {move['match_id']}")
        remaining_matches = fetch_rows(client, "matches", [remove_id])
        remaining_notifications = fetch_rows(client, "notifications", [remove_id])
        if remaining_matches or remaining_notifications:
            raise SafetyError(f"post-migration related rows remain for {remove_id}")
        canonical_matches = fetch_rows(client, "matches", [keep_id])
        expected_users = {row["user_id"] for row in plan["keep_matches"] + plan["remove_matches"]}
        actual_users = [row.get("user_id") for row in canonical_matches]
        if len(actual_users) != len(expected_users) or set(actual_users) != expected_users:
            raise SafetyError(f"post-migration match count/user verification failed for {keep_id}")
        canonical_notifications = fetch_rows(client, "notifications", [keep_id])
        expected_notification_keys = {notification_key(row) for row in plan["keep_notifications"] + plan["remove_notifications"]}
        actual_notification_keys = [notification_key(row) for row in canonical_notifications]
        if len(actual_notification_keys) != len(expected_notification_keys) or set(actual_notification_keys) != expected_notification_keys:
            raise SafetyError(f"post-migration notification count/key verification failed for {keep_id}")
        if not client.table("opportunities").select("id").eq("id", keep_id).limit(1).execute().data:
            raise SafetyError(f"canonical opportunity disappeared during migration: {keep_id}")
        checked_execute(client.table("opportunities").delete().eq("id", remove_id), f"delete duplicate opportunity {remove_id}")
        if client.table("opportunities").select("id").eq("id", remove_id).execute().data:
            raise SafetyError(f"duplicate opportunity still exists after delete: {remove_id}")
    print("Apply completed. No email delivery function was called.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect or apply the 10 explicitly approved duplicate opportunity merges.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true", help="Create and verify a local backup, then perform the approved merges. Omit for DRY-RUN.")
    modes.add_argument("--backup-only", action="store_true", help="Run full preflight, create and verify the local backup, and make no Supabase mutations.")
    args = parser.parse_args(argv)
    from collector_client import collector_supabase
    plans, opportunities, matches, notifications = load_and_plan(collector_supabase)
    if args.backup_only:
        path = backup_rows(opportunities, matches, notifications)
        try:
            counts = verify_backup(
                path,
                expected_opportunities=20,
                expected_matches=40,
                expected_notifications=0,
            )
        except SafetyError:
            print_backup_result(
                path,
                {
                    "opportunities": len(opportunities),
                    "matches": len(matches),
                    "notifications": len(notifications),
                    "pairs": len(APPROVED_PAIRS),
                },
                passed=False,
            )
            raise
        print_backup_result(path, counts, passed=True)
        return 0
    if not args.apply:
        print_plan(plans)
        return 0
    print("Mode: APPLY (explicit --apply received)")
    apply_plans(collector_supabase, plans, opportunities, matches, notifications)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
