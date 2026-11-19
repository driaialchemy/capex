"""Live mode refuses to call Claude when the key or the model name is missing."""

import pytest

from capex.llm import ConfigError, call_model


def test_live_mode_without_api_key_does_not_call_the_sdk(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr("capex.llm.anthropic.Anthropic", FakeClient)
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")
    monkeypatch.setenv("CAPEX_LLM_MODE", "live")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CAPEX_MODEL", "claude-sonnet-5-5")
    with pytest.raises(ConfigError):
        call_model("judge", "prompt", "CPX-001", 1)
    assert created == []


def test_live_mode_without_model_does_not_call_the_sdk(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr("capex.llm.anthropic.Anthropic", FakeClient)
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")
    monkeypatch.setenv("CAPEX_LLM_MODE", "live")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setenv("CAPEX_MODEL", "")
    with pytest.raises(ConfigError):
        call_model("judge", "prompt", "CPX-001", 1)
    assert created == []
