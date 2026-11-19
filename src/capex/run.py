"""CLI: python -m capex.run CPX-003"""

import sys

from capex.kill_switch import KillSwitchEngaged
from capex.pipeline import run


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m capex.run CPX-001")
        return 1
    try:
        result = run(sys.argv[1])
    except KillSwitchEngaged as error:
        print(error)
        return 1
    except FileNotFoundError as error:
        print(error)
        return 1
    for line in result.lines:
        print(line)
    return 0 if result.status == "PENDING_APPROVAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
