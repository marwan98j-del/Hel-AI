import unittest

from matcher import calculate_match
from opportunity_rules import (
    APPLICANT_COMPANY,
    APPLICANT_GOVERNMENT,
    APPLICANT_INDIVIDUAL,
    APPLICANT_MIXED,
    APPLICANT_ORGANIZATION,
    APPLICANT_UNIVERSITY,
    create_fingerprint,
    get_eligible_applicant_types,
    normalize_deadline,
    normalize_open_date,
    normalize_status,
    normalize_url,
    applicant_types_are_entity_only,
)


def individual_profile():
    return {
        "age": 22,
        "city": "Erbil",
        "education": "Bachelor's Degree",
        "grade": 90,
        "work_experience_years": 1,
        "languages": ["English"],
        "skills": ["Research", "Data Analysis"],
        "interests": ["Education", "Health"],
        "opportunity_types": ["Scholarships", "Grants"],
        "has_passport": True,
        "has_ielts": True,
        "has_portfolio": False,
        "has_cv": True,
        "applicant_type": APPLICANT_INDIVIDUAL,
    }


class HelAIRulesTest(unittest.TestCase):
    def test_individual_scholarship_can_be_eligible(self):
        opportunity = {
            "title": "Global Student Scholarship",
            "type": "Scholarships",
            "status": "Open",
            "education": "High School",
            "education_rule": "minimum",
            "languages": ["English"],
            "interests": ["Education"],
            "skills": [],
            "eligible_applicant_types": [
                APPLICANT_INDIVIDUAL,
            ],
        }

        result = calculate_match(
            individual_profile(),
            opportunity,
        )

        self.assertTrue(result["eligible"])

    def test_organization_only_ukri_blocks_individual(self):
        opportunity = {
            "title": (
                "UKRI Medicines Manufacturing Data "
                "Institute: Phase 1"
            ),
            "type": "Grants",
            "status": "Open",
            "education": "Any",
            "languages": [],
            "interests": ["Health"],
            "skills": ["Research"],
            "original_text": (
                "This funding opportunity is for eligible "
                "research organisations. Research organisations "
                "eligible to apply must submit the proposal."
            ),
        }

        result = calculate_match(
            individual_profile(),
            opportunity,
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "organizations or institutions",
            " ".join(result["eligibility_gaps"]),
        )

    def test_government_institution_grant_blocks_individual(self):
        opportunity = {
            "title": (
                "Cancer Prevention and Control Programs "
                "for State, Territorial, and Tribal Organizations"
            ),
            "type": "Grants",
            "status": "Open",
            "education": "Any",
            "languages": [],
            "interests": ["Health"],
            "skills": [],
            "eligible_applicant_types": [
                APPLICANT_GOVERNMENT,
            ],
        }

        result = calculate_match(
            individual_profile(),
            opportunity,
        )

        self.assertFalse(result["eligible"])

    def test_forecasted_grants_status_becomes_upcoming(self):
        self.assertEqual(
            normalize_status("Forecasted"),
            "Upcoming",
        )

        opportunity = {
            "title": "Forecasted Grant",
            "type": "Grants",
            "status": normalize_status("Forecasted"),
            "education": "Any",
            "languages": [],
            "interests": ["Health"],
            "skills": [],
        }

        result = calculate_match(
            individual_profile(),
            opportunity,
        )

        self.assertEqual(result["score"], 0)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["readiness"], 0)
        self.assertIn(
            "not open yet",
            " ".join(result["eligibility_gaps"]),
        )
        self.assertEqual(opportunity["status"], "Upcoming")

    def test_unknown_status_is_not_actionable(self):
        opportunity = {
            "title": "Unknown Status Grant",
            "type": "Grants",
            "status": "Unknown",
            "education": "Any",
            "languages": [],
            "interests": [],
            "skills": [],
        }

        result = calculate_match(
            individual_profile(),
            opportunity,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["score"], 0)

    def test_open_date_is_not_deadline(self):
        text = (
            "Applications accepted anytime starting "
            "2026-01-15. There is no closing date."
        )

        self.assertEqual(
            normalize_open_date("", text),
            "2026-01-15",
        )
        self.assertIsNone(
            normalize_deadline(text, "")
        )

    def test_real_deadline_is_preserved(self):
        text = (
            "Applications open on 2026-01-15. "
            "Application deadline: 2026-03-01."
        )

        self.assertEqual(
            normalize_deadline("", text),
            "2026-03-01",
        )

    def test_duplicate_identity_uses_normalized_url_external_id_and_fingerprint(self):
        title = "Engineering Biology Access to Infrastructure Pilot"
        url_a = (
            "https://www.ukri.org/opportunity/example/?utm_source=x#section"
        )
        url_b = "https://www.ukri.org/opportunity/example"

        self.assertEqual(
            normalize_url(url_a),
            normalize_url(url_b),
        )
        self.assertEqual(
            create_fingerprint(title, url_a, "UKRI-123"),
            create_fingerprint(title, url_b, "UKRI-123"),
        )

    def test_applicant_type_text_detection_does_not_promote_partner(self):
        opportunity = {
            "original_text": (
                "Small businesses may apply with a university "
                "research institution partner."
            )
        }

        applicant_types = get_eligible_applicant_types(
            opportunity
        )

        self.assertIn(
            APPLICANT_COMPANY,
            applicant_types,
        )
        self.assertNotIn(APPLICANT_UNIVERSITY, applicant_types)

    def assert_entity_only_text(self, text):
        types = get_eligible_applicant_types({"original_text": text})
        self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_explicit_institutional_submission_language_is_entity_only(self):
        examples = [
            "Unaffiliated individuals are not eligible.",
            "Individuals are not eligible to apply.",
            "Eligible submitters include universities and other institutions.",
            "The submitting organization must certify the proposal.",
            "The proposal must be approved by the Authorized Organizational Representative before submission.",
        ]
        for text in examples:
            with self.subTest(text=text):
                self.assert_entity_only_text(text)

    def test_host_university_does_not_make_individual_program_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Selected fellows will live at the host university. "
                    "The university is a program partner and sponsor."
                )
            }
        )
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_sponsor_company_or_foundation_does_not_make_program_company_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "The fellowship is sponsored by Example Company and "
                    "Example Foundation for individual students."
                )
            }
        )
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_individual_nsf_fellowship_remains_individual_facing(self):
        opportunity = {
            "title": "NSF Graduate Research Fellowship Program",
            "organization": "U.S. National Science Foundation",
            "original_text": (
                "Eligible applicants include senior undergraduates and "
                "graduate students. The fellowship is offered to the individual."
            ),
        }
        types = get_eligible_applicant_types(opportunity)
        self.assertIn(APPLICANT_INDIVIDUAL, types)
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_generic_government_employer_words_do_not_make_fellowship_government_only(self):
        opportunity = {
            "original_text": (
                "Eligible applicants are African women scientists working in "
                "government agencies, academia, NGOs, or the private sector."
            )
        }
        types = get_eligible_applicant_types(opportunity)
        self.assertNotIn(APPLICANT_GOVERNMENT, types)
        self.assertIn(APPLICANT_INDIVIDUAL, types)
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_program_explicitly_for_government_organizations_is_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Forecasted opportunity for state, territorial, and "
                    "tribal organizations."
                )
            }
        )
        self.assertIn(APPLICANT_GOVERNMENT, types)
        self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_generic_small_business_story_does_not_make_article_company_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Perhaps you work with small businesses but need stronger "
                    "knowledge of finance."
                )
            }
        )
        self.assertNotIn(APPLICANT_COMPANY, types)
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_eligibility_section_startup_requirement_is_company_only(self):
        text = (
            "Eligibility. To be considered for the competition, startups "
            "must meet the following criteria. The company must be operating "
            "in Ontario."
        )
        types = get_eligible_applicant_types({"original_text": text})
        self.assertIn(APPLICANT_COMPANY, types)
        self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_company_must_requires_eligibility_context(self):
        generic = get_eligible_applicant_types(
            {"original_text": "The company must improve its products this year."}
        )
        contextual = get_eligible_applicant_types(
            {
                "original_text": (
                    "Eligibility. Applicants enter the competition online. "
                    "The company must be operating in Ontario."
                )
            }
        )
        self.assertNotIn(APPLICANT_COMPANY, generic)
        self.assertIn(APPLICANT_COMPANY, contextual)

    def test_applicant_based_at_eligible_research_organization_is_entity_only(self):
        examples = [
            "Applicants must be based at a UK research organisation eligible for EPSRC funding.",
            "Applicants must be based at an eligible research institution.",
        ]
        for text in examples:
            with self.subTest(text=text):
                types = get_eligible_applicant_types({"original_text": text})
                self.assertIn(APPLICANT_UNIVERSITY, types)
                self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_researcher_based_at_eligible_organization_remains_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Applicants must be researchers or research technical "
                    "professionals based at a UK research organisation eligible "
                    "for BBSRC funding."
                )
            }
        )
        self.assertNotIn(APPLICANT_INDIVIDUAL, types)
        self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_researcher_employed_by_eligible_organization_remains_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Applicants must be researchers employed by eligible UK "
                    "research organisations. Only the lead research organisation "
                    "can submit an application."
                )
            }
        )
        self.assertNotIn(APPLICANT_INDIVIDUAL, types)
        self.assertTrue(applicant_types_are_entity_only(types), types)

    def test_generic_research_organization_partner_is_not_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "A research organization is a delivery partner and provides "
                    "mentors to selected fellows."
                )
            }
        )
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_personal_age_degree_and_citizenship_requirements_are_individual(self):
        examples = [
            "Applicants must be aged 18 to 35.",
            "Applicants must hold a master's degree.",
            "Applicants must be Ugandan citizens or refugees.",
        ]
        for text in examples:
            with self.subTest(text=text):
                types = get_eligible_applicant_types({"original_text": text})
                self.assertIn(APPLICANT_INDIVIDUAL, types)
                self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_open_to_explicit_people_roles_is_individual(self):
        for role in ("journalists", "students", "mid-career professionals"):
            with self.subTest(role=role):
                types = get_eligible_applicant_types(
                    {"original_text": f"Applications are open to {role}."}
                )
                self.assertIn(APPLICANT_INDIVIDUAL, types)

    def test_explicit_individuals_and_organizations_is_mixed(self):
        types = get_eligible_applicant_types(
            {"original_text": "Individuals and organizations may apply."}
        )
        self.assertIn(APPLICANT_INDIVIDUAL, types)
        self.assertIn(APPLICANT_ORGANIZATION, types)
        self.assertIn(APPLICANT_MIXED, types)
        self.assertFalse(applicant_types_are_entity_only(types), types)

    def test_mps_astronomy_wording_does_not_become_entity_only(self):
        types = get_eligible_applicant_types(
            {
                "original_text": (
                    "Supports individual investigators and collaborative research "
                    "projects. The university is a program partner."
                )
            }
        )
        self.assertFalse(applicant_types_are_entity_only(types), types)


if __name__ == "__main__":
    unittest.main()
