"""Tests for scenario detection, rule integration, and report status."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from fuqianhecha.analyzer import BaselineAnalyzer
from fuqianhecha.models import Scenario, Status


class AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = BaselineAnalyzer()

    def test_detects_job_scenario(self) -> None:
        scenario = self.analyzer.detect_scenario(
            "招聘方说兼职已经录取，入职前需要参加培训。"
        )
        self.assertEqual(scenario, Scenario.JOB)

    def test_detects_rental_scenario(self) -> None:
        scenario = self.analyzer.detect_scenario(
            "我准备租房，业主说看房后再签租约。"
        )
        self.assertEqual(scenario, Scenario.RENTAL)

    def test_leaves_unknown_or_tied_scenario_unresolved(self) -> None:
        self.assertEqual(self.analyzer.detect_scenario("对方让我今天回复。"), Scenario.AUTO)
        self.assertEqual(
            self.analyzer.detect_scenario("招聘人员同时发来一个租房广告。"),
            Scenario.AUTO,
        )

    def test_explicit_scenario_overrides_detection(self) -> None:
        report = self.analyzer.analyze(
            "这段文字提到招聘和入职。",
            scenario=Scenario.RENTAL,
        )
        self.assertEqual(report.scenario, Scenario.RENTAL)

    def test_normalizes_jurisdiction_and_reports_limitations(self) -> None:
        report = self.analyzer.analyze("我准备找兼职。", jurisdiction=" hk ")
        self.assertEqual(report.jurisdiction, "HK")
        self.assertEqual(report.status, Status.INSUFFICIENT_INFORMATION)
        self.assertTrue(any("不构成诈骗认定" in item for item in report.limitations))

    def test_risk_matches_become_literal_report_signals(self) -> None:
        text = "招聘方说先交五百培训费才能排班，今晚不交名额就没了。"
        report = self.analyzer.analyze(text)

        self.assertEqual(report.status, Status.RISK_SIGNALS)
        self.assertGreaterEqual(len(report.signals), 2)
        for signal in report.signals:
            self.assertIn(signal.evidence_quote, text)
            self.assertEqual(signal.source_ids, ["S02"])
        self.assertNotEqual(report.checklist, [])
        self.assertEqual([source.source_id for source in report.sources], ["S02"])
        self.assertEqual(report.sources[0].status, "reviewed")
        self.assertTrue(report.sources[0].url.startswith("https://"))
        self.assertNotIn("S01", {item for signal in report.signals for item in signal.source_ids})

    def test_rental_risk_uses_rental_source_and_checklist(self) -> None:
        report = self.analyzer.analyze(
            "不能看房，你先转一个月租金，收到钱就寄钥匙和租约。",
            scenario=Scenario.RENTAL,
        )
        self.assertEqual(report.status, Status.RISK_SIGNALS)
        self.assertEqual(
            {source_id for signal in report.signals for source_id in signal.source_ids},
            {"S03"},
        )
        self.assertTrue(any("实地看房" in item for item in report.checklist))

    def test_complete_job_context_can_be_no_obvious_signals(self) -> None:
        report = self.analyzer.analyze(
            "我通过自己找到的公司电话核实了岗位和招聘人员，"
            "合同写明工作地点和工资，不用支付培训费或押金。"
        )
        self.assertEqual(report.status, Status.NO_OBVIOUS_SIGNALS)
        self.assertEqual(report.signals, [])
        self.assertEqual([source.source_id for source in report.sources], ["S02"])
        self.assertTrue(any("不等于交易安全" in item for item in report.limitations))

    def test_no_rule_hit_without_complete_context_is_insufficient(self) -> None:
        report = self.analyzer.analyze("我们招周末兼职，工资日结，有兴趣加我了解。")
        self.assertEqual(report.status, Status.INSUFFICIENT_INFORMATION)
        self.assertEqual(report.signals, [])
        self.assertTrue(any("核实岗位" in item for item in report.checklist))

    def test_non_hk_risk_does_not_use_hk_citations(self) -> None:
        report = self.analyzer.analyze(
            "招聘方说先交五百培训费才能排班。",
            scenario=Scenario.JOB,
            jurisdiction="MO",
        )
        self.assertEqual(report.status, Status.RISK_SIGNALS)
        self.assertTrue(all(not signal.source_ids for signal in report.signals))
        self.assertEqual(report.checklist, [])
        self.assertEqual(report.sources, [])
        self.assertTrue(any("没有与当前地区匹配" in item for item in report.limitations))

    def test_all_development_cases_receive_expected_status(self) -> None:
        cases_path = Path(__file__).parents[1] / "data" / "dev_cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8"))

        for case in cases:
            with self.subTest(case_id=case["id"]):
                report = self.analyzer.analyze(
                    case["input"],
                    scenario=Scenario(case["scenario"]),
                )
                self.assertEqual(report.status, Status(case["expected_status"]))
                for signal in report.signals:
                    self.assertIn(signal.evidence_quote, case["input"])

    def test_marks_non_hk_knowledge_limit(self) -> None:
        report = self.analyzer.analyze("我准备租房。", jurisdiction="MO")
        self.assertTrue(any("仅覆盖香港" in item for item in report.limitations))

    def test_rejects_empty_and_oversized_text(self) -> None:
        for value in ("", "  \n\t"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.analyzer.analyze(value)

        with self.assertRaises(ValueError):
            self.analyzer.analyze("字" * 20_001)

    def test_rejects_non_string_text(self) -> None:
        with self.assertRaises(TypeError):
            self.analyzer.analyze(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
