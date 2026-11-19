"""Sign-off matches the dollar tier, and a blocked memo cannot be approved."""

import json

import pytest

from capex.approval import ApprovalError, approve
from capex.finance import compute_metrics
from capex.llm import repo_root
from capex.pipeline import run
from capex.policy import load_policy
from capex.schemas import Proposal


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")


def _approval_events(runs_root, run_id: str) -> list[dict]:
    path = runs_root / "flight_recorder.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["run_id"] == run_id and event["event_type"] == "approval":
            events.append(event)
    return events


def test_department_head_is_refused_and_cfo_finalizes_cpx_001(tmp_path):
    result = run("CPX-001", runs_root=tmp_path)
    assert result.status == "PENDING_APPROVAL"
    before = _approval_events(tmp_path, result.run_dir.name)
    with pytest.raises(ApprovalError):
        approve(result.run_dir, "Pat Lee", "department_head", "APPROVED")
    assert _approval_events(tmp_path, result.run_dir.name) == before
    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PENDING_APPROVAL"

    approved = approve(result.run_dir, "Demo CFO", "cfo", "APPROVED")
    assert approved["status"] == "FINAL"
    events = _approval_events(tmp_path, result.run_dir.name)
    assert len(events) == 1
    assert events[0]["actor"] == "Demo CFO"


def test_cpx_003_needs_cfo_and_ceo_and_rejects_a_duplicate_role(tmp_path):
    result = run("CPX-003", runs_root=tmp_path)
    assert result.status == "PENDING_APPROVAL"
    after_cfo = approve(result.run_dir, "Demo CFO", "cfo", "APPROVED")
    assert after_cfo["status"] == "PENDING_APPROVAL"
    with pytest.raises(ApprovalError):
        approve(result.run_dir, "Other CFO", "cfo", "APPROVED")
    still = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert still["status"] == "PENDING_APPROVAL"
    final = approve(result.run_dir, "Demo CEO", "ceo", "APPROVED")
    assert final["status"] == "FINAL"
    events = _approval_events(tmp_path, result.run_dir.name)
    assert len(events) == 2


def test_blocked_run_cannot_be_approved(tmp_path):
    root = repo_root()
    proposal = Proposal.model_validate_json(
        (root / "sample_data" / "proposals" / "CPX-001.json").read_text(encoding="utf-8")
    )
    metrics = compute_metrics(proposal, load_policy(root / "config" / "capex_policy.yaml"))
    run_dir = tmp_path / "CPX-001-blocked"
    run_dir.mkdir()
    (run_dir / "metrics.json").write_text(metrics.model_dump_json(), encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "BLOCKED",
                "recommendation": "APPROVE",
                "attempts": 1,
                "proposal_findings": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ApprovalError):
        approve(run_dir, "Demo CFO", "cfo", "APPROVED")
    assert not (tmp_path / "flight_recorder.jsonl").exists()
    assert not (run_dir / "approvals.json").exists()
