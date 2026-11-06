"""Explainable text rules for candidate pre-payment risk signals.

This module only extracts candidate signals and literal evidence. It does not
decide the report status or claim that a transaction is fraudulent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Scenario


_CLAUSE_BOUNDARY = re.compile(r"[。！？!?；;\n]")


@dataclass(frozen=True)
class Rule:
    """Configuration for one auditable text-matching rule."""

    code: str
    scenario: Scenario
    description: str
    patterns: tuple[str, ...]
    exclusion_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleMatch:
    """A rule hit whose evidence is copied verbatim from the input."""

    code: str
    scenario: Scenario
    description: str
    evidence_quote: str


_PAYMENT_NEGATIONS = (
    r"(?:不|无需|无须|不用|不必|不需要|毋须|毋需|免)(?:先)?(?:交|缴|支付|付款|转账|付)",
    r"(?:培训费|入职费|报名费|手续费|保证金|押金|订金)[^。！？!?；;\n]{0,8}(?:由公司承担|全免|免费)",
)

_PAYMENT_QUESTIONS = (
    r"(?:是否|要不要|需不需要|会不会|有没有)[^。！？!?；;\n]{0,12}(?:交|缴|支付|付款|转账|付)",
    r"(?:交|缴|支付|付款|转账|付)[^。！？!?；;\n]{0,12}(?:吗|么)",
)


RULES: tuple[Rule, ...] = (
    Rule(
        code="job_upfront_fee",
        scenario=Scenario.JOB,
        description="对方要求在入职、上岗或排班前支付费用。",
        patterns=(
            r"(?:先|预先|入职前|上岗前|排班前|开始工作前)[^。！？!?；;\n]{0,20}(?:交|缴|支付|付款|转账)[^。！？!?；;\n]{0,12}(?:培训费|入职费|报名费|手续费|保证金|押金|服装费|工本费)",
            r"(?:交|缴|支付|付款|转账)[^。！？!?；;\n]{0,12}(?:培训费|入职费|报名费|手续费|保证金|押金|服装费|工本费)[^。！？!?；;\n]{0,12}(?:才能|才可|才可以)(?:入职|上岗|排班|工作|录用)",
        ),
        exclusion_patterns=_PAYMENT_NEGATIONS + _PAYMENT_QUESTIONS,
    ),
    Rule(
        code="job_pay_to_unlock_task",
        scenario=Scenario.JOB,
        description="对方要求充值或垫付资金以解锁任务、订单或佣金。",
        patterns=(
            r"(?:充值|垫付|先垫|先付)[^。！？!?；;\n]{0,16}(?:解锁|领取|获得|完成)[^。！？!?；;\n]{0,12}(?:任务|订单|佣金)",
            r"(?:解锁|领取|获得|完成)[^。！？!?；;\n]{0,12}(?:任务|订单|佣金)[^。！？!?；;\n]{0,16}(?:充值|垫付|先垫|先付)",
        ),
        exclusion_patterns=_PAYMENT_NEGATIONS + _PAYMENT_QUESTIONS,
    ),
    Rule(
        code="job_pay_before_withdrawal",
        scenario=Scenario.JOB,
        description="对方把充值或垫付作为提现、返现或取得佣金的条件。",
        patterns=(
            r"(?:充值|垫付|先垫|先付)[^。！？!?；;\n]{0,12}(?:后才|才允许|才能|才可)[^。！？!?；;\n]{0,10}(?:提现|返现|取回|拿到佣金)",
            r"(?:提现|返现|取回|拿到佣金)[^。！？!?；;\n]{0,12}(?:前|之前)[^。！？!?；;\n]{0,10}(?:充值|垫付|先垫|先付)",
        ),
        exclusion_patterns=_PAYMENT_NEGATIONS + _PAYMENT_QUESTIONS,
    ),
    Rule(
        code="job_personal_account_transfer",
        scenario=Scenario.JOB,
        description="所谓工作要求使用个人银行账户或电子钱包代收、代转资金。",
        patterns=(
            r"(?:用|使用|借用|提供|绑定)[^。！？!?；;\n]{0,12}(?:个人|你的|本人)?(?:银行账户|银行户口|银行卡|电子钱包|收款码)[^。！？!?；;\n]{0,20}(?:收款|收钱|代收|转账|转出|汇出)",
            r"(?:代收|收取)[^。！？!?；;\n]{0,12}(?:款项|资金|钱)[^。！？!?；;\n]{0,12}(?:再|然后)[^。！？!?；;\n]{0,8}(?:转出|转账|汇出)",
        ),
        exclusion_patterns=(
            r"(?:不会|无需|不用|不需要)[^。！？!?；;\n]{0,14}(?:代收|转账|转出|汇出)",
        ),
    ),
    Rule(
        code="job_request_credentials",
        scenario=Scenario.JOB,
        description="对方索要账户密码、验证码或登录资料。",
        patterns=(
            r"(?:提供|交出|发送|告诉|索取)[^。！？!?；;\n]{0,12}(?:账户密码|银行卡密码|验证码|OTP|登录资料|登入资料)",
        ),
        exclusion_patterns=(
            r"(?:不要|不能|切勿|不会|无需|不用)[^。！？!?；;\n]{0,10}(?:提供|交出|发送|告诉)",
        ),
    ),
    Rule(
        code="rental_no_viewing",
        scenario=Scenario.RENTAL,
        description="出租方表示无法安排实地看房。",
        patterns=(
            r"(?:不能|无法|不可以|没法|暂时不能)[^。！？!?；;\n]{0,8}(?:看房|睇楼|实地查看)",
        ),
        exclusion_patterns=(
            r"(?:不是|并非)[^。！？!?；;\n]{0,5}(?:不能|无法|不可以|没法)",
        ),
    ),
    Rule(
        code="rental_upfront_payment",
        scenario=Scenario.RENTAL,
        description="出租方要求预先支付租金、订金或押金。",
        patterns=(
            r"(?:先|预先)[^。！？!?；;\n]{0,8}(?:转账|付款|支付|交钱|交租|付)[^。！？!?；;\n]{0,12}(?:租金|订金|定金|押金|保证金)",
            r"(?:先|预先)[^。！？!?；;\n]{0,8}(?:转)[^。！？!?；;\n]{0,12}(?:租金|订金|定金|押金|保证金)",
        ),
        exclusion_patterns=_PAYMENT_NEGATIONS
        + _PAYMENT_QUESTIONS
        + (r"(?:签约|签署租约|核对租约)(?:时|后)[^。！？!?；;\n]{0,10}(?:支付|付款|交|付)",),
    ),
    Rule(
        code="rental_keys_after_payment",
        scenario=Scenario.RENTAL,
        description="出租方表示收款后才会提供钥匙或租约。",
        patterns=(
            r"(?:收到钱|收到款|收款后|付款后|转账后|付清后)[^。！？!?；;\n]{0,16}(?:寄|给|提供|发送)[^。！？!?；;\n]{0,10}(?:钥匙|锁匙|租约|合同)",
        ),
        exclusion_patterns=(
            r"(?:不是|并非)[^。！？!?；;\n]{0,8}(?:收到钱|收款后|付款后|转账后)",
        ),
    ),
    Rule(
        code="rental_avoid_independent_verification",
        scenario=Scenario.RENTAL,
        description="对方阻止用户通过公司、门店或平台独立核实。",
        patterns=(
            r"(?:不要|别|不许)[^。！？!?；;\n]{0,12}(?:打(?:电话)?去|联系|致电|查询|核实|查证)[^。！？!?；;\n]{0,12}(?:公司|门店|平台|官网|业主)",
        ),
    ),
    Rule(
        code="rental_private_deposit",
        scenario=Scenario.RENTAL,
        description="经办人要求以私人身份收取订金、押金或租金。",
        patterns=(
            r"(?:我|本人|代理)?(?:私人|个人)[^。！？!?；;\n]{0,6}(?:收|代收)[^。！？!?；;\n]{0,10}(?:订金|定金|押金|租金|款)",
        ),
    ),
    Rule(
        code="payment_time_pressure",
        scenario=Scenario.AUTO,
        description="对方用很短的付款期限和失去名额或房源来催促转账。",
        patterns=(
            r"(?:今晚|今天|现在|立即|马上|立刻|十分钟内|半小时内|一小时内|\d+\s*分钟内)[^。！？!?；;\n]{0,24}不(?:交|缴|支付|付款|转账)[^。！？!?；;\n]{0,12}(?:名额|机会|房|房源)[^。！？!?；;\n]{0,8}(?:就)?(?:没了|取消|不留|失效)",
            r"(?:今晚|今天|现在|立即|马上|立刻|十分钟内|半小时内|一小时内|\d+\s*分钟内)[^。！？!?；;\n]{0,24}(?:交|缴|支付|付款|转账)[^。！？!?；;\n]{0,10}才(?:能)?(?:留房|保留|预留|有名额|保住名额)",
        ),
    ),
)


def _context_for_span(text: str, start: int, end: int) -> str:
    """Return a small, punctuation-bounded context around a regex match."""

    left = 0
    for boundary in _CLAUSE_BOUNDARY.finditer(text, 0, start):
        left = boundary.end()

    boundary = _CLAUSE_BOUNDARY.search(text, end)
    right = boundary.start() if boundary else len(text)

    # Keep exclusions local. A later phrase such as “今晚不交名额就没了”
    # must not cancel an earlier, separate “先交培训费” match.
    return text[max(left, start - 8) : min(right, end + 8)]


def find_rule_matches(text: str, scenario: Scenario) -> list[RuleMatch]:
    """Find at most one non-excluded match per rule.

    ``Scenario.AUTO`` checks both supported scenarios. With an explicit
    scenario, rules for that scenario and cross-scenario rules are checked.
    Every ``evidence_quote`` is a literal substring of ``text``.
    """

    matches: list[RuleMatch] = []
    for rule in RULES:
        if scenario is not Scenario.AUTO and rule.scenario not in (scenario, Scenario.AUTO):
            continue

        accepted_match: re.Match[str] | None = None
        for pattern in rule.patterns:
            for candidate in re.finditer(pattern, text, flags=re.IGNORECASE):
                context = _context_for_span(text, candidate.start(), candidate.end())
                excluded = any(
                    re.search(exclusion, context, flags=re.IGNORECASE)
                    for exclusion in rule.exclusion_patterns
                )
                if not excluded:
                    accepted_match = candidate
                    break
            if accepted_match is not None:
                break

        if accepted_match is not None:
            matches.append(
                RuleMatch(
                    code=rule.code,
                    scenario=rule.scenario,
                    description=rule.description,
                    evidence_quote=accepted_match.group(0),
                )
            )

    return matches
