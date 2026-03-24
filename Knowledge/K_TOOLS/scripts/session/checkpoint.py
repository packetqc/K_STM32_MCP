#!/usr/bin/env python3
"""Checkpoint — session state persistence for crash/compaction recovery.

Adapted for Knowledge 2.0 multi-module architecture.
Uses a lightweight JSON checkpoint file alongside K_MIND memory
to survive session compaction, crash, and container restart.

The checkpoint records the current execution phase so that
on resume/recovery, Claude knows exactly where work was interrupted.

Usage:
  python3 checkpoint.py --status           # Show current state
  python3 checkpoint.py --write PHASE      # Write checkpoint
  python3 checkpoint.py --clear            # Clear checkpoint

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(SCRIPT_DIR))))
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, ".claude", "checkpoint.json")


def write_checkpoint(phase: str, description: str = "",
                     details: dict = None) -> bool:
    """Write a checkpoint for crash/compaction recovery.

    Phases:
      - "idle"          : no active work
      - "pre_execution" : about to execute a command
      - "executing"     : command is running
      - "completed"     : command finished successfully
      - "failed"        : command failed
      - "saving"        : session save in progress

    Args:
        phase: Current phase.
        description: What is being executed.
        details: Optional dict with extra context.

    Returns:
        True if checkpoint was written.
    """
    checkpoint = {
        "phase": phase,
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }

    try:
        os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
        with open(CHECKPOINT_PATH, "w") as f:
            json.dump(checkpoint, f, indent=2)
        return True
    except OSError:
        return False


def read_checkpoint() -> dict:
    """Read the current checkpoint state.

    Returns:
        Checkpoint dict, or empty dict if no checkpoint exists.
    """
    try:
        if os.path.exists(CHECKPOINT_PATH):
            with open(CHECKPOINT_PATH, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def clear_checkpoint() -> bool:
    """Clear the checkpoint file."""
    try:
        if os.path.exists(CHECKPOINT_PATH):
            os.remove(CHECKPOINT_PATH)
        return True
    except OSError:
        return False


def format_status(checkpoint: dict) -> str:
    """Format checkpoint status for display."""
    if not checkpoint:
        return "No active checkpoint."

    phase = checkpoint.get("phase", "unknown")
    desc = checkpoint.get("description", "")
    ts = checkpoint.get("timestamp", "")
    details = checkpoint.get("details", {})

    lines = [f"Checkpoint: {phase}"]
    if desc:
        lines.append(f"  Description: {desc}")
    if ts:
        lines.append(f"  Timestamp: {ts}")
    if details:
        for k, v in details.items():
            lines.append(f"  {k}: {v}")

    # Recovery advice based on phase
    if phase == "pre_execution":
        lines.append("  Recovery: Command was not started — safe to re-execute.")
    elif phase == "executing":
        lines.append("  Recovery: Command was in progress — check results before re-executing.")
    elif phase == "completed":
        lines.append("  Recovery: Command completed — verify results, then clear checkpoint.")
    elif phase == "failed":
        lines.append("  Recovery: Command failed — investigate error, then retry or clear.")
    elif phase == "saving":
        lines.append("  Recovery: Save was in progress — check git status, then resume save.")

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Session checkpoint management")
    parser.add_argument("--status", action="store_true",
                        help="Show current checkpoint state")
    parser.add_argument("--write", metavar="PHASE",
                        help="Write checkpoint (phase: idle, pre_execution, "
                             "executing, completed, failed, saving)")
    parser.add_argument("--description", "-d", default="",
                        help="Description for write mode")
    parser.add_argument("--clear", action="store_true",
                        help="Clear checkpoint")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()

    if args.write:
        ok = write_checkpoint(args.write, args.description)
        if ok:
            print(f"Checkpoint written: {args.write}")
        else:
            print("Failed to write checkpoint.")
            sys.exit(1)
    elif args.clear:
        ok = clear_checkpoint()
        print("Checkpoint cleared." if ok else "Failed to clear.")
    else:
        # Default: status
        checkpoint = read_checkpoint()
        if args.json:
            print(json.dumps(checkpoint, indent=2))
        else:
            print(format_status(checkpoint))


if __name__ == "__main__":
    import sys
    main()
