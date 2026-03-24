#!/usr/bin/env python3
"""Save Session — pre-save summary + commit + push + PR workflow.

Adapted for Knowledge 2.0 multi-module architecture.
Uses K_MIND memory system for session data compilation instead
of the legacy runtime cache.

The save protocol:
  1. Compile pre-save summary from K_MIND near/far memory + git stats
  2. Commit all pending changes
  3. Push to branch
  4. Create PR to default branch
  5. Optionally merge PR (if elevated)

Usage:
  python3 save_session.py --summary          # Compile pre-save summary
  python3 save_session.py --save             # Full save protocol
  python3 save_session.py --save --merge     # Save + merge PR
  python3 save_session.py --repo packetqc/K_DOCS

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(SCRIPT_DIR))))
K_MIND_DIR = os.path.join(PROJECT_ROOT, "Knowledge", "K_MIND")
SESSIONS_DIR = os.path.join(K_MIND_DIR, "sessions")


def _get_gh_helper():
    """Get GitHubHelper instance if GH_TOKEN is available."""
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        return None
    try:
        gh_path = os.path.join(K_MIND_DIR, "scripts")
        if gh_path not in sys.path:
            sys.path.insert(0, gh_path)
        from gh_helper import GitHubHelper
        return GitHubHelper()
    except ImportError:
        return None


def _get_current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True,
            cwd=PROJECT_ROOT
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _get_default_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "show", "origin"],
            capture_output=True, text=True, timeout=15,
            cwd=PROJECT_ROOT
        )
        for line in result.stdout.splitlines():
            if "HEAD branch" in line:
                return line.split(":")[-1].strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return "main"


def compile_pre_save_summary(default_branch: str = "") -> str:
    """Compile pre-save summary from K_MIND memory + git stats.

    Generates: resume, metrics, near_memory highlights, time, deliveries.
    """
    if not default_branch:
        default_branch = _get_default_branch()

    # Git metrics
    try:
        changed_files = subprocess.check_output(
            ["git", "diff", "--name-only", f"origin/{default_branch}...HEAD"],
            stderr=subprocess.DEVNULL, cwd=PROJECT_ROOT
        ).decode().strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        changed_files = []

    try:
        commit_count = subprocess.check_output(
            ["git", "rev-list", "--count", f"origin/{default_branch}..HEAD"],
            stderr=subprocess.DEVNULL, cwd=PROJECT_ROOT
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit_count = "?"

    # K_MIND near_memory summaries
    near_summaries = []
    try:
        near_path = os.path.join(SESSIONS_DIR, "near_memory.json")
        with open(near_path, "r") as f:
            near_data = json.load(f)
        session_id = near_data.get("session_id", "?")
        for s in near_data.get("summaries", []):
            near_summaries.append(s.get("summary", ""))
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        session_id = "?"

    # K_MIND mindmap work nodes
    work_items = []
    try:
        mind_path = os.path.join(K_MIND_DIR, "mind", "mind_memory.md")
        with open(mind_path, "r") as f:
            in_work = False
            for line in f:
                stripped = line.strip()
                if "en cours" in stripped.lower():
                    in_work = True
                    continue
                if in_work and stripped and not stripped.startswith("```"):
                    if any(stripped.startswith(c) for c in
                           ["validation", "approbation", "documentation",
                            "conventions", "session", "architecture",
                            "constraints"]):
                        in_work = False
                        continue
                    work_items.append(stripped)
    except (FileNotFoundError, IOError):
        pass

    # Build summary
    sections = []

    sections.append("## Resume")
    sections.append(f"Session `{session_id[:8]}` — "
                    f"{len(near_summaries)} activities recorded in K_MIND.")
    if near_summaries:
        sections.append("")
        for s in near_summaries[-5:]:  # Last 5 summaries
            sections.append(f"- {s}")
    sections.append("")

    sections.append("## Metriques")
    sections.append("| Metrique | Valeur |")
    sections.append("|----------|--------|")
    sections.append(f"| Fichiers modifies | {len(changed_files)} |")
    sections.append(f"| Commits | {commit_count} |")
    sections.append(f"| Near memory entries | {len(near_summaries)} |")
    sections.append("")

    if work_items:
        sections.append("## En Cours (mindmap)")
        for item in work_items[:10]:
            sections.append(f"- {item}")
        sections.append("")

    if changed_files:
        sections.append("## Fichiers modifies")
        for f in changed_files[:20]:
            sections.append(f"- {f}")
        if len(changed_files) > 20:
            sections.append(f"- ... and {len(changed_files) - 20} more")
        sections.append("")

    sections.append("## Auto-evaluation")
    sections.append("| Critere | Conforme |")
    sections.append("|---------|----------|")
    has_token = bool(os.environ.get("GH_TOKEN", ""))
    sections.append(
        f"| GH_TOKEN elevated | {'Oui' if has_token else 'Non'} |")
    sections.append(
        f"| K_MIND maintained | {'Oui' if near_summaries else 'Non'} |")
    sections.append(
        f"| Work items tracked | {'Oui' if work_items else 'Non'} |")

    return "\n".join(sections)


def save_session(
    branch: str = "",
    default_branch: str = "",
    repo: str = "packetqc/K_DOCS",
    merge: bool = False,
    commit_message: str = "",
) -> dict:
    """Execute the save protocol.

    Steps:
      1. Compile pre-save summary
      2. Commit pending changes
      3. Push to branch
      4. Create PR
      5. Merge (if requested and elevated)
    """
    if not branch:
        branch = _get_current_branch()
    if not default_branch:
        default_branch = _get_default_branch()

    results = {
        "summary_compiled": False,
        "committed": False,
        "pushed": False,
        "pr_number": None,
        "merged": False,
        "errors": [],
    }

    # Step 1: Compile summary
    summary = compile_pre_save_summary(default_branch)
    results["summary_compiled"] = True
    results["summary"] = summary

    # Step 2: Commit
    if not commit_message:
        commit_message = f"save: session save — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    try:
        subprocess.run(
            ["git", "add", "-A"],
            check=True, capture_output=True, cwd=PROJECT_ROOT
        )
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True, cwd=PROJECT_ROOT
        )
        results["committed"] = result.returncode == 0
    except Exception as e:
        results["errors"].append(f"Commit failed: {e}")

    # Step 3: Push
    if branch:
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                capture_output=True, timeout=30, cwd=PROJECT_ROOT
            )
            results["pushed"] = result.returncode == 0
            if result.returncode != 0:
                results["errors"].append(
                    f"Push failed: {result.stderr.decode().strip()}")
        except Exception as e:
            results["errors"].append(f"Push failed: {e}")

    # Step 4+5: Create PR and optionally merge
    if branch and repo:
        gh = _get_gh_helper()
        if gh:
            try:
                pr_title = f"Session save — {branch}"
                pr_body = f"Pre-save summary:\n\n{summary[:3000]}"
                if merge:
                    pr_result = gh.pr_create_and_merge(
                        repo, branch, default_branch,
                        pr_title, body=pr_body
                    )
                    results["pr_number"] = pr_result.get("number")
                    results["merged"] = pr_result.get("merged", False)
                else:
                    pr_result = gh.pr_create(
                        repo, branch, default_branch,
                        pr_title, body=pr_body
                    )
                    results["pr_number"] = pr_result.get("number")
            except Exception as e:
                results["errors"].append(f"PR failed: {e}")
        else:
            results["errors"].append("No GH_TOKEN — cannot create PR")

    return results


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Session save protocol")
    parser.add_argument("--summary", action="store_true",
                        help="Compile pre-save summary only")
    parser.add_argument("--save", action="store_true",
                        help="Full save protocol")
    parser.add_argument("--merge", action="store_true",
                        help="Merge PR after creation")
    parser.add_argument("--repo", default="packetqc/K_DOCS")
    parser.add_argument("--message", "-m", default="",
                        help="Custom commit message")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()

    if args.summary:
        print(compile_pre_save_summary())
    elif args.save:
        result = save_session(
            repo=args.repo, merge=args.merge,
            commit_message=args.message
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Committed: {result['committed']}")
            print(f"Pushed: {result['pushed']}")
            if result['pr_number']:
                print(f"PR: #{result['pr_number']}")
            if result['merged']:
                print("Merged: Yes")
            if result['errors']:
                print(f"Errors: {'; '.join(result['errors'])}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
