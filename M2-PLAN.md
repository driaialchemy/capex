# M2 Plan — Finance engine and code-only verifier

Status: **approved** (2026-11-18), with two changes: rendered money is whole dollars (`$110,330`, `-$72,086`) while `Metrics` and `metrics.json` keep cents; `{{proposal_id}}` is not a citeable figure and `tokens_valid` rejects it. IRR is `None` when inflows never cover the investment. Run folders stay `CPX-003-20261118T233045Z`.

Read first: `AGENTS.md`, `HANDOFF.md`, `DECISIONS.md`, and the M1 package (`schemas.py`, `policy.py`, `kill_switch.py`, `validate_samples.py`, `config/capex_policy.yaml`, the three sample proposals). M1 stays as it is. `Proposal` and `CapexPolicy` are not edited. The existing 12 tests stay as they are.

## Goal

Build the calculator and the inspector, both in plain Python, with no model calls.

- Finance math lives in `src/capex/finance.py`. Cash flows are end-of-year. Salvage is added only to the final year, and only for NPV and IRR. Payback ignores salvage. Stress tests scale the operating flows and leave salvage alone. That is the convention that matches the published answer key (CPX-001 at −10% is 59,349.50 only if the $40,000 salvage is not scaled).
- `python -m capex.compute CPX-001` writes `runs/<run_id>/metrics.json` after the kill switch check.
- A stage gate re-reads that file from disk and recomputes. It does not trust an in-memory flag.
- A decision memo may mention figures only as `{{metric_key}}` tokens. `render_memo` fills them in. `verifier.py` checks the token memo and never calls a model.

Workshop moments the tests lock in:

- CPX-002 NPV is about +$6,570.83 at plan and about −$72,086.26 if flows are 10% light.
- CPX-003 payback is `None` (the operating cash flows never recover $1,150,000 inside 5 years), so "pays for itself in 2 years" fails the verifier. NPV is about −$233,924.97, so the only allowed recommendations are DEFER and REJECT.

The answer key is used as given. Tests will not add new expected dollar or rate figures beyond that table.

## Files

```
capex/
  M2-PLAN.md
  src/capex/finance.py          # new
  src/capex/compute.py          # new
  src/capex/gates.py            # new
  src/capex/render.py           # new
  src/capex/verifier.py         # new
  src/capex/schemas.py          # add DecisionMemo only
  tests/test_finance.py         # new
  tests/test_gates.py           # new
  tests/test_verifier.py        # new
  tests/test_render.py          # new
  HANDOFF.md                    # updated at the end
  DECISIONS.md                  # finance conventions appended at the end
```

No new dependencies. IRR is a bisection loop from the standard library. Numpy is not imported.

### Finance engine (`src/capex/finance.py`)

Short functions, plain loops.

`npv(rate, initial_investment, flows, salvage)`

```
-investment + each flow / (1 + rate) ^ year
salvage added to the last year's flow
```

`irr(initial_investment, flows, salvage)`

- If `sum(flows) + salvage` is less than the investment, return `None`. A negative root can still sit inside the bracket (investment 1000, flows `[10, 10]`), and the test wants `None` for that case.
- Otherwise bisect on `[-0.99, 1.0]` until the bracket is narrower than `1e-7`. Keep the half where the NPV sign changes. If the two ends have the same sign, return `None`.
- Round the root to 4 decimals. Checked against the key: 0.2338, 0.1724, 0.1027, 0.0253.

`payback_years(initial_investment, flows)`

Walk the years. Salvage is not an argument. In the year the remaining balance is covered, return `year - 1 + remaining / that year's flow`. Exact recovery at a year-end is a whole number (textbook 2.0, CPX-001 4.0). If the flows never cover the investment, return `None` (CPX-003).

`discounted_payback_years(rate, initial_investment, flows)`

Same walk, using each flow's present value. Textbook result is about 2.352, inside ±0.01.

`sensitivity` is not a separate public puzzle. `compute_metrics` calls `npv` four more times:

- flows × 0.8, × 0.9, × 1.1, salvage unchanged
- same flows, rate = hurdle + 0.02, salvage unchanged

`compute_metrics(proposal, policy) -> Metrics`

Money is rounded to cents. Rates are rounded to 4 decimals. Payback years are stored to 3 decimals (the renderer still shows one decimal). `None` stays `None`.

`Metrics` fields, `extra="forbid"`:

| Field | Meaning |
|---|---|
| `proposal_id` | Identity for the stage gate. Not one of the answer-key figures. |
| `npv`, `irr` | Base case. Salvage included. |
| `payback_years`, `discounted_payback_years` | Salvage excluded. |
| `npv_flows_minus_20`, `npv_flows_minus_10`, `npv_flows_plus_10` | Operating flows scaled. Salvage not scaled. |
| `npv_rate_plus_2pp` | Hurdle plus 2 percentage points. |
| `hurdle_rate`, `max_payback_years`, `initial_investment` | Copied from policy and proposal. |
| `approval_tier` | Existing `approval_tier()` function. |
| `allowed_recommendations` | Rule below. |

`proposal_id` is on the model because `gate_metrics` validates `metrics.json` as `Metrics` and then checks the id. The other fields are the citeable metric keys.

`allowed_recommendations(npv, payback_years, policy)` in one function, in this order:

1. NPV < 0 → `[DEFER, REJECT]`
2. NPV ≥ 0 and (payback is `None` or payback > `max_payback_years`) → `[APPROVE_WITH_CONDITIONS, DEFER, REJECT]`
3. Otherwise → all four, in policy order: APPROVE, APPROVE_WITH_CONDITIONS, DEFER, REJECT

Payback equal to the max (5.0) is allowed through. CPX-001 takes branch 3. CPX-003 takes branch 1. CPX-002's payback is not in the answer key (the table's dash). The tests will not assert a payback number or an allowed-list for CPX-002.

### Run artifact and gate

`src/capex/compute.py`

`python -m capex.compute CPX-001`

1. `assert_not_engaged()`
2. Load `sample_data/proposals/<id>.json` and `config/capex_policy.yaml` from the working directory.
3. `run_id = <proposal_id>-<UTC timestamp>` with no colons, so Windows can store it: `CPX-001-20261118T233045Z`.
4. Write `runs/<run_id>/metrics.json`. Create the directory only if it does not already exist.
5. Print the run directory.

`src/capex/gates.py`

`gate_metrics(run_dir, proposal, policy) -> GateResult`

`GateResult` is `passed: bool` and `reasons: list[str]`.

The function opens `metrics.json` from disk. Missing file fails. The file is validated as `Metrics`. A `proposal_id` that does not match the proposal fails. Every stored value is compared with a fresh `compute_metrics(proposal, policy)`. One edited number fails. There is no in-memory shortcut.

### Memo schema and renderer

Added to `schemas.py` (nothing else in that file changes):

- `MemoSection`: `title`, `body`
- `DecisionMemo`: `proposal_id`, `recommendation` (one of the four names), `headline`, `sections`, `cited_metrics` (`list[str]`)
- Unknown fields rejected.

`src/capex/render.py` — `render_memo(memo, metrics) -> DecisionMemo`

Returns a new memo. The original token text is left alone. Substitution:

| Kind | Keys | Format |
|---|---|---|
| Money | `npv`, the three flow NPVs, `npv_rate_plus_2pp`, `initial_investment` | `$110,330` or `-$72,086` (whole dollars). Cents stay in `Metrics` and `metrics.json`. |
| Rate | `irr`, `hurdle_rate` | `17.2%` (one decimal). `None` → `n/a` |
| Years | `payback_years`, `discounted_payback_years`, `max_payback_years` | `4.0`, or `not recovered` when `None` |
| Words | `approval_tier` | the stored word |
| List | `allowed_recommendations` | `DEFER, REJECT` |
| Identity | `proposal_id` | left as the token `{{proposal_id}}`. It is not a citeable figure. |

### Verifier (`src/capex/verifier.py`)

Imports: `re`, pydantic, and the local memo and metrics types. No `anthropic`, `requests`, `httpx`, `urllib`, `socket`, or any other AI or network library.

`verify(memo, metrics, proposal) -> VerificationReport`

`VerificationReport.passed` is true only when every check below passes, except `sponsor_percent_claims`, which is informational and always passes.

| Check | Pass rule |
|---|---|
| `recommendation_allowed` | `memo.recommendation` is in `metrics.allowed_recommendations`. |
| `no_raw_figures` | After `{{...}}` tokens are masked, headline and section bodies contain no `$` amount, no percent, and no bare number of two or more digits. `Year 1` through `Year 20` (any case) are masked first and allowed. |
| `tokens_valid` | Every `{{token}}` is a citeable `Metrics` field (`proposal_id` is rejected), and every token that appears is listed in `cited_metrics`. |
| `sponsor_payback_claim` | From `sponsor_notes`, extract `pays for itself in N years` and `payback of N years`. Fail if payback is `None`, or if the claim and the computed payback differ by more than 0.5 years. No such sentence → pass. |
| `sponsor_percent_claims` | Any `40%`-style claim in `sponsor_notes` is reported as `UNVERIFIED`. The check itself passes. |

The verifier reads the memo and the metrics object. It does not read a model transcript. Percent claims are not checked against a calculated fuel saving; M2 has no fuel model.

## Tests

Existing 12 tests still run. New tests use the published tolerances and do not loosen them: NPV ±0.01, IRR ±0.0005, discounted payback ±0.01.

`tests/test_finance.py`

- Textbook: investment 1000, flows `[500, 500, 500]`, salvage 0, rate 0.10. NPV 243.43, IRR 0.2338, payback 2.0, discounted payback ≈ 2.352, NPV at flows −10% = 119.08.
- CPX-001: NPV 110329.85, IRR 0.1724, payback 4.0, NPV at flows −10% = 59349.50, allowed = all four.
- CPX-002: NPV 6570.83, IRR 0.1027, NPV at flows −10% = −72086.26.
- CPX-003: NPV −233924.97, IRR 0.0253, payback `None`, NPV at flows −10% = −316218.65, allowed = `[DEFER, REJECT]`.
- `irr(1000, [10, 10], 0)` is `None`.

`tests/test_gates.py` (all under `tmp_path`)

- A file written from `compute_metrics` passes.
- A missing file fails.
- One hand-edited value fails.
- A `proposal_id` that does not match the proposal fails.

`tests/test_verifier.py`

- A hand-built CPX-001 APPROVE memo that cites only real tokens passes.
- CPX-003 recommending APPROVE fails `recommendation_allowed`.
- A body with `$110,000` or `17%` fails `no_raw_figures`.
- `{{roi}}` fails `tokens_valid`. A real token omitted from `cited_metrics` fails the same check.
- CPX-003's "pays for itself in 2 years" fails `sponsor_payback_claim`.
- CPX-003's "40% fuel savings" is reported `UNVERIFIED`, and that check's `passed` flag is true. A otherwise-clean memo whose notes contain only a percentage claim still passes overall.
- An `ast` walk of `src/capex/verifier.py` finds no import of `anthropic`, `requests`, `httpx`, `urllib`, or `socket`.

`tests/test_render.py`

- Money, rate, and year tokens use the formats in the table above.
- Payback `None` renders `not recovered`.

**Smoke test** (PowerShell, repo root, venv already installed):

```powershell
pytest -q
python -m capex.compute CPX-003
```

Then update `HANDOFF.md` (M2 done, M3 next) and append to `DECISIONS.md`: end-of-year cash flows, salvage only in NPV and IRR, the allowed-recommendation rule, and token-only figures. No git commands.

## Out of scope

AI calls, debate agents, the flight recorder, the human approval gate, the Streamlit UI, and git. Those are M3–M5.

Also not in M2:

- Editing `Proposal` or `CapexPolicy`
- Generating a memo from a proposal (tests build memos by hand; nothing writes a memo file)
- A fuel-savings calculation for the "40%" claim (it stays UNVERIFIED on purpose)
- Numpy, numpy-financial, or any new package
- Rewriting M1 tests

## Choices

1. **Money on the page.** Whole dollars: `$110,330`, `-$72,086`. Cents stay in `Metrics` and `metrics.json`.
2. **`proposal_id` is stored, not citeable.** The gate matches it. `tokens_valid` rejects `{{proposal_id}}`.
3. **IRR of a project that never recovers its cost is `None`.** Bisection still runs only when total inflows, including salvage, cover the investment and the bracket changes sign.
4. **Run folder name.** `CPX-003-20261118T233045Z` (UTC, no colons). The smoke run wrote `runs/CPX-003-20261118T233722Z`.
