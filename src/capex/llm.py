"""Model calls. Offline replay is the default. Live Claude is optional."""

import os
from pathlib import Path

import anthropic

from capex.kill_switch import assert_not_engaged


class ConfigError(RuntimeError):
    """Live mode was asked for without the key or the model name."""


def repo_root() -> Path:
    """Directory that contains pyproject.toml."""
    start = Path(__file__).resolve().parent
    for folder in (start, *start.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return Path.cwd()


def current_mode() -> str:
    mode = os.environ.get("CAPEX_LLM_MODE", "offline").strip() or "offline"
    if mode not in {"offline", "live"}:
        raise ConfigError(f"CAPEX_LLM_MODE must be offline or live, not {mode!r}.")
    return mode


def call_model(role: str, prompt_text: str, proposal_id: str, attempt: int) -> str:
    """Return the model text for one role. The kill switch is checked first."""
    assert_not_engaged()
    if current_mode() == "live":
        return _live(prompt_text)
    return _offline(role, proposal_id, attempt)


def _offline(role: str, proposal_id: str, attempt: int) -> str:
    folder = repo_root() / "sample_data" / "replays" / proposal_id
    if attempt > 1:
        retry = folder / f"{role}.attempt{attempt}.json"
        if retry.is_file():
            return retry.read_text(encoding="utf-8")
    path = folder / f"{role}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No replay for {proposal_id} {role}")
    return path.read_text(encoding="utf-8")


def _live(prompt_text: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("CAPEX_MODEL", "").strip()
    if not key or not model:
        raise ConfigError(
            "ANTHROPIC_API_KEY and CAPEX_MODEL are required when CAPEX_LLM_MODE=live."
        )
    # max_tokens is required by the API. No thinking budget is set.
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt_text}],
    )
    parts: list[str] = []
    for block in message.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def parse_json_response(text: str, model_cls):
    """Strip a code fence, then validate. Invalid JSON raises ValidationError."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return model_cls.model_validate_json(cleaned)
