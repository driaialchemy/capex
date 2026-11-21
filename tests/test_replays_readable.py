"""Replays stay valid, and the words a person reads stay plain."""

import json
import re

from capex.finance import compute_metrics
from capex.llm import repo_root
from capex.pipeline import run
from capex.policy import load_policy
from capex.render import render_memo, render_text
from capex.schemas import DecisionMemo, Position, Proposal
from capex.verifier import VerificationReport

ROOT = repo_root()
_CODES = re.compile(r"\b(?:APPROVE_WITH_CONDITIONS|APPROVE|DEFER|REJECT)\b")
_EMPTY_FLAGS = re.compile(r"(?m)^#+ .*Red flags.*\n\s*(?:None\.?)?\s*$")


def _proposal(proposal_id: str) -> Proposal:
    path = ROOT / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _memo_prose(memo: DecisionMemo) -> str:
    parts = [memo.headline]
    for section in memo.sections:
        parts.extend([section.title, section.body])
    parts.extend(memo.conditions)
    parts.extend(memo.disagreements_addressed)
    return "\n".join(parts)


def _assert_readable(text: str) -> None:
    assert "{{" not in text
    assert _CODES.search(text) is None
    assert _EMPTY_FLAGS.search(text) is None


def test_replays_validate_and_rendered_memos_stay_plain(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")
    policy = load_policy(ROOT / "config" / "capex_policy.yaml")
    metrics = {name: compute_metrics(_proposal(name), policy) for name in ("CPX-001", "CPX-002", "CPX-003")}
    rendered_cpx_002 = ""
    for path in sorted((ROOT / "sample_data" / "replays").rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        proposal_id = path.relative_to(ROOT / "sample_data" / "replays").parts[0]
        if "headline" in payload:
            memo = DecisionMemo.model_validate(payload)
            rendered = render_memo(memo, metrics[proposal_id])
            prose = _memo_prose(rendered)
            _assert_readable(prose)
            if proposal_id == "CPX-002":
                rendered_cpx_002 = prose
        else:
            position = Position.model_validate(payload)
            chunks = [argument.point for argument in position.arguments]
            chunks.append(position.top_risk)
            chunks.extend(position.questions_for_sponsor)
            filled = "\n".join(render_text(chunk, metrics[proposal_id]) for chunk in chunks)
            _assert_readable(filled)
    assert "net present value" in rendered_cpx_002

    result = run("CPX-002", runs_root=tmp_path)
    memo_md = (result.run_dir / "memo.md").read_text(encoding="utf-8")
    _assert_readable(memo_md)
    assert "net present value" in memo_md
    assert "## Proposal findings" not in memo_md

    cpx_003 = run("CPX-003", runs_root=tmp_path)
    first = VerificationReport.model_validate_json(
        (cpx_003.run_dir / "verification.attempt1.json").read_text(encoding="utf-8")
    )
    second = VerificationReport.model_validate_json(
        (cpx_003.run_dir / "verification.attempt2.json").read_text(encoding="utf-8")
    )
    second_memo = DecisionMemo.model_validate_json(
        (cpx_003.run_dir / "memo.attempt2.json").read_text(encoding="utf-8")
    )
    assert next(item.passed for item in first.checks if item.name == "recommendation_allowed") is False
    assert next(item.passed for item in first.checks if item.name == "no_raw_figures") is False
    assert next(item.passed for item in second.checks if item.name == "recommendation_allowed") is True
    assert next(item.passed for item in second.checks if item.name == "no_raw_figures") is True
    assert second_memo.recommendation == "REJECT"
