import unittest

from matcher import (
    INTEREST_OVERLAP_FLOOR,
    MISSING_DATA_POINTS,
    SKILL_OVERLAP_FLOOR,
    calculate_location_relevance,
    calculate_match,
)
from test_helai_rules import individual_profile


def opportunity(**fields):
    base = {
        "title": "Data Science Corps (DSC)",
        "status": "Open",
        "type": "Grants",
        "education": "Any",
        "languages": [],
        "interests": [],
        "skills": [],
        "location": "",
        "eligible_applicant_types": ["individual"],
    }
    base.update(fields)
    return base


def score(**fields):
    return calculate_match(individual_profile(), opportunity(**fields))["score"]


# Long lists from real opportunities: one overlap used to earn 30/13 or 25/15.
THIRTEEN_INTERESTS = ["Education"] + [f"Interest {n}" for n in range(12)]
FIFTEEN_SKILLS = ["Research"] + [f"Skill {n}" for n in range(14)]


class MissingDataScoreTests(unittest.TestCase):
    def test_empty_record_no_longer_scores_62(self):
        # Type match 25 + three missing components at 5 each.
        self.assertEqual(score(), 40)

    def test_missing_values_stay_below_smallest_real_evidence(self):
        self.assertLess(MISSING_DATA_POINTS, 8)
        self.assertLess(MISSING_DATA_POINTS, INTEREST_OVERLAP_FLOOR)
        self.assertLess(MISSING_DATA_POINTS, SKILL_OVERLAP_FLOOR)

    def test_missing_location_is_neutral_and_below_a_mismatch(self):
        profile = individual_profile()
        missing, _ = calculate_location_relevance(profile, {"location": ""})
        mismatch, _ = calculate_location_relevance(profile, {"location": "Nairobi, Kenya"})
        self.assertEqual(missing, MISSING_DATA_POINTS)
        self.assertEqual(mismatch, 8)
        self.assertGreater(score(location="Nairobi, Kenya"), score())


class EvidenceFloorTests(unittest.TestCase):
    def test_one_interest_in_a_long_list_beats_no_interest_list(self):
        self.assertGreater(score(interests=THIRTEEN_INTERESTS), score())
        # 25 + 5 + 7.5 + 5 = 42.5, rounded to even.
        self.assertEqual(score(interests=THIRTEEN_INTERESTS), 42)

    def test_one_skill_in_a_long_list_beats_no_skill_list(self):
        self.assertGreater(score(skills=FIFTEEN_SKILLS), score())
        # 25 + 5 + 5 + 6.25 = 41.25.
        self.assertEqual(score(skills=FIFTEEN_SKILLS), 41)

    def test_floor_does_not_cap_strong_overlap(self):
        # Full interest (30) and skill (25) overlap, location in the user's city (20).
        self.assertEqual(
            score(
                location="Erbil",
                interests=["Education", "Health"],
                skills=["Research", "Data Analysis"],
            ),
            100,
        )

    def test_listed_but_unmatched_scores_below_missing(self):
        # Real evidence of no overlap earns 0, less than unknown (5).
        self.assertLess(
            score(interests=["Agriculture"], skills=["Welding"]),
            score(),
        )


if __name__ == "__main__":
    unittest.main()
