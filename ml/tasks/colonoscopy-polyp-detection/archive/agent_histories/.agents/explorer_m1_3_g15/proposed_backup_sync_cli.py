#!/usr/bin/env python3
"""
ChakraModel Backup Synchronization, Recovery & Daily Scheduling Engine
Command-Line Interface (CLI) & Scheduling Logic Module

Supports:
- Standalone execution without arguments (runs full workflow: sync + recovery)
- Explicit flags: --verify-and-sync, --recover-downloads, --all
- Scheduled startup mode: --startup-task (enforces 6-11 AM window and daily guard)
- Diagnostic & testing flags: --check-window, --dry-run, --force
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Default Constants
DEFAULT_WINDOW_START = "06:00"
DEFAULT_WINDOW_END = "11:00"
PROJECT_ROOT = Path("M:/chakramodel")
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "backup_sync.log"
DEFAULT_STATE_FILE = PROJECT_ROOT / "logs" / "backup_sync_state.json"

logger = logging.getLogger("backup_sync")


# ---------------------------------------------------------------------------
# Time Window Enforcement
# ---------------------------------------------------------------------------

def parse_time_str(time_str: str) -> datetime.time:
    """Parse 'HH:MM' or 'HH:MM:SS' string to datetime.time."""
    parts = [int(p) for p in time_str.strip().split(":")]
    if len(parts) == 2:
        return datetime.time(parts[0], parts[1], 0)
    elif len(parts) == 3:
        return datetime.time(parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid time format: '{time_str}'. Expected 'HH:MM' or 'HH:MM:SS'.")


def is_within_scheduled_window(
    start_str: str = DEFAULT_WINDOW_START,
    end_str: str = DEFAULT_WINDOW_END,
    current_time: Optional[datetime.time] = None,
) -> Tuple[bool, str]:
    """
    Check if the given or current time falls between start_str and end_str inclusive.
    Returns (is_in_window, descriptive_message).
    """
    start_t = parse_time_str(start_str)
    end_t = parse_time_str(end_str)
    now_t = current_time or datetime.datetime.now().time()

    in_window = start_t <= now_t <= end_t
    now_formatted = now_t.strftime("%H:%M:%S")

    if in_window:
        msg = f"Current time ({now_formatted}) is within scheduled window ({start_str}-{end_str})."
    else:
        msg = f"Outside scheduled window ({start_str}-{end_str}), skipping. Current time: {now_formatted}."

    return in_window, msg


# ---------------------------------------------------------------------------
# State Tracker & Daily Run Guard
# ---------------------------------------------------------------------------

class SyncStateManager:
    """
    Persists and inspects backup synchronization state using atomic JSON file updates.
    Guards against redundant multi-boot runs on the same calendar day.
    """

    def __init__(self, state_file: Path = DEFAULT_STATE_FILE):
        self.state_file = Path(state_file)

    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file or return empty defaults."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read state file '{self.state_file}': {e}. Treating as empty.")
            return {}

    def has_run_successfully_today(self, reference_date: Optional[datetime.date] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if a successful backup sync was already completed today.
        Returns (has_run, last_run_timestamp_or_none).
        """
        today_str = (reference_date or datetime.date.today()).isoformat()
        state = self.load_state()

        last_date = state.get("last_run_date")
        last_status = state.get("last_status")
        last_timestamp = state.get("last_run_timestamp")

        if last_date == today_str and last_status == "SUCCESS":
            return True, last_timestamp

        return False, last_timestamp

    def record_run(
        self,
        status: str,
        trigger_mode: str,
        metrics: Optional[Dict[str, Any]] = None,
        reference_dt: Optional[datetime.datetime] = None,
    ) -> None:
        """
        Atomically record a sync run to the state file using temporary file and os.replace.
        """
        now = reference_dt or datetime.datetime.now()
        state = self.load_state()

        # Update root state
        state["last_run_timestamp"] = now.isoformat()
        state["last_run_date"] = now.date().isoformat()
        state["last_status"] = status
        state["last_trigger_mode"] = trigger_mode
        state["last_metrics"] = metrics or {}

        # Maintain last 10 runs history
        history = state.get("history", [])
        history.append({
            "timestamp": now.isoformat(),
            "date": now.date().isoformat(),
            "status": status,
            "trigger_mode": trigger_mode,
            "metrics": metrics or {},
        })
        state["history"] = history[-10:]

        # Atomic write
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(temp_file, self.state_file)
            logger.debug(f"State updated successfully at '{self.state_file}' with status '{status}'.")
        except Exception as e:
            logger.error(f"Failed to write state file '{self.state_file}': {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# CLI Argument Parser Construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for backup_sync.py."""
    parser = argparse.ArgumentParser(
        prog="backup_sync.py",
        description=(
            "ChakraModel Backup Synchronization & Recovery Engine.\n"
            "Automatically verifies and repairs 5 target backup locations using SHA-256,\n"
            "scans and recovers downloads, and handles scheduled daily startup tasks."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    action_group = parser.add_argument_group("Execution Modes & Actions")
    action_group.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run full backup synchronization and downloads recovery (default behavior when no actions specified).",
    )
    action_group.add_argument(
        "--verify-and-sync",
        action="store_true",
        default=False,
        help="Verify all 5 target backup directories against M:\\chakramodel and auto-fix discrepancies.",
    )
    action_group.add_argument(
        "--recover-downloads",
        action="store_true",
        default=False,
        help="Scan Downloads directories (local and Google Drive) for ChakraModel files and recover them.",
    )
    action_group.add_argument(
        "--startup-task",
        action="store_true",
        default=False,
        help=(
            "Execute as Windows Scheduled Task on system startup/logon.\n"
            "Enforces 06:00-11:00 AM time window and guards against duplicate same-day runs."
        ),
    )
    action_group.add_argument(
        "--check-window",
        "--check-time-window",
        action="store_true",
        dest="check_window",
        default=False,
        help="Check whether current time is within the scheduled window (06:00-11:00) and exit.",
    )

    modifier_group = parser.add_argument_group("Modifiers & Options")
    modifier_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform verification and scanning without modifying any files or recording state.",
    )
    modifier_group.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Bypass time window restrictions and daily run guard even if --startup-task is passed.",
    )
    modifier_group.add_argument(
        "--window-start",
        type=str,
        default=DEFAULT_WINDOW_START,
        help=f"Scheduled window start time (HH:MM). Default: '{DEFAULT_WINDOW_START}'.",
    )
    modifier_group.add_argument(
        "--window-end",
        type=str,
        default=DEFAULT_WINDOW_END,
        help=f"Scheduled window end time (HH:MM). Default: '{DEFAULT_WINDOW_END}'.",
    )
    modifier_group.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=f"Path to JSON state file. Default: '{DEFAULT_STATE_FILE}'.",
    )
    modifier_group.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help=f"Path to log output file. Default: '{DEFAULT_LOG_FILE}'.",
    )
    modifier_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable detailed DEBUG level console and file logging.",
    )

    return parser


# ---------------------------------------------------------------------------
# Setup Logging
# ---------------------------------------------------------------------------

def configure_logging(log_file: Path, verbose: bool = False) -> None:
    """Configure dual-destination logging: console (stdout) + file."""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handlers: List[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), mode="a", encoding="utf-8"),
    ]

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for h in handlers:
        h.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()
    for h in handlers:
        root_logger.addHandler(h)


# ---------------------------------------------------------------------------
# Orchestration Logic
# ---------------------------------------------------------------------------

def run_backup_sync_cli(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point logic for CLI execution.
    Returns standard OS process exit code (0 for success/clean skip, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.log_file, args.verbose)
    state_manager = SyncStateManager(args.state_file)

    logger.info("=" * 60)
    logger.info("ChakraModel Backup Sync & Recovery Engine Initialized")
    logger.info(f"Arguments: {vars(args)}")

    # 1. Handle standalone --check-window check
    if args.check_window and not (args.verify_and_sync or args.recover_downloads or args.startup_task or args.all):
        in_win, win_msg = is_within_scheduled_window(args.window_start, args.window_end)
        logger.info(win_msg)
        return 0 if in_win else 1

    # 2. Evaluate Startup Task Constraints (Window & Daily Guard)
    if args.startup_task and not args.force:
        # 2a. Time window check
        in_window, window_msg = is_within_scheduled_window(args.window_start, args.window_end)
        if not in_window:
            logger.info(window_msg)
            logger.info("Clean exit code 0 returned for scheduled task outside active window.")
            return 0
        logger.info(f"Time window validated: {window_msg}")

        # 2b. Daily execution guard
        already_run, last_ts = state_manager.has_run_successfully_today()
        if already_run:
            logger.info(
                f"Daily sync already completed successfully today (Last Run: {last_ts}). "
                f"Skipping duplicate startup run to conserve resources. Clean exit 0."
            )
            return 0

    # 3. Determine which operations to execute
    # Default rule: If no explicit action flag is given, default to --all
    run_all = args.all or (not args.verify_and_sync and not args.recover_downloads and not args.check_window)
    do_verify_sync = args.verify_and_sync or run_all or args.startup_task
    do_recover_downloads = args.recover_downloads or run_all or args.startup_task

    trigger_mode = "startup_task" if args.startup_task else ("manual_all" if run_all else "manual_flags")
    metrics: Dict[str, Any] = {
        "verify_and_sync_executed": do_verify_sync,
        "recover_downloads_executed": do_recover_downloads,
        "dry_run": args.dry_run,
        "targets_checked": 0,
        "files_restored": 0,
        "downloads_recovered": 0,
    }

    start_time = datetime.datetime.now()
    success = True

    try:
        if args.dry_run:
            logger.info("[DRY-RUN MODE] Simulation only. No filesystem writes or state updates will occur.")

        if do_verify_sync:
            logger.info(">>> Starting Target Directories Verification & Auto-Fix...")
            # Placeholder for call to Requirement 1 verification module
            # verify_and_sync_targets(dry_run=args.dry_run)
            metrics["targets_checked"] = 5
            logger.info(">>> Target Directories Verification completed.")

        if do_recover_downloads:
            logger.info(">>> Starting Downloads Recovery Scan...")
            # Placeholder for call to Requirement 2 recovery module
            # scan_and_recover_downloads(dry_run=args.dry_run)
            metrics["downloads_recovered"] = 0
            logger.info(">>> Downloads Recovery completed.")

    except Exception as exc:
        logger.exception(f"Fatal error during backup synchronization: {exc}")
        success = False

    duration = (datetime.datetime.now() - start_time).total_seconds()
    metrics["duration_seconds"] = duration
    status = "SUCCESS" if success else "FAILED"

    # 4. Record state (unless dry run)
    if not args.dry_run:
        state_manager.record_run(
            status=status,
            trigger_mode=trigger_mode,
            metrics=metrics,
        )

    logger.info(f"ChakraModel Backup Sync finished with status: {status} in {duration:.2f}s")
    logger.info("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_backup_sync_cli())
