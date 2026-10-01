import ast
import unittest
from datetime import date
from functools import partial
from pathlib import Path

from helai_ui import card_status, result_kpis, result_sort_key


TODAY = date(2026, 10, 1)


def match(score, eligible=True, readiness=100):
    return {"score": score, "eligible": eligible, "readiness": readiness}


class HelAICardStatusTests(unittest.TestCase):
    def test_status_aliases_are_normalized(self):
        cases = {
            "active": ("Open", "open"),
            "posted": ("Open", "open"),
            "expired": ("Closed", "closed"),
            "archived": ("Closed", "closed"),
            "forecasted": ("Upcoming", "upcoming"),
            " OPEN ": ("Open", "open"),
        }
        for stored, expected in cases.items():
            with self.subTest(stored=stored):
                self.assertEqual(card_status({"status": stored}, today=TODAY), expected)

    def test_open_with_past_deadline_shows_closed(self):
        opportunity = {"status": "Open", "deadline": "2026-09-30"}
        self.assertEqual(card_status(opportunity, today=TODAY), ("Closed", "closed"))

    def test_deadline_day_is_still_open(self):
        opportunity = {"status": "active", "deadline": "2026-10-01"}
        self.assertEqual(card_status(opportunity, today=TODAY), ("Open", "open"))

    def test_missing_or_invalid_deadline_keeps_stored_status(self):
        for deadline in (None, "", "rolling"):
            with self.subTest(deadline=deadline):
                opportunity = {"status": "Open", "deadline": deadline}
                self.assertEqual(card_status(opportunity, today=TODAY), ("Open", "open"))

    def test_unknown_status_uses_review_badge(self):
        for stored in (None, "", "pending"):
            with self.subTest(stored=stored):
                self.assertEqual(card_status({"status": stored}, today=TODAY), ("Unknown", "review"))


class HelAIResultSummaryTests(unittest.TestCase):
    def setUp(self):
        self.live = ({"title": "live", "status": "Open", "deadline": "2026-12-01"}, match(40))
        self.alias = ({"title": "alias", "status": "active"}, match(30, readiness=50))
        # The opportunity rows store Open, but the deadline has passed; values
        # in the match dicts are deliberately high so only status can explain
        # the ordering and counts below.
        self.expired = ({"title": "expired", "status": "Open", "deadline": "2026-09-30"}, match(99))
        self.closed = ({"title": "closed", "status": "Closed"}, match(50))

    def test_expired_stored_open_is_not_counted_as_open(self):
        kpis = result_kpis([self.live, self.alias, self.expired, self.closed], today=TODAY)
        self.assertEqual(kpis, {"open": 2, "eligible": 2, "ready": 1, "best_score": 40})

    def test_expired_stored_open_sorts_with_closed_records(self):
        results = [self.expired, self.closed, self.alias, self.live]
        results.sort(key=partial(result_sort_key, today=TODAY), reverse=True)
        titles = [opportunity["title"] for opportunity, _ in results]
        self.assertEqual(titles[:2], ["live", "alias"])
        self.assertEqual(set(titles[2:]), {"expired", "closed"})
        self.assertEqual(result_sort_key(self.expired, today=TODAY)[0], False)
        self.assertEqual(result_sort_key(self.closed, today=TODAY)[0], False)

    def test_no_open_results_gives_zero_kpis(self):
        kpis = result_kpis([self.expired, self.closed], today=TODAY)
        self.assertEqual(kpis, {"open": 0, "eligible": 0, "ready": 0, "best_score": 0})

    def test_app_uses_effective_status_helpers_for_sort_and_kpis(self):
        tree = ast.parse(Path(__file__).with_name("app.py").read_text(encoding="utf-8"))
        calls = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertIn("results.sort(key=result_sort_key, reverse=True)", calls)
        self.assertIn("result_kpis(results)", calls)
        normalize_calls = [call for call in calls if call.startswith("normalize_status(")]
        self.assertEqual(len(normalize_calls), 1)
        self.assertIn("extracted.get('status')", normalize_calls[0])


if __name__ == "__main__":
    unittest.main()
