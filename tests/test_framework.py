"""Structural tests for the initial code framework."""

from __future__ import annotations

import unittest

from fuqianhecha.cli import build_parser
from fuqianhecha.models import (
    AnalysisReport,
    RiskSignal,
    Scenario,
    SourceReference,
    Status,
)


class FrameworkTests(unittest.TestCase):
    def test_report_is_json_serializable_shape(self) -> None:
        report = AnalysisReport(
            analyzer_version="test",
            scenario=Scenario.JOB,
            jurisdiction="HK",
            status=Status.RISK_SIGNALS,
            signals=[
                RiskSignal(
                    code="example",
                    description="example signal",
                    evidence_quote="example evidence",
                )
            ],
            sources=[
                SourceReference(
                    source_id="S00",
                    title="Example source",
                    publisher="Example publisher",
                    url="https://example.com/source",
                    published_at="2026-01-01",
                    checked_at="2026-01-02",
                    jurisdiction="HK",
                    status="reviewed",
                    summary="Example summary",
                    limits="Example limits",
                )
            ],
        )

        output = report.to_dict()
        self.assertEqual(output["scenario"], "job")
        self.assertEqual(output["status"], "risk_signals")
        self.assertEqual(output["signals"][0]["evidence_quote"], "example evidence")
        self.assertEqual(output["sources"][0]["source_id"], "S00")

    def test_cli_accepts_supported_scenarios(self) -> None:
        args = build_parser().parse_args(["--scenario", "rental", "--text", "test"])
        self.assertEqual(args.scenario, "rental")
        self.assertEqual(args.text, "test")


if __name__ == "__main__":
    unittest.main()
