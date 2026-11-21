# CapEx Decision Engine

A teaching demo for business owners. The AI argues, code calculates, code verifies, and a human decides.

You give the engine a capital-spending proposal. Code checks the shape of the proposal and computes NPV, IRR, and payback. Three roles (sponsor, CFO, operations) debate those figures. A draft memo is written, then checked by code that does not call a model. Nothing is approved until a person says so.

The default is offline. Replays in `sample_data/replays/` stand in for the model, so the demo runs with no API key.

## Setup and tests

Requires Python 3.11. From this folder, in PowerShell:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q; python -m capex.validate_samples
```

Check the sample proposals on their own:

```powershell
python -m capex.validate_samples
```

Run one proposal and, when it is waiting, sign it. From this folder, with the venv active:

```powershell
python -m capex.run CPX-001
python -m capex.approve --proposal CPX-001 --latest --name "Demo CFO" --role cfo --decision APPROVED
```

Exit code 0 means the run is `PENDING_APPROVAL`. CPX-003 needs both a CFO and a CEO. CPX-001 needs a CFO.

## Present the demo

From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
```

Windows blocks unsigned scripts by default, so the launch command includes `-ExecutionPolicy Bypass`. The script creates `.venv` when it is missing, installs `requirements.txt`, copies `.env.example` to `.env` when `.env` is missing, and runs `streamlit run app.py`.

The page has one sidebar and six tabs. Each tab after the proposal is labeled so the boundary is on screen.

1. **Proposal.** The order. Title, sponsor, investment, approval tier, sponsor notes, and assumptions. CPX-003's notes include the "2 years" claim.
2. **Calculator. Code check.** NPV, IRR, and payback from `render.py`, plus a Rules decision card: the outcome, the rule, and the reasons in plain English. Below that, a bar chart of the stored scenarios: plan, flows −20%, flows −10%, flows +10%, and rate +2pp. If a scenario NPV is below zero, the page says "This proposal loses money if…" and names it. CPX-002 loses money at flows −10%.
3. **Panel. AI judgment.** Sponsor, CFO, and operations side by side. Tokens are filled from the metrics file.
4. **Inspector. Code check.** One block per memo attempt. Blocking checks and red flags are separate. The on-screen heading is "Red flags for the approver". CPX-003 attempt 1 is blocked; attempt 2 passes, and the payback claim stays a finding. The final `memo.md` is below.
5. **Logbook. Record.** This run's flight-recorder rows, filtered by event type. A retry row shows `attempt_number`, `retry_of`, and `retry_reason`, and is repeated in a warning.
6. **Sign-off. Human.** The line "Decided by rule R#: …" names the rule that set the recommendation. Name, role, decision, and a note follow. Submit calls `approval.approve`. A refused role shows the reason. It does not crash, and it does not write an approval.

Code decides the recommendation from the numbers. The Judge explains that result. First matching rule wins.

| Rule | When it fires | Recommendation |
| --- | --- | --- |
| R1 | Net present value is below zero | Reject |
| R2 | Payback is missing, or longer than the policy limit | Defer |
| R3 | Net present value is below zero if cash flows come in a tenth light | Approve with conditions |
| R4 | Otherwise | Approve |

CPX-001 is R4, CPX-002 is R3, and CPX-003 is R1. The stress figure is `npv_flows_minus_10`, named in `config/capex_policy.yaml`.

The sidebar shows offline or live mode and the kill switch. **Run review** calls the pipeline. **Engage kill switch** creates `KILL_SWITCH` and the next run refuses to start. **Release kill switch** removes the file.

## See the evidence

A copy of one finished CPX-003 review is in [docs/sample_run/CPX-003](docs/sample_run/CPX-003). It includes `metrics.json`, the three positions, both memo attempts, `memo.md`, `status.json`, and that run's `flight_recorder.jsonl`. The live `runs/` folder stays gitignored. Refresh the copy with:

```powershell
python -m capex.export_sample CPX-003
```

## Live mode

Leave `CAPEX_LLM_MODE=offline` unless you intend to call Claude. To switch:

1. Copy `.env.example` to `.env`.
2. Set `ANTHROPIC_API_KEY` to your key.
3. Set `CAPEX_MODEL=claude-sonnet-5-5`.
4. Set `CAPEX_LLM_MODE=live`.

If the key or the model name is missing, live mode raises `ConfigError` before it constructs a client. The kill switch is still checked first.

## Architecture

```
proposal.json ──► [1 Intake: Pydantic schema]            deterministic
                ──► [2 Finance engine: NPV/IRR/payback]   deterministic  (model never does math)
                ──► [3 Debate: Sponsor · CFO · Ops]       probabilistic  (G9, read-only, cites metric keys only)
                ──► [4 Synthesizer → draft memo]          probabilistic
                ──► [5 Independent verifier]              deterministic  (A7, code-only, no AI imports)
                ──► [6 Stage gates: re-read files on disk] deterministic
                ──► [7 Human approval gate]               human          (A5, enforced in code)
every step ──► runs/flight_recorder.jsonl (append-only, A8)
```

Steps 2 through 7 run in code. `app.py` presents them. `runs/flight_recorder.jsonl` is written by the pipeline, by sign-off, and by the kill-switch buttons. The page only reads that file when it draws the logbook. Each line is one JSON object and is only appended. A line has `event_id`, `ts`, `run_id`, `event_type`, `actor`, `mode` (`offline` or `live`), `model` (null offline), `attempt_number`, `retry_of`, `retry_reason`, `input_sha256`, `output_path`, `status`, and `detail`. Event types are `stage`, `model_call`, `gate`, `verifier`, `retry`, `approval`, `kill_switch_block`, and `error`. Proposal findings are copied into the verifier line's `detail`.

## Governance

**Owner:** Dr. Michael Seller (AI Alchemy)

**What can it do?**
It reads a proposal, computes NPV, IRR, and payback, runs the sponsor, CFO, and operations positions, and writes a draft memo. The Streamlit page shows that work. Code then checks that memo. Blocking failures (`recommendation_allowed`, `no_raw_figures`, `tokens_valid`) stop the run or trigger one Judge retry. Other failures, such as CPX-003's "pays for itself in 2 years" claim, are Proposal findings the approver still sees. It cannot move money or send messages. A human decides.

**What can it reach?**
Local files in this project: the policy, the sample proposals, the replays, `.env`, and the `runs/` folder. Offline mode opens no network connection. Live mode calls the Anthropic API when `CAPEX_LLM_MODE=live`. The API key stays in `.env`, which is not committed.

**What evidence remains?**
Each run writes `metrics.json`, the three positions, the memo attempts, `memo.md`, `verification.attemptN.json`, and `status.json` under `runs/<proposal-id>-<UTC timestamp>/`. Sign-off writes `approvals.json` in that folder. Every stage also appends one line to `runs/flight_recorder.jsonl`. `.env` is gitignored. The `runs/` folder is gitignored except for `runs/.gitkeep`.

**Kill switch:** set `CAPEX_KILL_SWITCH=1` in `.env`, or create a file named `KILL_SWITCH` in the repo root. The pipeline refuses to run. If `CAPEX_KILL_SWITCH` is already set in the process environment, the value in `.env` does not replace it.
