"""The logbook only appends. Earlier lines stay byte-for-byte."""

import json
from pathlib import Path

from capex.flight_recorder import FlightEvent, record

REQUIRED = [
    "event_id",
    "ts",
    "run_id",
    "event_type",
    "actor",
    "mode",
    "model",
    "attempt_number",
    "retry_of",
    "retry_reason",
    "input_sha256",
    "output_path",
    "status",
    "detail",
]


def _event(**overrides) -> FlightEvent:
    base = {
        "event_id": "evt-1",
        "ts": "2026-11-18T00:00:00+00:00",
        "run_id": "CPX-001-test",
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
        "detail": "one",
    }
    base.update(overrides)
    return FlightEvent(**base)


def test_earlier_lines_stay_byte_identical(tmp_path: Path):
    path = tmp_path / "flight_recorder.jsonl"
    record(_event(event_id="evt-1", detail="one"), path)
    before = path.read_bytes()
    record(_event(event_id="evt-2", detail="two"), path)
    after = path.read_bytes()
    assert after.startswith(before)
    assert after[len(before) :]
    lines = after.decode("utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["detail"] == "one"


def test_every_required_field_is_present(tmp_path: Path):
    path = tmp_path / "flight_recorder.jsonl"
    record(_event(), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for field in REQUIRED:
        assert field in payload


def test_retry_event_carries_attempt_link_and_reason(tmp_path: Path):
    path = tmp_path / "flight_recorder.jsonl"
    record(
        _event(
            event_id="evt-retry",
            event_type="retry",
            actor="judge",
            status="fail",
            attempt_number=2,
            retry_of="evt-judge-1",
            retry_reason="recommendation_allowed, no_raw_figures",
            detail="Retrying the Judge.",
        ),
        path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["attempt_number"] == 2
    assert payload["retry_of"] == "evt-judge-1"
    assert payload["retry_reason"] == "recommendation_allowed, no_raw_figures"
