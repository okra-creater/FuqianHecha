"""Reproducible evaluation for labelled synthetic development cases."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .analyzer import BaselineAnalyzer
from .models import AnalysisReport, Scenario, Status


_STATUS_VALUES = tuple(status.value for status in Status)
_SENSITIVE_QUESTION_TERMS = (
    "账户密码",
    "账号密码",
    "银行卡密码",
    "验证码",
    "身份证号",
    "OTP",
)
_UNSAFE_GUARANTEE_TERMS = ("绝对安全", "保证安全", "百分之百安全", "100%安全")


def load_cases(path: Path | str, *, allow_holdout: bool = False) -> list[dict[str, Any]]:
    """Load a case file while preventing accidental holdout-set use."""

    case_path = Path(path)
    if case_path.name.casefold() == "holdout_cases.json" and not allow_holdout:
        raise ValueError(
            "holdout_cases.json is protected; pass allow_holdout=True only for final evaluation"
        )

    try:
        raw_cases = json.loads(case_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"evaluation case file not found: {case_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid evaluation case JSON: {case_path}") from error

    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("evaluation case JSON must contain a non-empty list")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_cases):
        case = _validate_case(item, index)
        if case["id"] in seen_ids:
            raise ValueError(f"duplicate evaluation case id: {case['id']}")
        seen_ids.add(case["id"])
        cases.append(case)
    return cases


def evaluate_cases(
    cases: list[dict[str, Any]],
    *,
    analyzer: BaselineAnalyzer | None = None,
    dataset_name: str = "in_memory",
) -> dict[str, Any]:
    """Evaluate status, evidence, citations, questions, and safety wording."""

    if not cases:
        raise ValueError("cases cannot be empty")
    checked_cases = [_validate_case(case, index) for index, case in enumerate(cases)]
    active_analyzer = analyzer or BaselineAnalyzer()
    confusion_matrix = {
        expected: {predicted: 0 for predicted in _STATUS_VALUES}
        for expected in _STATUS_VALUES
    }

    predictions: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    status_correct = 0
    risk_expected = 0
    risk_correct = 0
    no_obvious_expected = 0
    no_obvious_false_positive = 0
    signal_count = 0
    literal_evidence_count = 0
    valid_citation_count = 0
    valid_question_case_count = 0
    safe_wording_case_count = 0

    for case in checked_cases:
        expected_status = Status(case["expected_status"])
        if expected_status is Status.RISK_SIGNALS:
            risk_expected += 1
        if expected_status is Status.NO_OBVIOUS_SIGNALS:
            no_obvious_expected += 1

        try:
            report = active_analyzer.analyze(
                case["input"],
                scenario=Scenario(case["scenario"]),
                jurisdiction=case["jurisdiction"],
            )
        except Exception as error:  # Keep failed cases in the denominator.
            errors.append(
                {
                    "id": case["id"],
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            predictions.append(
                {
                    "id": case["id"],
                    "expected_status": expected_status.value,
                    "predicted_status": None,
                    "status_correct": False,
                    "evidence_valid": False,
                    "citations_valid": False,
                    "questions_valid": False,
                    "safe_wording": False,
                }
            )
            continue

        predicted_status = report.status
        confusion_matrix[expected_status.value][predicted_status.value] += 1
        is_status_correct = predicted_status is expected_status
        status_correct += int(is_status_correct)
        if expected_status is Status.RISK_SIGNALS:
            risk_correct += int(predicted_status is Status.RISK_SIGNALS)
        if expected_status is Status.NO_OBVIOUS_SIGNALS:
            no_obvious_false_positive += int(predicted_status is Status.RISK_SIGNALS)

        evidence_valid, citations_valid, case_signal_count = _validate_signals(
            report,
            case,
            active_analyzer,
        )
        signal_count += case_signal_count
        literal_evidence_count += sum(
            1 for signal in report.signals if signal.evidence_quote in case["input"]
        )
        valid_citation_count += sum(
            1
            for signal in report.signals
            if signal.source_ids
            and all(
                active_analyzer.knowledge.get(source_id) is not None
                and source_id in case["relevant_source_ids"]
                for source_id in signal.source_ids
            )
        )

        questions_valid = _questions_are_valid(report.questions)
        valid_question_case_count += int(questions_valid)
        safe_wording = _has_safe_wording(report)
        safe_wording_case_count += int(safe_wording)

        predictions.append(
            {
                "id": case["id"],
                "expected_status": expected_status.value,
                "predicted_status": predicted_status.value,
                "status_correct": is_status_correct,
                "evidence_valid": evidence_valid,
                "citations_valid": citations_valid,
                "questions_valid": questions_valid,
                "safe_wording": safe_wording,
            }
        )

    case_count = len(checked_cases)
    return {
        "dataset": dataset_name,
        "analyzer_version": active_analyzer.version,
        "case_count": case_count,
        "status_accuracy": _fraction(status_correct, case_count),
        "confusion_matrix": confusion_matrix,
        "risk_recall": _fraction(risk_correct, risk_expected),
        "no_obvious_false_positive": _fraction(
            no_obvious_false_positive,
            no_obvious_expected,
        ),
        "literal_evidence": _fraction(literal_evidence_count, signal_count),
        "citation_validity": _fraction(valid_citation_count, signal_count),
        "question_quality": _fraction(valid_question_case_count, case_count),
        "safe_wording": _fraction(safe_wording_case_count, case_count),
        "failure_count": len(errors),
        "errors": errors,
        "predictions": predictions,
        "limitations": [
            "这些案例是合成开发数据，指标不能代表真实世界表现。",
            "自动检查只能验证格式、原文子串和来源编号，仍需人工审查语境与来源支持程度。",
        ],
    }


def evaluate_file(
    path: Path | str,
    *,
    allow_holdout: bool = False,
) -> dict[str, Any]:
    """Load and evaluate one JSON case file."""

    case_path = Path(path)
    cases = load_cases(case_path, allow_holdout=allow_holdout)
    return evaluate_cases(cases, dataset_name=case_path.name)


def build_parser() -> argparse.ArgumentParser:
    """Build the evaluation command-line parser."""

    default_dataset = Path(__file__).resolve().parents[1] / "data" / "dev_cases.json"
    parser = argparse.ArgumentParser(
        description="Evaluate FuqianHecha on labelled synthetic cases."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset,
        help="case JSON file; defaults to data/dev_cases.json",
    )
    parser.add_argument(
        "--allow-holdout",
        action="store_true",
        help="explicitly allow final evaluation on holdout_cases.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run evaluation and print a JSON report."""

    args = build_parser().parse_args(argv)
    try:
        result = evaluate_file(args.dataset, allow_holdout=args.allow_holdout)
    except (FileNotFoundError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _validate_case(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"evaluation case at index {index} must be an object")

    required_strings = ("id", "input", "scenario", "jurisdiction", "expected_status")
    for key in required_strings:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"evaluation case at index {index} has invalid {key!r}")

    try:
        Scenario(item["scenario"])
    except ValueError as error:
        raise ValueError(
            f"evaluation case {item['id']!r} has unsupported scenario"
        ) from error
    try:
        Status(item["expected_status"])
    except ValueError as error:
        raise ValueError(
            f"evaluation case {item['id']!r} has unsupported expected_status"
        ) from error

    source_ids = item.get("relevant_source_ids")
    if not isinstance(source_ids, list) or any(
        not isinstance(source_id, str) or not source_id for source_id in source_ids
    ):
        raise ValueError(
            f"evaluation case {item['id']!r} has invalid relevant_source_ids"
        )
    return item


def _validate_signals(
    report: AnalysisReport,
    case: dict[str, Any],
    analyzer: BaselineAnalyzer,
) -> tuple[bool, bool, int]:
    evidence_valid = all(
        bool(signal.evidence_quote) and signal.evidence_quote in case["input"]
        for signal in report.signals
    )
    citations_valid = all(
        bool(signal.source_ids)
        and all(
            analyzer.knowledge.get(source_id) is not None
            and source_id in case["relevant_source_ids"]
            for source_id in signal.source_ids
        )
        for signal in report.signals
    )
    return evidence_valid, citations_valid, len(report.signals)


def _questions_are_valid(questions: list[str]) -> bool:
    normalized = [question.strip().casefold() for question in questions]
    return (
        len(questions) <= 3
        and len(normalized) == len(set(normalized))
        and all(
            sensitive.casefold() not in question
            for question in normalized
            for sensitive in _SENSITIVE_QUESTION_TERMS
        )
    )


def _has_safe_wording(report: AnalysisReport) -> bool:
    rendered = json.dumps(report.to_dict(), ensure_ascii=False).casefold()
    return all(term.casefold() not in rendered for term in _UNSAFE_GUARANTEE_TERMS)


def _fraction(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": round(numerator / denominator, 4) if denominator else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
