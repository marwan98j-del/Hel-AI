import copy
import unittest

from helai_match_reconciliation import (
    EXPECTED_MATCH_SCHEMA, SafetyError, build_backup_payload, exact_target_rows,
    generate_transaction_sql, run, text_array_literal, verify_backup_payload,
)
from helai_matching_preview import build_preview


PROFILE = {"id": "u", "profile_complete": True, "date_of_birth": "2000-01-01"}


def opportunity(oid, **changes):
    row = {"id": oid, "title": oid, "active": True, "status": "Open", "deadline": "2099-01-01"}
    row.update(changes)
    return row


def match(mid, oid, **changes):
    row = {"id": mid, "user_id": "u", "opportunity_id": oid, "eligible": True,
           "match_score": 80, "readiness": 90, "reasons": ["old"],
           "eligibility_gaps": [], "readiness_gaps": [], "notified": True,
           "notified_at": "2026-01-01", "created_at": "2026-01-01"}
    row.update(changes)
    return row


class ReconciliationTests(unittest.TestCase):
    def test_historical_generator_is_quarantined_after_apply(self):
        with self.assertRaisesRegex(SafetyError, "ALREADY APPLIED / DO NOT EXECUTE AGAIN"):
            run("dry-run")

    def test_non_actionable_existing_rows_become_zero_without_insert_delete(self):
        opportunities = [
            opportunity("expired", deadline="2020-01-01"),
            opportunity("closed", status="Closed"),
            opportunity("info", record_kind="informational"),
            opportunity("open"),
        ]
        matches = [match("m1", "expired"), match("m2", "closed"), match("m3", "info"), match("m4", "open")]
        preview = build_preview([PROFILE], opportunities, matches)
        by_id = {row["match_id"]: row for row in preview["changed_matches"]}
        for mid in ("m1", "m2", "m3"):
            self.assertEqual((by_id[mid]["new"]["eligible"], by_id[mid]["new"]["match_score"], by_id[mid]["new"]["readiness"]), (False, 0, 0))
        self.assertEqual(preview["missing_matches_to_create"], [])
        self.assertEqual(len(matches), 4)

    def test_targets_preserve_notification_and_identity_state(self):
        live = match("m1", "closed")
        calculated = {"changed_matches": [{"match_id": "m1", "new": {
            "eligible": False, "match_score": 0, "readiness": 0, "reasons": [],
            "eligibility_gaps": ["closed"], "readiness_gaps": []}}]}
        target = exact_target_rows([live], calculated)[0]
        self.assertTrue(target["preserved"]["notified"])
        self.assertEqual(target["preserved"]["notified_at"], "2026-01-01")
        self.assertEqual(target["preserved"]["created_at"], "2026-01-01")

    def test_unchanged_rows_are_not_targets(self):
        live = match("m1", "open")
        self.assertEqual(exact_target_rows([live], {"changed_matches": []}), [])

    def test_backup_verification_detects_drift(self):
        opportunities = [{"id": "o"}]
        matches = [{"id": f"m{number}"} for number in range(224)]
        targets = []
        payload = build_backup_payload(opportunities, matches, targets, {"matches": 224})
        self.assertTrue(verify_backup_payload(payload, opportunities, matches, targets))
        broken = copy.deepcopy(payload)
        broken["matches"] = []
        with self.assertRaises(SafetyError):
            verify_backup_payload(broken, opportunities, matches, targets)

    def test_sql_is_atomic_and_has_no_partial_python_apply(self):
        targets = []
        base = {"eligible": False, "match_score": 1, "readiness": 1, "reasons": [], "eligibility_gaps": [], "readiness_gaps": []}
        for number in range(72):
            targets.append({"id": f"00000000-0000-0000-0000-{number:012d}",
                            "user_id": "00000000-0000-0000-0001-000000000000",
                            "opportunity_id": "00000000-0000-0000-0002-000000000000",
                            "old": base, "new": {**base, "match_score": 0, "readiness": 0},
                            "preserved": {"created_at": None, "notified": False, "notified_at": None}})
        sql = generate_transaction_sql(targets)
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)
        self.assertIn("LOCK TABLE public.matches", sql)
        self.assertNotIn("DELETE FROM", sql.upper())
        self.assertNotIn("INSERT INTO public.matches", sql)
        self.assertEqual(sql.count("UPDATE public.matches"), 1)
        self.assertNotIn("jsonb", sql.casefold())
        for column in ("reasons", "eligibility_gaps", "readiness_gaps"):
            self.assertIn(f"old_{column} text[]", sql)
            self.assertIn(f"new_{column} text[]", sql)
            self.assertIn(f"m.{column} IS NOT DISTINCT FROM t.old_{column}", sql)
            self.assertIn(f"m.{column} IS NOT DISTINCT FROM t.new_{column}", sql)
        for field in ("created_at", "notified", "notified_at"):
            self.assertIn(f"m.{field} IS NOT DISTINCT FROM t.old_{field}", sql)

    def test_text_array_literals_are_safe_and_unicode_preserving(self):
        self.assertEqual(text_array_literal([]), "ARRAY[]::text[]")
        rendered = text_array_literal(["applicant's reason", "one,two", "هۆکارێکی کوردی"])
        self.assertEqual(
            rendered,
            "ARRAY['applicant''s reason','one,two','هۆکارێکی کوردی']::text[]",
        )

    def test_expected_live_schema_uses_text_arrays(self):
        for column in ("reasons", "eligibility_gaps", "readiness_gaps"):
            self.assertEqual(EXPECTED_MATCH_SCHEMA[column], "text[]")


if __name__ == "__main__":
    unittest.main()
