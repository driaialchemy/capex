# Handoff

## Current milestone

M4.1 theme is done. M5 is next: commit the sample evidence and push to GitHub. Do not run git until that milestone.

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
- Tests: 62 passed. The original 50 still pass.
- Debate pipeline in `src/capex/pipeline.py`. Offline mode reads `sample_data/replays/`. Sponsor, CFO, and operations run in that order. Each prompt omits the other panelists' output. The Judge may see the three positions.
- Verifier checks carry `blocking`. `recommendation_allowed`, `no_raw_figures`, and `tokens_valid` block. `sponsor_payback_claim` and `sponsor_percent_claims` do not. A retry, and `PENDING_APPROVAL`, depend only on the blocking checks. Non-blocking failures are Proposal findings in `memo.md`, `status.json`, and the flight recorder.
- CPX-003's first Judge draft fails the blocking checks, retries once, and lands on REJECT at `PENDING_APPROVAL`. The payback claim stays under Proposal findings. Smoke run: `runs/CPX-003-20261118T235435Z`.
- `runs/flight_recorder.jsonl` is append-only. Approval matches the tier exactly. CPX-001 (`cfo`) became FINAL after Demo CFO approved `runs/CPX-001-20261118T235441Z`. CPX-003 (`cfo_and_ceo`) stays pending until both a CFO and a CEO approve.
- Streamlit page `app.py`. Sidebar runs the pipeline, shows offline/live mode, and engages or releases the kill switch. Six tabs: Proposal, Calculator (Code check), Panel (AI judgment), Inspector (Code check), Logbook (Record), Sign-off (Human).
- `scripts/run_demo.ps1` creates the venv, installs requirements, copies `.env.example` when `.env` is missing, and starts Streamlit.
- Sample evidence: `docs/sample_run/CPX-003/` from smoke run `runs/CPX-003-20261119T000937Z`. `runs/` stays gitignored.
- Dark theme in `.streamlit/config.toml` and `src/capex/ui_theme.py`. Page background `assets/bg_page.webp`, sidebar `assets/bg_sidebar.webp`, hero `assets/hero_pipeline.webp`. Tables stay on a solid panel. Originals live in `assets/source/` and stay gitignored.

## Next (M5)

Commit `docs/sample_run/` and push the repository to GitHub. No new product behavior.

## Manual check

1. Run `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1` → the browser opens.
2. CPX-002 → Run review → Calculator shows the −10% scenario losing money.
3. CPX-003 → Run review → Inspector shows attempt 1 blocked and attempt 2 passing; Logbook shows the retry row.
4. Sign-off: department_head is refused for CPX-001 and cfo is accepted.
5. Engage the kill switch → Run review is refused → release it.

## Known issues

`tests/test_kill_switch.py` loads a temporary `.env` that sets `CAPEX_KILL_SWITCH=1`. That write stays in the process after the test, so a later test in the same pytest run sees the switch on. The M3 pipeline tests set `CAPEX_KILL_SWITCH=0` themselves. A fresh `python -m capex.run` is unaffected.
