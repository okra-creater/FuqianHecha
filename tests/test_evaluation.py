"""Tests for deterministic development-set evaluation."""

from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from fuqianhecha.evaluation import evaluate_file, load_cases, main


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev_path = Path(__file__).parents[1] / "data" / "dev_cases.json"

    def test_development_evaluation_reports_expected_counts(self) -> None:
        result = evaluate_file(self.dev_path)

        self.assertEqual(result["dataset"], "dev_cases.json")
        self.assertEqual(result["case_count"], 12)
        self.assertEqual(result["status_accuracy"]["numerator"], 12)
        self.assertEqual(result["status_accuracy"]["denominator"], 12)
        self.assertEqual(result["failure_count"], 0)

    def test_confusion_matrix_and_targeted_metrics_use_counts(self) -> None:
        result = evaluate_file(self.dev_path)
        matrix = result["confusion_matrix"]

        self.assertEqual(matrix["risk_signals"]["risk_signals"], 4)
        self.assertEqual(
            matrix["insufficient_information"]["insufficient_information"],
            4,
        )
        self.assertEqual(matrix["no_obvious_signals"]["no_obvious_signals"], 4)
        self.assertEqual(result["risk_recall"]["numerator"], 4)
        self.assertEqual(result["risk_recall"]["denominator"], 4)
        self.assertEqual(result["no_obvious_false_positive"]["numerator"], 0)
        self.assertEqual(result["no_obvious_false_positive"]["denominator"], 4)

    def test_evidence_citations_questions_and_wording_are_checked(self) -> None:
        result = evaluate_file(self.dev_path)

        self.assertGreater(result["literal_evidence"]["denominator"], 0)
        self.assertEqual(result["literal_evidence"]["value"], 1.0)
        self.assertEqual(result["citation_validity"]["value"], 1.0)
        self.assertEqual(result["question_quality"]["value"], 1.0)
        self.assertEqual(result["safe_wording"]["value"], 1.0)

    def test_result_is_json_serializable_and_keeps_case_predictions(self) -> None:
        result = evaluate_file(self.dev_path)
        rendered = json.dumps(result, ensure_ascii=False)

        self.assertIn("D01", rendered)
        self.assertEqual(len(result["predictions"]), 12)
        self.assertTrue(all(item["status_correct"] for item in result["predictions"]))

    def test_holdout_file_requires_explicit_permission_before_reading(self) -> None:
        with self.assertRaisesRegex(ValueError, "protected"):
            load_cases(Path("/does/not/exist/holdout_cases.json"))

    def test_cli_runs_default_development_evaluation(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["--dataset", str(self.dev_path)])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["case_count"], 12)


if __name__ == "__main__":
    unittest.main()
