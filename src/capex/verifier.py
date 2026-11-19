"""Check a decision memo against the figures. No model and no network."""

import re

from pydantic import BaseModel, ConfigDict

from capex.finance import Metrics, citeable_metrics
from capex.schemas import DecisionMemo, Proposal

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
    "sponsor_payback_claim": False,
    "sponsor_percent_claims": False,
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
    if memo.recommendation in allowed:
        return _make(
            "recommendation_allowed",
            True,
            f"{memo.recommendation} is allowed.",
        )
    listed = ", ".join(allowed)
    return _make(
        "recommendation_allowed",
        False,
        f"{memo.recommendation} is not allowed. Allowed: {listed}.",
    )


def check_no_raw_figures_text(text: str, label: str = "text") -> Check:
    """Raw-figure check for one block of text. Positions and memos both use this."""
    found = _raw_figure(text)
    if found is not None:
        return _make("no_raw_figures", False, f"{label} contains a raw figure: {found}")
    return _make("no_raw_figures", True, "No raw figures in the memo.")


def _check_no_raw_figures(memo: DecisionMemo) -> Check:
    problems: list[str] = []
    chunks = [("headline", memo.headline)]
    for index, section in enumerate(memo.sections, start=1):
        chunks.append((f"section {index}", section.body))
    for label, text in chunks:
        found = _raw_figure(text)
        if found is not None:
            problems.append(f"{label} contains a raw figure: {found}")
    if problems:
        return _make("no_raw_figures", False, " ".join(problems))
    return _make("no_raw_figures", True, "No raw figures in the memo.")


def check_tokens_text(text: str, cited_metrics: list[str]) -> Check:
    """Token check for one block of text and the metrics it claims to cite."""
    used = _TOKEN.findall(text)
    citeable = set(citeable_metrics())
    problems: list[str] = []
    if "proposal_id" in used or "proposal_id" in cited_metrics:
        problems.append("{{proposal_id}} is not a citeable metric")
    for name in used:
        if name == "proposal_id":
            continue
        if name not in citeable:
            problems.append("{{" + name + "}} is not a citeable metric")
        elif name not in cited_metrics:
            problems.append("{{" + name + "}} is used but not listed in cited_metrics")
    if problems:
        return _make("tokens_valid", False, " ".join(problems))
    return _make("tokens_valid", True, "Every token is a cited metric.")


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
                f"Notes claim payback of {claim:g} years, but the investment is not recovered."
            )
        elif abs(claim - metrics.payback_years) > 0.5:
            problems.append(
                f"Notes claim payback of {claim:g} years; "
                f"computed payback is {metrics.payback_years:.1f} years."
            )
    if problems:
        return _make("sponsor_payback_claim", False, " ".join(problems))
    return _make(
        "sponsor_payback_claim",
        True,
        "Payback claims match the computed payback.",
    )


def _check_percent_claims(proposal: Proposal) -> Check:
    """Informational. A percentage in the notes is reported and does not fail the memo."""
    found = _PERCENT.findall(proposal.sponsor_notes)
    if not found:
        return _make("sponsor_percent_claims", True, "No percentage claims.")
    listed = ", ".join(f"UNVERIFIED: {claim.replace(' ', '')}" for claim in found)
    return _make("sponsor_percent_claims", True, listed)


def verify(memo: DecisionMemo, metrics: Metrics, proposal: Proposal) -> VerificationReport:
    """Read the memo, the metrics, and the proposal notes. Nothing else."""
    checks = [
        _check_recommendation(memo, metrics),
        _check_no_raw_figures(memo),
        _check_tokens(memo),
        _check_payback_claim(proposal, metrics),
        _check_percent_claims(proposal),
    ]
    passed = all(check.passed for check in checks if check.blocking)
    return VerificationReport(passed=passed, checks=checks)


def blocking_failures(report: VerificationReport) -> list[Check]:
    """Checks that failed and are allowed to block approval."""
    return [check for check in report.checks if check.blocking and not check.passed]


def proposal_findings(report: VerificationReport) -> list[Check]:
    """Non-blocking checks that failed. The approver still sees these."""
    return [check for check in report.checks if not check.blocking and not check.passed]
