import unittest
from datetime import date
from unittest.mock import patch

from matcher import calculate_match
from matching_service import opportunity_is_actionable
from notification_service import create_notification
from opportunity_rules import effective_status
from test_helai_rules import individual_profile


REFERENCE_DATE = date(2026, 9, 19)


def opportunity(**overrides):
    row = {
        "id": "o1",
        "title": "Test opportunity",
        "status": "Open",
        "active": True,
        "deadline": "2026-09-20",
        "record_kind": "unknown",
        "type": "Grants",
        "education": "Any",
        "languages": [],
        "interests": [],
        "skills": [],
    }
    row.update(overrides)
    return row


class EffectiveStatusTests(unittest.TestCase):
    def test_open_yesterday_is_effectively_closed(self):
        self.assertEqual(
            effective_status(opportunity(deadline="2026-09-18"), REFERENCE_DATE),
            "Closed",
        )

    def test_deadline_today_is_inclusively_open(self):
        self.assertEqual(
            effective_status(opportunity(deadline="2026-09-19"), REFERENCE_DATE),
            "Open",
        )

    def test_future_deadline_is_open(self):
        self.assertEqual(
            effective_status(opportunity(deadline="2026-09-20"), REFERENCE_DATE),
            "Open",
        )

    def test_closed_with_future_deadline_stays_closed(self):
        self.assertEqual(
            effective_status(opportunity(status="Closed", deadline="2027-01-01"), REFERENCE_DATE),
            "Closed",
        )

    def test_missing_or_invalid_deadline_preserves_status(self):
        self.assertEqual(effective_status(opportunity(deadline=None), REFERENCE_DATE), "Open")
        self.assertEqual(effective_status(opportunity(deadline="not-a-date"), REFERENCE_DATE), "Open")
        self.assertEqual(effective_status(opportunity(deadline="2026-02-31"), REFERENCE_DATE), "Open")

    def test_explicit_reference_date_is_deterministic(self):
        row = opportunity(deadline="2026-09-18")
        self.assertEqual(effective_status(row, date(2026, 9, 18)), "Open")
        self.assertEqual(effective_status(row, date(2026, 9, 19)), "Closed")

    def test_matcher_returns_ineligible_zero_zero_for_expired_open(self):
        result = calculate_match(
            individual_profile(), opportunity(deadline="2026-09-18"), REFERENCE_DATE
        )
        self.assertFalse(result["eligible"])
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["readiness"], 0)

    def test_matching_service_excludes_expired_stored_open(self):
        self.assertFalse(
            opportunity_is_actionable(
                opportunity(deadline="2026-09-18"), reference_date=REFERENCE_DATE
            )
        )

    def test_notification_creation_excludes_expired_stored_open(self):
        expired = opportunity(deadline="2026-09-18")
        with (
            patch("notification_service.notification_exists", return_value=False),
            patch("notification_service.load_profile", return_value={
                "email": "person@example.com", "email_notifications": True
            }),
            patch("notification_service.load_opportunity", return_value=expired),
            patch("notification_service.effective_status", return_value="Closed"),
        ):
            result = create_notification({"id": "m1", "user_id": "u1", "opportunity_id": "o1"})
        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "Opportunity is not open.")

    def test_known_expired_regressions(self):
        for title, deadline in (
            ("Mathematics in Africa Grant 2026", "2026-09-15"),
            ("AI Olympiad Kurdistan 2026", "2026-09-11"),
        ):
            with self.subTest(title=title):
                self.assertEqual(
                    effective_status(opportunity(title=title, deadline=deadline), REFERENCE_DATE),
                    "Closed",
                )


if __name__ == "__main__":
    unittest.main()
