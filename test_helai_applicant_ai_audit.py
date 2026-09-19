import unittest

from helai_applicant_ai_audit import (
    benchmark_is_sensible,
    evidence_is_verbatim,
    source_payload,
    validate_result,
)


class ApplicantAIAuditTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "title": "Example",
            "summary_en": "Students may apply directly.",
            "notes": "",
            "original_text": "Applications are accepted from students.",
            "organization": "Sponsor Name",
            "secret_field": "must not be sent",
        }

    def test_payload_is_allowlisted(self):
        payload = source_payload(self.row)
        self.assertNotIn("secret_field", payload)
        self.assertEqual(payload["title"], "Example")

    def test_evidence_must_be_verbatim(self):
        self.assertTrue(evidence_is_verbatim("Students may apply", self.row))
        self.assertFalse(evidence_is_verbatim("Researchers may apply", self.row))

    def test_invalid_evidence_is_detected(self):
        result = {
            "record_kind": "application_opportunity",
            "applicant_types": ["individual"],
            "classification": "individual",
            "confidence": "high",
            "evidence": ["invented evidence"],
            "reason": "test",
        }
        self.assertTrue(validate_result(result, self.row))

    def test_unknown_must_be_low_confidence(self):
        result = {
            "record_kind": "unknown",
            "applicant_types": [],
            "classification": "unknown",
            "confidence": "high",
            "evidence": [],
            "reason": "test",
        }
        self.assertIn("unknown must have low confidence", validate_result(result, self.row))

    def test_benchmark_gate(self):
        rows = []
        for group, total in (("entity", 5), ("individual", 4), ("mixed", 2), ("non_opportunity", 2)):
            rows.extend({"expected": group, "agrees": True} for _ in range(total))
        self.assertTrue(benchmark_is_sensible(rows))
        rows[-1]["agrees"] = False
        self.assertFalse(benchmark_is_sensible(rows))


if __name__ == "__main__":
    unittest.main()
