import unittest

from collector_service import (
    find_matching_opportunity,
    identity_match_reasons,
)


class OpportunityIdentityDedupeTests(unittest.TestCase):
    def assert_existing(self, incoming, stored, reason):
        self.assertIs(find_matching_opportunity(incoming, [stored]), stored)
        self.assertIn(reason, identity_match_reasons(incoming, stored))

    def test_exact_same_source_url_does_not_insert_twice(self):
        self.assert_existing(
            {"source_url": "https://example.org/opportunity/one"},
            {"source_url": "https://example.org/opportunity/one"},
            "source_url",
        )

    def test_trailing_slash_does_not_insert_twice(self):
        self.assert_existing(
            {"source_url": "https://example.org/opportunity/one"},
            {"source_url": "https://example.org/opportunity/one/"},
            "source_url",
        )

    def test_utm_tracking_difference_does_not_insert_twice(self):
        self.assert_existing(
            {"source_url": "https://example.org/opportunity/one?utm_source=feed"},
            {"source_url": "https://example.org/opportunity/one"},
            "source_url",
        )

    def test_fragment_difference_does_not_insert_twice(self):
        self.assert_existing(
            {"source_url": "https://example.org/opportunity/one#eligibility"},
            {"source_url": "https://example.org/opportunity/one"},
            "source_url",
        )

    def test_same_external_id_does_not_insert_twice(self):
        self.assert_existing(
            {"external_id": "UKRI-123"},
            {"external_id": "UKRI-123"},
            "external_id",
        )

    def test_same_fingerprint_does_not_insert_twice(self):
        self.assert_existing(
            {"fingerprint": "abc123"},
            {"fingerprint": "abc123"},
            "fingerprint",
        )

    def test_similar_titles_do_not_suppress_distinct_opportunities(self):
        incoming = {
            "title": "AI Research Grant 2027",
            "source_url": "https://example.org/opportunity/two",
            "external_id": "two",
            "fingerprint": "fingerprint-two",
        }
        stored = {
            "title": "AI Research Grants 2027",
            "source_url": "https://example.org/opportunity/one",
            "external_id": "one",
            "fingerprint": "fingerprint-one",
        }
        self.assertIsNone(find_matching_opportunity(incoming, [stored]))
        self.assertEqual(identity_match_reasons(incoming, stored), [])

    def test_ukri_legacy_and_generic_pipeline_identity_shape(self):
        stored = {
            "title": "Small Molecule High Throughput Screen Using AstraZeneca Facilities",
            "source_url": (
                "https://www.ukri.org/opportunity/"
                "small-molecule-high-throughput-screen-using-astrazeneca-facilities/"
            ),
            "external_id": (
                "small-molecule-high-throughput-screen-using-astrazeneca-facilities"
            ),
            "fingerprint": "legacy-fingerprint",
        }
        incoming = {
            "title": "Small molecule high throughput screen using AstraZeneca facilities",
            "source_url": (
                "https://www.ukri.org/opportunity/"
                "small-molecule-high-throughput-screen-using-astrazeneca-facilities"
            ),
            "external_id": None,
            "fingerprint": "new-fingerprint",
        }
        self.assert_existing(incoming, stored, "source_url")


if __name__ == "__main__":
    unittest.main()
