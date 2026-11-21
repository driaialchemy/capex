# Decisions

## 2026-11-18 — Stack

Python 3.11, Streamlit, and Pydantic v2. PyYAML for the policy file. pytest for tests. Streamlit and the Anthropic client are listed now and unused until later milestones.

## 2026-11-18 — Deterministic finance engine

All money figures are calculated in code (`src/capex/finance.py`, M2). The model never produces or edits numbers.

## 2026-11-18 — Code-only verifier

`src/capex/verifier.py` stays deterministic Python. It does not import an AI or network library.

## 2026-11-18 — Append-only flight recorder

`runs/flight_recorder.jsonl` is append-only (M3). Writes are single-threaded.

## 2026-11-18 — Synthetic data only

Sample proposals are fictional. No customer data.

## 2026-11-18 — Approval tier boundaries

Under 250000: `department_head`. From 250000 through 1000000 inclusive: `cfo`. Above 1000000: `cfo_and_ceo`.

## 2026-11-18 — Editable install from src/

`pyproject.toml` has a setuptools `[build-system]` and package discovery under `src/`. `requirements.txt` ends with `-e .` so the smoke-test command can import `capex`.

## 2026-11-18 — Kill switch reads .env without overriding the process

`python-dotenv` loads `.env` from the repo root, or from the `root` argument when `is_engaged` is given one. `override=False`, so a variable already set in the environment is left as-is. The switch is on when `CAPEX_KILL_SWITCH` is `1` or a `KILL_SWITCH` file is present.

## 2026-11-18 — Finance conventions

Cash flows arrive at the end of each year. Salvage is added to the final year's flow for NPV and IRR, and is excluded from payback. Stress cases multiply the operating flows by 0.8, 0.9, or 1.1 and leave salvage unchanged. Money is stored to the cent. Rates are stored to 4 decimals. A rendered memo shows money as whole dollars (`$110,330`, `-$72,086`).

## 2026-11-18 — IRR is None when the project never covers its cost

`irr()` returns `None` when the cash flows plus salvage are less than the investment, even if a negative root exists between −99% and 100%. It also returns `None` when NPV does not change sign on [−0.99, 1.0]. Otherwise it bisects until the bracket is narrower than 1e-7 and rounds the root to 4 decimals.

## 2026-11-18 — Allowed recommendations

NPV below zero allows only DEFER and REJECT. NPV at or above zero with no payback, or with payback longer than `max_payback_years`, allows APPROVE_WITH_CONDITIONS, DEFER, and REJECT. Otherwise all four recommendations are allowed. Payback equal to the maximum still allows all four.

## 2026-11-18 — Token-only figures

Headline and section body text cite figures as `{{metric_key}}` tokens. `render_memo` fills them in. `proposal_id` is stored on `Metrics` so the stage gate can match the file, and it is not a figure a memo can cite. `tokens_valid` rejects `{{proposal_id}}`.

## 2026-11-18 — Offline replay is the default

`CAPEX_LLM_MODE` defaults to `offline`. The pipeline reads `sample_data/replays/<id>/<role>.json`. A Judge retry reads `<role>.attemptN.json` when that file exists. Live mode calls the Anthropic API only when `CAPEX_LLM_MODE=live`, and it raises `ConfigError` before constructing a client if `ANTHROPIC_API_KEY` or `CAPEX_MODEL` is missing. The model name in `.env.example` is `claude-sonnet-5-5`. No thinking budget is set.

## 2026-11-18 — Panelists run in order and do not see each other

Sponsor, CFO, and operations run one after another on one thread, so the flight recorder has a single writer. A round-one prompt contains the proposal, the metrics table, and that role's instructions. It does not contain another panelist's replay. The Judge prompt may contain the three positions.

## 2026-11-18 — The Judge is retried once

Only the Judge is retried, and only once. A second attempt is recorded with `attempt_number` 2, `retry_of` set to the first Judge model-call event, and `retry_reason` set to the failed blocking check names. There is no third attempt. A panelist that fails validation blocks the run and the Judge is not called.

## 2026-11-18 — Approval roles match the tier exactly

`department_head` accepts only `department_head`. `cfo` accepts only `cfo`. `cfo_and_ceo` stays `PENDING_APPROVAL` until one `cfo` and one `ceo` have each approved. The same role cannot approve twice. One `RETURNED` from an eligible role sets `RETURNED` immediately. A run that is not `PENDING_APPROVAL` cannot be signed.

## 2026-11-18 — Blocking checks versus Proposal findings

`recommendation_allowed`, `no_raw_figures`, and `tokens_valid` are blocking. `sponsor_payback_claim` and `sponsor_percent_claims` are not. Retry and `PENDING_APPROVAL` look only at blocking checks. A non-blocking failure stays visible as a Proposal finding in `memo.md`, in `status.json`, and in the verifier line of the flight recorder. CPX-003 can reach the approver with REJECT while the sponsor's "2 years" claim remains a finding, because the Judge cannot edit the sponsor notes.

## 2026-11-18 — The demo page is a thin layer

`app.py` lays out widgets. Figures come from `metrics.json` through `render.py`. Pass and fail come from the verifier files already on disk. Sign-off calls `approval.approve`. The only model call is `pipeline.run`. The page reads the flight recorder and does not rewrite its lines. Engage and Release append one new line each. Tests set `CAPEX_RUNS_ROOT` so pytest writes to a temp folder, not the real `runs/` logbook.

Custom CSS is allowed only in `src/capex/ui_theme.py`. The page background is `assets/bg_page.webp`, the sidebar is `assets/bg_sidebar.webp` under a dark overlay, and the hero banner is `assets/hero_pipeline.webp`, shown as cropped. Originals stay in `assets/source/`, which is gitignored.

## 2026-11-18 — Display labels stay out of the logic

Words a person reads live in `src/capex/labels.py`. Check names, status codes, and recommendation codes stay in the logic, the JSON logs, and the tests. `memo.md` uses the English recommendation. When a sponsor finding exists, the file still ends with `## Proposal findings` and the raw check name, because an existing test reads that heading. The page shows that block once, in plain language, and keeps the raw lines inside “Technical details (for builders).”

## 2026-11-20 — Code decides the recommendation from the numbers; the LLM explains it

`decide()` in `src/capex/decision.py` applies the first matching rule. R1 rejects a negative net present value. R2 defers when payback is missing or longer than the policy limit. R3 approves with conditions when the stress figure named in policy, `npv_flows_minus_10`, is below zero. R4 approves otherwise. The Judge copies that recommendation, explains it, proposes conditions, and lists concerns. It cannot change the outcome. `recommendation_matches_rules` and `conditions_cite_stress` block a mismatch. `panel_disagreement` is a red flag when two or more panelists share a stance the rules did not choose, and it does not block. The on-disk memo heading stays `## Proposal findings`. The page heading is "Red flags for the approver".

## 2026-11-18 — Sample evidence lives outside runs/

`runs/` stays gitignored. `python -m capex.export_sample CPX-003` copies the latest CPX-003 run, and only that run's flight-recorder lines, into `docs/sample_run/CPX-003/`. That folder is the evidence a visitor can read. Committing it is M5.
