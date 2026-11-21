"""One page for the live CapEx review. Layout only."""

import os
from pathlib import Path

import streamlit as st

from capex.approval import ApprovalError, approve
from capex.decision import decide
from capex.gates import PANEL_ROLES
from capex.kill_switch import KillSwitchEngaged, engage, is_engaged, release
from capex.labels import (
    CHECKS_FAILED,
    CHECKS_PASSED,
    EVENT_TYPES,
    LOG_COLUMNS as LOG_HEADERS,
    METRICS as METRIC_LABELS,
    REASONS,
    RECOMMENDATIONS,
    ROLES,
    RULES,
    SIGN_OFF_DECISIONS,
    SIGN_OFF_ROLES,
    STATUSES,
)
from capex.llm import current_mode, repo_root
from capex.pipeline import run
from capex.policy import approval_tier, load_policy
from capex.render import format_metric, format_money, render_text
from capex.ui_data import latest_run, list_proposals, load_run, run_events, sensitivity_rows
from capex.ui_theme import apply_theme, hero_path

LOG_COLUMNS = (
    "ts",
    "event_type",
    "actor",
    "attempt_number",
    "retry_of",
    "retry_reason",
    "status",
    "detail",
)
METRIC_KEYS = (
    "npv",
    "irr",
    "payback_years",
    "discounted_payback_years",
    "hurdle_rate",
    "max_payback_years",
    "initial_investment",
    "approval_tier",
    "allowed_recommendations",
)

st.set_page_config(page_title="CapEx Decision Engine", layout="wide")
apply_theme()
_hero = hero_path()
if _hero is not None:
    st.image(str(_hero), use_container_width=True)
st.title("CapEx Decision Engine")
st.caption("The AI argues. Code calculates. Code inspects. A person decides.")

_CHIPS = {
    "AI judgment": "capex-ai",
    "Code check": "capex-code",
    "Record": "capex-record",
    "Human": "capex-human",
}


def _runs_root() -> Path:
    return Path(os.environ.get("CAPEX_RUNS_ROOT", "runs"))


def _label(text: str) -> None:
    kind = _CHIPS.get(text, "")
    st.markdown(f'<p class="capex-label {kind}">{text}</p>', unsafe_allow_html=True)


def _needs_run() -> None:
    st.info("Run a review to see this.")


def _person_memo(memo_md: str) -> str:
    """The decision memo without the machine findings block at the bottom."""
    marker = "\n## Proposal findings"
    if marker in memo_md:
        return memo_md.split(marker, 1)[0].rstrip() + "\n"
    return memo_md


proposals = list_proposals()
proposal_ids = [item.proposal_id for item in proposals]
policy = load_policy(repo_root() / "config" / "capex_policy.yaml")

with st.sidebar:
    proposal_id = st.selectbox("Proposal", proposal_ids, key="proposal")
    if st.button("Run review", key="run_review"):
        try:
            result = run(proposal_id, runs_root=_runs_root())
            st.success(result.status)
        except KillSwitchEngaged as error:
            st.error(str(error))
        except FileNotFoundError as error:
            st.error(str(error))
    st.write(f"Mode: {current_mode()}")
    st.write("Kill switch: engaged" if is_engaged() else "Kill switch: off")
    log_path = _runs_root() / "flight_recorder.jsonl"
    if st.button("Engage kill switch", key="engage_kill_switch"):
        engage(repo_root(), log_path)
        st.rerun()
    if st.button("Release kill switch", key="release_kill_switch"):
        release(repo_root(), log_path)
        st.rerun()

proposal = next(item for item in proposals if item.proposal_id == proposal_id)
run_dir = latest_run(proposal_id, _runs_root())
loaded = load_run(run_dir) if run_dir is not None else None

proposal_tab, calculator_tab, panel_tab, inspector_tab, logbook_tab, signoff_tab = st.tabs(
    [
        "1 Proposal",
        "2 Calculator",
        "3 Panel",
        "4 Inspector",
        "5 Logbook",
        "6 Sign-off",
    ]
)

with proposal_tab:
    st.caption("The order: what the sponsor is asking the company to buy.")
    st.subheader(proposal.title)
    st.write(f"Sponsor: {proposal.sponsor}")
    st.write(f"Department: {proposal.department}")
    st.write(f"Investment: {format_money(proposal.initial_investment)}")
    st.write(f"Approval tier: {approval_tier(proposal.initial_investment, policy)}")
    st.markdown("**Sponsor notes**")
    st.write(proposal.sponsor_notes)
    st.markdown("**Assumptions**")
    for assumption in proposal.assumptions:
        st.write(f"- {assumption}")

with calculator_tab:
    st.caption("The scale: code checks whether the project still makes money when the cash flows change.")
    _label("Code check")
    if loaded is None:
        _needs_run()
    else:
        metrics = loaded["metrics"]
        rows_for_table = []
        for key in METRIC_KEYS:
            raw = getattr(metrics, key)
            if key == "allowed_recommendations":
                value = ", ".join(RECOMMENDATIONS.get(item, item) for item in raw)
            else:
                value = format_metric(key, raw)
            rows_for_table.append({"Metric": METRIC_LABELS[key], "Value": value})
        st.dataframe(rows_for_table, hide_index=True)
        decision = loaded["decision"]
        if decision is None:
            decision = decide(metrics, policy)
        st.markdown("**Rules decision**")
        st.markdown(f"**{RECOMMENDATIONS[decision.recommendation]}**")
        st.markdown(f"{decision.rule}. {RULES[decision.rule]}")
        for code in decision.reasons:
            st.markdown(REASONS.get(code, code))
        rows = sensitivity_rows(metrics)
        st.bar_chart(rows, x="scenario", y="npv", sort=False)
        losses = [row["scenario"] for row in rows if row["negative"]]
        if losses:
            st.warning("This proposal loses money if " + ", ".join(losses) + ".")

with panel_tab:
    st.caption("The cooks: three roles argue from the same figures, without seeing each other.")
    _label("AI judgment")
    if loaded is None:
        _needs_run()
    else:
        columns = st.columns(3)
        for column, role in zip(columns, PANEL_ROLES):
            position = loaded["positions"].get(role)
            with column:
                st.subheader(ROLES[role])
                if position is None:
                    st.write("No position file.")
                    continue
                st.write(f"Stance: {RECOMMENDATIONS.get(position.stance, position.stance)}")
                for argument in position.arguments:
                    st.write(render_text(argument.point, loaded["metrics"]))
                st.markdown("**Top risk**")
                st.write(render_text(position.top_risk, loaded["metrics"]))
                st.markdown("**Questions for the sponsor**")
                for question in position.questions_for_sponsor:
                    st.write(render_text(question, loaded["metrics"]))

with inspector_tab:
    st.caption("The inspector: code checks the memo. It does not call a model.")
    _label("Code check")
    if loaded is None:
        _needs_run()
    else:
        for number, report in enumerate(loaded["verification_attempts"], start=1):
            st.subheader(f"Attempt {number}")
            st.markdown("**Inspector checks**")
            st.caption("must pass before anyone can sign off")
            for check in report.checks:
                if not check.blocking:
                    continue
                if check.passed:
                    st.write(f"✅ {CHECKS_PASSED[check.name]}")
                else:
                    st.write(f"❌ {CHECKS_FAILED[check.name]}")
                    st.write(check.detail)
            with st.expander("Technical details (for builders)"):
                for check in report.checks:
                    state = "pass" if check.passed else "fail"
                    st.code(
                        f"{check.name} | {state} | blocking={check.blocking} | {check.detail}"
                    )
                st.code(f"status={loaded['status'].get('status')}")
        latest = loaded["verification_attempts"][-1]
        findings = [check for check in latest.checks if not check.blocking and not check.passed]
        st.markdown("**Red flags for the approver**")
        st.caption("shown to the approver; these don't block the memo")
        if not findings:
            st.write("None found.")
        for check in findings:
            st.write(f"❌ {CHECKS_FAILED[check.name]}")
            st.write(check.detail)
        st.markdown("**Decision memo**")
        st.markdown(_person_memo(loaded["memo_md"]))

with logbook_tab:
    st.caption("The logbook: every step is a line that was appended, not edited.")
    _label("Record")
    if run_dir is None:
        _needs_run()
    else:
        events = run_events(run_dir.name, _runs_root())
        names = ["All", *sorted({event["event_type"] for event in events})]
        chosen = st.selectbox(
            "Event type",
            names,
            format_func=lambda name: "All" if name == "All" else EVENT_TYPES.get(name, name),
            key="event_type",
        )
        shown = events if chosen == "All" else [event for event in events if event["event_type"] == chosen]
        for event in shown:
            if event["event_type"] == "retry":
                st.warning(
                    "Retry "
                    f"attempt_number={event.get('attempt_number')} "
                    f"retry_of={event.get('retry_of')} "
                    f"retry_reason={event.get('retry_reason')}"
                )
        st.dataframe(
            [
                {LOG_HEADERS[column]: event.get(column) for column in LOG_COLUMNS}
                for event in shown
            ],
            hide_index=True,
        )

with signoff_tab:
    st.caption("The owner: a person decides. The wrong role is refused by code.")
    _label("Human")
    if loaded is None or run_dir is None:
        _needs_run()
    else:
        flash = st.session_state.pop("flash_success", None)
        status_code = loaded["status"].get("status")
        recommendation_code = loaded["status"].get("recommendation")
        st.markdown(f"**Status:** {STATUSES.get(status_code, status_code)}")
        st.markdown(
            f"**Recommendation:** {RECOMMENDATIONS.get(recommendation_code, recommendation_code)}"
        )
        decision = loaded["decision"]
        if decision is None and loaded["metrics"] is not None:
            decision = decide(loaded["metrics"], policy)
        if decision is not None:
            st.markdown(
                f"**Decided by rule {decision.rule}:** {RECOMMENDATIONS[decision.recommendation]}"
            )
        if loaded["approvals"]:
            st.dataframe(loaded["approvals"], hide_index=True)
        else:
            st.write("No approvals yet.")
        if flash:
            st.success(flash)
        with st.form("sign_off_form"):
            name = st.text_input("Approver name", key="approver_name")
            role = st.selectbox(
                "Role",
                ["department_head", "cfo", "ceo"],
                format_func=lambda item: SIGN_OFF_ROLES.get(item, item),
                key="approver_role",
            )
            decision = st.selectbox(
                "Decision",
                ["APPROVED", "RETURNED"],
                format_func=lambda item: SIGN_OFF_DECISIONS.get(item, item),
                key="decision",
            )
            note = st.text_area("Note", key="note")
            submitted = st.form_submit_button("Submit", key="sign_off")
        if submitted:
            try:
                updated = approve(run_dir, name, role, decision, note or "")
            except ApprovalError as error:
                st.error(str(error))
            else:
                st.session_state["flash_success"] = updated["status"]
                st.rerun()
