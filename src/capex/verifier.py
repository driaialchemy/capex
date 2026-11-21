"""Check a decision memo against the figures. No model and no network."""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from capex.decision import decide
from capex.finance import Metrics, citeable_metrics
from capex.labels import RECOMMENDATIONS
from capex.policy import load_policy
from capex.schemas import DecisionMemo, Position, Proposal

_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_YEAR_LABEL = re.compile(r"\byear\s+(?:[1-9]|1[0-9]|20)\b", re.IGNORECASE)
_MONEY = re.compile(r"\$\s*\d[\d,]*")
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_MULTI_DIGIT = re.compile(r"\d{2,}")
_PAYBACK_CLAIM = re.compile(
    r"(?:pays for itself in|payback of)\s+(\d+(?:\.\d+)?)\s+years?",
    re.IGNORECASE,
)


class Check(BaseModel):
    """One named pass or fail from the verifier.

    Blocking checks can stop a retry from succeeding and can keep a memo
    from reaching PENDING_APPROVAL. Non-blocking failures are proposal
    findings: the approver sees them, and they do not by themselves block.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    blocking: bool
    detail: str


_BLOCKING = {
    "recommendation_allowed": True,
    "no_raw_figures": True,
    "tokens_valid": True,
    "recommendation_matches_rules": True,
    "conditions_cite_stress": True,
    "sponsor_payback_claim": False,
    "sponsor_percent_claims": False,
    "panel_disagreement": False,
}


def _make(name: str, passed: bool, detail: str) -> Check:
    return Check(name=name, passed=passed, blocking=_BLOCKING[name], detail=detail)


class VerificationReport(BaseModel):
    """The inspector's result. passed is true when every blocking check passed."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    checks: list[Check]


def _prose(memo: DecisionMemo) -> str:
    parts = [memo.headline]
    parts.extend(section.body for section in memo.sections)
    return "\n".join(parts)


def _visible(text: str) -> str:
    """Prose with tokens and Year 1–Year 20 labels removed."""
    masked = _TOKEN.sub(" ", text)
    return _YEAR_LABEL.sub(" ", masked)


def _raw_figure(text: str) -> str | None:
    visible = _visible(text)
    for pattern in (_MONEY, _PERCENT, _MULTI_DIGIT):
        match = pattern.search(visible)
        if match:
            return match.group(0)
    return None


def _check_recommendation(memo: DecisionMemo, metrics: Metrics) -> Check:
    allowed = metrics.allowed_recommendations
    label = RECOMMENDATIONS[memo.recommendation]
    if memo.recommendation in allowed:
        return _make(
            "recommendation_allowed",
            True,
            f"Policy allows {label} for this proposal.",
        )
    listed = ", ".join(RECOMMENDATIONS[item] for item in allowed)
    return _make(
        "recommendation_allowed",
        False,
        f"The recommendation isn't allowed by the spending policy. Allowed: {listed}.",
    )


def _raw_sentence(found: str) -> str:
    return f"The memo says '{found}' directly instead of using the calculator's figure."


def check_no_raw_figures_text(text: str, label: str = "text") -> Check:
    """Raw-figure check for one block of text. Positions and memos both use this."""
    _ = label
    found = _raw_figure(text)
    if found is not None:
        return _make("no_raw_figures", False, _raw_sentence(found))
    return _make("no_raw_figures", True, "Every number came from the calculator, not the AI.")


def _check_no_raw_figures(memo: DecisionMemo) -> Check:
    problems: list[str] = []
    chunks = [("headline", memo.headline)]
    for index, section in enumerate(memo.sections, start=1):
        chunks.append((f"section {index}", section.body))
    for _label, text in chunks:
        found = _raw_figure(text)
        if found is not None:
            problems.append(_raw_sentence(found))
    if problems:
        return _make("no_raw_figures", False, " ".join(problems))
    return _make("no_raw_figures", True, "Every number came from the calculator, not the AI.")


def check_tokens_text(text: str, cited_metrics: list[str]) -> Check:
    """Token check for one block of text and the metrics it claims to cite."""
    used = _TOKEN.findall(text)
    citeable = set(citeable_metrics())
    problems: list[str] = []
    if "proposal_id" in used or "proposal_id" in cited_metrics:
        problems.append("proposal_id is not a real calculation")
    for name in used:
        if name == "proposal_id":
            continue
        if name not in citeable:
            problems.append(f"{name} points to a calculation that doesn't exist")
        elif name not in cited_metrics:
            problems.append(f"{name} is used but was not listed as a cited figure")
    if problems:
        return _make("tokens_valid", False, " ".join(problems))
    return _make("tokens_valid", True, "Every figure links to a real calculation.")


def _check_tokens(memo: DecisionMemo) -> Check:
    return check_tokens_text(_prose(memo), memo.cited_metrics)


def _check_payback_claim(proposal: Proposal, metrics: Metrics) -> Check:
    claims = [float(match) for match in _PAYBACK_CLAIM.findall(proposal.sponsor_notes)]
    if not claims:
        return _make(
            "sponsor_payback_claim",
            True,
            "No payback claim in the sponsor notes.",
        )
    problems: list[str] = []
    for claim in claims:
        if metrics.payback_years is None:
            problems.append(
                f"The sponsor says it pays for itself in {claim:g} years, "
                "but the cash flows never recover the investment."
            )
        elif abs(claim - metrics.payback_years) > 0.5:
            problems.append(
                f"The sponsor says it pays for itself in {claim:g} years, "
                f"but the calculator's payback is {metrics.payback_years:.1f} years."
            )
    if problems:
        return _make("sponsor_payback_claim", False, " ".join(problems))
    return _make(
        "sponsor_payback_claim",
        True,
        "The sponsor's payback claim matches the math.",
    )


def _check_percent_claims(proposal: Proposal) -> Check:
    """Informational. A percentage in the notes is reported and does not fail the memo."""
    found = _PERCENT.findall(proposal.sponsor_notes)
    if not found:
        return _make("sponsor_percent_claims", True, "No percentage claims in the sponsor's notes.")
    listed = " ".join(
        f"UNVERIFIED: {claim.replace(' ', '')} appears in the sponsor's notes, "
        "and the calculator did not check it."
        for claim in found
    )
    return _make("sponsor_percent_claims", True, listed)


def _policy_path() -> Path:
    start = Path(__file__).resolve().parent
    for folder in (start, *start.parents):
        candidate = folder / "config" / "capex_policy.yaml"
        if candidate.is_file():
            return candidate
    return Path("config/capex_policy.yaml")


def _rules(metrics: Metrics):
    policy = load_policy(_policy_path())
    return policy, decide(metrics, policy)


def _check_rules_match(memo: DecisionMemo, metrics: Metrics) -> Check:
    _policy, decision = _rules(metrics)
    if memo.recommendation == decision.recommendation:
        return _make(
            "recommendation_matches_rules",
            True,
            "The memo's recommendation matches the rules decision.",
        )
    got = RECOMMENDATIONS[memo.recommendation]
    expected = RECOMMENDATIONS[decision.recommendation]
    return _make(
        "recommendation_matches_rules",
        False,
        f"The memo says {got}. The rules decision is {expected}.",
    )


def _check_conditions_cite_stress(memo: DecisionMemo, metrics: Metrics) -> Check:
    policy, _decision = _rules(metrics)
    if memo.recommendation != "APPROVE_WITH_CONDITIONS":
        return _make(
            "conditions_cite_stress",
            True,
            "This recommendation does not require a stress-test condition.",
        )
    token = "{{" + policy.stress_test_metric + "}}"
    if any(token in item for item in memo.conditions):
        return _make(
            "conditions_cite_stress",
            True,
            "A condition cites the stress-test figure.",
        )
    return _make(
        "conditions_cite_stress",
        False,
        "Approve with conditions needs a condition that cites the stress-test figure.",
    )


def _check_panel_disagreement(positions: list[Position] | None, metrics: Metrics) -> Check:
    if not positions:
        return _make(
            "panel_disagreement",
            True,
            "The panel does not share a different outcome.",
        )
    _policy, decision = _rules(metrics)
    counts: dict[str, int] = {}
    for position in positions:
        counts[position.stance] = counts.get(position.stance, 0) + 1
    disagreed = [
        stance
        for stance, count in counts.items()
        if stance != decision.recommendation and count >= 2
    ]
    if not disagreed:
        return _make(
            "panel_disagreement",
            True,
            "The panel does not share a different outcome.",
        )
    named = ", ".join(RECOMMENDATIONS[stance] for stance in disagreed)
    return _make(
        "panel_disagreement",
        False,
        f"Two or more panelists argued for {named}, which is not the rules decision.",
    )


def verify(
    memo: DecisionMemo,
    metrics: Metrics,
    proposal: Proposal,
    positions: list[Position] | None = None,
) -> VerificationReport:
    """Read the memo, the metrics, and the proposal notes. Positions are optional."""
    checks = [
        _check_recommendation(memo, metrics),
        _check_no_raw_figures(memo),
        _check_tokens(memo),
        _check_rules_match(memo, metrics),
        _check_conditions_cite_stress(memo, metrics),
        _check_payback_claim(proposal, metrics),
        _check_percent_claims(proposal),
        _check_panel_disagreement(positions, metrics),
    ]
    passed = all(check.passed for check in checks if check.blocking)
    return VerificationReport(passed=passed, checks=checks)


def blocking_failures(report: VerificationReport) -> list[Check]:
    """Checks that failed and are allowed to block approval."""
    return [check for check in report.checks if check.blocking and not check.passed]


def proposal_findings(report: VerificationReport) -> list[Check]:
    """Non-blocking checks that failed. The approver still sees these."""
    return [check for check in report.checks if not check.blocking and not check.passed]
