import unittest

from helai_duplicate_cleanup import (
    APPROVED_PAIRS,
    SafetyError,
    backup_rows,
    build_pair_plan,
    main,
    merge_match_values,
    opportunity_patch,
    verify_backup,
    verify_identity,
)


class DuplicateCleanupLogicTests(unittest.TestCase):
    def opportunity(self, row_id, **extra):
        return {"id": row_id, "title": "Expected Title", "source_url": "https://example.org/item/?utm_source=x", "external_id": "ABC", **extra}

    def test_identity_requires_expected_title_and_shared_source_identity(self):
        result = verify_identity(self.opportunity("keep"), self.opportunity("remove", source_url="https://example.org/item"), "Expected Title")
        self.assertTrue(result["same_source_url"])
        with self.assertRaises(SafetyError):
            verify_identity(self.opportunity("keep"), self.opportunity("remove", title="Changed", source_url="https://elsewhere.test"), "Expected Title")

    def test_identity_accepts_only_the_explicit_approved_title_alias(self):
        expanded = "IIH SHIFT (Scaling Homegrown Innovations & Frontier Technologies) Programme 2026"
        keep = self.opportunity("keep", title=expanded)
        remove = self.opportunity("remove", title=expanded)
        self.assertTrue(verify_identity(keep, remove, "IIH SHIFT Programme 2026")["same_source_url"])

    def test_opportunity_merge_only_fills_missing_canonical_fields(self):
        keep = self.opportunity(
            "keep",
            summary_en="canonical summary",
            original_text="canonical source text",
            skills=["python"],
            eligible_applicant_types=["student"],
            deadline="2026-01-01",
            status="Open",
            requires_cv=False,
        )
        remove = self.opportunity(
            "remove",
            summary_en="a much longer but stale duplicate summary",
            summary_ku="کوردی",
            original_text="a much longer but stale duplicate source text",
            skills=["python", "sql"],
            eligible_applicant_types=["professional"],
            deadline="2027-01-01",
            status="Closed",
            requires_cv=True,
        )
        patch = opportunity_patch(keep, remove)
        self.assertEqual(patch["summary_ku"], "کوردی")
        self.assertNotIn("summary_en", patch)
        self.assertNotIn("original_text", patch)
        self.assertNotIn("skills", patch)
        self.assertNotIn("eligible_applicant_types", patch)
        self.assertNotIn("deadline", patch)
        self.assertNotIn("status", patch)
        self.assertNotIn("requires_cv", patch)

    def test_opportunity_merge_can_copy_a_populated_list_when_canonical_is_empty(self):
        keep = self.opportunity("keep", skills=[])
        remove = self.opportunity("remove", skills=["python", "sql"])
        self.assertEqual(opportunity_patch(keep, remove)["skills"], ["python", "sql"])

    def test_match_merge_rejects_stale_derived_values_but_preserves_notification_safety(self):
        patch = merge_match_values(
            {"match_score": 70, "eligible": False, "readiness": "needs_work", "reasons": ["canonical"], "eligibility_gaps": ["canonical eligibility gap"], "readiness_gaps": ["canonical readiness gap"], "notified": False, "notified_at": "2026-01-01"},
            {"match_score": 99, "eligible": True, "readiness": "ready", "reasons": ["stale"], "eligibility_gaps": ["stale eligibility gap"], "readiness_gaps": ["stale readiness gap"], "notified": True, "notified_at": "2026-01-02"},
        )
        for field in ("match_score", "eligible", "readiness", "reasons", "eligibility_gaps", "readiness_gaps"):
            self.assertNotIn(field, patch)
        self.assertTrue(patch["notified"])
        self.assertEqual(patch["notified_at"], "2026-01-02")

    def test_pair_plan_moves_unique_match_and_deduplicates_conflict(self):
        keep, remove = self.opportunity("keep"), self.opportunity("remove")
        matches = [
            {"id": "k1", "opportunity_id": "keep", "user_id": "u1", "match_score": 50},
            {"id": "r1", "opportunity_id": "remove", "user_id": "u1", "match_score": 80},
            {"id": "r2", "opportunity_id": "remove", "user_id": "u2", "match_score": 70},
        ]
        plan = build_pair_plan(keep, remove, matches, [], "Expected Title")
        self.assertEqual([row["match_id"] for row in plan["match_moves"]], ["r2"])
        self.assertEqual(plan["match_conflicts"][0]["survivor_id"], "k1")
        self.assertNotIn("match_score", plan["match_conflicts"][0]["merged_fields"])

    def test_pair_plan_stops_on_preexisting_duplicate_user_matches(self):
        keep, remove = self.opportunity("keep"), self.opportunity("remove")
        matches = [
            {"id": "r1", "opportunity_id": "remove", "user_id": "u1"},
            {"id": "r2", "opportunity_id": "remove", "user_id": "u1"},
        ]
        with self.assertRaises(SafetyError):
            build_pair_plan(keep, remove, matches, [], "Expected Title")

    def test_apply_and_backup_only_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as context:
            main(["--apply", "--backup-only"])
        self.assertEqual(context.exception.code, 2)

    def test_backup_round_trip_verifies_counts_pairs_and_ids(self):
        opportunities = [
            {"id": opportunity_id, "title": title}
            for keep_id, remove_id, title in APPROVED_PAIRS
            for opportunity_id in (keep_id, remove_id)
        ]
        matches = [{"id": f"match-{index}"} for index in range(40)]
        path = backup_rows(opportunities, matches, [])
        try:
            counts = verify_backup(path, 20, 40, 0)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(
            counts,
            {"opportunities": 20, "matches": 40, "notifications": 0, "pairs": 10},
        )

    def test_backup_verification_rejects_wrong_counts(self):
        opportunities = [
            {"id": opportunity_id}
            for keep_id, remove_id, _title in APPROVED_PAIRS
            for opportunity_id in (keep_id, remove_id)
        ]
        path = backup_rows(opportunities, [], [])
        try:
            with self.assertRaises(SafetyError):
                verify_backup(path, 20, 40, 0)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
