# M1 Plan — CapEx Decision Engine scaffold

Status: **approved** (2026-11-18), with one change: `python-dotenv` loads `.env` from the repo root (or from `root` when given) before the kill switch reads `CAPEX_KILL_SWITCH`. An existing environment variable is not overridden. A test covers a `.env` in `tmp_path` that sets `CAPEX_KILL_SWITCH=1`.

## Goal

Lay the rails for a teaching demo whose lesson is: the AI argues, code calculates, code verifies, a human decides.

Milestone 1 creates the project scaffold, governance files, policy config, three synthetic proposals, Pydantic schemas, a kill switch, and tests. A novice should be able to read every module aloud in a workshop.

No AI model calls. No finance math. No abstractions this milestone does not need.

Done when `pytest -q` and `python -m capex.validate_samples` pass from the repo root, and `HANDOFF.md` records M1 done / M2 next.

## Files (full tree)

```
capex/
  M1-PLAN.md                          # this plan (kept as the approval record)
  AGENTS.md                           # rules every coding agent inherits
  CLAUDE.md                           # one line: Read and follow AGENTS.md.
  HANDOFF.md                          # milestone status; updated at the end of M1
  DECISIONS.md                        # dated decision log
  README.md                           # plain-English overview, setup, ASCII architecture, governance
  .env.example
  .gitignore
  requirements.txt
  pyproject.toml
  .cursor/rules/governance.mdc        # file-scoped; verifier.py only
  config/capex_policy.yaml
  sample_data/proposals/CPX-001.json
  sample_data/proposals/CPX-002.json
  sample_data/proposals/CPX-003.json
  runs/.gitkeep
  src/capex/__init__.py               # empty; required so `python -m capex...` works
  src/capex/schemas.py
  src/capex/policy.py
  src/capex/kill_switch.py
  src/capex/validate_samples.py
  tests/test_schemas.py
  tests/test_sample_data.py
  tests/test_kill_switch.py
```

Not created in M1: `finance.py`, `verifier.py`, debate agents, flight recorder, Streamlit UI. The governance rule still targets `src/capex/verifier.py` so it is in force when M2 adds that file.

### How each piece behaves

**Governance docs**

- `AGENTS.md` states the project purpose, the `src/` layout, and the probabilistic/deterministic boundary. It includes these rules verbatim in substance: the model never produces or edits numbers (all figures come from `src/capex/finance.py`); `src/capex/verifier.py` may not import `anthropic`, `requests`, `httpx`, or any network/AI library; file and record writes are single-threaded; never commit `.env`; don't modify tests to make them pass; how to run tests.
- `CLAUDE.md` is one line: `Read and follow AGENTS.md.`
- `DECISIONS.md` is seeded, dated 2026-11-18, with: Python/Streamlit/Pydantic stack; deterministic finance engine; code-only verifier; append-only `.jsonl` flight recorder; synthetic data only. Any extra M1 choice (below) is appended when the code is written.
- `HANDOFF.md` starts as "M1 in progress" and is rewritten at the end to "M1 done, M2 next" with known issues (none expected).
- `README.md` is plain English: what the app is, one-command setup and test run, the ASCII architecture from the build plan, and a Governance section. That section names Dr. Michael Seller (AI Alchemy) as owner, answers the three NetWitness exposure questions (What can it do? What can it reach? What evidence remains?), and documents the kill switch.
- `.cursor/rules/governance.mdc` is Cursor-only and file-scoped. Frontmatter: `globs: src/capex/verifier.py`, `alwaysApply: false`. Body is only: no AI or network imports; pure deterministic Python. It does not restate `AGENTS.md`.

**Config and env**

- `.env.example`: `ANTHROPIC_API_KEY=`, `CAPEX_MODEL=`, `CAPEX_LLM_MODE=offline`, `CAPEX_KILL_SWITCH=0`. M1 does not load this file. The kill switch reads the process environment, which a later milestone can populate from `.env`.
- `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `runs/*`, with a negation so `runs/.gitkeep` is kept.
- `requirements.txt`: `pydantic>=2`, `PyYAML`, `pytest`, `streamlit`, `anthropic`, `python-dotenv`, then `-e .`. Streamlit and anthropic are installed and unused until later milestones. `-e .` is what makes `python -m capex.validate_samples` work after the specified smoke command, because the package lives under `src/` and that command does not set `PYTHONPATH`.
- `pyproject.toml`: package name `capex`, requires Python `>=3.11`, setuptools build backend, packages found under `src`, and pytest `pythonpath = ["src"]` with `testpaths = ["tests"]`. Dependencies stay in `requirements.txt` so there is one place a novice edits them.

**Policy**

`config/capex_policy.yaml`:

```yaml
hurdle_rate: 0.10
max_payback_years: 5
approval_tiers:
  department_head_if_under: 250000
  cfo_if_up_to: 1000000
  above_that: cfo_and_ceo
allowed_recommendations:
  - APPROVE
  - APPROVE_WITH_CONDITIONS
  - DEFER
  - REJECT
```

Tier rule, readable in one function:

- amount **< 250000** → `department_head` (so 200000 is department_head)
- amount **<= 1000000** → `cfo` (so 250000 and 780000 and 1000000 are cfo)
- amount **> 1000000** → `cfo_and_ceo` (so 1150000 is cfo_and_ceo)

`load_policy(path) -> CapexPolicy` reads the YAML. `approval_tier(amount, policy) -> str` applies the rule above. No hurdle-rate or payback math in M1; those fields are stored for M2.

**Schemas** (`src/capex/schemas.py`)

Pydantic v2, `extra="forbid"` on every model (unknown fields rejected).

`Proposal`

| Field | Rule |
|---|---|
| `proposal_id` | string |
| `title` | string |
| `sponsor` | string |
| `department` | string |
| `initial_investment` | number, greater than 0 |
| `useful_life_years` | int, 1 through 20 |
| `salvage_value` | number, ≥ 0 |
| `annual_net_cash_flows` | list of numbers; length must equal `useful_life_years` |
| `assumptions` | list of strings |
| `sponsor_notes` | string |

`CapexPolicy` mirrors the YAML: `hurdle_rate` (float), `max_payback_years` (int), `approval_tiers` (a small nested model with the three keys above), `allowed_recommendations` (list of strings).

**Kill switch** (`src/capex/kill_switch.py`)

- `is_engaged(root=None) -> bool`. Loads `.env` from the repo root, or from `root` when given, with `override=False` (an existing environment variable is left alone). Then engaged when `CAPEX_KILL_SWITCH` is exactly `"1"`, or when a file named `KILL_SWITCH` exists in that same directory. Only `"1"` counts; `"0"`, empty, and unset are off.
- `assert_not_engaged(root=None)` raises `KillSwitchEngaged` (a `RuntimeError` subclass) when engaged.
- An optional `root` argument is how tests point at `tmp_path` without touching the real repo.

**Sample validator** (`src/capex/validate_samples.py`)

`python -m capex.validate_samples` loads every `*.json` in `sample_data/proposals/` (relative to the working directory), validates each as a `Proposal`, and prints one line per file: `PASS <path>` or `FAIL <path>: <reason>`. Exit code 0 when all pass, 1 otherwise.

**Synthetic proposals** (USD, fictional sponsors)

Cash-flow list length matches useful life in all three, so they pass M1 validation. The third one's notes are written to be wrong on purpose; M2's verifier is what catches that, not M1.

- `CPX-001` "CNC Machining Center", sponsor Alex Nguyen, Manufacturing. Investment 420000, life 7, salvage 40000, flows `[95000, 105000, 110000, 110000, 110000, 105000, 100000]`. Assumptions and notes: realistic, modest claims.
- `CPX-002` "Warehouse Pick Automation", sponsor Jordan Hale, Operations. Investment 780000, life 6, salvage 0, flows `[120000, 170000, 200000, 210000, 210000, 200000]`. Notes: ramp-up risk and a labor-savings assumption.
- `CPX-003` "Delivery Fleet Replacement", sponsor Riley Cho, Logistics. Investment 1150000, life 5, salvage 150000, flows `[180000, 210000, 230000, 240000, 240000]`. Notes include an unverified vendor claim of "40% fuel savings" and the sponsor's statement "pays for itself in 2 years".

## Tests

If a test fails, fix the code, not the test.

`tests/test_schemas.py`

- A valid proposal loads.
- Cash-flow length ≠ useful life is rejected.
- Negative investment is rejected.
- An unknown field is rejected.

`tests/test_sample_data.py`

- All three sample proposals validate.
- Proposal IDs are unique.
- The policy file loads.
- `approval_tier` returns `department_head` / `cfo` / `cfo_and_ceo` at 200000 / 780000 / 1150000.

`tests/test_kill_switch.py` (tmp_path and monkeypatch only; never writes a real `KILL_SWITCH` in the repo)

- Off by default.
- On when `CAPEX_KILL_SWITCH=1`.
- On when a `KILL_SWITCH` file exists under tmp_path.
- `assert_not_engaged` raises `KillSwitchEngaged` when on.

**Smoke test** (PowerShell, from `capex/`):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q; python -m capex.validate_samples
```

After the smoke test passes: update `HANDOFF.md` (M1 done, M2 next) and append any new decisions to `DECISIONS.md`. No git commands.

## Out of scope

Finance calculations, AI calls, debate agents, flight recorder, Streamlit UI, and git commands. Those belong to M2–M5.

Also out of scope for M1, so they are not built "while we're here":

- Loading `.env` inside the app
- NPV, IRR, payback, or any check that the sponsor's "2 years" claim is false
- Creating `finance.py` or `verifier.py`
- A pipeline runner that calls the kill switch (the function exists and is tested; nothing invokes it yet)
- Base classes, plugin registries, or a config framework beyond one YAML file and one loader

## Choices that need a yes

1. **Tier boundaries.** Under 250000 is department head. 250000 through 1000000 inclusive is CFO. Above 1000000 is CFO and CEO. The YAML uses three plainly named keys instead of a list of range objects.
2. **Editable install.** `requirements.txt` ends with `-e .` so the given smoke command can import `capex` from `src/` without a separate `PYTHONPATH` step.
3. **Kill switch API.** `is_engaged(root=None)` loads `.env` from the repo root (or from `root` when given) without overriding existing environment variables. Only the env value `"1"` or a `KILL_SWITCH` file engages it. The optional directory keeps tests off the real tree.
4. **Empty `src/capex/__init__.py`.** Not in the original file list; required for `python -m capex.validate_samples`.
