import unittest

from helai_matching_preview import (
    PreviewSafetyError,
    backup_matches,
    build_preview,
    changed_fields,
    result_fields,
    verify_match_backup,
)


class MatchingPreviewTests(unittest.TestCase):
    def test_result_fields_maps_matcher_output_without_notification_metadata(self):
        fields = result_fields(
            {
                "score": 71.6,
                "eligible": True,
                "readiness": 50,
                "reasons": ["reason"],
                "eligibility_gaps": [],
                "readiness_gaps": ["gap"],
            }
        )
        self.assertEqual(fields["match_score"], 72)
        self.assertNotIn("notified", fields)
        self.assertNotIn("notified_at", fields)

    def test_changed_fields_reports_only_derived_differences(self):
        old = {"match_score": 50, "eligible": True, "readiness": 100, "reasons": [], "eligibility_gaps": [], "readiness_gaps": []}
        new = dict(old, eligible=False, match_score=0)
        self.assertEqual(set(changed_fields(old, new)), {"match_score", "eligible"})

    def test_preview_blocks_upcoming_and_entity_only_for_individual(self):
        profiles = [{"id": "u1", "profile_complete": True, "date_of_birth": "2000-01-01", "education": "Bachelor's Degree"}]
        opportunities = [
            {"id": "up", "title": "Upcoming", "status": "Upcoming", "active": True, "type": "Grants", "education": "Any", "languages": [], "interests": [], "skills": []},
            {"id": "entity", "title": "Entity", "status": "Open", "active": True, "type": "Grants", "education": "Any", "languages": [], "interests": [], "skills": [], "eligible_applicant_types": ["government entity"]},
        ]
        matches = [
            {"id": "m1", "user_id": "u1", "opportunity_id": "up", "match_score": 50, "eligible": True, "readiness": 100, "reasons": [], "eligibility_gaps": [], "readiness_gaps": []},
            {"id": "m2", "user_id": "u1", "opportunity_id": "entity", "match_score": 50, "eligible": True, "readiness": 100, "reasons": [], "eligibility_gaps": [], "readiness_gaps": []},
        ]
        preview = build_preview(profiles, opportunities, matches)
        changes = {row["opportunity_id"]: row for row in preview["changed_matches"]}
        self.assertFalse(changes["up"]["new"]["eligible"])
        self.assertEqual(changes["up"]["new"]["match_score"], 0)
        self.assertFalse(changes["entity"]["new"]["eligible"])
        self.assertEqual(preview["entity_eligible_errors"], [])

    def test_backup_round_trip_verifies_ids_and_counts(self):
        rows = [
            {"id": "m1", "user_id": "u1", "opportunity_id": "o1"},
            {"id": "m2", "user_id": "u2", "opportunity_id": "o1"},
        ]
        path = backup_matches(rows)
        try:
            summary = verify_match_backup(path, rows)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(summary["total_matches"], 2)
        self.assertEqual(summary["unique_users"], 2)
        self.assertEqual(summary["unique_opportunities"], 1)


if __name__ == "__main__":
    unittest.main()
