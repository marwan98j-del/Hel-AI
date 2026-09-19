"""Read-only final verification for the already-applied match reconciliation."""

import copy
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from helai_applicant_ai_audit import load_rows
from helai_maintenance import duplicate_groups
from helai_match_reconciliation import canonical, duplicate_match_count
from helai_matching_preview import DERIVED_FIELDS, build_preview
from matching_service import opportunity_is_actionable
from opportunity_rules import effective_status, normalize_status, record_kind_is_non_actionable
from supabase_client import supabase


BACKUP = Path(__file__).with_name("helai_match_reconciliation_backups") / "helai_matches_20260919T113453819009Z.json"
SNAPSHOT_DIRECTORY = Path(__file__).with_name("helai_match_reconciliation_snapshots")
PRESERVED_FIELDS = ("id", "user_id", "opportunity_id", "created_at", "notified", "notified_at")


class VerificationError(RuntimeError):
    pass


def verify_final_state(opportunities, matches, profiles, backup):
    if len(opportunities) != 122 or len(matches) != 224:
        raise VerificationError("global count drift")
    if duplicate_groups(opportunities) or duplicate_match_count(matches):
        raise VerificationError("duplicate drift")

    old_by_id = {row["id"]: row for row in backup["matches"]}
    target_by_id = {row["id"]: row for row in backup["changed_matches"]}
    live_by_id = {row["id"]: row for row in matches}
    if set(old_by_id) != set(live_by_id) or len(target_by_id) != 72:
        raise VerificationError("match identity or reviewed target drift")

    preserved_differences = []
    final_differences = []
    target_correct = 0
    unchanged_correct = 0
    for match_id, live in live_by_id.items():
        old = old_by_id[match_id]
        changed_preserved = [field for field in PRESERVED_FIELDS if canonical(live.get(field)) != canonical(old.get(field))]
        if changed_preserved:
            preserved_differences.append({"id": match_id, "fields": changed_preserved})
        expected = target_by_id[match_id]["new"] if match_id in target_by_id else {
            field: old.get(field) for field in DERIVED_FIELDS
        }
        changed_result = [field for field in DERIVED_FIELDS if canonical(live.get(field)) != canonical(expected.get(field))]
        if changed_result:
            final_differences.append({"id": match_id, "fields": changed_result})
        elif match_id in target_by_id:
            target_correct += 1
        else:
            unchanged_correct += 1

    recomputed = build_preview(profiles, opportunities, matches)
    if recomputed["changed_matches"] or recomputed["missing_matches_to_create"] or recomputed["errors"]:
        raise VerificationError(
            f"live rows differ from current matcher: changed={len(recomputed['changed_matches'])}, "
            f"new={len(recomputed['missing_matches_to_create'])}, errors={recomputed['errors']}"
        )
    if preserved_differences or final_differences or target_correct != 72 or unchanged_correct != 152:
        raise VerificationError(
            f"final target mismatch: target={target_correct}, unchanged={unchanged_correct}, "
            f"preserved={preserved_differences}, result={final_differences}"
        )

    opportunities_by_id = {row["id"]: row for row in opportunities}
    non_actionable = []
    expired = []
    reviewed_non_opportunity = []
    violations = []
    for row in matches:
        opportunity = opportunities_by_id[row["opportunity_id"]]
        expired_open = normalize_status(opportunity.get("status")) == "Open" and effective_status(opportunity) == "Closed"
        reviewed_non = record_kind_is_non_actionable(opportunity.get("record_kind"))
        non_actionable_now = not opportunity_is_actionable(opportunity) or reviewed_non
        if non_actionable_now:
            non_actionable.append(row)
            if row.get("eligible") is not False or row.get("match_score") != 0 or row.get("readiness") != 0:
                violations.append(row["id"])
        if expired_open:
            expired.append(row)
        if reviewed_non:
            reviewed_non_opportunity.append(row)
    if len(non_actionable) != 54 or violations:
        raise VerificationError(f"non-actionable reconciliation mismatch: {len(non_actionable)}, {violations}")

    return {
        "live_opportunities": 122,
        "live_matches": 224,
        "duplicate_opportunity_groups": 0,
        "duplicate_match_keys": 0,
        "final_target_rows_correct": target_correct,
        "unchanged_rows_correct": unchanged_correct,
        "unexpected_live_differences": 0,
        "new_matches": 0,
        "deleted_matches": 0,
        "non_actionable_reconciled": len(non_actionable),
        "expired_matches": len(expired),
        "expired_matches_still_eligible": sum(bool(row.get("eligible")) for row in expired),
        "reviewed_non_opportunity_matches": len(reviewed_non_opportunity),
        "non_opportunity_matches_still_eligible": sum(bool(row.get("eligible")) for row in reviewed_non_opportunity),
        "created_at_preserved": True,
        "notified_preserved": True,
        "notified_at_preserved": True,
        "reviewed_impact": {
            "eligible_true_to_false": 44,
            "eligible_false_to_true": 0,
            "score_changes": 54,
            "readiness_changes": 54,
        },
    }


def main():
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    opportunities, matches, profiles = load_rows()
    notifications = supabase.table("notifications").select("*").execute().data or []
    summary = verify_final_state(opportunities, matches, profiles, backup)
    related_ids = {row["id"] for row in opportunities if not opportunity_is_actionable(row) or record_kind_is_non_actionable(row.get("record_kind"))}
    summary["related_notification_rows"] = sum(row.get("opportunity_id") in related_ids for row in notifications)
    summary["notification_rows_total"] = len(notifications)
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "POST_RECONCILIATION_READ_ONLY_SNAPSHOT",
        "summary": copy.deepcopy(summary),
        "matches": copy.deepcopy(matches),
        "opportunities": copy.deepcopy(opportunities),
    }
    SNAPSHOT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = SNAPSHOT_DIRECTORY / f"helai_matches_post_reconciliation_{stamp}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    reread = json.loads(path.read_text(encoding="utf-8"))
    if len(reread.get("matches") or []) != 224 or len(reread.get("opportunities") or []) != 122:
        raise VerificationError("post-reconciliation snapshot verification failed")
    print(json.dumps({"verification": "PASS", "summary": summary, "snapshot_path": str(path.resolve())}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except VerificationError as error:
        print(f"VERIFICATION FAILED: {error}", file=sys.stderr)
        raise SystemExit(2)
