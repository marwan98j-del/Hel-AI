import unittest
from types import SimpleNamespace
from unittest.mock import patch

import automatic_collector
import email_service
import source_adapters


class _NotificationQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _fields):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _NotificationClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        if name != "notifications":
            raise AssertionError(f"Unexpected table access: {name}")
        return _NotificationQuery(self.rows)


def _notification():
    return {
        "id": "n1",
        "user_id": "u1",
        "opportunity_id": "o1",
        "match_id": "m1",
        "status": "pending",
        "attempts": 0,
    }


def _related_rows(deadline="2099-01-01"):
    return {
        "profiles": {
            "id": "u1",
            "email": "user@example.com",
            "email_notifications": True,
            "preferred_language": "English",
        },
        "opportunities": {
            "id": "o1",
            "title": "Safe test opportunity",
            "status": "Open",
            "deadline": deadline,
            "source_url": "https://example.com/opportunity",
        },
        "matches": {
            "id": "m1",
            "eligible": True,
            "match_score": 90,
        },
    }


class CollectorAndSourceAdapterTests(unittest.TestCase):
    def test_source_catalog_has_expected_active_connectors(self):
        catalog = source_adapters.get_source_catalog()
        self.assertEqual(
            [item["key"] for item in catalog],
            ["opportunity_desk", "ukri", "grants_gov", "nsf"],
        )
        self.assertTrue(all(item["active"] for item in catalog))

    def test_rss_parser_returns_normalized_candidate_shape_without_network(self):
        xml = """
        <rss><channel><item>
          <title>  Example   Grant  </title>
          <link>https://example.com/grant</link>
          <description><![CDATA[<p>Useful <b>summary</b>.</p>]]></description>
        </item></channel></rss>
        """
        with patch(
            "source_adapters.request_with_retries",
            return_value=SimpleNamespace(text=xml),
        ):
            rows = source_adapters.parse_rss(
                "https://example.com/feed.xml", "Example", "Example Source", 1
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Example Grant")
        self.assertEqual(rows[0]["url"], "https://example.com/grant")
        self.assertEqual(rows[0]["summary"], "Useful summary .")

    def test_collector_duplicate_check_normalizes_url(self):
        with patch(
            "automatic_collector.find_existing_opportunity",
            return_value={"id": "existing"},
        ) as lookup:
            self.assertTrue(
                automatic_collector.already_imported(
                    "https://example.com/grant/?utm_source=test#details"
                )
            )
        lookup.assert_called_once_with(
            {"source_url": "https://example.com/grant"},
            client=automatic_collector.collector_supabase,
        )


class EmailSafetyTests(unittest.TestCase):
    def _run(self, rows, *, test_mode=True, test_recipient=""):
        client = _NotificationClient([_notification()])

        def get_one(_client, table_name, _record_id):
            return rows[table_name]

        with (
            patch("email_service.get_supabase", return_value=client),
            patch("email_service.get_one", side_effect=get_one),
            patch("email_service.TEST_MODE", test_mode),
            patch("email_service.TEST_RECIPIENT", test_recipient),
            patch("email_service.send_resend_email") as send,
            patch("email_service.mark_sent") as mark_sent,
            patch("email_service.mark_failed") as mark_failed,
        ):
            result = email_service.send_pending_notifications()
        return result, send, mark_sent, mark_failed

    def test_test_mode_with_empty_recipient_never_sends(self):
        result, send, mark_sent, mark_failed = self._run(_related_rows())
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        send.assert_not_called()
        mark_sent.assert_not_called()
        mark_failed.assert_not_called()

    def test_expired_opportunity_never_sends(self):
        result, send, mark_sent, mark_failed = self._run(
            _related_rows(deadline="2000-01-01"),
            test_recipient="safe@example.com",
        )
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        send.assert_not_called()
        mark_sent.assert_not_called()
        mark_failed.assert_not_called()

    def test_test_mode_routes_only_to_configured_recipient(self):
        rows = _related_rows()
        with patch(
            "email_service.send_resend_email",
            return_value={"success": True, "data": {}},
        ) as send:
            client = _NotificationClient([_notification()])

            def get_one(_client, table_name, _record_id):
                return rows[table_name]

            with (
                patch("email_service.get_supabase", return_value=client),
                patch("email_service.get_one", side_effect=get_one),
                patch("email_service.TEST_MODE", True),
                patch("email_service.TEST_RECIPIENT", "safe@example.com"),
                patch("email_service.mark_sent"),
            ):
                result = email_service.send_pending_notifications()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(send.call_args.args[0], "safe@example.com")


if __name__ == "__main__":
    unittest.main()
