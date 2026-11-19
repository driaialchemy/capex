"""Known-answer tests for NPV, IRR, payback, and the recommendation rule."""

from pathlib import Path

import pytest

from capex.finance import (
    compute_metrics,
    discounted_payback_years,
    irr,
    npv,
    payback_years,
)
from capex.policy import load_policy
from capex.schemas import Proposal

ROOT = Path(__file__).resolve().parents[1]
ALL_FOUR = ["APPROVE", "APPROVE_WITH_CONDITIONS", "DEFER", "REJECT"]


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _policy():
    return load_policy(ROOT / "config" / "capex_policy.yaml")


def test_textbook_case():
    flows = [500, 500, 500]
    assert npv(0.10, 1000, flows, 0) == pytest.approx(243.43, abs=0.01)
    assert irr(1000, flows, 0) == pytest.approx(0.2338, abs=0.0005)
    assert payback_years(1000, flows) == pytest.approx(2.0, abs=0.01)
    assert discounted_payback_years(0.10, 1000, flows) == pytest.approx(2.352, abs=0.01)
    lighter = [cash * 0.9 for cash in flows]
    assert npv(0.10, 1000, lighter, 0) == pytest.approx(119.08, abs=0.01)


def test_cpx_001():
    metrics = compute_metrics(_proposal("CPX-001"), _policy())
    assert metrics.npv == pytest.approx(110329.85, abs=0.01)
    assert metrics.irr == pytest.approx(0.1724, abs=0.0005)
    assert metrics.payback_years == pytest.approx(4.0, abs=0.01)
    assert metrics.npv_flows_minus_10 == pytest.approx(59349.50, abs=0.01)
    assert metrics.allowed_recommendations == ALL_FOUR


def test_cpx_002():
    metrics = compute_metrics(_proposal("CPX-002"), _policy())
    assert metrics.npv == pytest.approx(6570.83, abs=0.01)
    assert metrics.irr == pytest.approx(0.1027, abs=0.0005)
    assert metrics.npv_flows_minus_10 == pytest.approx(-72086.26, abs=0.01)


def test_cpx_003():
    metrics = compute_metrics(_proposal("CPX-003"), _policy())
    assert metrics.npv == pytest.approx(-233924.97, abs=0.01)
    assert metrics.irr == pytest.approx(0.0253, abs=0.0005)
    assert metrics.payback_years is None
    assert metrics.npv_flows_minus_10 == pytest.approx(-316218.65, abs=0.01)
    assert metrics.allowed_recommendations == ["DEFER", "REJECT"]


def test_irr_is_none_when_inflows_never_cover_the_investment():
    assert irr(1000, [10, 10], 0) is None
