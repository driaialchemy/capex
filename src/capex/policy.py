"""Load the policy file and name the approval tier for an amount."""

from pathlib import Path

import yaml

from capex.schemas import CapexPolicy


def load_policy(path: str | Path) -> CapexPolicy:
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return CapexPolicy.model_validate(data)


def approval_tier(amount: float, policy: CapexPolicy) -> str:
    tiers = policy.approval_tiers
    if amount < tiers.department_head_if_under:
        return "department_head"
    if amount <= tiers.cfo_if_up_to:
        return "cfo"
    return tiers.above_that
