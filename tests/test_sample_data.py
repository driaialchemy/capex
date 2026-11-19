"""Sample proposals and the policy file load, and the tiers match the demo amounts."""

from pathlib import Path

from capex.policy import approval_tier, load_policy
from capex.schemas import Proposal

ROOT = Path(__file__).resolve().parents[1]


def test_sample_proposals_validate_and_ids_are_unique():
    folder = ROOT / "sample_data" / "proposals"
    files = sorted(folder.glob("*.json"))
    assert len(files) == 3

    ids = []
    for path in files:
        proposal = Proposal.model_validate_json(path.read_text(encoding="utf-8"))
        ids.append(proposal.proposal_id)

    assert len(ids) == len(set(ids))
    assert set(ids) == {"CPX-001", "CPX-002", "CPX-003"}


def test_policy_loads_and_approval_tiers():
    policy = load_policy(ROOT / "config" / "capex_policy.yaml")
    assert approval_tier(200000, policy) == "department_head"
    assert approval_tier(780000, policy) == "cfo"
    assert approval_tier(1150000, policy) == "cfo_and_ceo"
