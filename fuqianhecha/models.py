"""Shared data structures used by analyzers, interfaces, and evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Scenario(StrEnum):
    """Supported transaction scenarios."""

    AUTO = "auto"
    JOB = "job"
    RENTAL = "rental"


class Status(StrEnum):
    """Permitted analysis outcomes."""

    RISK_SIGNALS = "risk_signals"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NO_OBVIOUS_SIGNALS = "no_obvious_signals"


@dataclass(frozen=True)
class RiskSignal:
    """One risk signal tied to literal evidence from the user's text."""

    code: str
    description: str
    evidence_quote: str
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceReference:
    """Public metadata for one reviewed source used by a report."""

    source_id: str
    title: str
    publisher: str
    url: str
    published_at: str
    checked_at: str
    jurisdiction: str
    status: str
    summary: str
    limits: str


@dataclass
class AnalysisReport:
    """Stable output contract for every analysis implementation."""

    analyzer_version: str
    scenario: Scenario
    jurisdiction: str
    status: Status
    signals: list[RiskSignal] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    sources: list[SourceReference] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)
