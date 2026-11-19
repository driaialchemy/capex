"""Copy one run into docs/sample_run so the evidence can be committed."""

import json
import shutil
import sys
from pathlib import Path

from capex.approval import latest_run
from capex.llm import repo_root
from capex.ui_data import runs_root_from_env


def export_sample(
    proposal_id: str,
    runs_root: str | Path | None = None,
    dest: str | Path | None = None,
) -> Path:
    """Copy the latest run folder and that run's log lines."""
    root = runs_root_from_env(runs_root)
    folder = latest_run(proposal_id, root)
    target = Path(dest) if dest is not None else repo_root() / "docs" / "sample_run" / proposal_id
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(folder, target)
    lines = []
    log_path = root / "flight_recorder.jsonl"
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("run_id") == folder.name:
                lines.append(line)
    text = ("\n".join(lines) + "\n") if lines else ""
    (target / "flight_recorder.jsonl").write_text(text, encoding="utf-8")
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m capex.export_sample CPX-003")
        return 1
    print(export_sample(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
