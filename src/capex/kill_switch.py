"""Stop the pipeline when the kill switch is on."""

import os
from pathlib import Path

from dotenv import load_dotenv

from capex.flight_recorder import new_event, record


class KillSwitchEngaged(RuntimeError):
    """Raised when the pipeline is asked to run with the kill switch on."""


def _repo_root() -> Path:
    """Directory that contains pyproject.toml, walking up from this file."""
    start = Path(__file__).resolve().parent
    for folder in (start, *start.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return Path.cwd()


def is_engaged(root: Path | None = None) -> bool:
    """True when CAPEX_KILL_SWITCH=1 or a KILL_SWITCH file is present.

    Loads `.env` from the repo root, or from `root` when given.
    A variable already set in the environment is not replaced.
    """
    folder = Path(root) if root is not None else _repo_root()
    load_dotenv(folder / ".env", override=False)
    if os.environ.get("CAPEX_KILL_SWITCH") == "1":
        return True
    return (folder / "KILL_SWITCH").is_file()


def assert_not_engaged(root: Path | None = None) -> None:
    if is_engaged(root):
        raise KillSwitchEngaged(
            "Kill switch is engaged. Refusing to run. "
            "Unset CAPEX_KILL_SWITCH or remove the KILL_SWITCH file."
        )


def engage(root: Path | None = None, log_path: Path | None = None) -> None:
    """Create the KILL_SWITCH file and append one log line."""
    folder = Path(root) if root is not None else _repo_root()
    (folder / "KILL_SWITCH").write_text("", encoding="utf-8")
    record(
        new_event(
            "kill-switch",
            "kill_switch_block",
            "system",
            "blocked",
            "Kill switch engaged from the demo.",
        ),
        log_path,
    )


def release(root: Path | None = None, log_path: Path | None = None) -> None:
    """Remove the KILL_SWITCH file and append one log line."""
    folder = Path(root) if root is not None else _repo_root()
    path = folder / "KILL_SWITCH"
    if path.is_file():
        path.unlink()
    record(
        new_event(
            "kill-switch",
            "stage",
            "system",
            "ok",
            "Kill switch released from the demo.",
        ),
        log_path,
    )
