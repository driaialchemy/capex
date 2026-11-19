"""Read run folders for the demo page. No new figures and no model calls."""

import json
import os
from pathlib import Path

from capex.approval import ApprovalError, latest_run as _latest_run
from capex.finance import Metrics
from capex.llm import repo_root
from capex.render import format_money
from capex.schemas import DecisionMemo, Position, Proposal
from capex.verifier import VerificationReport

_SCENARIOS = (
    ("plan", "Plan", "npv"),
    ("flows_minus_20", "Flows −20%", "npv_flows_minus_20"),
    ("flows_minus_10", "Flows −10%", "npv_flows_minus_10"),
    ("flows_plus_10", "Flows +10%", "npv_flows_plus_10"),
    ("rate_plus_2pp", "Rate +2pp", "npv_rate_plus_2pp"),
)


def runs_root_from_env(runs_root: str | Path | None = None) -> Path:
    """Folder that holds run directories. Tests set CAPEX_RUNS_ROOT."""
    if runs_root is not None:
        return Path(runs_root)
    return Path(os.environ.get("CAPEX_RUNS_ROOT", "runs"))


def list_proposals() -> list[Proposal]:
    folder = repo_root() / "sample_data" / "proposals"
    proposals = []
    for path in sorted(folder.glob("*.json")):
        proposals.append(Proposal.model_validate_json(path.read_text(encoding="utf-8")))
    return proposals


def latest_run(proposal_id: str, runs_root: str | Path | None = None) -> Path | None:
    """Newest run folder, or None when this proposal has not been reviewed."""
    try:
        return _latest_run(proposal_id, runs_root_from_env(runs_root))
    except ApprovalError:
        return None


def load_run(run_dir: str | Path) -> dict:
    """Artifacts already written for one run. Missing optional files stay empty."""
    folder = Path(run_dir)
    metrics = Metrics.model_validate_json((folder / "metrics.json").read_text(encoding="utf-8"))
    positions: dict[str, Position] = {}
    position_dir = folder / "positions"
    if position_dir.is_dir():
        for path in sorted(position_dir.glob("*.json")):
            position = Position.model_validate_json(path.read_text(encoding="utf-8"))
            positions[position.role] = position
    memo_attempts = [
        DecisionMemo.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("memo.attempt*.json"))
    ]
    verification_attempts = [
        VerificationReport.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("verification.attempt*.json"))
    ]
    memo_path = folder / "memo.md"
    memo_md = memo_path.read_text(encoding="utf-8") if memo_path.is_file() else ""
    status_path = folder / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    approvals_path = folder / "approvals.json"
    approvals: list[dict] = []
    if approvals_path.is_file():
        approvals = list(json.loads(approvals_path.read_text(encoding="utf-8")).get("approvals", []))
    return {
        "metrics": metrics,
        "positions": positions,
        "memo_attempts": memo_attempts,
        "verification_attempts": verification_attempts,
        "memo_md": memo_md,
        "status": status,
        "approvals": approvals,
    }


def run_events(run_id: str, runs_root: str | Path | None = None) -> list[dict]:
    """Flight-recorder rows for one run. Other runs stay out of the list."""
    path = runs_root_from_env(runs_root) / "flight_recorder.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("run_id") == run_id:
            events.append(event)
    return events


def sensitivity_rows(metrics: Metrics) -> list[dict]:
    """Stored NPV scenarios for the chart. Negative means the stored value is below zero."""
    values = metrics.model_dump()
    rows = []
    for key, scenario, field in _SCENARIOS:
        amount = float(values[field])
        rows.append(
            {
                "key": key,
                "scenario": scenario,
                "npv": amount,
                "negative": amount < 0,
                "label": format_money(amount),
            }
        )
    return rows
