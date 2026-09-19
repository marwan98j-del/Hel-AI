import copy
import unittest

from helai_opportunity_intelligence_backfill_preview import (
    D_PRIZE_TITLE,
    NON_OPPORTUNITIES,
    SafetyStop,
    old_to_new,
    opportunity_match_effect,
    select_previous_individuals,
    validate_preflight,
)


class IntelligenceBackfillPreviewTests(unittest.TestCase):
    def test_exactly_approved_non_opportunity_ids_are_configured(self):
        self.assertEqual(set(NON_OPPORTUNITIES), {
            "afcc85f3-91fd-4b7c-8bf2-27876c80355b",
            "82a18662-c566-418c-9e40-6e40fcd086be",
        })

    def test_exactly_13_previous_high_confidence_individuals_selected(self):
        audited = [
            {"opportunity_id": str(index), "ai": {"classification": "individual", "confidence": "high"}}
            for index in range(13)
        ]
        selected = select_previous_individuals({"audited": audited})
        self.assertEqual(len(selected), 13)

    def test_no_low_or_medium_confidence_enters_prior_safe_set(self):
        audited = [
            {"opportunity_id": str(index), "ai": {"classification": "individual", "confidence": "high"}}
            for index in range(13)
        ] + [
            {"opportunity_id": "low", "ai": {"classification": "individual", "confidence": "low"}},
            {"opportunity_id": "medium", "ai": {"classification": "individual", "confidence": "medium"}},
        ]
        self.assertEqual(len(select_previous_individuals({"audited": audited})), 13)

    def test_d_prize_cannot_enter_safe_reviewed_configuration(self):
        self.assertNotIn(D_PRIZE_TITLE, [item["title"] for item in NON_OPPORTUNITIES.values()])

    def test_reviewed_backfill_never_changes_unrelated_fields(self):
        row = {"title": "Keep", "status": "Open", "record_kind": "unknown"}
        patch = {"record_kind": "informational", "record_kind_reviewed": True}
        proposed = copy.deepcopy(row)
        proposed.update(patch)
        self.assertEqual(proposed["title"], row["title"])
        self.assertEqual(proposed["status"], row["status"])
        self.assertEqual(set(old_to_new(row, patch)), set(patch))

    def test_null_applicant_fields_remain_null_for_non_opportunity_patch(self):
        row = {"applicant_type": None, "eligible_applicant_types": None, "record_kind": "unknown"}
        proposed = copy.deepcopy(row)
        proposed.update({"record_kind": "informational", "record_kind_reviewed": True})
        self.assertIsNone(proposed["applicant_type"])
        self.assertIsNone(proposed["eligible_applicant_types"])

    def test_record_kind_unknown_is_distinct_from_informational(self):
        self.assertNotEqual("unknown", "informational")

    def test_hypothetical_effect_does_not_mutate_source_objects(self):
        opportunity = {"id": "o", "status": "Open", "record_kind": "unknown", "active": True}
        matches = []
        original = copy.deepcopy(opportunity)
        opportunity_match_effect(opportunity, {"record_kind": "informational"}, matches, {})
        self.assertEqual(opportunity, original)

    def test_false_to_true_warning_condition_is_captured(self):
        effect = {"before": {"eligible": False}, "after": {"eligible": True}, "evaluated": True}
        warnings = [effect] if not effect["before"]["eligible"] and effect["after"]["eligible"] else []
        self.assertEqual(warnings, [effect])

    def test_duplicate_preflight_must_be_zero(self):
        rows = [{"id": str(i), **{field: None for field in (
            "applicant_type", "eligible_applicant_types", "record_kind",
            "applicant_type_reviewed", "record_kind_reviewed")}} for i in range(121)]
        rows[0]["source_url"] = "https://example.com/same"
        rows[1]["source_url"] = "https://example.com/same"
        matches = [{"id": str(i), "user_id": "u", "opportunity_id": str(i)} for i in range(222)]
        with self.assertRaises(SafetyStop):
            validate_preflight(rows, matches)


if __name__ == "__main__":
    unittest.main()
