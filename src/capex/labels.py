"""Words a person reads. The codes stay in the logic and the logs."""

RECOMMENDATIONS = {
    "APPROVE": "Approve",
    "APPROVE_WITH_CONDITIONS": "Approve with conditions",
    "DEFER": "Defer",
    "REJECT": "Reject",
}

STATUSES = {
    "PENDING_APPROVAL": "Waiting for sign-off",
    "BLOCKED": "Blocked by the inspector",
    "FINAL": "Approved and final",
    "RETURNED": "Sent back to the sponsor",
}

CHECKS_PASSED = {
    "recommendation_allowed": "The recommendation is one the spending policy allows",
    "no_raw_figures": "Every number came from the calculator, not the AI",
    "tokens_valid": "Every figure links to a real calculation",
    "sponsor_payback_claim": "The sponsor's payback claim matches the math",
    "sponsor_percent_claims": "Percentage claims in the sponsor's notes, not verified",
    "recommendation_matches_rules": "The memo's recommendation matches the rules decision",
    "conditions_cite_stress": "A condition cites the stress-test figure",
    "panel_disagreement": "The panel does not share a different outcome",
}

CHECKS_FAILED = {
    "recommendation_allowed": "The recommendation isn't allowed by the spending policy",
    "no_raw_figures": "The AI typed a number itself",
    "tokens_valid": "A figure points to a calculation that doesn't exist",
    "sponsor_payback_claim": "The sponsor's payback claim doesn't match the math",
    "sponsor_percent_claims": "Percentage claims in the sponsor's notes, not verified",
    "recommendation_matches_rules": "The memo's recommendation does not match the rules decision",
    "conditions_cite_stress": "Approve with conditions needs a condition that cites the stress-test figure",
    "panel_disagreement": "Two or more panelists argued for a different outcome than the rules",
}

RULES = {
    "R1": "Reject, because the project is worth less than zero in today's dollars",
    "R2": "Defer, because payback is missing or longer than the policy allows",
    "R3": "Approve with conditions, because the project loses money if cash flows come in a tenth light",
    "R4": "Approve, because the plan and the lighter case both stay above zero",
}

REASONS = {
    "npv_below_zero": "Net present value is below zero",
    "payback_missing": "The cash flows never pay back the investment",
    "payback_over_limit": "Payback is longer than the policy allows",
    "stress_npv_below_zero": "Net present value is below zero if cash flows come in a tenth light",
    "plan_clears_hurdle": "The plan and the lighter case both stay above zero",
}

METRICS = {
    "proposal_id": "Proposal",
    "npv": "Net present value (today's dollars)",
    "irr": "Internal rate of return",
    "payback_years": "Years to pay back",
    "discounted_payback_years": "Years to pay back, in today's dollars",
    "npv_flows_minus_20": "Net present value if cash flows are a fifth lower",
    "npv_flows_minus_10": "Net present value if cash flows are a tenth lower",
    "npv_flows_plus_10": "Net present value if cash flows are a tenth higher",
    "npv_rate_plus_2pp": "Net present value if the hurdle rate is two points higher",
    "hurdle_rate": "Hurdle rate",
    "max_payback_years": "Longest payback the policy allows",
    "initial_investment": "Upfront investment",
    "approval_tier": "Who must sign",
    "allowed_recommendations": "Recommendations the policy allows",
}

ROLES = {
    "sponsor_advocate": "Sponsor Advocate",
    "cfo_stress_tester": "CFO Stress-Tester",
    "operations_risk": "Operations Risk",
    "judge": "Judge",
}

EVENT_TYPES = {
    "stage": "Step",
    "model_call": "Model call",
    "gate": "Gate",
    "verifier": "Inspector",
    "retry": "Retry",
    "approval": "Sign-off",
    "kill_switch_block": "Kill switch",
    "error": "Error",
}

LOG_COLUMNS = {
    "ts": "When",
    "event_type": "Event",
    "actor": "Who",
    "attempt_number": "Attempt",
    "retry_of": "Retry of",
    "retry_reason": "Why it was retried",
    "status": "Result",
    "detail": "What happened",
}

SIGN_OFF_ROLES = {
    "department_head": "Department head",
    "cfo": "CFO",
    "ceo": "CEO",
}

SIGN_OFF_DECISIONS = {
    "APPROVED": "Approve",
    "RETURNED": "Send back",
}
