"""Proposal schema accepts a valid case and rejects the broken ones."""

import pytest
from pydantic import ValidationError

from capex.schemas import Proposal


def _valid(**overrides):
    data = {
        "proposal_id": "CPX-TEST",
        "title": "Test press",
        "sponsor": "Sam Lee",
        "department": "Manufacturing",
        "initial_investment": 1000,
        "useful_life_years": 2,
        "salvage_value": 0,
        "annual_net_cash_flows": [100, 100],
        "assumptions": ["Volume stays flat."],
        "sponsor_notes": "A complete test proposal.",
    }
    data.update(overrides)
    return data


def test_valid_proposal_loads():
    proposal = Proposal.model_validate(_valid())
    assert proposal.proposal_id == "CPX-TEST"
    assert len(proposal.annual_net_cash_flows) == proposal.useful_life_years


def test_cash_flow_length_must_match_useful_life():
    with pytest.raises(ValidationError):
        Proposal.model_validate(_valid(annual_net_cash_flows=[100]))


def test_negative_investment_is_rejected():
    with pytest.raises(ValidationError):
        Proposal.model_validate(_valid(initial_investment=-420000))


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Proposal.model_validate(_valid(unexpected_note="not in the schema"))
