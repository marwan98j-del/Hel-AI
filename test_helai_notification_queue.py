import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import notification_service


TODAY = date.today()
FUTURE = (TODAY + timedelta(days=30)).isoformat()
PAST = (TODAY - timedelta(days=7)).isoformat()


def opportunity(opportunity_id="o1", status="Open", deadline=FUTURE):
    return {
        "id": opportunity_id,
        "title": f"Opportunity {opportunity_id}",
        "status": status,
        "deadline": deadline,
        "source_url": "https://example.com/opportunity",
    }


def match(match_id, opportunity_id):
    return {
        "id": match_id,
        "user_id": "u1",
        "opportunity_id": opportunity_id,
        "match_score": 80,
        "eligible": True,
        "notified": False,
    }


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.action = "select"
        self.payload = None
        self.ids = None

    def select(self, _fields="*"):
        return self

    def in_(self, _column, values):
        self.ids = list(values)
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _count):
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def execute(self):
        self.client.calls.append((self.table, self.action, self.payload, self.ids))
        if self.table == "opportunities":
            return SimpleNamespace(data=[
                record for record in self.client.opportunities if record["id"] in (self.ids or [])
            ])
        if self.action == "insert":
            return SimpleNamespace(data=[dict(self.payload, id="n1")])
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self, opportunities=()):
        self.opportunities = list(opportunities)
        self.calls = []

    def table(self, name):
        return _Query(self, name)


class ExpiredCountTests(unittest.TestCase):
    def test_closed_opportunities_are_left_out_of_the_count(self):
        client = _Client([opportunity("open"), opportunity("gone", deadline=PAST)])
        candidates = [match("m1", "open"), match("m2", "gone"), match("m3", "gone")]
        with (
            patch.object(notification_service, "collector_supabase", client),
            patch("notification_service.load_notification_candidates", return_value=candidates),
            patch("notification_service.create_notification", return_value={"created": False, "reason": "x"}) as create,
        ):
            result = notification_service.build_notification_queue()

        self.assertEqual(result["strong_new_matches"], 1)
        self.assertEqual(result["expired"], 2)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual([call.args[0]["id"] for call in create.call_args_list], ["m1"])

    def test_one_lookup_for_all_candidates(self):
        client = _Client([opportunity("a"), opportunity("b")])
        with patch.object(notification_service, "collector_supabase", client):
            current, expired = notification_service.split_expired(
                [match("m1", "a"), match("m2", "b"), match("m3", "a")]
            )
        self.assertEqual(len(current), 3)
        self.assertEqual(expired, [])
        lookups = [call for call in client.calls if call[0] == "opportunities"]
        self.assertEqual(len(lookups), 1)
        self.assertEqual(sorted(lookups[0][3]), ["a", "b"])

    def test_missing_opportunity_still_reaches_create_notification(self):
        client = _Client([])
        with patch.object(notification_service, "collector_supabase", client):
            current, expired = notification_service.split_expired([match("m1", "missing")])
        self.assertEqual([record["id"] for record in current], ["m1"])
        self.assertEqual(expired, [])

    def test_no_candidates_means_no_lookup(self):
        client = _Client([])
        with patch.object(notification_service, "collector_supabase", client):
            self.assertEqual(notification_service.split_expired([]), ([], []))
        self.assertEqual(client.calls, [])


class NotOpenReasonTests(unittest.TestCase):
    def test_passed_deadline_names_the_deadline(self):
        self.assertEqual(
            notification_service.not_open_reason(opportunity(deadline=PAST)),
            f"Opportunity is closed (deadline {PAST} passed).",
        )

    def test_other_statuses_are_named(self):
        self.assertEqual(
            notification_service.not_open_reason(opportunity(status="Closed")),
            "Opportunity is not open (status: Closed).",
        )
        self.assertEqual(
            notification_service.not_open_reason(opportunity(status="Forecasted")),
            "Opportunity is not open (status: Upcoming).",
        )

    def test_open_opportunities_have_no_reason(self):
        self.assertIsNone(notification_service.not_open_reason(opportunity()))
        self.assertIsNone(notification_service.not_open_reason(opportunity(deadline=None)))


if __name__ == "__main__":
    unittest.main()
