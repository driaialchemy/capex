# Handoff

## Current milestone

M4.3 rules decision engine is published, together with the M4.2 wording, at https://github.com/driaialchemy/capex on `main` (`5b418b8`).

## Done

- M1 scaffold, schemas, policy, sample proposals, and kill switch.
- Finance engine in `src/capex/finance.py`. End-of-year cash flows. Salvage is included in NPV and IRR only. Payback ignores salvage. Stress cases scale the operating flows and leave salvage alone.
- Known answers hold: CPX-001 NPV $110,329.85 (renders as $110,330); CPX-002 NPV $6,570.83 and −$72,086.26 if flows are 10% light (renders as -$72,086); CPX-003 NPV −$233,924.97, payback not recovered, allowed recommendations DEFER and REJECT.
- `irr()` returns `None` when inflows, including salvage, never cover the investment.
- `python -m capex.compute CPX-003` writes `runs/<proposal-id>-<UTC timestamp>/metrics.json` after the kill switch check. The smoke run is `runs/CPX-003-20261118T233722Z`.
- `gate_metrics` re-opens that file and recomputes. A missing file, a hand-edited value, or a mismatched `proposal_id` fails.
- `DecisionMemo` cites figures only as `{{metric_key}}` tokens. `render_memo` shows whole dollars, rates like `17.2%`, and years to one decimal, or `not recovered`. Cents stay in `Metrics`.
- `{{proposal_id}}` is rejected by `tokens_valid`.
- The code-only verifier catches a disallowed recommendation, raw figures, unknown tokens, and CPX-003's "pays for itself in 2 years" claim. "40% fuel savings" is reported UNVERIFIED and does not fail the memo by itself.
- Tests: 73 passed. The original 50 still pass.
- Display labels live in `src/capex/labels.py`. Internal names stay in the logic and the logs. Replays name each figure, as in “a net present value of {{npv}}.”
- Code decides the recommendation from the numbers. `decide()` applies R1 Reject, R2 Defer, R3 Approve with conditions, then R4 Approve. The Judge explains that result. Smoke decisions: `runs/CPX-001-20261121T003324Z` is R4, `runs/CPX-002-20261121T003328Z` is R3, `runs/CPX-003-20261121T003332Z` is R1. CPX-003 still retries once, and the payback claim stays a finding.
- Debate pipeline in `src/capex/pipeline.py`. Offline mode reads `sample_data/replays/`. Sponsor, CFO, and operations run in that order. Each prompt omits the other panelists' output. The Judge may see the three positions.
- Verifier checks carry `blocking`. `recommendation_allowed`, `no_raw_figures`, and `tokens_valid` block. `sponsor_payback_claim` and `sponsor_percent_claims` do not. A retry, and `PENDING_APPROVAL`, depend only on the blocking checks. Non-blocking failures are Proposal findings in `memo.md`, `status.json`, and the flight recorder.
- CPX-003's first Judge draft fails the blocking checks, retries once, and lands on REJECT at `PENDING_APPROVAL`. The payback claim stays under Proposal findings. Smoke run: `runs/CPX-003-20261118T235435Z`.
- `runs/flight_recorder.jsonl` is append-only. Approval matches the tier exactly. CPX-001 (`cfo`) became FINAL after Demo CFO approved `runs/CPX-001-20261118T235441Z`. CPX-003 (`cfo_and_ceo`) stays pending until both a CFO and a CEO approve.
- Streamlit page `app.py`. Sidebar runs the pipeline, shows offline/live mode, and engages or releases the kill switch. Six tabs: Proposal, Calculator (Code check), Panel (AI judgment), Inspector (Code check), Logbook (Record), Sign-off (Human).
- `scripts/run_demo.ps1` creates the venv, installs requirements, copies `.env.example` when `.env` is missing, and starts Streamlit.
- Sample evidence: `docs/sample_run/CPX-003/` from smoke run `runs/CPX-003-20261119T000937Z`. `runs/` stays gitignored.
- Dark theme in `.streamlit/config.toml` and `src/capex/ui_theme.py`. Page background `assets/bg_page.webp`, sidebar `assets/bg_sidebar.webp`, hero `assets/hero_pipeline.webp`. Tables stay on a solid panel. Originals live in `assets/source/` and stay gitignored.

## Next

No further product work is queued. The rules engine and the readable-text wording are on `main`.

## Manual check

1. Run `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1` → the browser opens.
2. CPX-002 → Run review → Calculator shows the −10% scenario losing money.
3. CPX-003 → Run review → Inspector shows attempt 1 blocked and attempt 2 passing; Logbook shows the retry row.
4. Sign-off: department_head is refused for CPX-001 and cfo is accepted.
5. Engage the kill switch → Run review is refused → release it.

## Known issues

`tests/test_kill_switch.py` loads a temporary `.env` that sets `CAPEX_KILL_SWITCH=1`. That write stays in the process after the test, so a later test in the same pytest run sees the switch on. The M3 pipeline tests set `CAPEX_KILL_SWITCH=0` themselves. A fresh `python -m capex.run` is unaffected.
