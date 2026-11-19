# M5 GitHub push

Status: **waiting for approval**. No `git init`, commit, remote, or push until this plan is approved. No `gh repo create`, `git push`, or `git remote add` until the reply is exactly `approved push`.

## Goal

Publish `C:\Users\msell\OneDrive\aialchemyrepos\workuity\capex` as the public teaching repo https://github.com/driaialchemy/capex. Local steps stay reversible. Publishing waits for a second, explicit approval.

## What is already true

- The folder is not a git repo. The parent `workuity` folder is not one either.
- `.gitignore` already excludes `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `runs/*` with `!runs/.gitkeep`, and `assets/source/`.
- `runs/.gitkeep` exists. There is no `.env` file in the folder. `.env.example` has an empty `ANTHROPIC_API_KEY=` plus the model name, `offline`, and kill switch `0`.
- `docs/sample_run/CPX-003/` is present, including `metrics.json`, the three positions, both memo attempts, `memo.md`, `status.json`, and `flight_recorder.jsonl`.
- `README.md` links to that sample, names Dr. Michael Seller, documents the kill switch, gives `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1`, and asks the three governance questions: what it can do, what it can reach, and what evidence remains.
- Last full suite was 62 passed. Phase A runs it again before anything is committed.

## Phase A — local, after this plan is approved

1. Stay in the capex folder. Run `pytest -q` and require 62 passed.
2. Re-read `.gitignore`. Add any missing line from the list above. Do not add a LICENSE or change product code.
3. Secret scan of files that would be tracked. Search for `sk-ant`, `ANTHROPIC_API_KEY=` followed by a non-empty value, and `api_key`. Confirm `.env.example` is placeholders only. If a real secret is found, stop and report it. Do not commit.
4. Confirm the sample folder and the README items listed above. If a link or a required README line is missing, fix that local text and say what changed.
5. `git init -b main`. Then `git add .` and `git status --short`. The staged set must not include `.env`, `.venv`, `runs` output other than `runs/.gitkeep`, or anything under `assets/source/`.
6. One local commit: `CapEx Decision Engine: Workuity AI Exchange Track 1 companion app`.
7. `gh auth status`, then `gh repo view driaialchemy/capex`. Record whether the remote already exists and whether it already has commits.

If OneDrive reports a file lock, wait and retry that one command once, then stop and report.

## Phase B — stop and show

- pytest result
- secret-scan result
- staged file count from the commit, and the total size of the repo
- any file over 1 MB
- the single next command, chosen from what `gh repo view` found:
  - remote missing: `gh repo create driaialchemy/capex --public --source=. --remote=origin --push`
  - remote exists and is empty: `git remote add origin https://github.com/driaialchemy/capex.git` then `git push -u origin main`
  - remote already has commits: do not push. Show what is there.

Then wait for the reply `approved push`.

## Phase C — only after `approved push`

- Run the one command shown in Phase B.
- Confirm with `gh repo view driaialchemy/capex` and print https://github.com/driaialchemy/capex.
- Update `HANDOFF.md` to M5 done, published, with that URL and the date.
- Commit that HANDOFF change and push it. This follow-up push is the only push pre-approved by the original prompt.

## Out of scope

- No force-push, history rewrite, or branch deletion.
- No LICENSE file. No description, visibility, or settings changes beyond the create-or-push command above.
- No product behavior changes. No edits to finance, the verifier, the pipeline, or the tests to make them pass.
