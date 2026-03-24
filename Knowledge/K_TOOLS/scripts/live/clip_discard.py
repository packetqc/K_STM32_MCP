#!/usr/bin/env python3
"""
Clip Discard — Live Session Clip Lifecycle Manager
===================================================
Manages the discard/capture lifecycle for live-session clips.

When Claude is NOT actively monitoring (discussion, planning, interaction),
clips must be actively deleted from:
  1. Local live/dynamic/ folder
  2. Git-tracked files on the current branch
  3. Remote default branch (via commit + push or PR)

This prevents clip accumulation that wastes git space, context window,
and processing time during non-capture phases.

Usage:
    python3 live/clip_discard.py --discard          # Delete all clips everywhere
    python3 live/clip_discard.py --discard --local   # Local only (no git ops)
    python3 live/clip_discard.py --status            # Report clip state
    python3 live/clip_discard.py --discard --branch main  # Also clean a specific branch

Designed to be called by Claude Code during live-session mode transitions.
"""

import argparse
import os
import subprocess
import sys
import json
import shutil
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DYNAMIC_DIR = os.path.join(SCRIPT_DIR, "dynamic")

CLIP_PATTERNS = ["clip_*.mp4", "uart_*.mp4", "cam_*.mp4"]
CLIP_EXTENSIONS = (".mp4",)

# Threshold in seconds — if the newest clip commit on main is younger than
# this, the capture script is probably still running.
CAPTURE_ACTIVE_THRESHOLD = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _git(*args, cwd=None, timeout=15):
    """Run a git command and return (returncode, stdout, stderr)."""
    cmd = ["git"] + list(args)
    try:
        result = subprocess.run(
            cmd, cwd=cwd or REPO_ROOT,
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def _detect_default_branch():
    """Detect the remote default branch (main or master)."""
    rc, out, _ = _git("remote", "show", "origin")
    if rc == 0:
        for line in out.split("\n"):
            if "HEAD branch" in line:
                return line.split(":")[-1].strip()
    # Fallback: try main, then master
    rc, _, _ = _git("rev-parse", "--verify", "origin/main")
    if rc == 0:
        return "main"
    return "master"


def _current_branch():
    """Get current branch name."""
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "HEAD")
    return out if rc == 0 else None


def _find_local_clips():
    """Find all clip files in live/dynamic/."""
    clips = []
    if not os.path.isdir(DYNAMIC_DIR):
        return clips
    for f in os.listdir(DYNAMIC_DIR):
        if f.endswith(CLIP_EXTENSIONS) and not f.startswith("."):
            clips.append(os.path.join(DYNAMIC_DIR, f))
    return sorted(clips)


def _find_tracked_clips():
    """Find clip files tracked by git in live/dynamic/."""
    rc, out, _ = _git("ls-files", "live/dynamic/")
    if rc != 0 or not out:
        return []
    return [f for f in out.split("\n") if f.endswith(CLIP_EXTENSIONS)]


def _find_remote_clips(branch):
    """Find clip files on a remote branch."""
    rc, out, _ = _git("ls-tree", "-r", "--name-only", f"origin/{branch}", "live/dynamic/")
    if rc != 0 or not out:
        return []
    return [f for f in out.split("\n") if f.endswith(CLIP_EXTENSIONS)]


def _is_capture_active(branch=None):
    """Detect if the capture script is actively pushing clips.

    Checks the age of the last clip-related commit on the branch.
    If < CAPTURE_ACTIVE_THRESHOLD seconds old, capture is likely running.
    Returns (active: bool, age_seconds: int or None, last_msg: str or None).
    """
    if not branch:
        branch = _detect_default_branch()
    # Fetch latest state
    _git("fetch", "origin", branch, timeout=15)
    # Get the timestamp of the last commit that touched live/dynamic/
    rc, out, _ = _git(
        "log", f"origin/{branch}", "-1", "--format=%ct|%s",
        "--", "live/dynamic/"
    )
    if rc != 0 or not out or "|" not in out:
        return False, None, None
    parts = out.split("|", 1)
    commit_ts = int(parts[0])
    commit_msg = parts[1]
    import time
    age = int(time.time() - commit_ts)
    return age < CAPTURE_ACTIVE_THRESHOLD, age, commit_msg


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def clip_status():
    """Report the current state of clips across local, tracked, and remote."""
    local_clips = _find_local_clips()
    tracked_clips = _find_tracked_clips()
    default_branch = _detect_default_branch()
    current = _current_branch()

    # Remote clips on default branch
    remote_default_clips = _find_remote_clips(default_branch)

    # Remote clips on current branch (if different from default)
    remote_current_clips = []
    if current and current != default_branch:
        remote_current_clips = _find_remote_clips(current)

    total_local_size = sum(
        os.path.getsize(f) for f in local_clips
    ) if local_clips else 0

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "current_branch": current,
        "default_branch": default_branch,
        "local": {
            "count": len(local_clips),
            "files": [os.path.basename(f) for f in local_clips],
            "total_size_kb": round(total_local_size / 1024, 1)
        },
        "tracked": {
            "count": len(tracked_clips),
            "files": tracked_clips
        },
        "remote_default": {
            "branch": default_branch,
            "count": len(remote_default_clips),
            "files": remote_default_clips
        },
        "remote_current": {
            "branch": current,
            "count": len(remote_current_clips),
            "files": remote_current_clips
        }
    }
    return report


def print_status(report):
    """Print a human-readable status report."""
    print("=== Clip Status ===")
    print(f"  Branch: {report['current_branch']} (default: {report['default_branch']})")
    print()
    print(f"  Local (live/dynamic/):  {report['local']['count']} clips "
          f"({report['local']['total_size_kb']} KB)")
    for f in report['local']['files']:
        print(f"    - {f}")
    print()
    print(f"  Git-tracked:            {report['tracked']['count']} clips")
    for f in report['tracked']['files']:
        print(f"    - {f}")
    print()
    print(f"  Remote ({report['remote_default']['branch']}):  "
          f"{report['remote_default']['count']} clips")
    for f in report['remote_default']['files']:
        print(f"    - {f}")
    if report['remote_current']['branch'] != report['remote_default']['branch']:
        print(f"  Remote ({report['remote_current']['branch']}):  "
              f"{report['remote_current']['count']} clips")
        for f in report['remote_current']['files']:
            print(f"    - {f}")

    total = (report['local']['count'] + report['remote_default']['count']
             + report['remote_current']['count'])
    if total == 0:
        print("\n  ✅ Clean — no clips anywhere")
    else:
        print(f"\n  ⚠️  {total} clip(s) found — run --discard to clean up")


# ---------------------------------------------------------------------------
# Discard
# ---------------------------------------------------------------------------
def discard_local():
    """Delete all clip files from live/dynamic/ locally."""
    clips = _find_local_clips()
    if not clips:
        print("[DISCARD] No local clips to delete")
        return 0
    count = 0
    for clip_path in clips:
        try:
            os.remove(clip_path)
            print(f"[DISCARD] Deleted local: {os.path.basename(clip_path)}")
            count += 1
        except OSError as e:
            print(f"[DISCARD] Error deleting {clip_path}: {e}")
    return count


def discard_tracked():
    """Remove git-tracked clips and commit the removal."""
    tracked = _find_tracked_clips()
    if not tracked:
        print("[DISCARD] No tracked clips in git")
        return 0

    # git rm the tracked clips
    for f in tracked:
        rc, _, err = _git("rm", "-f", f)
        if rc != 0:
            print(f"[DISCARD] git rm failed for {f}: {err}")
        else:
            print(f"[DISCARD] git rm: {f}")

    # Commit the removal
    rc, out, err = _git("commit", "-m", "live: discard clips (cleanup)")
    if rc != 0:
        if "nothing to commit" in (out + err):
            print("[DISCARD] Nothing to commit after git rm")
            return 0
        print(f"[DISCARD] Commit failed: {err}")
        return 0

    print(f"[DISCARD] Committed clip removal")
    return len(tracked)


def discard_push(branch=None):
    """Push the discard commit to the remote branch."""
    if not branch:
        branch = _current_branch()
    if not branch:
        print("[DISCARD] Cannot determine branch for push")
        return False

    for attempt in range(4):
        rc, _, err = _git("push", "-u", "origin", branch, timeout=30)
        if rc == 0:
            print(f"[DISCARD] Pushed to origin/{branch}")
            return True
        if attempt < 3:
            import time
            wait = 2 ** attempt
            print(f"[DISCARD] Push failed, retrying in {wait}s... ({err[:80]})")
            time.sleep(wait)

    print(f"[DISCARD] Push failed after 4 retries")
    return False


def discard_remote_branch(branch):
    """Remove clips from a specific remote branch.

    Fetches the branch, checks out a temporary state, removes clips,
    commits, and pushes. Only works if we have push access to that branch.
    For the default branch, this typically requires a PR.
    """
    remote_clips = _find_remote_clips(branch)
    if not remote_clips:
        print(f"[DISCARD] No clips on remote {branch}")
        return 0

    current = _current_branch()
    print(f"[DISCARD] Found {len(remote_clips)} clip(s) on origin/{branch}")

    # We can only push to our assigned claude/* branch.
    # For the default branch, we report what needs cleanup.
    # The caller (Claude) can create a PR if elevated.
    print(f"[DISCARD] Clips on origin/{branch}:")
    for f in remote_clips:
        print(f"  - {f}")
    print(f"[DISCARD] Note: cleanup of {branch} requires PR merge access")

    return len(remote_clips)


def discard_all(local_only=False, target_branch=None, wait=False,
                wait_timeout=120, wait_interval=10):
    """Full discard — delete clips from all locations.

    If wait=True and capture is active, polls until capture stops
    (no new clip commits within CAPTURE_ACTIVE_THRESHOLD), then cleans.

    Returns a summary dict with counts of what was cleaned.
    """
    summary = {
        "local_deleted": 0,
        "tracked_removed": 0,
        "pushed": False,
        "remote_clips": 0,
        "remote_branch": None,
        "capture_was_active": False,
        "waited_seconds": 0
    }

    # 0. Check if capture is active
    default_branch = _detect_default_branch()
    active, age, msg = _is_capture_active(default_branch)
    summary["capture_was_active"] = active

    if active:
        if wait:
            import time
            print(f"[DISCARD] Capture active (last clip commit {age}s ago)")
            print(f"[DISCARD] Waiting for capture to stop (timeout {wait_timeout}s)...")
            elapsed = 0
            while elapsed < wait_timeout:
                time.sleep(wait_interval)
                elapsed += wait_interval
                active, age, _ = _is_capture_active(default_branch)
                if not active:
                    print(f"[DISCARD] Capture stopped (last commit {age}s ago)")
                    break
                print(f"[DISCARD] Still active ({age}s ago) — waiting... "
                      f"({elapsed}/{wait_timeout}s)")
            summary["waited_seconds"] = elapsed
            if active:
                print(f"[DISCARD] Timeout — capture still active after {wait_timeout}s")
                print(f"[DISCARD] Cleaning local + branch only, main will need manual cleanup")
        else:
            print(f"[DISCARD] ⚠️  Capture appears active (last clip commit {age}s ago)")
            print(f"[DISCARD] Main branch cleanup will race with capture script")
            print(f"[DISCARD] Tip: Ctrl+C the capture script first, or use --wait")

    # 1. Local files
    summary["local_deleted"] = discard_local()

    if local_only:
        return summary

    # 2. Git-tracked clips
    summary["tracked_removed"] = discard_tracked()

    # 3. Push if we removed tracked clips
    if summary["tracked_removed"] > 0:
        summary["pushed"] = discard_push()

    # 4. Check remote default branch
    summary["remote_branch"] = default_branch
    summary["remote_clips"] = discard_remote_branch(default_branch)

    # 5. Also check a specific target branch if requested
    if target_branch and target_branch != default_branch:
        extra = discard_remote_branch(target_branch)
        summary["remote_clips"] += extra

    return summary


def print_summary(summary):
    """Print a human-readable discard summary."""
    print()
    print("=== Discard Summary ===")
    if summary.get("capture_was_active"):
        if summary.get("waited_seconds", 0) > 0:
            print(f"  Capture was active:      waited {summary['waited_seconds']}s")
        else:
            print(f"  Capture was active:      ⚠️  race condition possible")
    print(f"  Local clips deleted:     {summary['local_deleted']}")
    print(f"  Tracked clips removed:   {summary['tracked_removed']}")
    print(f"  Pushed to remote:        {'✅' if summary['pushed'] else '—'}")
    if summary['remote_clips'] > 0:
        print(f"  Clips on {summary['remote_branch']}:  "
              f"{summary['remote_clips']} (requires PR to clean)")
    else:
        print(f"  Remote ({summary.get('remote_branch', '?')}):  ✅ clean")

    total_cleaned = summary['local_deleted'] + summary['tracked_removed']
    if total_cleaned == 0 and summary['remote_clips'] == 0:
        print("\n  ✅ Already clean — no clips found anywhere")
    elif summary['remote_clips'] > 0:
        print(f"\n  ⚠️  {summary['remote_clips']} clip(s) remain on remote "
              f"— need PR merge to clean")
    else:
        print(f"\n  ✅ Cleaned {total_cleaned} clip(s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Clip Discard — Live Session Clip Lifecycle Manager")
    parser.add_argument("--discard", action="store_true",
                        help="Delete all clips (local + git + remote check)")
    parser.add_argument("--local", action="store_true",
                        help="Local only — no git operations")
    parser.add_argument("--status", action="store_true",
                        help="Report clip state across all locations")
    parser.add_argument("--branch", type=str, default=None,
                        help="Additional branch to check/clean")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for capture to stop before cleaning main")
    parser.add_argument("--wait-timeout", type=int, default=120,
                        help="Max seconds to wait for capture to stop (default: 120)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON (for programmatic use)")
    args = parser.parse_args()

    if args.status:
        report = clip_status()
        # Add capture activity to status
        active, age, msg = _is_capture_active()
        report["capture_active"] = active
        report["capture_last_commit_age"] = age
        report["capture_last_commit_msg"] = msg
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_status(report)
            if active:
                print(f"\n  📡 Capture ACTIVE (last clip commit {age}s ago)")
            elif age is not None:
                print(f"\n  ⏸️  Capture idle (last clip commit {age}s ago)")
    elif args.discard:
        summary = discard_all(
            local_only=args.local,
            target_branch=args.branch,
            wait=args.wait,
            wait_timeout=args.wait_timeout
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print_summary(summary)
    else:
        # Default: show status
        report = clip_status()
        print_status(report)
        print()
        print("Run with --discard to clean up, or --status for JSON report")


if __name__ == "__main__":
    main()
