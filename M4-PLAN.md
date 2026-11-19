# M4 Streamlit presentation

Status: **approved** (2026-11-18).

## Goal

A single page Mike can present from. Tabs follow the workshop story and are labeled **AI judgment**, **Code check**, **Record**, or **Human**. The page calls `pipeline.run`, `render.py`, and `approval.approve`. It does not calculate figures, judge memos, or call a model itself.

## Choices

- **Runs stay on the existing path argument.** `pipeline.run` and `approval.latest_run` already take `runs_root`. The app reads `CAPEX_RUNS_ROOT` (default `runs`) and passes that directory through. Pytest sets the variable to `tmp_path` and also sets `CAPEX_KILL_SWITCH=0` and `CAPEX_LLM_MODE=offline`, so the suite never writes the real `runs/` folder or the real logbook. This also avoids the known leak where `tests/test_kill_switch.py` leaves `CAPEX_KILL_SWITCH=1` set for later tests in the same process.
- **The kill-switch buttons write the file; the AppTest does not.** Engage creates `KILL_SWITCH` in the repo root and Release deletes it. Both append one flight-recorder line through `record()` (engage as `kill_switch_block`, release as `stage`). They do not edit earlier lines. The AppTest for "switch engaged" sets `CAPEX_KILL_SWITCH=1`, which is the existing stop, so pytest does not leave a `KILL_SWITCH` file in the repo. A separate test calls engage/release against a temp root.
- **Sensitivity reads stored NPVs.** `sensitivity_rows` lists plan, flows −20%, flows −10%, flows +10%, and rate +2pp from the five fields already on `Metrics`. A row is `negative` when that stored value is below zero. Display text comes from `format_money`. Nothing is recomputed.
- **Panel tokens use the existing renderer.** Add public `render_text(text, metrics)` in `render.py` as the same fill `render_memo` already uses. Arguments, top risk, and questions go through it.
- **Sample evidence is written, not committed.** `python -m capex.export_sample CPX-003` fills `docs/sample_run/CPX-003/`. Git add/commit/push stays in M5.

## Files

- `app.py` — layout only. `st.sidebar`, `st.tabs`, `st.columns`, `st.dataframe`, `st.bar_chart`, `st.form`. Stable widget keys: `proposal`, `run_review`, `engage_kill_switch`, `release_kill_switch`, `approver_name`, `approver_role`, `decision`, `note`, `sign_off`, `event_type`. A one-line markdown style marks the four labels. Each tab opens with one plain sentence plus its label.
- `src/capex/ui_data.py` — `list_proposals()`, `latest_run(proposal_id, runs_root=None)` (None when no folder), `load_run(run_dir)` with `metrics`, `positions`, `memo_attempts`, `verification_attempts`, `memo_md`, `status`, `approvals`, `run_events(run_id, runs_root=None)`, `sensitivity_rows(metrics)`. `runs_root` defaults from `CAPEX_RUNS_ROOT`.
- `src/capex/kill_switch.py` — `engage(root, log_path)` and `release(root, log_path)`.
- `src/capex/export_sample.py` — copy the latest run folder to `docs/sample_run/<id>/` and write `flight_recorder.jsonl` containing only that `run_id`. CLI: `python -m capex.export_sample CPX-003`. Tests pass temp `runs_root` and `dest`.
- `scripts/run_demo.ps1` — from the repo root: create `.venv` if missing, `pip install -r requirements.txt`, copy `.env.example` to `.env` when `.env` is missing, then `streamlit run app.py`.
- Tests: `tests/test_ui_data.py`, `tests/test_app.py`, `tests/test_export_sample.py`.

## Screen

Sidebar: proposal select (CPX-001, CPX-002, CPX-003), **Run review** calls `pipeline.run`, mode from `current_mode()`, kill-switch status from `is_engaged()`, Engage and Release.

1. **Proposal** — title, sponsor, investment via `format_money`, tier from `policy.approval_tier`, sponsor notes (the CPX-003 "2 years" claim), assumptions. Works before a run.
2. **Calculator** (Code check) — metrics table through `format_metric`, bar chart of the five stored NPVs, and "This proposal loses money if…" naming each negative scenario. CPX-002's flows −10% row is negative (−$72,086).
3. **Panel** (AI judgment) — three columns from `positions/<role>.json`: stance, rendered arguments, top risk, questions.
4. **Inspector** (Code check) — one block per `verification.attemptN.json`. Blocking checks and proposal findings are separate lists. Then the saved `memo.md`.
5. **Logbook** (Record) — this run's rows only, columns `ts`, `event_type`, `actor`, `attempt_number`, `retry_of`, `retry_reason`, `status`, `detail`, filtered by `event_type`. Retry rows are repeated in a warning above the table.
6. **Sign-off** (Human) — current status and approvals, then the form. Submit calls `approval.approve`. `ApprovalError` and `KillSwitchEngaged` become `st.error` with the reason. A missing run shows a short empty state, not a traceback.

## Tests

Existing 50 tests stay unchanged.

- `test_ui_data`: run CPX-003 into `tmp_path`. `load_run` has both memo attempts and `status["proposal_findings"]` naming `sponsor_payback_claim`. `run_events` returns only that `run_id` and includes the retry row with `attempt_number` 2. `sensitivity_rows` on CPX-002 metrics marks the flows −10% scenario negative.
- `test_app`: `AppTest.from_file("app.py", default_timeout=90)`. The app loads with no exception. Select CPX-003, press Run review, page shows `PENDING_APPROVAL`. For CPX-001, submit role `department_head` and the error is shown while status stays `PENDING_APPROVAL`. With `CAPEX_KILL_SWITCH=1`, Run review shows the refusal and creates no run folder.
- `test_export_sample`: export from a temp run root into a temp dest. Dest contains `metrics.json`, `positions/`, `memo.attempt1.json`, `memo.attempt2.json`, `memo.md`, `status.json`, and `flight_recorder.jsonl`.

## Out of scope

Git commands. New packages, custom CSS beyond the label line, and any UI library beyond Streamlit built-ins. New finance math or verifier rules. Model calls from the app except through `pipeline.run`. Rewriting or deleting flight-recorder lines. Editing the existing 50 tests.
