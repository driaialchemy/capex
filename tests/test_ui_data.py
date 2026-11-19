"""The demo page reads artifacts. It does not recompute them."""

import json

import pytest

from capex.finance import compute_metrics
from capex.kill_switch import engage, is_engaged, release
from capex.llm import repo_root
from capex.pipeline import run
from capex.policy import load_policy
from capex.schemas import Proposal
from capex.ui_data import load_run, run_events, sensitivity_rows


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")


def test_load_run_includes_both_attempts_and_the_payback_finding(tmp_path):
    result = run("CPX-003", runs_root=tmp_path)
    loaded = load_run(result.run_dir)
    assert len(loaded["memo_attempts"]) == 2
    assert len(loaded["verification_attempts"]) == 2
    assert loaded["memo_md"]
    names = [item["name"] for item in loaded["status"]["proposal_findings"]]
    assert "sponsor_payback_claim" in names
    assert set(loaded["positions"]) == {
        "sponsor_advocate",
        "cfo_stress_tester",
        "operations_risk",
    }


def test_run_events_returns_only_this_run_and_includes_the_retry(tmp_path):
    result = run("CPX-003", runs_root=tmp_path)
    log = tmp_path / "flight_recorder.jsonl"
    extra = {
        "event_id": "other",
        "ts": "2026-11-18T00:00:00+00:00",
        "run_id": "CPX-001-other",
        "event_type": "stage",
        "actor": "system",
        "mode": "offline",
        "model": None,
        "attempt_number": None,
        "retry_of": None,
        "retry_reason": None,
        "input_sha256": None,
        "output_path": None,
        "status": "ok",
        "detail": "not this run",
    }
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(extra) + "\n")
    events = run_events(result.run_dir.name, tmp_path)
    assert events
    assert {event["run_id"] for event in events} == {result.run_dir.name}
    retries = [event for event in events if event["event_type"] == "retry"]
    assert len(retries) == 1
    assert retries[0]["attempt_number"] == 2
    assert retries[0]["retry_of"]
    assert retries[0]["retry_reason"]


def test_cpx_002_minus_10_is_negative():
    root = repo_root()
    proposal = Proposal.model_validate_json(
        (root / "sample_data" / "proposals" / "CPX-002.json").read_text(encoding="utf-8")
    )
    metrics = compute_metrics(proposal, load_policy(root / "config" / "capex_policy.yaml"))
    rows = sensitivity_rows(metrics)
    minus = next(row for row in rows if row["scenario"] == "Flows −10%")
    assert minus["negative"] is True
    assert minus["label"] == "-$72,086"


def test_engage_and_release_append_log_lines(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    log = tmp_path / "flight_recorder.jsonl"
    engage(root, log)
    assert (root / "KILL_SWITCH").is_file()
    assert is_engaged(root) is True
    release(root, log)
    assert not (root / "KILL_SWITCH").exists()
    assert is_engaged(root) is False
    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [line["event_type"] for line in lines] == ["kill_switch_block", "stage"]
    assert lines[0]["status"] == "blocked"
    assert lines[1]["detail"] == "Kill switch released from the demo."
