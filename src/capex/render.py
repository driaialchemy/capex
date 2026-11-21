"""Fill {{metric_key}} tokens with display text. Stored metrics keep their cents."""

import re

from capex.finance import Metrics
from capex.schemas import DecisionMemo, MemoSection

_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

_MONEY_KEYS = {
    "npv",
    "npv_flows_minus_20",
    "npv_flows_minus_10",
    "npv_flows_plus_10",
    "npv_rate_plus_2pp",
    "initial_investment",
}
_RATE_KEYS = {"irr", "hurdle_rate"}
_YEAR_KEYS = {"payback_years", "discounted_payback_years", "max_payback_years"}


def format_money(amount: float) -> str:
    """Whole dollars with a thousands separator. Cents stay in Metrics, not here."""
    dollars = round(amount)
    if dollars < 0:
        return f"-${abs(dollars):,}"
    return f"${dollars:,}"


def format_metric(key: str, value: object) -> str:
    """One stored value as a person would read it on the memo."""
    if key in _MONEY_KEYS and isinstance(value, (int, float)):
        return format_money(float(value))
    if key in _RATE_KEYS:
        if value is None:
            return "n/a"
        if isinstance(value, (int, float)):
            return f"{value * 100:.1f}%"
    if key in _YEAR_KEYS:
        if value is None:
            return "not recovered"
        if isinstance(value, (int, float)):
            return f"{value:.1f}"
    if key == "allowed_recommendations" and isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _fill(text: str, metrics: Metrics) -> str:
    values = metrics.model_dump()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in values or key == "proposal_id":
            return match.group(0)
        return format_metric(key, values[key])

    return _TOKEN.sub(replace, text)


def render_text(text: str, metrics: Metrics) -> str:
    """Replace {{metric_key}} tokens. Unknown tokens stay as written."""
    return _fill(text, metrics)


def render_memo(memo: DecisionMemo, metrics: Metrics) -> DecisionMemo:
    """Return a new memo with tokens replaced. The caller's memo is unchanged."""
    sections = [
        MemoSection(title=section.title, body=_fill(section.body, metrics))
        for section in memo.sections
    ]
    return memo.model_copy(
        update={
            "headline": _fill(memo.headline, metrics),
            "sections": sections,
            "conditions": [_fill(item, metrics) for item in memo.conditions],
            "disagreements_addressed": [
                _fill(item, metrics) for item in memo.disagreements_addressed
            ],
            "panel_concerns": [_fill(item, metrics) for item in memo.panel_concerns],
        }
    )
