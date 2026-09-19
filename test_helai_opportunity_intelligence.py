import unittest
from unittest.mock import patch

from collector_service import (
    execute_with_schema_fallback,
    process_announcement,
    protect_reviewed_intelligence,
)
from matcher import calculate_match
from matching_service import opportunity_is_actionable
from opportunity_rules import (
    APPLICANT_COMPANY,
    APPLICANT_INDIVIDUAL,
    APPLICANT_MIXED,
    normalize_applicant_types,
    normalize_record_kind,
)
from test_helai_rules import individual_profile


def extracted(**overrides):
    value = {
        "title": "Test opportunity",
        "organization": "Test organization",
        "type": "Grants",
        "location": "International",
        "status": "Open",
        "record_kind": "application_opportunity",
        "eligible_applicant_types": [],
        "applicant_type": "",
        "education": "Any",
        "languages": [],
        "interests": [],
        "skills": [],
        "notes": "",
    }
    value.update(overrides)
    return value


class OpportunityIntelligenceTests(unittest.TestCase):
    def process(self, **overrides):
        with patch(
            "collector_service.extract_opportunity",
            return_value=extracted(**overrides),
        ):
            return process_announcement("Stored page content")

    def test_unknown_applicant_type_stays_distinguishable(self):
        row = self.process(record_kind="unknown")
        self.assertIsNone(row["applicant_type"])
        self.assertIsNone(row["eligible_applicant_types"])

    def test_eligible_applicant_types_json_normalization(self):
        self.assertEqual(
            normalize_applicant_types(["individual", "student", "bogus"]),
            [APPLICANT_INDIVIDUAL],
        )

    def test_individual_persistence(self):
        row = self.process(eligible_applicant_types=["individual"])
        self.assertEqual(row["applicant_type"], "individual")
        self.assertEqual(row["eligible_applicant_types"], ["individual"])

    def test_entity_persistence(self):
        row = self.process(eligible_applicant_types=["company/business"])
        self.assertEqual(row["applicant_type"], APPLICANT_COMPANY)
        self.assertEqual(row["eligible_applicant_types"], [APPLICANT_COMPANY])

    def test_mixed_persistence(self):
        row = self.process(
            eligible_applicant_types=["individual", "company/business"]
        )
        self.assertEqual(row["applicant_type"], "mixed")
        self.assertEqual(
            row["eligible_applicant_types"],
            [APPLICANT_INDIVIDUAL, APPLICANT_COMPANY],
        )

    def test_informational_record_kind_clears_irrelevant_applicant_type(self):
        row = self.process(
            record_kind="informational",
            eligible_applicant_types=["individual"],
        )
        self.assertEqual(row["record_kind"], "informational")
        self.assertIsNone(row["applicant_type"])
        self.assertIsNone(row["eligible_applicant_types"])

    def test_roundup_and_unknown_record_kinds(self):
        self.assertEqual(normalize_record_kind("roundup"), "roundup")
        self.assertEqual(normalize_record_kind("unexpected"), "unknown")
        self.assertEqual(self.process(record_kind="roundup")["record_kind"], "roundup")
        self.assertEqual(self.process(record_kind="unknown")["record_kind"], "unknown")

    def test_informational_content_cannot_be_actionable(self):
        opportunity = {
            "status": "Open",
            "active": True,
            "record_kind": "informational",
            "type": "Grants",
            "education": "Any",
            "languages": [],
            "interests": [],
            "skills": [],
        }
        result = calculate_match(individual_profile(), opportunity)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["score"], 0)
        self.assertFalse(opportunity_is_actionable(opportunity, True))

    def test_compatibility_switch_does_not_exclude_unknown_yet(self):
        opportunity = {"status": "Open", "active": True, "record_kind": "unknown"}
        self.assertTrue(opportunity_is_actionable(opportunity, False))
        self.assertFalse(opportunity_is_actionable(opportunity, True))

    def test_reviewed_values_are_protected(self):
        existing = {
            "applicant_type": "individual",
            "eligible_applicant_types": ["individual"],
            "applicant_type_reviewed": True,
            "record_kind": "informational",
            "record_kind_reviewed": True,
        }
        incoming = {
            "applicant_type": "company/business",
            "eligible_applicant_types": ["company/business"],
            "applicant_type_reviewed": False,
            "record_kind": "application_opportunity",
            "record_kind_reviewed": False,
        }
        protected = protect_reviewed_intelligence(incoming, existing)
        self.assertEqual(protected["applicant_type"], "individual")
        self.assertEqual(protected["eligible_applicant_types"], ["individual"])
        self.assertEqual(protected["record_kind"], "informational")
        self.assertTrue(protected["applicant_type_reviewed"])
        self.assertTrue(protected["record_kind_reviewed"])

    def test_weaker_empty_extraction_does_not_erase_automated_value(self):
        protected = protect_reviewed_intelligence(
            {"applicant_type": None, "eligible_applicant_types": None, "record_kind": "unknown"},
            {"applicant_type": "individual", "eligible_applicant_types": ["individual"], "record_kind": "application_opportunity"},
        )
        self.assertEqual(protected["applicant_type"], "individual")
        self.assertEqual(protected["record_kind"], "application_opportunity")

    def test_schema_success_keeps_supported_fields(self):
        seen = []
        record = {
            "applicant_type": "individual",
            "eligible_applicant_types": ["individual"],
            "record_kind": "application_opportunity",
        }
        execute_with_schema_fallback(lambda item: seen.append(item) or "ok", record)
        self.assertEqual(seen, [record])

    def test_old_schema_fallback_strips_optional_fields(self):
        seen = []

        def query(item):
            seen.append(item)
            if len(seen) == 1:
                raise RuntimeError("column record_kind does not exist")
            return "ok"

        record = {
            "title": "Legacy compatible",
            "applicant_type": "individual",
            "eligible_applicant_types": ["individual"],
            "record_kind": "application_opportunity",
            "applicant_type_reviewed": False,
            "record_kind_reviewed": False,
        }
        execute_with_schema_fallback(query, record)
        self.assertEqual(seen[-1], {"title": "Legacy compatible"})


if __name__ == "__main__":
    unittest.main()
