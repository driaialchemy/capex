"""One proposal, top to bottom: metrics, three panelists, Judge, then a person."""

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template

from pydantic import ValidationError

from capex.compute import write_metrics
from capex.decision import decide
from capex.finance import Metrics, citeable_metrics
from capex.labels import RECOMMENDATIONS
from capex.flight_recorder import new_event, prompt_sha256, record
from capex.gates import PANEL_ROLES, gate_decision, gate_metrics, gate_positions
from capex.kill_switch import KillSwitchEngaged, is_engaged
from capex.llm import call_model, parse_json_response, repo_root
from capex.policy import load_policy
from capex.render import format_metric, render_memo
from capex.schemas import DecisionMemo, Position, Proposal
from capex.verifier import (
    VerificationReport,
    blocking_failures,
    proposal_findings,
    verify,
)


@dataclass
class RunResult:
    proposal_id: str
    run_dir: Path | None
    status: str
    recommendation: str | None
    lines: list[str]


def metrics_table(metrics: Metrics) -> str:
    """Two columns: metric key and the value a person would read. No proposal_id."""
    data = metrics.model_dump()
    rows = ["key | value"]
    for key in citeable_metrics():
        rows.append(f"{key} | {format_metric(key, data[key])}")
    return "\n".join(rows)


def render_prompt(
    role: str,
    proposal: Proposal,
    metrics: Metrics,
    positions_json: str = "",
    verifier_failures: str = "none",
    rules_decision: str = "",
) -> str:
    """Fill $placeholders. {{metric_key}} tokens in the prompt stay literal."""
    path = repo_root() / "prompts" / f"{role}.md"
    template = Template(path.read_text(encoding="utf-8"))
    mapping = {
        "proposal_id": proposal.proposal_id,
        "proposal_json": proposal.model_dump_json(indent=2),
        "metrics_table": metrics_table(metrics),
        "allowed": ", ".join(metrics.allowed_recommendations),
        "position_schema": json.dumps(Position.model_json_schema(), indent=2),
        "memo_schema": json.dumps(DecisionMemo.model_json_schema(), indent=2),
        "positions_json": positions_json,
        "verifier_failures": verifier_failures,
        "rules_decision": rules_decision,
    }
    return template.safe_substitute(mapping)


def _load_proposal(proposal_id: str) -> Proposal:
    path = repo_root() / "sample_data" / "proposals" / f"{proposal_id}.json"
    return Proposal.model_validate_json(path.read_text(encoding="utf-8"))


def _feedback(report: VerificationReport) -> str:
    failed = blocking_failures(report)
    if not failed:
        return "none"
    return "\n".join(f"{check.name}: {check.detail}" for check in failed)


def _verifier_detail(report: VerificationReport) -> str:
    failed = blocking_failures(report)
    if failed:
        parts = ["blocking: " + ", ".join(check.name for check in failed)]
    else:
        parts = ["blocking checks passed"]
    findings = proposal_findings(report)
    if findings:
        rendered = "; ".join(f"{check.name}: {check.detail}" for check in findings)
        parts.append("Proposal findings: " + rendered)
    return " | ".join(parts)


def _write_memo_md(path: Path, memo: DecisionMemo, metrics: Metrics, findings: list) -> None:
    rendered = render_memo(memo, metrics)
    shown = RECOMMENDATIONS.get(rendered.recommendation, rendered.recommendation)
    lines = [
        f"# {rendered.headline}",
        "",
        f"**{shown}**",
        "",
    ]
    if rendered.conditions:
        lines.extend(["## Conditions", ""])
        lines.extend(f"- {item}" for item in rendered.conditions)
        lines.append("")
    for section in rendered.sections:
        lines.extend([f"## {section.title}", "", section.body, ""])
    if rendered.disagreements_addressed:
        lines.extend(["## Disagreements addressed", ""])
        lines.extend(f"- {item}" for item in rendered.disagreements_addressed)
        lines.append("")
    if rendered.panel_concerns:
        lines.extend(["## Concerns from the panel", ""])
        lines.extend(f"- {item}" for item in rendered.panel_concerns)
        lines.append("")
    if findings:
        lines.extend(["## Proposal findings", ""])
        lines.extend(f"- {check.name}: {check.detail}" for check in findings)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_status(run_dir: Path, status: str, recommendation: str | None, attempts: int, findings: list) -> None:
    payload = {
        "status": status,
        "recommendation": recommendation,
        "attempts": attempts,
        "proposal_findings": [
            {"name": check.name, "detail": check.detail} for check in findings
        ],
    }
    (run_dir / "status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _judge(
    run_dir: Path,
    run_id: str,
    log_path: Path,
    proposal: Proposal,
    metrics: Metrics,
    positions_json: str,
    attempt: int,
    verifier_failures: str,
    lines: list[str],
    positions: list[Position],
    rules_decision: str,
) -> tuple[DecisionMemo | None, VerificationReport | None, str]:
    prompt = render_prompt(
        "judge",
        proposal,
        metrics,
        positions_json=positions_json,
        verifier_failures=verifier_failures,
        rules_decision=rules_decision,
    )
    text = call_model("judge", prompt, proposal.proposal_id, attempt)
    event = new_event(
        run_id,
        "model_call",
        "judge",
        "ok",
        f"judge attempt {attempt}",
        attempt_number=attempt,
        input_sha256=prompt_sha256(prompt),
        output_path=f"memo.attempt{attempt}.json",
    )
    try:
        memo = parse_json_response(text, DecisionMemo)
    except ValidationError:
        event = event.model_copy(update={"status": "fail", "detail": "Judge response was not valid JSON."})
        record(event, log_path)
        lines.append(f"judge attempt {attempt} fail")
        return None, None, event.event_id

    memo_path = run_dir / f"memo.attempt{attempt}.json"
    memo_path.write_text(memo.model_dump_json(indent=2) + "\n", encoding="utf-8")
    record(event, log_path)
    report = verify(memo, metrics, proposal, positions=positions)
    ver_path = run_dir / f"verification.attempt{attempt}.json"
    ver_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    record(
        new_event(
            run_id,
            "verifier",
            "system",
            "ok" if not blocking_failures(report) else "fail",
            _verifier_detail(report),
            attempt_number=attempt,
            output_path=f"verification.attempt{attempt}.json",
        ),
        log_path,
    )
    if blocking_failures(report):
        lines.append(f"judge attempt {attempt} fail")
    else:
        lines.append(f"judge attempt {attempt} ok")
    return memo, report, event.event_id


def run(proposal_id: str, runs_root: str | Path | None = None) -> RunResult:
    """Metrics, three independent panelists, Judge, one retry at most."""
    root = Path(runs_root) if runs_root is not None else Path("runs")
    log_path = root / "flight_recorder.jsonl"
    lines: list[str] = []

    if is_engaged():
        record(
            new_event(
                f"{proposal_id}-kill-switch",
                "kill_switch_block",
                "system",
                "blocked",
                "Kill switch is engaged. Refusing to run.",
            ),
            log_path,
        )
        raise KillSwitchEngaged(
            "Kill switch is engaged. Refusing to run. "
            "Unset CAPEX_KILL_SWITCH or remove the KILL_SWITCH file."
        )

    run_dir = write_metrics(proposal_id, runs_root=root)
    run_id = run_dir.name
    lines.append("metrics ok")
    record(
        new_event(run_id, "stage", "system", "ok", "metrics.json written", output_path="metrics.json"),
        log_path,
    )

    proposal = _load_proposal(proposal_id)
    policy = load_policy(repo_root() / "config" / "capex_policy.yaml")
    metrics_gate = gate_metrics(run_dir, proposal, policy)
    record(
        new_event(
            run_id,
            "gate",
            "system",
            "ok" if metrics_gate.passed else "fail",
            "metrics gate passed" if metrics_gate.passed else "; ".join(metrics_gate.reasons),
            output_path="metrics.json",
        ),
        log_path,
    )
    if not metrics_gate.passed:
        lines.append("metrics gate fail")
        _write_status(run_dir, "BLOCKED", None, 0, [])
        lines.append("status BLOCKED")
        lines.append(str(run_dir))
        return RunResult(proposal_id, run_dir, "BLOCKED", None, lines)

    metrics = Metrics.model_validate_json((run_dir / "metrics.json").read_text(encoding="utf-8"))
    decision = decide(metrics, policy)
    (run_dir / "decision.json").write_text(decision.model_dump_json(indent=2) + "\n", encoding="utf-8")
    decision_gate = gate_decision(run_dir, proposal, policy)
    record(
        new_event(
            run_id,
            "gate",
            "rules",
            "ok" if decision_gate.passed else "fail",
            "decision gate passed" if decision_gate.passed else "; ".join(decision_gate.reasons),
            output_path="decision.json",
        ),
        log_path,
    )
    if not decision_gate.passed:
        lines.append("decision gate fail")
        _write_status(run_dir, "BLOCKED", None, 0, [])
        lines.append("status BLOCKED")
        lines.append(str(run_dir))
        return RunResult(proposal_id, run_dir, "BLOCKED", None, lines)
    record(
        new_event(
            run_id,
            "stage",
            "rules",
            "ok",
            f"Rules decision {decision.rule}",
            output_path="decision.json",
        ),
        log_path,
    )
    lines.append(f"decision {decision.rule}")
    rules_text = (
        f"Rule {decision.rule} sets the recommendation to {decision.recommendation}. "
        "Copy that recommendation exactly."
    )
    positions_dir = run_dir / "positions"
    written_positions: list[Position] = []
    positions_dir.mkdir()
    for role in PANEL_ROLES:
        prompt = render_prompt(role, proposal, metrics)
        text = call_model(role, prompt, proposal_id, 1)
        try:
            position = parse_json_response(text, Position)
        except ValidationError:
            record(
                new_event(
                    run_id,
                    "model_call",
                    role,
                    "fail",
                    "Response was not a valid position.",
                    attempt_number=1,
                    input_sha256=prompt_sha256(prompt),
                ),
                log_path,
            )
            lines.append(f"{role} fail")
            _write_status(run_dir, "BLOCKED", None, 1, [])
            lines.append("status BLOCKED")
            lines.append(str(run_dir))
            return RunResult(proposal_id, run_dir, "BLOCKED", None, lines)
        written_positions.append(position)
        out = positions_dir / f"{role}.json"
        out.write_text(position.model_dump_json(indent=2) + "\n", encoding="utf-8")
        record(
            new_event(
                run_id,
                "model_call",
                role,
                "ok",
                f"{role} position written",
                attempt_number=1,
                input_sha256=prompt_sha256(prompt),
                output_path=f"positions/{role}.json",
            ),
            log_path,
        )
        lines.append(f"{role} ok")

    position_gate = gate_positions(run_dir)
    record(
        new_event(
            run_id,
            "gate",
            "system",
            "ok" if position_gate.passed else "fail",
            "positions gate passed" if position_gate.passed else "; ".join(position_gate.reasons),
        ),
        log_path,
    )
    if not position_gate.passed:
        lines.append("gate_positions fail")
        _write_status(run_dir, "BLOCKED", None, 1, [])
        lines.append("status BLOCKED")
        lines.append(str(run_dir))
        return RunResult(proposal_id, run_dir, "BLOCKED", None, lines)
    lines.append("gate_positions ok")

    positions_json = json.dumps(
        {
            role: json.loads((positions_dir / f"{role}.json").read_text(encoding="utf-8"))
            for role in PANEL_ROLES
        },
        indent=2,
    )
    memo, report, judge_event_id = _judge(
        run_dir,
        run_id,
        log_path,
        proposal,
        metrics,
        positions_json,
        attempt=1,
        verifier_failures="none",
        lines=lines,
        positions=written_positions,
        rules_decision=rules_text,
    )
    attempts = 1
    needs_retry = memo is None or report is None or bool(blocking_failures(report))
    if needs_retry:
        if report is None:
            reason = "invalid_json"
            feedback = "The previous response was not valid JSON."
        else:
            reason = ", ".join(check.name for check in blocking_failures(report))
            feedback = _feedback(report)
        record(
            new_event(
                run_id,
                "retry",
                "judge",
                "fail",
                f"Retrying the Judge because {reason}.",
                attempt_number=2,
                retry_of=judge_event_id,
                retry_reason=reason,
            ),
            log_path,
        )
        memo, report, _second_id = _judge(
            run_dir,
            run_id,
            log_path,
            proposal,
            metrics,
            positions_json,
            attempt=2,
            verifier_failures=feedback,
            lines=lines,
            positions=written_positions,
            rules_decision=rules_text,
        )
        attempts = 2

    findings = proposal_findings(report) if report is not None else []
    blocked = memo is None or report is None or bool(blocking_failures(report))
    status = "BLOCKED" if blocked else "PENDING_APPROVAL"
    recommendation = None if memo is None else memo.recommendation
    if memo is not None:
        _write_memo_md(run_dir / "memo.md", memo, metrics, findings)
    _write_status(run_dir, status, recommendation, attempts, findings)
    lines.append(f"status {status}")
    lines.append(str(run_dir))
    return RunResult(proposal_id, run_dir, status, recommendation, lines)
