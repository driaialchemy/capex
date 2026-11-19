"""The stage gate trusts the file on disk, then recomputes."""

import json
from pathlib import Path

from capex.finance import compute_metrics
from capex.gates import gate_metrics
from capex.policy import load_policy
from capex.schemas import Proposal

ROOT = Path(__file__).resolve().parents[1]


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _policy():
    return load_policy(ROOT / "config" / "capex_policy.yaml")


def _write(tmp_path: Path, payload: dict) -> None:
    (tmp_path / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")


def test_gate_passes_on_a_fresh_file(tmp_path):
    proposal = _proposal("CPX-001")
    policy = _policy()
    metrics = compute_metrics(proposal, policy)
    _write(tmp_path, json.loads(metrics.model_dump_json()))
    result = gate_metrics(tmp_path, proposal, policy)
    assert result.passed
    assert result.reasons == []


def test_gate_fails_when_the_file_is_missing(tmp_path):
    result = gate_metrics(tmp_path, _proposal("CPX-001"), _policy())
    assert result.passed is False


def test_gate_fails_when_a_value_is_edited(tmp_path):
    proposal = _proposal("CPX-001")
    policy = _policy()
    payload = json.loads(compute_metrics(proposal, policy).model_dump_json())
    payload["npv"] = payload["npv"] + 1
    _write(tmp_path, payload)
    result = gate_metrics(tmp_path, proposal, policy)
    assert result.passed is False


def test_gate_fails_on_a_proposal_id_mismatch(tmp_path):
    proposal = _proposal("CPX-001")
    policy = _policy()
    payload = json.loads(compute_metrics(proposal, policy).model_dump_json())
    payload["proposal_id"] = "CPX-999"
    _write(tmp_path, payload)
    result = gate_metrics(tmp_path, proposal, policy)
    assert result.passed is False
