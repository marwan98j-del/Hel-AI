import unittest
from pathlib import Path

from helai_ui import NO_DOCUMENT_REQUIREMENTS, readiness_display
from matcher import calculate_match
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    get_eligible_applicant_types,
    opportunity_is_non_actionable,
)
from test_helai_rules import individual_profile


UNCONFIRMED_GAP = "Applicant eligibility could not be confirmed"


def open_opportunity(**fields):
    opportunity = {
        "status": "Open",
        "type": "Grants",
        "education": "Any",
        "languages": [],
        "interests": [],
        "skills": [],
        "record_kind": "unknown",
    }
    opportunity.update(fields)
    return opportunity


class FailClosedApplicantTypeTests(unittest.TestCase):
    # Real Grants.gov rows: the scraped text is only the API summary plus the
    # .gov banner, so no applicant type can be extracted or inferred.
    GRANTS_GOV_TITLES = (
        "Small Business Transportation Technical Assistance Center (Region 1)",
        "Fiscal Year (FY) 2027 Service Area Competition (SAC)",
        "The DOE Quantum Genesis Q Competition",
    )

    def test_grants_gov_with_unknown_applicant_type_is_not_eligible(self):
        for title in self.GRANTS_GOV_TITLES:
            with self.subTest(title=title):
                opportunity = open_opportunity(
                    title=title,
                    source="Grants.gov",
                    original_text=(
                        f"Title: {title}\nStatus: posted\n\n"
                        "Official websites use .gov A .gov website belongs "
                        "to an official government organization in the "
                        "United States."
                    ),
                )
                self.assertEqual(get_eligible_applicant_types(opportunity), [])
                result = calculate_match(individual_profile(), opportunity)
                self.assertFalse(result["eligible"])
                self.assertIn(UNCONFIRMED_GAP, result["eligibility_gaps"])

    def test_nsf_with_unknown_applicant_type_is_not_eligible(self):
        opportunity = open_opportunity(
            title="Emerging Frontiers in Research and Innovation (EFRI): Wave-Based Computing (WBC)",
            source="NSF",
        )
        result = calculate_match(individual_profile(), opportunity)
        self.assertFalse(result["eligible"])
        self.assertIn(UNCONFIRMED_GAP, result["eligibility_gaps"])

    def test_individual_nsf_fellowship_stays_eligible(self):
        opportunity = open_opportunity(
            title="NSF Graduate Research Fellowship Program (GRFP)",
            source="NSF",
            type="Fellowships",
            eligible_applicant_types=[APPLICANT_INDIVIDUAL],
        )
        result = calculate_match(individual_profile(), opportunity)
        self.assertTrue(result["eligible"])
        self.assertNotIn(UNCONFIRMED_GAP, result["eligibility_gaps"])

    def test_other_sources_with_unknown_applicant_type_are_unchanged(self):
        opportunity = open_opportunity(
            title="Maple Global Innovation Fellowship 2026",
            source="Opportunity Desk",
            type="Fellowships",
        )
        result = calculate_match(individual_profile(), opportunity)
        self.assertTrue(result["eligible"])
        self.assertNotIn(UNCONFIRMED_GAP, result["eligibility_gaps"])

    def test_student_training_wording_is_not_individual(self):
        # Real NSF MPS Astro wording that used to match \bfor students?\b.
        types = get_eligible_applicant_types(
            {
                "title": "MPS Astronomical Sciences Research Programs (MPS Astro)",
                "original_text": (
                    "Proposals may include a plan for student training and "
                    "STEM workforce development."
                ),
            }
        )
        self.assertNotIn(APPLICANT_INDIVIDUAL, types)

    def test_for_students_wording_is_still_individual(self):
        types = get_eligible_applicant_types(
            {"original_text": "A summer programme for students in Erbil."}
        )
        self.assertIn(APPLICANT_INDIVIDUAL, types)


class RoundupTitleTests(unittest.TestCase):
    NON_ACTIONABLE_TITLES = (
        "69 Master’s and PhD Scholarships and Fellowships You Can Apply for Now – October",
        "30 Masters, Ph.D and Other Scholarship Opportunities Currently Open – September",
        "How to Write a Winning Mastercard Foundation Scholarship Essay",
    )

    ACTIONABLE_TITLES = (
        "Chevening Scholarship Iraq 2027-2028",
        "UBA National Essay Competition 2026",
        "Maple Global Innovation Fellowship 2026",
        "Fiscal Year (FY) 2027 Service Area Competition (SAC)",
        "2027 Global Fellowships Programme",
    )

    def test_roundup_titles_with_unknown_kind_are_not_scored(self):
        for title in self.NON_ACTIONABLE_TITLES:
            with self.subTest(title=title):
                opportunity = open_opportunity(title=title, type="Scholarships")
                self.assertTrue(opportunity_is_non_actionable(opportunity))
                result = calculate_match(individual_profile(), opportunity)
                self.assertFalse(result["eligible"])
                self.assertEqual(result["score"], 0)

    def test_real_opportunity_titles_are_still_actionable(self):
        for title in self.ACTIONABLE_TITLES:
            with self.subTest(title=title):
                self.assertFalse(
                    opportunity_is_non_actionable(open_opportunity(title=title))
                )

    def test_explicit_application_kind_overrides_title(self):
        opportunity = open_opportunity(
            title=self.NON_ACTIONABLE_TITLES[0],
            record_kind="application_opportunity",
        )
        self.assertFalse(opportunity_is_non_actionable(opportunity))

    def test_extractor_prompt_has_no_unknown_record_kind_default(self):
        source = Path(__file__).with_name("ai_extractor.py").read_text(encoding="utf-8")
        self.assertNotIn('"record_kind": "unknown"', source)
        self.assertIn('"record_kind": ""', source)


class ReadinessDisplayTests(unittest.TestCase):
    def test_no_document_flags_is_not_shown_as_100_percent(self):
        opportunity = {"title": "Data Science Corps (DSC)"}
        label, _ = readiness_display(opportunity, {"readiness": 100}, lang="en")
        self.assertEqual(label, NO_DOCUMENT_REQUIREMENTS)

    def test_false_document_flags_count_as_none(self):
        opportunity = {
            "title": "Maple Global Innovation Fellowship 2026",
            "requires_passport": False,
            "requires_ielts": False,
            "requires_portfolio": False,
            "requires_cv": False,
        }
        label, _ = readiness_display(opportunity, {"readiness": 100}, lang="en")
        self.assertEqual(label, NO_DOCUMENT_REQUIREMENTS)

    def test_tracked_documents_show_percentage(self):
        opportunity = {"title": "Chevening Scholarship Iraq 2027-2028", "requires_cv": True}
        self.assertEqual(
            readiness_display(opportunity, {"readiness": 100}, lang="en"),
            ("100%", "success"),
        )
        self.assertEqual(
            readiness_display(
                {"requires_ielts": True, "requires_cv": True},
                {"readiness": 50},
                lang="en",
            ),
            ("50%", "warning"),
        )


if __name__ == "__main__":
    unittest.main()
