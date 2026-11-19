"""NPV, IRR, and payback. The model never does this math."""

from pydantic import BaseModel, ConfigDict

from capex.policy import approval_tier
from capex.schemas import CapexPolicy, Proposal


def _npv_raw(rate: float, initial_investment: float, flows: list[float], salvage: float) -> float:
    """Unrounded NPV. Salvage is added to the last year's cash flow."""
    total = -initial_investment
    last_year = len(flows)
    for year, cash in enumerate(flows, start=1):
        amount = cash
        if year == last_year:
            amount += salvage
        total += amount / (1 + rate) ** year
    return total


def npv(rate: float, initial_investment: float, flows: list[float], salvage: float) -> float:
    """NPV in dollars, rounded to cents. Cash flows arrive at each year-end."""
    return round(_npv_raw(rate, initial_investment, flows, salvage), 2)


def irr(initial_investment: float, flows: list[float], salvage: float) -> float | None:
    """Annual IRR, rounded to 4 decimals.

    Returns None when the inflows, including salvage, never cover the
    investment, or when NPV does not change sign on [-0.99, 1.0].
    A negative root is not reported for a project that never pays back.
    """
    if sum(flows) + salvage < initial_investment:
        return None

    low = -0.99
    high = 1.0
    low_value = _npv_raw(low, initial_investment, flows, salvage)
    high_value = _npv_raw(high, initial_investment, flows, salvage)
    if low_value == 0:
        return round(low, 4)
    if high_value == 0:
        return round(high, 4)
    if low_value * high_value > 0:
        return None

    while high - low > 1e-7:
        mid = (low + high) / 2
        mid_value = _npv_raw(mid, initial_investment, flows, salvage)
        if low_value * mid_value <= 0:
            high = mid
            high_value = mid_value
        else:
            low = mid
            low_value = mid_value
    return round((low + high) / 2, 4)


def _payback(initial_investment: float, amounts: list[float]) -> float | None:
    """Years to recover the investment from a list of yearly amounts."""
    remaining = initial_investment
    for year, cash in enumerate(amounts, start=1):
        if cash <= 0:
            remaining -= cash
            continue
        if remaining <= cash:
            return round((year - 1) + (remaining / cash), 3)
        remaining -= cash
    return None


def payback_years(initial_investment: float, flows: list[float]) -> float | None:
    """Simple payback. Salvage is not included. None if never recovered."""
    return _payback(initial_investment, list(flows))


def discounted_payback_years(
    rate: float, initial_investment: float, flows: list[float]
) -> float | None:
    """Payback using each year's present value. Salvage is not included."""
    discounted = [cash / (1 + rate) ** year for year, cash in enumerate(flows, start=1)]
    return _payback(initial_investment, discounted)


def allowed_recommendations(
    npv_value: float, payback: float | None, policy: CapexPolicy
) -> list[str]:
    """Which of the four recommendations the figures still permit."""
    if npv_value < 0:
        return ["DEFER", "REJECT"]
    too_slow = payback is None or payback > policy.max_payback_years
    if too_slow:
        return ["APPROVE_WITH_CONDITIONS", "DEFER", "REJECT"]
    return list(policy.allowed_recommendations)


class Metrics(BaseModel):
    """Figures for one proposal. Money is in cents. Rates are 4 decimals."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    npv: float
    irr: float | None
    payback_years: float | None
    discounted_payback_years: float | None
    npv_flows_minus_20: float
    npv_flows_minus_10: float
    npv_flows_plus_10: float
    npv_rate_plus_2pp: float
    hurdle_rate: float
    max_payback_years: int
    initial_investment: float
    approval_tier: str
    allowed_recommendations: list[str]


def citeable_metrics() -> tuple[str, ...]:
    """Metric keys a memo may cite. proposal_id is not one of them."""
    return tuple(name for name in Metrics.model_fields if name != "proposal_id")


def compute_metrics(proposal: Proposal, policy: CapexPolicy) -> Metrics:
    """All stored figures for a proposal. Salvage is not scaled in the stress cases."""
    flows = list(proposal.annual_net_cash_flows)
    investment = proposal.initial_investment
    salvage = proposal.salvage_value
    rate = policy.hurdle_rate
    npv_value = npv(rate, investment, flows, salvage)
    payback = payback_years(investment, flows)
    return Metrics(
        proposal_id=proposal.proposal_id,
        npv=npv_value,
        irr=irr(investment, flows, salvage),
        payback_years=payback,
        discounted_payback_years=discounted_payback_years(rate, investment, flows),
        npv_flows_minus_20=npv(rate, investment, [cash * 0.8 for cash in flows], salvage),
        npv_flows_minus_10=npv(rate, investment, [cash * 0.9 for cash in flows], salvage),
        npv_flows_plus_10=npv(rate, investment, [cash * 1.1 for cash in flows], salvage),
        npv_rate_plus_2pp=npv(rate + 0.02, investment, flows, salvage),
        hurdle_rate=round(rate, 4),
        max_payback_years=policy.max_payback_years,
        initial_investment=round(investment, 2),
        approval_tier=approval_tier(investment, policy),
        allowed_recommendations=allowed_recommendations(npv_value, payback, policy),
    )
