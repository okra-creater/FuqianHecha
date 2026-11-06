"""Command-line entry point for local development and demonstrations."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .analyzer import BaselineAnalyzer
from .models import Scenario


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser separately so it can be tested."""

    parser = argparse.ArgumentParser(
        description="Analyze a job or rental conversation before payment."
    )
    parser.add_argument(
        "--scenario",
        choices=[item.value for item in Scenario],
        default=Scenario.AUTO.value,
        help="conversation scenario; defaults to automatic detection",
    )
    parser.add_argument(
        "--jurisdiction",
        default="HK",
        help="knowledge jurisdiction; the first version supports HK",
    )
    parser.add_argument(
        "--text",
        help="conversation text; if omitted, read it from standard input",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse input, call the analyzer, and print JSON."""

    args = build_parser().parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()

    try:
        report = BaselineAnalyzer().analyze(
            text,
            scenario=Scenario(args.scenario),
            jurisdiction=args.jurisdiction,
        )
    except NotImplementedError as error:
        print(str(error), file=sys.stderr)
        return 2

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0

