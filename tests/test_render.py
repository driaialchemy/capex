"""Tokens become whole dollars, one-decimal rates, and one-decimal years."""

from pathlib import Path

from capex.finance import compute_metrics
from capex.render import render_memo
from capex.policy import load_policy
from capex.schemas import DecisionMemo, MemoSection, Proposal

ROOT = Path(__file__).resolve().parents[1]


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _policy():
    return load_policy(ROOT / "config" / "capex_policy.yaml")


def _memo(proposal_id: str, headline: str, body: str, cited: list[str]) -> DecisionMemo:
    return DecisionMemo(
        proposal_id=proposal_id,
        recommendation="APPROVE",
        headline=headline,
        sections=[MemoSection(title="Case", body=body)],
        cited_metrics=cited,
    )


def test_money_renders_as_whole_dollars_and_metrics_keep_cents():
    base = compute_metrics(_proposal("CPX-001"), _policy())
    stress = compute_metrics(_proposal("CPX-002"), _policy())
    assert base.npv == 110329.85
    assert stress.npv_flows_minus_10 == -72086.26

    rendered_base = render_memo(
        _memo("CPX-001", "{{npv}}", "Investment {{initial_investment}}.", ["npv", "initial_investment"]),
        base,
    )
    rendered_stress = render_memo(
        _memo("CPX-002", "{{npv_flows_minus_10}}", "Plan {{npv}}.", ["npv_flows_minus_10", "npv"]),
        stress,
    )
    assert rendered_base.headline == "$110,330"
    assert rendered_base.sections[0].body == "Investment $420,000."
    assert rendered_stress.headline == "-$72,086"
    assert rendered_stress.sections[0].body == "Plan $6,571."


def test_rates_and_years_render_in_the_stated_formats():
    metrics = compute_metrics(_proposal("CPX-001"), _policy())
    memo = _memo(
        "CPX-001",
        "{{irr}} at {{hurdle_rate}}",
        "Payback {{payback_years}}.",
        ["irr", "hurdle_rate", "payback_years"],
    )
    rendered = render_memo(memo, metrics)
    assert rendered.headline == "17.2% at 10.0%"
    assert rendered.sections[0].body == "Payback 4.0."
    assert memo.headline == "{{irr}} at {{hurdle_rate}}"


def test_missing_payback_renders_not_recovered():
    metrics = compute_metrics(_proposal("CPX-003"), _policy())
    memo = _memo("CPX-003", "{{payback_years}}", "Still {{payback_years}}.", ["payback_years"])
    rendered = render_memo(memo, metrics)
    assert rendered.headline == "not recovered"
    assert rendered.sections[0].body == "Still not recovered."
