"""Replays match the schemas, and round-one prompts do not see the other panelists."""

import re

from capex.finance import citeable_metrics, compute_metrics
from capex.gates import PANEL_ROLES
from capex.llm import repo_root
from capex.pipeline import render_prompt
from capex.policy import load_policy
from capex.schemas import DecisionMemo, Position, Proposal
from capex.verifier import check_no_raw_figures_text, check_tokens_text

ROOT = repo_root()
PLACEHOLDERS = [
    "$proposal_id",
    "$proposal_json",
    "$metrics_table",
    "$allowed",
    "$position_schema",
    "$memo_schema",
    "$positions_json",
    "$verifier_failures",
]
TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _metrics(proposal: Proposal):
    return compute_metrics(proposal, load_policy(ROOT / "config" / "capex_policy.yaml"))


def _position_text(position: Position) -> str:
    parts = [argument.point for argument in position.arguments]
    parts.append(position.top_risk)
    parts.extend(position.questions_for_sponsor)
    return "\n".join(parts)


def test_every_replay_validates_and_tokens_are_citeable():
    citeable = set(citeable_metrics())
    for proposal_id in ("CPX-001", "CPX-002", "CPX-003"):
        folder = ROOT / "sample_data" / "replays" / proposal_id
        for role in PANEL_ROLES:
            text = (folder / f"{role}.json").read_text(encoding="utf-8")
            position = Position.model_validate_json(text)
            cited: list[str] = []
            for argument in position.arguments:
                cited.extend(argument.cited_metrics)
            prose = _position_text(position)
            assert check_tokens_text(prose, cited).passed
            assert check_no_raw_figures_text(prose, role).passed
            for token in TOKEN.findall(text):
                assert token in citeable
        for name in ("judge.json", "judge.attempt2.json"):
            path = folder / name
            if not path.is_file():
                continue
            memo_text = path.read_text(encoding="utf-8")
            DecisionMemo.model_validate_json(memo_text)
            for token in TOKEN.findall(memo_text):
                assert token in citeable


def test_cpx_002_cfo_highlights_the_downside_case():
    text = (
        ROOT / "sample_data" / "replays" / "CPX-002" / "cfo_stress_tester.json"
    ).read_text(encoding="utf-8")
    assert "{{npv_flows_minus_10}}" in text


def test_round_one_prompts_omit_other_panelists_and_leave_no_placeholders():
    for proposal_id in ("CPX-001", "CPX-002", "CPX-003"):
        proposal = _proposal(proposal_id)
        metrics = _metrics(proposal)
        folder = ROOT / "sample_data" / "replays" / proposal_id
        for role in PANEL_ROLES:
            prompt = render_prompt(role, proposal, metrics)
            for other in PANEL_ROLES:
                if other == role:
                    continue
                replay = (folder / f"{other}.json").read_text(encoding="utf-8")
                assert replay not in prompt
            for placeholder in PLACEHOLDERS:
                assert placeholder not in prompt
        judge = render_prompt(
            "judge",
            proposal,
            metrics,
            positions_json="{}",
            verifier_failures="none",
        )
        for placeholder in PLACEHOLDERS:
            assert placeholder not in judge
