import unittest
from pathlib import Path

from helai_ukri_duplicate_cleanup import (
    EXPECTED_KEEP_EXTERNAL_ID,
    EXPECTED_KEEP_FINGERPRINT,
    EXPECTED_NORMALIZED_URL,
    EXPECTED_REMOVE_FINGERPRINT,
    EXPECTED_SOURCE_NAME,
    EXPECTED_TITLE,
    KEEP_ID,
    REMOVE_ID,
    SafetyError,
    backup_plan,
    build_plan,
    main,
    proposed_opportunity_patch,
    verify_backup,
)


class UKRIDuplicateCleanupTests(unittest.TestCase):
    def opportunities(self):
        text = "identical source text"
        keep = {
            "id": KEEP_ID, "title": EXPECTED_TITLE, "source": "UKRI",
            "source_name": EXPECTED_SOURCE_NAME,
            "source_url": EXPECTED_NORMALIZED_URL + "/",
            "external_id": EXPECTED_KEEP_EXTERNAL_ID,
            "fingerprint": EXPECTED_KEEP_FINGERPRINT,
            "original_text": text, "status": "Open", "summary_en": "canonical",
        }
        remove = {
            "id": REMOVE_ID, "title": EXPECTED_TITLE.lower(), "source": "UKRI",
            "source_name": EXPECTED_SOURCE_NAME,
            "source_url": EXPECTED_NORMALIZED_URL,
            "external_id": None, "fingerprint": EXPECTED_REMOVE_FINGERPRINT,
            "original_text": text, "status": "Open", "summary_en": "duplicate",
        }
        return keep, remove

    def matches(self):
        fields = {
            "match_score": 39, "eligible": False, "readiness": 100,
            "reasons": ["canonical"], "eligibility_gaps": ["gap"],
            "readiness_gaps": [], "notified": False, "notified_at": None,
        }
        return [
            {"id": "k1", "opportunity_id": KEEP_ID, "user_id": "u1", **fields},
            {"id": "k2", "opportunity_id": KEEP_ID, "user_id": "u2", **fields},
            {"id": "r1", "opportunity_id": REMOVE_ID, "user_id": "u1", **dict(fields, match_score=99)},
            {"id": "r2", "opportunity_id": REMOVE_ID, "user_id": "u2", **dict(fields, eligible=True)},
        ]

    def plan(self):
        keep, remove = self.opportunities()
        return build_plan(keep, remove, self.matches(), [])

    def test_correct_pair_passes(self):
        plan = self.plan()
        self.assertEqual(len(plan["match_conflicts"]), 2)

    def test_wrong_keep_or_remove_id_fails(self):
        keep, remove = self.opportunities()
        keep["id"] = "wrong"
        with self.assertRaises(SafetyError):
            build_plan(keep, remove, self.matches(), [])

    def test_changed_normalized_url_fails(self):
        keep, remove = self.opportunities()
        remove["source_url"] = "https://www.ukri.org/opportunity/different"
        with self.assertRaises(SafetyError):
            build_plan(keep, remove, self.matches(), [])

    def test_external_id_drift_fails(self):
        keep, remove = self.opportunities()
        remove["external_id"] = "unexpected"
        with self.assertRaises(SafetyError):
            build_plan(keep, remove, self.matches(), [])

    def test_unexpected_match_count_fails(self):
        keep, remove = self.opportunities()
        with self.assertRaises(SafetyError):
            build_plan(keep, remove, self.matches()[:-1], [])

    def test_nonempty_keep_fields_cannot_be_overwritten(self):
        keep, remove = self.opportunities()
        self.assertEqual(proposed_opportunity_patch(keep, remove), {})
        self.assertEqual(keep["summary_en"], "canonical")

    def test_no_backfill_occurs(self):
        self.assertEqual(self.plan()["opportunity_patch"], {})

    def test_keep_derived_match_values_remain_authoritative(self):
        plan = self.plan()
        self.assertEqual(plan["keep_match_snapshots"]["k1"]["match_score"], 39)
        self.assertFalse(plan["keep_match_snapshots"]["k2"]["eligible"])
        self.assertEqual(plan["delete_match_ids"], ["r1", "r2"])
        self.assertNotIn("match_updates", plan)

    def test_backup_verification_round_trip(self):
        plan = self.plan()
        directory = Path(__file__).parent / "helai_ukri_duplicate_cleanup_test_backups"
        path = backup_plan(plan, directory)
        try:
            counts = verify_backup(path, plan)
        finally:
            path.unlink(missing_ok=True)
            directory.rmdir()
        self.assertEqual(
            counts,
            {"opportunities": 2, "matches": 4, "notifications": 0, "approved_pair": True},
        )

    def test_apply_and_backup_only_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as context:
            main(["--apply", "--backup-only"])
        self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
