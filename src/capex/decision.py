"""The recommendation is a rule applied to the numbers. Same numbers, same result."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from capex.finance import Metrics
from capex.schemas import CapexPolicy, Recommendation

RuleId = Literal["R1", "R2", "R3", "R4"]


class RulesDecision(BaseModel):
    """The outcome, the rule that fired, and the reason codes."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    recommendation: Recommendation
    rule: RuleId
    reasons: list[str]


def decide(metrics: Metrics, policy: CapexPolicy) -> RulesDecision:
    """First matching rule wins. This function does not recompute NPV."""
    stress = getattr(metrics, policy.stress_test_metric)
    if metrics.npv < 0:
        recommendation: Recommendation = "REJECT"
        rule: RuleId = "R1"
        reasons = ["npv_below_zero"]
    elif metrics.payback_years is None:
        recommendation = "DEFER"
        rule = "R2"
        reasons = ["payback_missing"]
    elif metrics.payback_years > policy.max_payback_years:
        recommendation = "DEFER"
        rule = "R2"
        reasons = ["payback_over_limit"]
    elif stress < 0:
        recommendation = "APPROVE_WITH_CONDITIONS"
        rule = "R3"
        reasons = ["stress_npv_below_zero"]
    else:
        recommendation = "APPROVE"
        rule = "R4"
        reasons = ["plan_clears_hurdle"]
    return RulesDecision(
        proposal_id=metrics.proposal_id,
        recommendation=recommendation,
        rule=rule,
        reasons=reasons,
    )
