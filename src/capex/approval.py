"""A person signs the memo. The role has to match the dollar tier."""

import json
from datetime import datetime, timezone
from pathlib import Path

from capex.finance import Metrics
from capex.flight_recorder import new_event, record

REQUIRED_ROLES = {
    "department_head": ("department_head",),
    "cfo": ("cfo",),
    "cfo_and_ceo": ("cfo", "ceo"),
}


class ApprovalError(RuntimeError):
    """The sign-off was refused."""


def _approvals(run_dir: Path) -> list[dict]:
    path = run_dir / "approvals.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("approvals", []))


def latest_run(proposal_id: str, runs_root: str | Path | None = None) -> Path:
    """Newest run folder for a proposal. Names sort in UTC timestamp order."""
    root = Path(runs_root) if runs_root is not None else Path("runs")
    prefix = f"{proposal_id}-"
    folders = [path for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix)]
    if not folders:
        raise ApprovalError(f"No run folder for {proposal_id}")
    return max(folders, key=lambda path: path.name)


def approve(
    run_dir: str | Path,
    approver_name: str,
    approver_role: str,
    decision: str,
    note: str = "",
) -> dict:
    """Record one human decision. Refusals raise and do not write an approval event."""
    folder = Path(run_dir)
    status_path = folder / "status.json"
    if not status_path.is_file():
        raise ApprovalError("status.json is missing")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "PENDING_APPROVAL":
        raise ApprovalError(
            f"status is {status.get('status')}, not PENDING_APPROVAL. Refusing to approve."
        )
    if decision not in {"APPROVED", "RETURNED"}:
        raise ApprovalError("decision must be APPROVED or RETURNED")

    metrics = Metrics.model_validate_json((folder / "metrics.json").read_text(encoding="utf-8"))
    allowed = REQUIRED_ROLES.get(metrics.approval_tier, ())
    if approver_role not in allowed:
        raise ApprovalError(
            f"{approver_role} cannot approve a {metrics.approval_tier} proposal"
        )

    approvals = _approvals(folder)
    if any(item["approver_role"] == approver_role for item in approvals):
        raise ApprovalError(f"{approver_role} has already decided on this run")

    approvals.append(
        {
            "approver_name": approver_name,
            "approver_role": approver_role,
            "decision": decision,
            "note": note,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )
    (folder / "approvals.json").write_text(
        json.dumps({"approvals": approvals}, indent=2) + "\n",
        encoding="utf-8",
    )

    if decision == "RETURNED":
        status["status"] = "RETURNED"
    else:
        approved_roles = {
            item["approver_role"] for item in approvals if item["decision"] == "APPROVED"
        }
        if all(role in approved_roles for role in allowed):
            status["status"] = "FINAL"
        else:
            status["status"] = "PENDING_APPROVAL"
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    record(
        new_event(
            folder.name,
            "approval",
            approver_name,
            "ok",
            f"{decision} as {approver_role}",
        ),
        folder.parent / "flight_recorder.jsonl",
    )
    return status
