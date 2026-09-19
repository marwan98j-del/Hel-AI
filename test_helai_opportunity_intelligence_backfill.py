import copy
import json
import re
import unittest
import uuid
from pathlib import Path

from helai_opportunity_intelligence_backfill import (
    D_PRIZE_ID,
    EXPECTED_IMPACT,
    NON_OPPORTUNITY_IDS,
    OPEN_NOTEBOOK_ID,
    SafetyError,
    build_backup_payload,
    load_approved_manifest,
    parse_args,
    validate_preflight,
    verify_backup_payload,
    verify_impact,
    apply_exact,
)


class ExactIntelligenceBackfillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.approved = load_approved_manifest()
        cls.approved_ids = {row["id"] for row in cls.approved}

    def test_exact_approved_count_and_subsets(self):
        self.assertEqual(len(self.approved), 15)
        non_opportunities = {
            row["id"] for row in self.approved if "record_kind" in row["patch"]
        }
        individuals = {
            row["id"] for row in self.approved if "applicant_type" in row["patch"]
        }
        self.assertEqual(non_opportunities, NON_OPPORTUNITY_IDS)
        self.assertEqual(len(individuals), 13)

    def test_excluded_groups_are_never_used_as_approval_sources(self):
        safe_ids = {row["id"] for row in self.report["groups"]["SAFE_REVIEWED_BACKFILL"]}
        self.assertEqual(self.approved_ids, safe_ids)
        self.assertFalse(
            self.approved_ids & {
                row.get("id") for row in self.report["groups"]["REVIEW_REQUIRED_HIGH_CONFIDENCE"]
            }
        )
        deterministic_only = {
            row.get("id") for row in self.report["groups"]["DETERMINISTIC_UNREVIEWED"]
        } - safe_ids
        self.assertFalse(self.approved_ids & deterministic_only)
        self.assertNotIn(D_PRIZE_ID, self.approved_ids)
        self.assertNotIn(OPEN_NOTEBOOK_ID, self.approved_ids)

    def test_patch_allowlists_and_individual_record_kind_unchanged(self):
        for row in self.approved:
            fields = set(row["patch"])
            if row["id"] in NON_OPPORTUNITY_IDS:
                self.assertEqual(fields, {"record_kind", "record_kind_reviewed"})
            else:
                self.assertEqual(fields, {
                    "applicant_type", "eligible_applicant_types", "applicant_type_reviewed"
                })
                self.assertNotIn("record_kind", fields)

    def sample_rows(self):
        rows = []
        for proposal in self.approved:
            row = {"id": proposal["id"], "title": proposal["title"]}
            row.update({field: change["old"] for field, change in proposal["old_to_new"].items()})
            rows.append(row)
        # These synthetic rows cannot satisfy production identity digests; callers
        # use count/duplicate branches that fail before the identity check.
        return rows

    def test_old_value_drift_raises(self):
        proposal = copy.deepcopy(self.approved[0])
        row = {"id": proposal["id"], "title": proposal["title"]}
        row.update({field: change["old"] for field, change in proposal["old_to_new"].items()})
        row["record_kind"] = "changed"
        with self.assertRaises(SafetyError):
            validate_preflight([row] * 122, [{}] * 224, [proposal], check_runtime=False)

    def test_title_id_drift_raises(self):
        rows = self.sample_rows()
        rows[0]["title"] = "Changed title"
        filler = [{"id": f"f{i}"} for i in range(122 - len(rows))]
        matches = [{"user_id": "u", "opportunity_id": str(i)} for i in range(224)]
        with self.assertRaises(SafetyError):
            validate_preflight(rows + filler, matches, self.approved, check_runtime=False)

    def test_count_and_duplicate_drift_raise(self):
        with self.assertRaises(SafetyError):
            validate_preflight([], [{}] * 224, self.approved, check_runtime=False)
        with self.assertRaises(SafetyError):
            validate_preflight([{"id": str(i)} for i in range(122)], [], self.approved, check_runtime=False)
        duplicate_rows = [{"id": str(i)} for i in range(122)]
        duplicate_rows[0]["source_url"] = duplicate_rows[1]["source_url"] = "https://same.test/x"
        matches = [{"user_id": "u", "opportunity_id": str(i)} for i in range(224)]
        with self.assertRaises(SafetyError):
            validate_preflight(duplicate_rows, matches, self.approved, check_runtime=False)

    def test_backup_verification_round_trip(self):
        opportunities = []
        for proposal in self.approved:
            row = {"id": proposal["id"], "title": proposal["title"]}
            row.update({field: None for field in (
                "applicant_type", "eligible_applicant_types", "record_kind",
                "applicant_type_reviewed", "record_kind_reviewed",
            )})
            opportunities.append(row)
        payload = build_backup_payload(opportunities, [], [], self.approved, {
            "opportunities": 122, "matches": 224,
            "duplicate_opportunity_groups": 0, "duplicate_match_keys": 0,
        })
        reread = json.loads(json.dumps(payload))
        self.assertTrue(verify_backup_payload(reread, self.approved, [], []))

    def test_cli_modes_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            parse_args(["--backup-only", "--apply"])

    def test_false_to_true_zero_and_impact_mismatch_blocks(self):
        impact = {**EXPECTED_IMPACT, "all_effects": [
            {"evaluated": True, "opportunity_id": next(iter(NON_OPPORTUNITY_IDS)),
             "before": {"eligible": True}, "after": {"eligible": False}},
            {"evaluated": True, "opportunity_id": next(iter(NON_OPPORTUNITY_IDS)),
             "before": {"eligible": True}, "after": {"eligible": False}},
        ]}
        self.assertEqual(len(verify_impact(impact)), 2)
        bad = copy.deepcopy(impact)
        bad["eligibility_false_to_true"] = 1
        with self.assertRaises(SafetyError):
            verify_impact(bad)

    def test_python_sequential_apply_is_disabled(self):
        with self.assertRaisesRegex(SafetyError, "sequential Python apply is disabled"):
            apply_exact(self.approved, None, [], [])

    def test_transaction_sql_has_exact_scope_and_atomic_guards(self):
        sql = (Path(__file__).parent / "helai_opportunity_intelligence_backfill_transaction.sql").read_text(encoding="utf-8")
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)
        self.assertIn("RAISE EXCEPTION", sql)
        self.assertEqual(sql.lower().count("update public.opportunities"), 2)
        self.assertNotIn("UPDATE public.matches", sql)
        self.assertNotIn("UPDATE public.notifications", sql)
        self.assertNotIn("DELETE ", sql.upper())
        self.assertNotIn("INSERT ", sql.upper())
        self.assertNotIn(D_PRIZE_ID, sql)
        self.assertNotIn(OPEN_NOTEBOOK_ID, sql)
        for opportunity_id in self.approved_ids:
            self.assertIn(opportunity_id, sql)

    def test_every_transaction_uuid_is_valid_and_manifest_exact(self):
        sql = (Path(__file__).parent / "helai_opportunity_intelligence_backfill_transaction.sql").read_text(encoding="utf-8")
        literals = re.findall(r"'([0-9a-fA-F-]{32,40})'", sql)
        self.assertTrue(literals)
        parsed = {str(uuid.UUID(value)) for value in literals}
        self.assertEqual(parsed, self.approved_ids)
        self.assertTrue(all(str(uuid.UUID(value)) == value.lower() for value in literals))
        voqal = "93f8b7ed-dce3-4f0b-a0a8-497785494faa"
        malformed = "93f8b7ed-dce3-4f0b-bc50-1a13a7355b97"
        self.assertIn(voqal, self.approved_ids)
        self.assertIn(voqal, literals)
        self.assertNotIn(malformed, sql)
        # Every validation/update/result scope derives from the one canonical
        # 15-ID manifest rather than carrying independent copied UUID lists.
        for required_scope in (
            "jsonb_each_text(approved_titles)",
            "id = ANY(approved_ids)",
            "id = ANY(non_opportunity_ids)",
            "id = ANY(individual_ids)",
        ):
            self.assertIn(required_scope, sql)


if __name__ == "__main__":
    unittest.main()
