"""Write runs/<proposal-id>-<UTC timestamp>/metrics.json for one proposal."""

import sys
from datetime import datetime, timezone
from pathlib import Path

from capex.finance import compute_metrics
from capex.kill_switch import assert_not_engaged
from capex.llm import repo_root
from capex.policy import load_policy
from capex.schemas import Proposal


def write_metrics(proposal_id: str, runs_root: str | Path | None = None) -> Path:
    """Compute one proposal and store the metrics file. Returns the run directory."""
    assert_not_engaged()
    source = repo_root() / "sample_data" / "proposals" / f"{proposal_id}.json"
    if not source.is_file():
        raise FileNotFoundError(f"No proposal file for {proposal_id}")
    proposal = Proposal.model_validate_json(source.read_text(encoding="utf-8"))
    policy = load_policy(repo_root() / "config" / "capex_policy.yaml")
    metrics = compute_metrics(proposal, policy)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(runs_root) if runs_root is not None else Path("runs")
    run_dir = root / f"{proposal_id}-{stamp}"
    run_dir.mkdir(parents=True)
    text = metrics.model_dump_json(indent=2) + "\n"
    (run_dir / "metrics.json").write_text(text, encoding="utf-8")
    return run_dir


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m capex.compute CPX-001")
        return 1
    try:
        run_dir = write_metrics(sys.argv[1])
    except FileNotFoundError as error:
        print(error)
        return 1
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
