# M3 Plan — Panel, logbook, and sign-off

Status: **approved** (2026-11-18). Each verifier check has `blocking`: true for `recommendation_allowed`, `no_raw_figures`, and `tokens_valid`; false for `sponsor_payback_claim` and `sponsor_percent_claims`. Retry and `PENDING_APPROVAL` use only blocking checks. Non-blocking failures are "Proposal findings" in `memo.md`, `status.json`, and the flight recorder.

Read first: `AGENTS.md`, `HANDOFF.md`, `DECISIONS.md`, and the M1–M2 package (`schemas.py`, `finance.py`, `verifier.py`, `gates.py`, `compute.py`, `render.py`, `kill_switch.py`). The existing 34 tests stay as they are. `finance.py` is not edited. `verifier.py` keeps the same pass/fail rules for a memo. The only verifier change is exposing the text checks so a position file can use them.

## Goal

Join the probabilistic panel to the deterministic gates, in one top-to-bottom function a business owner can follow.

- Three agents argue in sequence. None of them sees the others. A Judge reads all three and drafts the memo.
- Offline replay is the default, so the demo needs no API key and no network. `CAPEX_LLM_MODE=live` is the optional Claude path.
- Every model call, gate, verifier result, retry, and approval is appended to `runs/flight_recorder.jsonl`. Lines are never edited.
- A human whose role matches the approval tier signs off in code. A memo that failed verification cannot be approved.
- Scripted moment: CPX-003's first Judge draft recommends a disallowed outcome and types a raw dollar figure. The verifier blocks it. The Judge retries once. The second draft recommends REJECT and the run waits for both a CFO and a CEO.

## The CPX-003 pass rule (needs a yes)

`verify()` already fails every CPX-003 memo on `sponsor_payback_claim`, because the sponsor notes say "pays for itself in 2 years" and payback is `None`. The M2 test locks that. The Judge cannot fix the notes by rewriting the memo, so a retry can never make `verify().passed` true, and the run could never reach `PENDING_APPROVAL`.

Planned rule, without changing that check:

- `verification.attemptN.json` stores the full `verify()` report, unchanged.
- The retry and the final status look only at the checks the Judge can repair: `recommendation_allowed`, `no_raw_figures`, and `tokens_valid`.
- `sponsor_payback_claim` still fails on CPX-003 and stays in the report. It does not force a second retry or `BLOCKED`.
- `sponsor_percent_claims` stays informational, as it is today.
- CPX-003 attempt 1 fails `recommendation_allowed` and `no_raw_figures`, one retry runs, attempt 2 passes those three checks with REJECT, and `status.json` is `PENDING_APPROVAL`.

If you want a failing payback-claim check to block sign-off instead, say so. That would leave CPX-003 `BLOCKED` after the one retry.

## Files

```
capex/
  M3-PLAN.md
  .env.example                         # CAPEX_MODEL=claude-sonnet-5-5
  prompts/sponsor_advocate.md
  prompts/cfo_stress_tester.md
  prompts/operations_risk.md
  prompts/judge.md
  sample_data/replays/CPX-001/*.json
  sample_data/replays/CPX-002/*.json
  sample_data/replays/CPX-003/*.json   # plus judge.attempt2.json
  src/capex/llm.py
  src/capex/flight_recorder.py
  src/capex/pipeline.py
  src/capex/run.py                     # python -m capex.run
  src/capex/approval.py
  src/capex/approve.py                 # python -m capex.approve
  src/capex/schemas.py                 # Position, and two fields on DecisionMemo
  src/capex/verifier.py                # expose text checks; memo rules unchanged
  src/capex/gates.py                   # add gate_positions
  src/capex/render.py                  # also fill tokens in the two new memo fields
  tests/test_flight_recorder.py
  tests/test_agents.py
  tests/test_pipeline.py
  tests/test_kill_switch_pipeline.py
  tests/test_live_config.py
  tests/test_approval.py
  HANDOFF.md
  DECISIONS.md
  README.md
```

No new packages. The Anthropic SDK is already in `requirements.txt`. Tests run offline and do not open a network connection.

### Schemas

`Argument`: `point`, `cited_metrics`, `cited_assumptions`. Unknown fields rejected.

`Position`: `role` (`sponsor_advocate`, `cfo_stress_tester`, or `operations_risk`), `stance` (one of the four recommendations), `arguments`, `top_risk`, `questions_for_sponsor`.

`DecisionMemo` gains:

- `conditions: list[str]`, default empty. A model validator requires it to be non-empty when the recommendation is `APPROVE_WITH_CONDITIONS`.
- `disagreements_addressed: list[str]`, default empty.

Defaults keep the existing memo tests working. They construct memos without these fields, and none of them use `APPROVE_WITH_CONDITIONS`.

### Model layer (`src/capex/llm.py`)

`call_model(role, prompt_text, proposal_id, attempt) -> str`

1. `assert_not_engaged()` before every call. That also loads `.env` without overriding a variable that is already set.
2. Mode defaults to `offline` when `CAPEX_LLM_MODE` is missing or `offline`.
3. Offline: read `sample_data/replays/<proposal_id>/<role>.json`. When `attempt` is greater than 1 and `<role>.attempt<N>.json` exists, return that file instead. Only the CPX-003 Judge has an attempt-2 file.
4. Live: if `ANTHROPIC_API_KEY` or `CAPEX_MODEL` is missing, raise `ConfigError` before constructing a client. Otherwise call the Anthropic messages API with the model from `CAPEX_MODEL`. Do not set a thinking budget. `max_tokens` is set only because the API requires it.
5. `parse_json_response(text, model_cls)` strips a leading code fence, then validates. Invalid JSON is a failure the Judge may retry once. A panelist who returns invalid JSON blocks the run. Panelists are not retried.

`.env.example` sets `CAPEX_MODEL=claude-sonnet-5-5`. The demo still defaults to `CAPEX_LLM_MODE=offline`.

### Prompts

`string.Template.safe_substitute` fills `$placeholders`. `{{metric_key}}` tokens stay literal. Round-1 panel prompts do not receive another agent's output.

The sponsor and Judge files use the prompt text exactly as specified. CFO and Operations use that same tag structure. Their instruction and reasoning are the specified paragraphs. Their context block matches the sponsor. Verification lines:

- CFO: stance is one of the allowed recommendations; at least one argument cites a sensitivity token (`{{npv_flows_minus_10}}`, `{{npv_flows_minus_20}}`, or `{{npv_rate_plus_2pp}}`).
- Operations: stance is one of the allowed recommendations; unevidenced claims become questions for the sponsor.

`$metrics_table` is a two-column text table, key and rendered value, from `citeable_metrics()` and `format_metric`. `proposal_id` is excluded. `$position_schema` and `$memo_schema` are `model_json_schema()`. Pydantic schemas contain `$ref` and `$defs`. Those are schema syntax, not leftover placeholders. The test will assert the Template names are gone (`$proposal_id`, `$proposal_json`, `$metrics_table`, `$allowed`, `$position_schema`, `$memo_schema`, `$positions_json`, `$verifier_failures`), not that the string contains no `$` at all.

`$verifier_failures` is `none` on the Judge's first attempt. On the retry it lists each failed repairable check and its detail.

### Replays

Each file validates. Every `{{token}}` is a citeable metric key. Prose does not quote `CPX-003`, `40%`, or a dollar amount, except the one flawed Judge draft. `no_raw_figures` treats `CPX-003` and `40%` as raw figures, so quoting them would fail the position gate.

- CPX-001: Judge recommends APPROVE. Conditions empty.
- CPX-002: the CFO's argument contains `{{npv_flows_minus_10}}` and cites it. Judge recommends APPROVE_WITH_CONDITIONS. Conditions include a staged rollout and a labor-savings checkpoint.
- CPX-003 positions use allowed stances only (DEFER or REJECT). `judge.json` still parses, recommends APPROVE_WITH_CONDITIONS, has a non-empty conditions list so the schema accepts it, and its body contains `the $1,150,000 fleet pays for itself in 2 years`. `judge.attempt2.json` recommends REJECT, cites `{{payback_years}}` and `{{npv}}` in the body and in `cited_metrics`, and calls the fuel-savings claim unverified without writing a percent or any other raw number.

### Pipeline (`src/capex/pipeline.py`)

`run(proposal_id, runs_root=None) -> RunResult`. Default root is `runs/`. Tests pass `tmp_path` so they do not append to the real logbook. One function, in this order:

1. If the kill switch is on, append a `kill_switch_block` event, raise `KillSwitchEngaged`, and create no run folder and no positions folder. This happens before any model call.
2. Reuse `write_metrics` and `gate_metrics`. A failed metrics gate writes `status.json` as `BLOCKED` and stops.
3. Sponsor, then CFO, then Operations. Each prompt gets the proposal, the metrics table, and the allowed list. Write `positions/<role>.json` from the parsed model.
4. `gate_positions` re-opens each file, validates `Position`, and runs the exposed `no_raw_figures` and `tokens_valid` checks on the point text, top risk, and questions. Cited metrics are the union of the argument lists. A `$1,000,000` tamper fails the gate. The run then stops as `BLOCKED` and does not call the Judge.
5. Judge, `memo.attempt1.json`, `verify()`, `verification.attempt1.json`.
6. If a repairable check failed, call the Judge once more with `attempt=2`. The flight-recorder retry event has `attempt_number: 2`, `retry_of` set to the first Judge model-call event id, and `retry_reason` set to the failed check names. No third attempt.
7. `PENDING_APPROVAL` when the final attempt's repairable checks passed, otherwise `BLOCKED`. Write `memo.md` from the rendered final memo, and write `status.json`.

`python -m capex.run CPX-003` prints one line per stage, then the final status and the run directory.

Agents run one after another so file writes stay single-threaded. They are independent because the prompt omits the other positions, not because they run at the same time.

### Flight recorder (`src/capex/flight_recorder.py`)

`record(event, path=None)` opens `runs/flight_recorder.jsonl` (or the given path) in binary append mode and writes one JSON object plus a newline. There is no rewrite, edit, or delete function.

`FlightEvent` fields, all present on every line: `event_id` (uuid4), `ts` (UTC ISO), `run_id`, `event_type` (`stage`, `model_call`, `gate`, `verifier`, `retry`, `approval`, `kill_switch_block`, `error`), `actor` (role, `system`, or the approver's name), `mode` (`offline` or `live`), `model` (null offline), `attempt_number`, `retry_of`, `retry_reason`, `input_sha256` (sha256 of the prompt text for model calls, otherwise null), `output_path`, `status` (`ok`, `fail`, or `blocked`), `detail`.

The optional `path` argument is how tests keep their bytes off the real logbook. The CLI does not pass it.

### Approval (`src/capex/approval.py`)

`approve(run_dir, approver_name, approver_role, decision, note)`.

`decision` is `APPROVED` or `RETURNED`. Refuse, and do not append an approval event, when:

- `status.json` is not `PENDING_APPROVAL`. That covers `BLOCKED`, `FINAL`, and `RETURNED`.
- `approver_role` is not one of the roles the tier names. `department_head` for a tier under $250,000. `cfo` from $250,000 through $1,000,000. `cfo` and `ceo` above $1,000,000. CPX-001 is the `cfo` tier, so a department head is refused and one CFO approval makes it `FINAL`.
- That same role has already approved this run.

`cfo_and_ceo` stays `PENDING_APPROVAL` until both roles have `APPROVED`. One `RETURNED` from an eligible role sets `RETURNED` immediately. Write `approvals.json` and append an `approval` event on every accepted decision.

CLI: `python -m capex.approve --proposal CPX-001 --latest --name "Demo CFO" --role cfo --decision APPROVED`. `--latest` picks the newest run folder whose name starts with that proposal id. `note` defaults to an empty string.

## Tests

Offline only. No network. Existing 34 tests still run. Live-mode tests are skipped unless `CAPEX_LIVE_TESTS=1`. The config test below is not a live call, so it runs every time. No test calls the Anthropic API.

`tests/test_flight_recorder.py`

- Append twice under `tmp_path`. The first file's bytes are the prefix of the second.
- Every required field is present.
- A retry event has `attempt_number` 2, a non-null `retry_of`, and a non-null `retry_reason`.

`tests/test_agents.py`

- Every replay validates (`Position` or `DecisionMemo`, including `judge.attempt2.json`).
- Every `{{token}}` is citeable. This test does not require the flawed CPX-003 first draft to be free of raw figures.
- The CPX-002 CFO replay contains `{{npv_flows_minus_10}}`.
- Each panelist's rendered prompt does not contain another role's replay file as a substring. The Judge prompt is allowed to contain the positions.
- All four rendered prompts have none of the `$placeholder` names left.

`tests/test_pipeline.py` (tmp run root)

- CPX-001 → `PENDING_APPROVAL`, recommendation APPROVE, no retry.
- CPX-002 → `PENDING_APPROVAL`, APPROVE_WITH_CONDITIONS, conditions non-empty.
- CPX-003 → attempt 1 fails `recommendation_allowed` and `no_raw_figures`; exactly one retry; attempt 2 recommends REJECT and passes the three repairable checks; status `PENDING_APPROVAL`.
- A positions file edited to include `$1,000,000` fails `gate_positions`.

`tests/test_kill_switch_pipeline.py`

- With `CAPEX_KILL_SWITCH=1`, `run()` raises before any model call, a `kill_switch_block` event is recorded, and no `positions` folder is created.

`tests/test_live_config.py`

- Live mode without `ANTHROPIC_API_KEY` raises `ConfigError`.
- The Anthropic client constructor is monkeypatched and is not called.
- Same for a missing `CAPEX_MODEL`.

`tests/test_approval.py`

- A `department_head` is refused for CPX-001.
- A `cfo` approval makes CPX-001 `FINAL`.
- CPX-003 stays pending after the CFO and becomes `FINAL` only after the CEO. A second CFO is refused while the run is still pending.
- A `BLOCKED` run cannot be approved.
- Each accepted approval appends one flight-recorder event.

**Smoke test** (PowerShell, repo root, venv already active):

```powershell
pytest -q
python -m capex.run CPX-003
python -m capex.run CPX-001
python -m capex.approve --proposal CPX-001 --latest --name "Demo CFO" --role cfo --decision APPROVED
```

Then update `HANDOFF.md` (M3 done, M4 next), `DECISIONS.md` (offline-default replay, sequential independent agents, one capped retry, role-matched approvals, and the CPX-003 pass rule if you accept it), and `README.md` (how to switch to live mode, and what the flight recorder holds). The README sentences that still say the recorder is not written yet will be corrected. No git commands.

## Out of scope

The Streamlit UI (M4) and git (M5). No change to finance math. No change to when a memo check passes or fails, including `sponsor_payback_claim`. No parallel agent calls. No second retry. No live API call in the test run.

## Choices that need a yes

1. **CPX-003 pass rule**, above. Repairable checks decide the retry and `PENDING_APPROVAL`. The sponsor-note payback check is recorded and does not block.
2. **`record(event, path=None)` and `run(proposal_id, runs_root=None)`.** Defaults match the spec (`runs/flight_recorder.jsonl` and `runs/`). The extra argument keeps pytest off the real logbook.
3. **Only the Judge is retried**, and only once. A bad panelist response blocks the run.
4. **Role match is exact.** `cfo` tier accepts `cfo` only. `cfo_and_ceo` accepts one `cfo` and one `ceo`. A repeated role is refused.
