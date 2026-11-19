"""Sample evidence is a copy of one run, including only that run's log lines."""

import json

import pytest

from capex.export_sample import export_sample
from capex.pipeline import run


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")


def test_export_copies_the_cpx_003_artifacts(tmp_path):
    runs_root = tmp_path / "runs"
    dest = tmp_path / "docs" / "CPX-003"
    result = run("CPX-003", runs_root=runs_root)
    log = runs_root / "flight_recorder.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": "CPX-001-other", "event_type": "stage"}) + "\n")
    export_sample("CPX-003", runs_root=runs_root, dest=dest)
    for name in (
        "metrics.json",
        "memo.attempt1.json",
        "memo.attempt2.json",
        "memo.md",
        "status.json",
        "flight_recorder.jsonl",
    ):
        assert (dest / name).is_file()
    assert (dest / "positions").is_dir()
    assert list((dest / "positions").glob("*.json"))
    lines = [
        json.loads(line)
        for line in (dest / "flight_recorder.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines
    assert {line["run_id"] for line in lines} == {result.run_dir.name}
