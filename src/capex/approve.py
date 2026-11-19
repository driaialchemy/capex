"""CLI: python -m capex.approve --proposal CPX-001 --latest --name "Demo CFO" --role cfo --decision APPROVED"""

import argparse

from capex.approval import ApprovalError, approve, latest_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign off a CapEx run.")
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    if not args.latest:
        print("Pass --latest to select the newest run for that proposal.")
        return 1
    try:
        run_dir = latest_run(args.proposal)
        status = approve(run_dir, args.name, args.role, args.decision, args.note)
    except ApprovalError as error:
        print(error)
        return 1
    print(status["status"])
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
