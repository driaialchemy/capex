"""Proposal, policy, position, and decision-memo shapes. Unknown fields are rejected."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Recommendation = Literal["APPROVE", "APPROVE_WITH_CONDITIONS", "DEFER", "REJECT"]
PanelRole = Literal["sponsor_advocate", "cfo_stress_tester", "operations_risk"]


class ApprovalTiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_head_if_under: float
    cfo_if_up_to: float
    above_that: str


class CapexPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hurdle_rate: float
    max_payback_years: int
    stress_test_metric: str
    approval_tiers: ApprovalTiers
    allowed_recommendations: list[str]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    title: str
    sponsor: str
    department: str
    initial_investment: float = Field(gt=0)
    useful_life_years: int = Field(ge=1, le=20)
    salvage_value: float = Field(ge=0)
    annual_net_cash_flows: list[float]
    assumptions: list[str]
    sponsor_notes: str

    @model_validator(mode="after")
    def cash_flows_match_useful_life(self):
        count = len(self.annual_net_cash_flows)
        if count != self.useful_life_years:
            raise ValueError(
                "annual_net_cash_flows length must equal useful_life_years "
                f"({count} != {self.useful_life_years})"
            )
        return self


class MemoSection(BaseModel):
    """One headed block of a decision memo."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class DecisionMemo(BaseModel):
    """A memo. Figures in the headline and body are {{metric_key}} tokens."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    recommendation: Recommendation
    headline: str
    sections: list[MemoSection]
    cited_metrics: list[str]
    conditions: list[str] = Field(default_factory=list)
    disagreements_addressed: list[str] = Field(default_factory=list)
    panel_concerns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def conditions_required_for_conditional_approval(self):
        if self.recommendation == "APPROVE_WITH_CONDITIONS" and not self.conditions:
            raise ValueError(
                "conditions must be non-empty when recommendation is APPROVE_WITH_CONDITIONS"
            )
        return self


class Argument(BaseModel):
    """One point in a panelist's position."""

    model_config = ConfigDict(extra="forbid")

    point: str
    cited_metrics: list[str]
    cited_assumptions: list[str]


class Position(BaseModel):
    """One panelist's independent position. It does not see the others."""

    model_config = ConfigDict(extra="forbid")

    role: PanelRole
    stance: Recommendation
    arguments: list[Argument]
    top_risk: str
    questions_for_sponsor: list[str]
