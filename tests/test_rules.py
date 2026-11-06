"""Tests for transparent rule matching and common false-positive controls."""

from __future__ import annotations

import unittest

from fuqianhecha.models import Scenario
from fuqianhecha.rules import RULES, find_rule_matches


class RuleTests(unittest.TestCase):
    def codes(self, text: str, scenario: Scenario) -> set[str]:
        return {match.code for match in find_rule_matches(text, scenario)}

    def test_rule_codes_are_unique(self) -> None:
        codes = [rule.code for rule in RULES]
        self.assertEqual(len(codes), len(set(codes)))

    def test_job_upfront_fee_and_time_pressure(self) -> None:
        text = "线上客服每天三百，先交五百培训费才能排班，今晚不交名额就没了。"
        codes = self.codes(text, Scenario.JOB)
        self.assertIn("job_upfront_fee", codes)
        self.assertIn("payment_time_pressure", codes)

    def test_job_payment_negations_are_not_matches(self) -> None:
        samples = (
            "收到工作合同，不交任何费用。",
            "培训由公司承担，不用支付培训费或押金。",
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertNotIn("job_upfront_fee", self.codes(text, Scenario.JOB))

    def test_job_payment_question_is_not_a_match(self) -> None:
        text = "我想先问清楚是否需要交培训费。"
        self.assertNotIn("job_upfront_fee", self.codes(text, Scenario.JOB))

    def test_task_recharge_and_withdrawal_are_separate_matches(self) -> None:
        text = "充值两千就能解锁高佣任务，充值后才允许提现。"
        codes = self.codes(text, Scenario.JOB)
        self.assertIn("job_pay_to_unlock_task", codes)
        self.assertIn("job_pay_before_withdrawal", codes)

    def test_personal_account_transfer_is_detected(self) -> None:
        text = "工作要求使用你的银行卡代收款项，然后把钱转出。"
        self.assertIn("job_personal_account_transfer", self.codes(text, Scenario.JOB))

    def test_rental_no_viewing_advance_payment_and_keys(self) -> None:
        text = "我在海外，不能看房，你先转一个月租金，收到钱就寄钥匙和租约。"
        codes = self.codes(text, Scenario.RENTAL)
        self.assertIn("rental_no_viewing", codes)
        self.assertIn("rental_upfront_payment", codes)
        self.assertIn("rental_keys_after_payment", codes)

    def test_rental_verification_private_deposit_and_pressure(self) -> None:
        text = "不要打去公司，我私人收订金就行，十分钟内转账才留房。"
        codes = self.codes(text, Scenario.RENTAL)
        self.assertIn("rental_avoid_independent_verification", codes)
        self.assertIn("rental_private_deposit", codes)
        self.assertIn("payment_time_pressure", codes)

    def test_plain_deposit_at_signing_is_not_a_match(self) -> None:
        text = "签约时需要支付押金。"
        self.assertEqual(find_rule_matches(text, Scenario.RENTAL), [])

    def test_negated_rental_prepayment_is_not_a_match(self) -> None:
        text = "不用先交钱，周六先看房核对资料，再商议租约。"
        self.assertNotIn("rental_upfront_payment", self.codes(text, Scenario.RENTAL))

    def test_explicit_scenario_filters_other_scenario_rules(self) -> None:
        text = "不能看房，你先转一个月租金。"
        self.assertEqual(find_rule_matches(text, Scenario.JOB), [])

    def test_evidence_is_always_literal_input_text(self) -> None:
        text = "充值两千就能解锁高佣任务，充值后才允许提现。"
        for match in find_rule_matches(text, Scenario.JOB):
            self.assertIn(match.evidence_quote, text)


if __name__ == "__main__":
    unittest.main()
