import unittest

from helai_duplicate_cleanup import SafetyError, build_pair_plan
from helai_mastercard_cleanup import (
    APPROVED_PAIR,
    EXPECTED_DEADLINE,
    EXPECTED_TITLE,
    KEEP_ID,
    REMOVE_ID,
    backup_rows,
    parse_args,
    verify_backup,
)


class MastercardCleanupTests(unittest.TestCase):
    def test_default_is_dry_run_and_modes_are_mutually_exclusive(self):
        args = parse_args([])
        self.assertFalse(args.apply)
        self.assertFalse(args.backup_only)
        with self.assertRaises(SystemExit) as context:
            parse_args(["--apply", "--backup-only"])
        self.assertEqual(context.exception.code, 2)

    def test_approved_pair_is_exact(self):
        self.assertEqual(
            APPROVED_PAIR,
            (KEEP_ID, REMOVE_ID, EXPECTED_TITLE),
        )
        self.assertEqual(EXPECTED_DEADLINE, "2026-09-27")

    def test_backup_round_trip_verifies_exact_pair_ids_and_live_counts(self):
        opportunities = [
            {"id": KEEP_ID, "title": EXPECTED_TITLE},
            {"id": REMOVE_ID, "title": EXPECTED_TITLE},
        ]
        matches = [{"id": f"match-{index}"} for index in range(4)]
        path = backup_rows(opportunities, matches, [])
        try:
            counts = verify_backup(path, 0)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(
            counts,
            {"opportunities": 2, "matches": 4, "notifications": 0, "pairs": 1},
        )

    def test_backup_verification_rejects_missing_expected_id(self):
        opportunities = [
            {"id": KEEP_ID},
            {"id": "unexpected"},
        ]
        path = backup_rows(opportunities, [{"id": str(i)} for i in range(4)], [])
        try:
            with self.assertRaises(SafetyError):
                verify_backup(path, 0)
        finally:
            path.unlink(missing_ok=True)

    def test_pair_plan_has_no_backfill_and_keeps_canonical_match_results(self):
        keep = {
            "id": KEEP_ID,
            "title": EXPECTED_TITLE,
            "source_url": "https://opportunitydesk.org/item",
            "deadline": EXPECTED_DEADLINE,
            "summary_en": "canonical",
            "skills": ["Leadership", "Community engagement"],
        }
        remove = {
            "id": REMOVE_ID,
            "title": EXPECTED_TITLE,
            "source_url": "https://opportunitydesk.org/item/",
            "deadline": EXPECTED_DEADLINE,
            "summary_en": None,
            "skills": ["Leadership"],
        }
        matches = [
            {"id": "keep-1", "opportunity_id": KEEP_ID, "user_id": "user-1", "match_score": 45, "eligible": True, "readiness": 100, "reasons": ["canonical"], "notified": False},
            {"id": "remove-1", "opportunity_id": REMOVE_ID, "user_id": "user-1", "match_score": 99, "eligible": False, "readiness": 0, "reasons": ["stale"], "notified": True},
        ]
        plan = build_pair_plan(keep, remove, matches, [], EXPECTED_TITLE)
        self.assertEqual(plan["opportunity_patch"], {})
        self.assertEqual(len(plan["match_conflicts"]), 1)
        merged = plan["match_conflicts"][0]["merged_fields"]
        self.assertEqual(merged, {"notified": True})
        for field in ("match_score", "eligible", "readiness", "reasons"):
            self.assertNotIn(field, merged)


if __name__ == "__main__":
    unittest.main()
