"""Re-read metrics.json from disk and compare it with a fresh calculation."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from capex.finance import Metrics, compute_metrics
from capex.schemas import CapexPolicy, Position, Proposal
from capex.verifier import check_no_raw_figures_text, check_tokens_text

PANEL_ROLES = ("sponsor_advocate", "cfo_stress_tester", "operations_risk")


class GateResult(BaseModel):
    """Whether the file on disk still matches the finance engine."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    reasons: list[str]


def gate_metrics(run_dir: str | Path, proposal: Proposal, policy: CapexPolicy) -> GateResult:
    """Open metrics.json, validate it, and recompute. No in-memory shortcut."""
    path = Path(run_dir) / "metrics.json"
    if not path.is_file():
        return GateResult(passed=False, reasons=["metrics.json is missing"])

    try:
        saved = Metrics.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        return GateResult(passed=False, reasons=[error.errors()[0]["msg"]])

    reasons: list[str] = []
    if saved.proposal_id != proposal.proposal_id:
        reasons.append(
            f"proposal_id does not match ({saved.proposal_id} != {proposal.proposal_id})"
        )

    fresh = compute_metrics(proposal, policy)
    for key, fresh_value in fresh.model_dump().items():
        if getattr(saved, key) != fresh_value:
            reasons.append(f"{key} does not match a fresh calculation")
    return GateResult(passed=not reasons, reasons=reasons)


def _position_text(position: Position) -> str:
    parts = [argument.point for argument in position.arguments]
    parts.append(position.top_risk)
    parts.extend(position.questions_for_sponsor)
    return "\n".join(parts)


def gate_positions(run_dir: str | Path) -> GateResult:
    """Re-open each position file and check its prose. No in-memory shortcut."""
    folder = Path(run_dir) / "positions"
    reasons: list[str] = []
    for role in PANEL_ROLES:
        path = folder / f"{role}.json"
        if not path.is_file():
            reasons.append(f"{role}.json is missing")
            continue
        try:
            position = Position.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            reasons.append(f"{role}.json: {error.errors()[0]['msg']}")
            continue
        if position.role != role:
            reasons.append(f"{role}.json role is {position.role}")
        text = _position_text(position)
        cited: list[str] = []
        for argument in position.arguments:
            cited.extend(argument.cited_metrics)
        raw = check_no_raw_figures_text(text, role)
        tokens = check_tokens_text(text, cited)
        if not raw.passed:
            reasons.append(f"{role}: {raw.detail}")
        if not tokens.passed:
            reasons.append(f"{role}: {tokens.detail}")
    return GateResult(passed=not reasons, reasons=reasons)
