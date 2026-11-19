"""The code-only inspector catches bad recommendations, raw figures, and false claims."""

import ast
from pathlib import Path

import pytest

from capex.finance import compute_metrics
from capex.policy import load_policy
from capex.schemas import DecisionMemo, MemoSection, Proposal
from capex.verifier import verify

ROOT = Path(__file__).resolve().parents[1]


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _policy():
    return load_policy(ROOT / "config" / "capex_policy.yaml")


def _memo(
    proposal_id: str,
    recommendation: str,
    headline: str,
    body: str,
    cited: list[str],
) -> DecisionMemo:
    return DecisionMemo(
        proposal_id=proposal_id,
        recommendation=recommendation,  # type: ignore[arg-type]
        headline=headline,
        sections=[MemoSection(title="Case", body=body)],
        cited_metrics=cited,
    )


def _check(report, name: str):
    return next(item for item in report.checks if item.name == name)


def test_clean_cpx_001_approve_memo_passes():
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo(
        "CPX-001",
        "APPROVE",
        "NPV is {{npv}}",
        "Payback is {{payback_years}}. Cash arrives in Year 1 and the case still holds in Year 20.",
        ["npv", "payback_years"],
    )
    report = verify(memo, metrics, proposal)
    assert report.passed


def test_cpx_003_approve_fails_recommendation_allowed():
    proposal = _proposal("CPX-003")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-003", "APPROVE", "Do it", "See {{npv}}.", ["npv"])
    report = verify(memo, metrics, proposal)
    assert report.passed is False
    assert _check(report, "recommendation_allowed").passed is False


@pytest.mark.parametrize("body", ["The savings are $110,000.", "The return is 17%."])
def test_raw_figures_fail(body):
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-001", "APPROVE", "Proceed", body, ["npv"])
    report = verify(memo, metrics, proposal)
    assert _check(report, "no_raw_figures").passed is False
    assert report.passed is False


def test_unknown_token_fails():
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-001", "APPROVE", "ROI is {{roi}}", "See the case.", ["roi"])
    report = verify(memo, metrics, proposal)
    assert _check(report, "tokens_valid").passed is False


def test_uncited_token_fails():
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-001", "APPROVE", "NPV is {{npv}}", "See the case.", [])
    report = verify(memo, metrics, proposal)
    assert _check(report, "tokens_valid").passed is False


def test_proposal_id_token_is_rejected():
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo(
        "CPX-001",
        "APPROVE",
        "Proposal {{proposal_id}}",
        "NPV is {{npv}}.",
        ["proposal_id", "npv"],
    )
    report = verify(memo, metrics, proposal)
    check = _check(report, "tokens_valid")
    assert check.passed is False
    assert "proposal_id" in check.detail


def test_cpx_003_payback_claim_fails():
    proposal = _proposal("CPX-003")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-003", "DEFER", "Wait", "See {{npv}}.", ["npv"])
    report = verify(memo, metrics, proposal)
    assert _check(report, "sponsor_payback_claim").passed is False
    assert "2" in _check(report, "sponsor_payback_claim").detail


def test_percent_claim_is_unverified_and_does_not_fail_on_its_own():
    proposal = _proposal("CPX-003")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-003", "DEFER", "Wait", "See {{npv}}.", ["npv"])
    report = verify(memo, metrics, proposal)
    percent = _check(report, "sponsor_percent_claims")
    assert percent.passed is True
    assert "UNVERIFIED" in percent.detail
    assert "40%" in percent.detail

    clean = _proposal("CPX-001").model_copy(
        update={"sponsor_notes": "The vendor mentions 40% fuel savings."}
    )
    clean_metrics = compute_metrics(clean, _policy())
    clean_memo = _memo("CPX-001", "APPROVE", "Proceed", "See {{npv}}.", ["npv"])
    clean_report = verify(clean_memo, clean_metrics, clean)
    assert _check(clean_report, "sponsor_percent_claims").passed is True
    assert "UNVERIFIED" in _check(clean_report, "sponsor_percent_claims").detail
    assert clean_report.passed


def test_verifier_has_no_forbidden_imports():
    source = (ROOT / "src" / "capex" / "verifier.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"anthropic", "requests", "httpx", "urllib", "socket"}
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in forbidden:
                found.append(node.module)
    assert found == []
