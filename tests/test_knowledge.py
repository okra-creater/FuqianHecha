"""Tests for reviewed-source loading, retrieval, and signal mappings."""

from __future__ import annotations

import unittest

from fuqianhecha.knowledge import KnowledgeRepository
from fuqianhecha.models import Scenario


class KnowledgeRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = KnowledgeRepository()

    def test_only_reviewed_sources_are_available(self) -> None:
        self.assertEqual(
            [source.source_id for source in self.repository.all_sources()],
            ["S02", "S03", "S04"],
        )
        self.assertIsNone(self.repository.get("S01"))

    def test_search_filters_by_scenario_and_ranks_overlap(self) -> None:
        results = self.repository.search(
            "海外 钥匙 租约",
            scenario=Scenario.RENTAL,
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source_id, "S03")
        self.assertTrue(all("rental" in source.topics for source in results))

    def test_search_does_not_return_other_jurisdictions(self) -> None:
        self.assertEqual(
            self.repository.search("招聘 充值", jurisdiction="MO"),
            [],
        )

    def test_signal_mapping_uses_reviewed_sources(self) -> None:
        self.assertEqual(
            self.repository.source_ids_for_signal(
                "job_upfront_fee",
                Scenario.JOB,
            ),
            ["S02"],
        )
        self.assertEqual(
            self.repository.source_ids_for_signal(
                "rental_keys_after_payment",
                Scenario.RENTAL,
            ),
            ["S03"],
        )

    def test_cross_scenario_pressure_mapping_depends_on_scenario(self) -> None:
        self.assertEqual(
            self.repository.source_ids_for_signal(
                "payment_time_pressure",
                Scenario.JOB,
            ),
            ["S02"],
        )
        self.assertEqual(
            self.repository.source_ids_for_signal(
                "payment_time_pressure",
                Scenario.RENTAL,
            ),
            ["S04"],
        )

    def test_unknown_signal_or_wrong_jurisdiction_has_no_citation(self) -> None:
        self.assertEqual(
            self.repository.source_ids_for_signal("unknown", Scenario.JOB),
            [],
        )
        self.assertEqual(
            self.repository.source_ids_for_signal(
                "job_upfront_fee",
                Scenario.JOB,
                jurisdiction="TW",
            ),
            [],
        )

    def test_checklist_is_source_backed_and_deduplicated(self) -> None:
        checks = self.repository.checks_for_source_ids(["S03", "S03", "missing"])
        self.assertEqual(checks, list(self.repository.get("S03").checks))  # type: ignore[union-attr]

    def test_invalid_search_arguments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.search(" ")
        with self.assertRaises(ValueError):
            self.repository.search("招聘", limit=0)


if __name__ == "__main__":
    unittest.main()
