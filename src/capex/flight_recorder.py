"""Append-only logbook. Lines are added and never edited."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

EventType = Literal[
    "stage",
    "model_call",
    "gate",
    "verifier",
    "retry",
    "approval",
    "kill_switch_block",
    "error",
]
EventStatus = Literal["ok", "fail", "blocked"]


class FlightEvent(BaseModel):
    """One line in runs/flight_recorder.jsonl."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    ts: str
    run_id: str
    event_type: EventType
    actor: str
    mode: Literal["offline", "live"]
    model: str | None
    attempt_number: int | None
    retry_of: str | None
    retry_reason: str | None
    input_sha256: str | None
    output_path: str | None
    status: EventStatus
    detail: str


def default_log_path() -> Path:
    return Path("runs") / "flight_recorder.jsonl"


def new_event(run_id: str, event_type: EventType, actor: str, status: EventStatus, detail: str, **fields) -> FlightEvent:
    """Fill the required fields. Callers override only what this event uses."""
    from capex.llm import current_mode

    mode = current_mode()
    model = os_model() if mode == "live" else None
    base = {
        "event_id": str(uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "event_type": event_type,
        "actor": actor,
        "mode": mode,
        "model": model,
        "attempt_number": None,
        "retry_of": None,
        "retry_reason": None,
        "input_sha256": None,
        "output_path": None,
        "status": status,
        "detail": detail,
    }
    base.update(fields)
    return FlightEvent(**base)


def os_model() -> str | None:
    import os

    model = os.environ.get("CAPEX_MODEL", "").strip()
    return model or None


def prompt_sha256(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def record(event: FlightEvent, path: Path | None = None) -> FlightEvent:
    """Append one JSON line. The file is opened for append and never rewritten."""
    target = Path(path) if path is not None else default_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    line = event.model_dump_json() + "\n"
    with target.open("ab") as handle:
        handle.write(line.encode("utf-8"))
    return event
