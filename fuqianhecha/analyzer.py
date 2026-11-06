"""Scenario detection, rule matching, and report status generation."""

from __future__ import annotations

import re

from .knowledge import KnowledgeRepository
from .models import AnalysisReport, RiskSignal, Scenario, SourceReference, Status
from .rules import find_rule_matches


class BaselineAnalyzer:
    """Run the transparent baseline without making external safety claims."""

    version = "baseline-knowledge-v0.3"
    max_text_length = 20_000

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository | None = None,
    ) -> None:
        self.knowledge = knowledge_repository or KnowledgeRepository()

    _job_keywords = (
        "兼职",
        "招聘",
        "求职",
        "工作",
        "岗位",
        "职位",
        "入职",
        "上班",
        "排班",
        "面试",
        "工资",
        "薪金",
        "佣金",
        "雇主",
        "僱主",
        "培训费",
        "培訓費",
        "刷单",
        "刷單",
        "job",
        "employment",
        "employer",
        "salary",
        "commission",
        "interview",
    )
    _rental_keywords = (
        "租房",
        "租屋",
        "房源",
        "房东",
        "房東",
        "业主",
        "業主",
        "出租",
        "租约",
        "租約",
        "租金",
        "看房",
        "睇楼",
        "睇樓",
        "地产代理",
        "地產代理",
        "中介",
        "钥匙",
        "鎖匙",
        "landlord",
        "rental",
        "tenancy",
        "property viewing",
    )

    # ``no_obvious_signals`` requires all three groups for the selected
    # scenario. These phrases describe user-reported checks; the application
    # does not claim to have independently verified them.
    _verification_groups: dict[Scenario, tuple[tuple[str, ...], ...]] = {
        Scenario.JOB: (
            (
                r"(?:自己找到|自行找到|独立(?:查找|找到|联系))[^。！？!?；;\n]{0,36}(?:确认|核实)",
                r"通过[^。！？!?；;\n]{0,8}自己找到[^。！？!?；;\n]{0,30}(?:确认|核实)",
            ),
            (
                r"(?:收到|取得|签署|签了|有)[^。！？!?；;\n]{0,12}(?:工作合同|雇佣合同|聘用合同)",
                r"(?:合同|合约)[^。！？!?；;\n]{0,12}(?:写明|列明|注明)",
            ),
            (
                r"(?:不|无需|无须|不用|不必|不需要|毋须|毋需)[^。！？!?；;\n]{0,8}(?:交|缴|支付|付款|转账|付)[^。！？!?；;\n]{0,12}(?:费用|培训费|押金|保证金)",
            ),
        ),
        Scenario.RENTAL: (
            (
                r"(?:已|已经)?(?:实地)?(?:看房|睇楼|睇樓)",
            ),
            (
                r"(?:独立|自行|自己)[^。！？!?；;\n]{0,12}(?:联系|找到|致电)[^。！？!?；;\n]{0,24}(?:确认|核实)",
            ),
            (
                r"(?:收款安排|付款安排)[^。！？!?；;\n]{0,16}(?:书面约定|租约|租約|一致)",
                r"(?:签约|簽約|签署租约|簽署租約)(?:时|時|后|後)[^。！？!?；;\n]{0,10}(?:付款|支付|交|付)",
                r"(?:不|无需|无须|不用|不必|不需要)[^。！？!?；;\n]{0,8}(?:先)?(?:交钱|交錢|付款|支付|转账|轉賬)",
                r"(?:商议|商議|核对|核對|确认|確認)[^。！？!?；;\n]{0,10}(?:租约|租約|合同)",
            ),
        ),
    }

    def analyze(
        self,
        text: str,
        *,
        scenario: Scenario = Scenario.AUTO,
        jurisdiction: str = "HK",
    ) -> AnalysisReport:
        """Analyze one conversation and return an explainable report."""

        clean_text = self._validate_text(text)
        selected_scenario = self._coerce_scenario(scenario)
        resolved_scenario = (
            self.detect_scenario(clean_text)
            if selected_scenario is Scenario.AUTO
            else selected_scenario
        )
        normalized_jurisdiction = self._normalize_jurisdiction(jurisdiction)

        rule_matches = find_rule_matches(clean_text, resolved_scenario)
        signals: list[RiskSignal] = []
        cited_source_ids: list[str] = []
        for match in rule_matches:
            source_ids = self.knowledge.source_ids_for_signal(
                match.code,
                resolved_scenario,
                jurisdiction=normalized_jurisdiction,
            )
            signals.append(
                RiskSignal(
                    code=match.code,
                    description=match.description,
                    evidence_quote=match.evidence_quote,
                    source_ids=source_ids,
                )
            )
            cited_source_ids.extend(source_ids)

        checklist_source_ids = list(dict.fromkeys(cited_source_ids))
        if not signals:
            checklist_source_ids = self._scenario_source_ids(
                resolved_scenario,
                normalized_jurisdiction,
            )
        checklist = self.knowledge.checks_for_source_ids(checklist_source_ids)
        sources = self._source_references(checklist_source_ids)

        status = self._select_status(clean_text, resolved_scenario, signals)
        unknowns, questions = self._follow_up_items(status, resolved_scenario)

        limitations = [
            "结果仅基于用户提供的文字和透明规则，不构成诈骗认定或安全保证。",
            "系统未独立核实对方身份、文件、账户或线下情况。",
            "source_id 仅表示官方资料支持该类核查信号，不代表来源认定当前个案。",
        ]
        if status is Status.NO_OBVIOUS_SIGNALS:
            limitations.append("未发现明显信号只代表当前文字结果，不等于交易安全。")
        if normalized_jurisdiction != "HK":
            limitations.append(
                "首版知识资料仅覆盖香港；当前地区不能直接套用香港核查结论。"
            )
        if signals and any(not signal.source_ids for signal in signals):
            limitations.append("部分风险信号没有与当前地区匹配的已审核来源。")

        return AnalysisReport(
            analyzer_version=self.version,
            scenario=resolved_scenario,
            jurisdiction=normalized_jurisdiction,
            status=status,
            signals=signals,
            unknowns=unknowns,
            questions=questions,
            checklist=checklist,
            sources=sources,
            limitations=limitations,
        )

    def _source_references(self, source_ids: list[str]) -> list[SourceReference]:
        """Return public metadata for reviewed sources used by the report."""

        references: list[SourceReference] = []
        for source_id in source_ids:
            source = self.knowledge.get(source_id)
            if source is None:
                continue
            references.append(
                SourceReference(
                    source_id=source.source_id,
                    title=source.title,
                    publisher=source.publisher,
                    url=source.url,
                    published_at=source.published_at,
                    checked_at=source.checked_at,
                    jurisdiction=source.jurisdiction,
                    status=source.status,
                    summary=source.summary,
                    limits=source.limits,
                )
            )
        return references

    def _scenario_source_ids(
        self,
        scenario: Scenario,
        jurisdiction: str,
    ) -> list[str]:
        """Return reviewed context sources when no risk signal was matched."""

        if scenario is Scenario.JOB:
            query = "招聘 公司 核实 费用 充值"
        elif scenario is Scenario.RENTAL:
            query = "租屋 看房 租约 代理 核实"
        else:
            return []

        return [
            source.source_id
            for source in self.knowledge.search(
                query,
                scenario=scenario,
                jurisdiction=jurisdiction,
            )
        ]

    def detect_scenario(self, text: str) -> Scenario:
        """Infer a scenario from transparent keyword scores.

        A tie or a complete lack of evidence remains ``auto`` rather than being
        forced into the wrong business flow.
        """

        clean_text = self._validate_text(text)
        normalized = clean_text.casefold()
        job_score = self._keyword_score(normalized, self._job_keywords)
        rental_score = self._keyword_score(normalized, self._rental_keywords)

        if job_score > rental_score:
            return Scenario.JOB
        if rental_score > job_score:
            return Scenario.RENTAL
        return Scenario.AUTO

    def _select_status(
        self,
        text: str,
        scenario: Scenario,
        signals: list[RiskSignal],
    ) -> Status:
        if signals:
            return Status.RISK_SIGNALS
        if self._has_complete_verification_context(text, scenario):
            return Status.NO_OBVIOUS_SIGNALS
        return Status.INSUFFICIENT_INFORMATION

    @classmethod
    def _has_complete_verification_context(
        cls,
        text: str,
        scenario: Scenario,
    ) -> bool:
        groups = cls._verification_groups.get(scenario)
        if groups is None:
            return False
        return all(
            any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in group)
            for group in groups
        )

    @staticmethod
    def _follow_up_items(
        status: Status,
        scenario: Scenario,
    ) -> tuple[list[str], list[str]]:
        if scenario is Scenario.AUTO:
            return (
                ["无法从现有文字确定是兼职还是租房场景。"],
                ["这段对话主要涉及求职兼职，还是租房付款？"],
            )

        if status is Status.RISK_SIGNALS:
            unknown = "系统无法确认对方真实身份、授权和收款安排。"
        elif status is Status.NO_OBVIOUS_SIGNALS:
            unknown = "系统无法独立确认用户所述核实过程及后续是否发生变化。"
        else:
            unknown = "现有文字不足以判断身份核实、文件和付款条件是否完整。"

        if scenario is Scenario.JOB:
            question = "是否通过独立找到的公司渠道核实岗位、招聘人员和所有付款要求？"
        else:
            question = "是否已实地看房，并通过独立渠道核实出租方、租约和收款安排？"
        return [unknown], [question]

    @classmethod
    def _validate_text(cls, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        clean_text = re.sub(r"\s+", " ", text).strip()
        if not clean_text:
            raise ValueError("conversation text cannot be empty")
        if len(clean_text) > cls.max_text_length:
            raise ValueError(
                f"conversation text cannot exceed {cls.max_text_length} characters"
            )
        return clean_text

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
    def _keyword_score(text: str, keywords: tuple[str, ...]) -> int:
        return sum(1 for keyword in keywords if keyword.casefold() in text)
