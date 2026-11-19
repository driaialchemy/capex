"""Offline runs: approve, conditional approve, and the CPX-003 retry."""

import json
from pathlib import Path

import pytest

from capex.gates import gate_positions
from capex.pipeline import run
from capex.schemas import DecisionMemo
from capex.verifier import VerificationReport


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")


def _events(runs_root: Path, run_id: str) -> list[dict]:
    path = runs_root / "flight_recorder.jsonl"
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["run_id"] == run_id:
            events.append(event)
    return events


def _check(report: VerificationReport, name: str):
    return next(item for item in report.checks if item.name == name)


def test_cpx_001_is_pending_approval(tmp_path):
    result = run("CPX-001", runs_root=tmp_path)
    assert result.status == "PENDING_APPROVAL"
    assert result.recommendation == "APPROVE"
    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PENDING_APPROVAL"
    assert status["recommendation"] == "APPROVE"
    memo = DecisionMemo.model_validate_json(
        (result.run_dir / "memo.attempt1.json").read_text(encoding="utf-8")
    )
    assert memo.recommendation == "APPROVE"
    assert not (result.run_dir / "memo.attempt2.json").exists()
    retries = [event for event in _events(tmp_path, result.run_dir.name) if event["event_type"] == "retry"]
    assert retries == []


def test_cpx_002_is_conditional(tmp_path):
    result = run("CPX-002", runs_root=tmp_path)
    assert result.status == "PENDING_APPROVAL"
    memo = DecisionMemo.model_validate_json(
        (result.run_dir / "memo.attempt1.json").read_text(encoding="utf-8")
    )
    assert memo.recommendation == "APPROVE_WITH_CONDITIONS"
    assert memo.conditions


def test_cpx_003_retries_once_and_records_the_payback_finding(tmp_path):
    result = run("CPX-003", runs_root=tmp_path)
    assert result.status == "PENDING_APPROVAL"
    assert result.recommendation == "REJECT"

    first = VerificationReport.model_validate_json(
        (result.run_dir / "verification.attempt1.json").read_text(encoding="utf-8")
    )
    assert _check(first, "recommendation_allowed").passed is False
    assert _check(first, "no_raw_figures").passed is False

    second_memo = DecisionMemo.model_validate_json(
        (result.run_dir / "memo.attempt2.json").read_text(encoding="utf-8")
    )
    assert second_memo.recommendation == "REJECT"
    second = VerificationReport.model_validate_json(
        (result.run_dir / "verification.attempt2.json").read_text(encoding="utf-8")
    )
    assert _check(second, "recommendation_allowed").passed is True
    assert _check(second, "no_raw_figures").passed is True
    assert _check(second, "tokens_valid").passed is True
    payback = _check(second, "sponsor_payback_claim")
    assert payback.passed is False
    assert payback.blocking is False
    assert not (result.run_dir / "memo.attempt3.json").exists()

    events = _events(tmp_path, result.run_dir.name)
    retries = [event for event in events if event["event_type"] == "retry"]
    assert len(retries) == 1
    assert retries[0]["attempt_number"] == 2
    assert retries[0]["retry_reason"]
    assert "recommendation_allowed" in retries[0]["retry_reason"]
    assert "no_raw_figures" in retries[0]["retry_reason"]
    judge_calls = [
        event for event in events if event["event_type"] == "model_call" and event["actor"] == "judge"
    ]
    assert judge_calls[0]["attempt_number"] == 1
    assert retries[0]["retry_of"] == judge_calls[0]["event_id"]

    memo_md = (result.run_dir / "memo.md").read_text(encoding="utf-8")
    _before, findings = memo_md.split("## Proposal findings", 1)
    assert "sponsor_payback_claim" in findings
    assert "2" in findings

    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["proposal_findings"]
    assert status["proposal_findings"][0]["name"] == "sponsor_payback_claim"

    verifier_events = [event for event in events if event["event_type"] == "verifier"]
    assert any("Proposal findings" in event["detail"] and "sponsor_payback_claim" in event["detail"] for event in verifier_events)


def test_tampered_position_fails_the_gate(tmp_path):
    result = run("CPX-001", runs_root=tmp_path)
    path = result.run_dir / "positions" / "sponsor_advocate.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["top_risk"] = payload["top_risk"] + " $1,000,000"
    path.write_text(json.dumps(payload), encoding="utf-8")
    gate = gate_positions(result.run_dir)
    assert gate.passed is False
