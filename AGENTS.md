# Agent rules — CapEx Decision Engine

## Purpose

Teaching demo for business owners. The AI argues, code calculates, code verifies, a human decides.

## Layout

- `src/capex/` — the Python package
- `config/capex_policy.yaml` — hurdle rate, payback limit, approval tiers
- `sample_data/proposals/` — synthetic proposals only
- `tests/` — pytest
- `runs/` — later, the append-only flight recorder

`pyproject.toml` sets pytest `pythonpath = ["src"]`.

## Probabilistic / deterministic boundary

- Probabilistic steps (debate, memo draft) may cite metric keys. They may not invent or edit figures.
- Deterministic steps (schema checks, finance, verifier, stage gates, kill switch) are plain Python.
- The model never produces or edits numbers. All figures come from `src/capex/finance.py`.

## Verifier

`src/capex/verifier.py` may not import anthropic, requests, httpx, or any network/AI library.

## Writes

File and record writes are single-threaded.

## Secrets

Never commit `.env`.

## Tests

Don't modify tests to make them pass. Fix the code.

From the repo root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
python -m capex.validate_samples
```

## Kill switch

If `CAPEX_KILL_SWITCH=1` (environment or `.env`) or a file named `KILL_SWITCH` exists in the repo root, the pipeline must refuse to run. Do not bypass `assert_not_engaged()`. Loading `.env` must not override a variable that is already set.
