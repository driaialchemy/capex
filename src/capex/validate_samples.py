"""Validate every JSON file in sample_data/proposals/."""

import json
from pathlib import Path

from pydantic import ValidationError

from capex.schemas import Proposal


def main() -> int:
    folder = Path("sample_data/proposals")
    files = sorted(folder.glob("*.json"))
    if not files:
        print(f"FAIL {folder.as_posix()}: no proposal files found")
        return 1

    failed = False
    for path in files:
        label = path.as_posix()
        try:
            Proposal.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, json.JSONDecodeError) as error:
            failed = True
            if isinstance(error, ValidationError):
                reason = error.errors()[0]["msg"]
            else:
                reason = str(error)
            one_line = " ".join(reason.splitlines())
            print(f"FAIL {label}: {one_line}")
        else:
            print(f"PASS {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
