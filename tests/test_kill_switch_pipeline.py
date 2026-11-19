"""An engaged kill switch stops the run before any model call."""

import pytest

from capex.kill_switch import KillSwitchEngaged
from capex.pipeline import run


def test_kill_switch_raises_before_any_model_call(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "1")
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    called = []

    def _forbidden(*args, **kwargs):
        called.append(args)

    monkeypatch.setattr("capex.pipeline.call_model", _forbidden)
    with pytest.raises(KillSwitchEngaged):
        run("CPX-001", runs_root=tmp_path)
    assert called == []
    log = (tmp_path / "flight_recorder.jsonl").read_text(encoding="utf-8")
    assert "kill_switch_block" in log
    assert list(tmp_path.rglob("positions")) == []
