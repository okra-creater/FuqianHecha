"""Load, validate, and retrieve reviewed knowledge sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Scenario


@dataclass(frozen=True)
class KnowledgeSource:
    """Validated metadata for one reviewed external source."""

    source_id: str
    title: str
    publisher: str
    url: str
    published_at: str
    checked_at: str
    jurisdiction: str
    topics: tuple[str, ...]
    verification: str
    status: str
    summary: str
    checks: tuple[str, ...]
    limits: str


class KnowledgeRepository:
    """Read-only access to reviewed sources and explicit source mappings."""

    _signal_source_ids: dict[tuple[str, Scenario], tuple[str, ...]] = {
        ("job_upfront_fee", Scenario.JOB): ("S02",),
        ("job_pay_to_unlock_task", Scenario.JOB): ("S02",),
        ("job_pay_before_withdrawal", Scenario.JOB): ("S02",),
        ("job_personal_account_transfer", Scenario.JOB): ("S02",),
        ("job_request_credentials", Scenario.JOB): ("S02",),
        ("rental_no_viewing", Scenario.RENTAL): ("S03",),
        ("rental_upfront_payment", Scenario.RENTAL): ("S03",),
        ("rental_keys_after_payment", Scenario.RENTAL): ("S03",),
        ("rental_avoid_independent_verification", Scenario.RENTAL): ("S04",),
        ("rental_private_deposit", Scenario.RENTAL): ("S04",),
        ("payment_time_pressure", Scenario.JOB): ("S02",),
        ("payment_time_pressure", Scenario.RENTAL): ("S04",),
    }

    def __init__(self, source_path: Path | str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "knowledge" / "sources.json"
        self.source_path = Path(source_path) if source_path is not None else default_path
        sources = self._load_reviewed_sources(self.source_path)
        self._sources = {source.source_id: source for source in sources}

    def all_sources(self) -> list[KnowledgeSource]:
        """Return reviewed sources in source-id order."""

        return [self._sources[source_id] for source_id in sorted(self._sources)]

    def get(self, source_id: str) -> KnowledgeSource | None:
        """Return one reviewed source; provisional sources are unavailable."""

        return self._sources.get(source_id)

    def search(
        self,
        query: str,
        *,
        scenario: Scenario | str = Scenario.AUTO,
        jurisdiction: str = "HK",
        limit: int = 3,
    ) -> list[KnowledgeSource]:
        """Return reviewed sources ranked by transparent term overlap."""

        if not isinstance(query, str):
            raise TypeError("query must be a string")
        clean_query = query.strip().casefold()
        if not clean_query:
            raise ValueError("query cannot be empty")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit must be a positive integer")

        selected_scenario = self._coerce_scenario(scenario)
        normalized_jurisdiction = self._normalize_jurisdiction(jurisdiction)
        terms = self._query_terms(clean_query)
        ranked: list[tuple[int, KnowledgeSource]] = []

        for source in self._sources.values():
            if source.jurisdiction != normalized_jurisdiction:
                continue
            if (
                selected_scenario is not Scenario.AUTO
                and selected_scenario.value not in source.topics
            ):
                continue

            title_summary = f"{source.title} {source.summary}".casefold()
            other_text = " ".join(
                (source.publisher, *source.topics, *source.checks, source.limits)
            ).casefold()
            score = sum(
                2 if term in title_summary else 1 if term in other_text else 0
                for term in terms
            )
            if score:
                ranked.append((score, source))

        ranked.sort(key=lambda item: (-item[0], item[1].source_id))
        return [source for _, source in ranked[:limit]]

    def source_ids_for_signal(
        self,
        signal_code: str,
        scenario: Scenario | str,
        *,
        jurisdiction: str = "HK",
    ) -> list[str]:
        """Return reviewed source ids explicitly approved for one signal."""

        if not isinstance(signal_code, str):
            raise TypeError("signal_code must be a string")
        selected_scenario = self._coerce_scenario(scenario)
        normalized_jurisdiction = self._normalize_jurisdiction(jurisdiction)

        if selected_scenario is Scenario.AUTO:
            candidate_ids = self._deduplicate(
                source_id
                for (code, _), ids in self._signal_source_ids.items()
                if code == signal_code
                for source_id in ids
            )
        else:
            candidate_ids = list(
                self._signal_source_ids.get((signal_code, selected_scenario), ())
            )

        return [
            source_id
            for source_id in candidate_ids
            if (source := self.get(source_id)) is not None
            and source.jurisdiction == normalized_jurisdiction
        ]

    def checks_for_source_ids(self, source_ids: list[str]) -> list[str]:
        """Collect source-backed checks in input order without duplicates."""

        checks: list[str] = []
        seen: set[str] = set()
        for source_id in source_ids:
            source = self.get(source_id)
            if source is None:
                continue
            for check in source.checks:
                if check not in seen:
                    checks.append(check)
                    seen.add(check)
        return checks

    @classmethod
    def _load_reviewed_sources(cls, path: Path) -> list[KnowledgeSource]:
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise FileNotFoundError(f"knowledge source file not found: {path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid knowledge source JSON: {path}") from error

        if not isinstance(raw_data, list):
            raise ValueError("knowledge source JSON must contain a list")

        reviewed_sources: list[KnowledgeSource] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(raw_data):
            if not isinstance(item, dict):
                raise ValueError(f"knowledge source at index {index} must be an object")
            source = cls._parse_source(item, index)
            if source.source_id in seen_ids:
                raise ValueError(f"duplicate knowledge source id: {source.source_id}")
            seen_ids.add(source.source_id)
            if source.status == "reviewed":
                reviewed_sources.append(source)

        return reviewed_sources

    @classmethod
    def _parse_source(cls, item: dict[str, Any], index: int) -> KnowledgeSource:
        return KnowledgeSource(
            source_id=cls._required_string(item, "id", index),
            title=cls._required_string(item, "title", index),
            publisher=cls._required_string(item, "publisher", index),
            url=cls._required_string(item, "url", index),
            published_at=cls._required_string(item, "published_at", index),
            checked_at=cls._required_string(item, "checked_at", index),
            jurisdiction=cls._required_string(item, "jurisdiction", index).upper(),
            topics=cls._required_string_tuple(item, "topics", index),
            verification=cls._required_string(item, "verification", index),
            status=cls._required_string(item, "status", index),
            summary=cls._required_string(item, "summary", index),
            checks=cls._required_string_tuple(item, "checks", index),
            limits=cls._required_string(item, "limits", index),
        )

    @staticmethod
    def _required_string(item: dict[str, Any], key: str, index: int) -> str:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"knowledge source at index {index} has invalid {key!r}")
        return value.strip()

    @staticmethod
    def _required_string_tuple(
        item: dict[str, Any],
        key: str,
        index: int,
    ) -> tuple[str, ...]:
        value = item.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"knowledge source at index {index} has invalid {key!r}")
        if any(not isinstance(entry, str) or not entry.strip() for entry in value):
            raise ValueError(f"knowledge source at index {index} has invalid {key!r}")
        return tuple(entry.strip() for entry in value)

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        return [
            term
            for term in re.split(r"[\s,，。；;：:/]+", query)
            if term
        ]

    @staticmethod
    def _coerce_scenario(scenario: Scenario | str) -> Scenario:
        if isinstance(scenario, Scenario):
            return scenario
        try:
            return Scenario(scenario)
        except (TypeError, ValueError) as error:
            raise ValueError(f"unsupported scenario: {scenario!r}") from error

    @staticmethod
    def _normalize_jurisdiction(jurisdiction: str) -> str:
        if not isinstance(jurisdiction, str):
            raise TypeError("jurisdiction must be a string")
        normalized = jurisdiction.strip().upper()
        if not normalized:
            raise ValueError("jurisdiction cannot be empty")
        return normalized

    @staticmethod
    def _deduplicate(values: Any) -> list[str]:
        return list(dict.fromkeys(values))
