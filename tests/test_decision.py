"""The rules decision is the same every time, and a hand edit fails the gate."""

from pathlib import Path

from capex.decision import decide
from capex.finance import compute_metrics
from capex.gates import gate_decision
from capex.policy import load_policy
from capex.schemas import Argument, DecisionMemo, MemoSection, Position, Proposal
from capex.verifier import verify

ROOT = Path(__file__).resolve().parents[1]


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _policy():
    return load_policy(ROOT / "config" / "capex_policy.yaml")


def _memo(proposal_id: str, recommendation: str, conditions: list[str] | None = None) -> DecisionMemo:
    return DecisionMemo(
        proposal_id=proposal_id,
        recommendation=recommendation,  # type: ignore[arg-type]
        headline="See {{npv}}",
        sections=[MemoSection(title="Case", body="A net present value of {{npv}}.")],
        cited_metrics=["npv"],
        conditions=conditions or [],
    )


def _check(report, name: str):
    return next(item for item in report.checks if item.name == name)


def _position(role: str, stance: str) -> Position:
    return Position(
        role=role,  # type: ignore[arg-type]
        stance=stance,  # type: ignore[arg-type]
        arguments=[
            Argument(
                point="A net present value of {{npv}}.",
                cited_metrics=["npv"],
                cited_assumptions=[],
            )
        ],
        top_risk="The lighter case.",
        questions_for_sponsor=[],
    )


def test_samples_follow_the_ladder():
    policy = _policy()
    expected = {
        "CPX-001": ("R4", "APPROVE", ["plan_clears_hurdle"]),
        "CPX-002": ("R3", "APPROVE_WITH_CONDITIONS", ["stress_npv_below_zero"]),
        "CPX-003": ("R1", "REJECT", ["npv_below_zero"]),
    }
    for proposal_id, (rule, recommendation, reasons) in expected.items():
        decision = decide(compute_metrics(_proposal(proposal_id), policy), policy)
        assert decision.rule == rule
        assert decision.recommendation == recommendation
        assert decision.reasons == reasons


def test_payback_outside_the_limit_is_r2():
    policy = _policy()
    metrics = compute_metrics(_proposal("CPX-001"), policy).model_copy(
        update={"npv": 1000.0, "payback_years": 9.0, "npv_flows_minus_10": 500.0}
    )
    decision = decide(metrics, policy)
    assert decision.rule == "R2"
    assert decision.recommendation == "DEFER"
    assert decision.reasons == ["payback_over_limit"]


def test_decide_twice_is_identical():
    policy = _policy()
    metrics = compute_metrics(_proposal("CPX-001"), policy)
    assert decide(metrics, policy) == decide(metrics, policy)


def test_cpx_001_defer_memo_fails_rules_match():
    proposal = _proposal("CPX-001")
    metrics = compute_metrics(proposal, _policy())
    report = verify(_memo("CPX-001", "DEFER"), metrics, proposal)
    assert _check(report, "recommendation_matches_rules").passed is False


def test_conditions_without_the_stress_figure_fail():
    proposal = _proposal("CPX-002")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-002", "APPROVE_WITH_CONDITIONS", ["Stage the rollout."])
    report = verify(memo, metrics, proposal)
    assert _check(report, "conditions_cite_stress").passed is False

    empty = DecisionMemo.model_construct(
        proposal_id="CPX-002",
        recommendation="APPROVE_WITH_CONDITIONS",
        headline="See {{npv}}",
        sections=[MemoSection(title="Case", body="A net present value of {{npv}}.")],
        cited_metrics=["npv"],
        conditions=[],
        disagreements_addressed=[],
        panel_concerns=[],
    )
    empty_report = verify(empty, metrics, proposal)
    assert _check(empty_report, "conditions_cite_stress").passed is False


def test_two_approve_panelists_on_cpx_003_are_a_non_blocking_flag():
    proposal = _proposal("CPX-003")
    metrics = compute_metrics(proposal, _policy())
    memo = _memo("CPX-003", "REJECT")
    positions = [
        _position("sponsor_advocate", "APPROVE"),
        _position("cfo_stress_tester", "APPROVE"),
        _position("operations_risk", "REJECT"),
    ]
    report = verify(memo, metrics, proposal, positions=positions)
    flag = _check(report, "panel_disagreement")
    assert flag.passed is False
    assert flag.blocking is False
    assert report.passed is True


def test_hand_edited_decision_fails_the_gate(tmp_path):
    proposal = _proposal("CPX-001")
    policy = _policy()
    decision = decide(compute_metrics(proposal, policy), policy)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    path = run_dir / "decision.json"
    path.write_text(decision.model_dump_json(indent=2) + "\n", encoding="utf-8")
    assert gate_decision(run_dir, proposal, policy).passed is True
    edited = decision.model_copy(update={"recommendation": "DEFER"})
    path.write_text(edited.model_dump_json(indent=2) + "\n", encoding="utf-8")
    result = gate_decision(run_dir, proposal, policy)
    assert result.passed is False
