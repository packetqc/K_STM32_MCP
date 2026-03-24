#!/usr/bin/env python3
"""Session Notes — generate markdown notes from K_MIND memory.

Adapted for Knowledge 2.0 multi-module architecture.
Generates session notes markdown from K_MIND near/far memory
instead of legacy runtime cache. Notes feed the Session Viewer (I3).

Usage:
  python3 session_notes.py                      # Generate notes
  python3 session_notes.py --output-dir notes   # Custom output dir
  python3 session_notes.py --preview            # Preview without writing

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(SCRIPT_DIR))))
K_MIND_DIR = os.path.join(PROJECT_ROOT, "Knowledge", "K_MIND")
SESSIONS_DIR = os.path.join(K_MIND_DIR, "sessions")


def _get_current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL, text=True,
            cwd=PROJECT_ROOT
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _slugify(text: str, max_len: int = 60) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def generate_session_notes(output_dir: str = "notes") -> Optional[str]:
    """Generate session notes markdown from K_MIND memory.

    Reads near_memory summaries and far_memory content to produce
    a structured markdown notes file for the Session Viewer.

    Returns:
        Path to the generated markdown file, or None if no data.
    """
    # Load near_memory
    near_path = os.path.join(SESSIONS_DIR, "near_memory.json")
    try:
        with open(near_path, "r") as f:
            near_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        return None

    session_id = near_data.get("session_id", "unknown")
    summaries = near_data.get("summaries", [])
    if not summaries:
        return None

    # Determine date and branch
    branch = _get_current_branch()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Try to get first timestamp from summaries
    first_ts = summaries[0].get("timestamp", "") if summaries else ""
    if first_ts:
        date_str = first_ts[:10]

    # Build slug from branch
    slug = ""
    if branch:
        slug = branch.replace("claude/", "")
        slug = re.sub(r"-[A-Za-z0-9]{5}$", "", slug)
    if not slug:
        slug = f"session-{session_id[:8]}"

    # Load far_memory for tool usage stats
    far_path = os.path.join(SESSIONS_DIR, "far_memory.json")
    tool_stats = {}
    try:
        with open(far_path, "r") as f:
            far_data = json.load(f)
        for msg in far_data.get("messages", []):
            for tool in msg.get("tools", []):
                tool_name = tool.get("tool", "")
                if tool_name:
                    tool_stats[tool_name] = tool_stats.get(tool_name, 0) + 1
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        far_data = {}

    # Git stats
    try:
        diff_stat = subprocess.check_output(
            ["git", "diff", "--stat", "HEAD~10..HEAD"],
            stderr=subprocess.DEVNULL, cwd=PROJECT_ROOT
        ).decode().strip().splitlines()
        file_count = len(diff_stat) - 1 if diff_stat else 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        file_count = 0

    # Build markdown
    lines = []
    lines.append(f"# Session Notes — {date_str} — {slug}")
    lines.append("")

    # Context
    lines.append("## Context")
    lines.append(f"Session: `{session_id[:8]}`")
    lines.append(f"Branch: `{branch}`")
    lines.append(f"Date: {date_str}")
    lines.append("")

    # Activities (from near_memory summaries)
    lines.append("## Activities")
    lines.append("")
    for s in summaries:
        mind_refs = s.get("mind_memory_refs", [])
        refs_str = ""
        if mind_refs:
            refs_str = f" [{', '.join(str(r) for r in mind_refs[:3])}]"
        lines.append(f"- {s.get('summary', '')}{refs_str}")
    lines.append("")

    # Tool usage
    if tool_stats:
        lines.append("## Tool Usage")
        lines.append("")
        lines.append("| Tool | Count |")
        lines.append("|------|-------|")
        for tool, count in sorted(tool_stats.items(),
                                   key=lambda x: -x[1]):
            lines.append(f"| {tool} | {count} |")
        lines.append("")

    # Metrics
    lines.append("## Metrics")
    lines.append("")
    msg_count = len(far_data.get("messages", [])) if far_data else 0
    lines.append(f"- {len(summaries)} near_memory summaries")
    lines.append(f"- {msg_count} far_memory messages")
    lines.append(f"- ~{file_count} files modified")
    lines.append("")

    # Write file
    content = "\n".join(lines)
    abs_output = os.path.join(PROJECT_ROOT, output_dir)
    os.makedirs(abs_output, exist_ok=True)
    filename = f"session-{date_str}-{_slugify(slug)}.md"
    filepath = os.path.join(abs_output, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
    except OSError:
        return None


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate session notes from K_MIND memory")
    parser.add_argument("--output-dir", default="notes",
                        help="Output directory for notes")
    parser.add_argument("--preview", action="store_true",
                        help="Preview notes without writing")

    args = parser.parse_args()

    if args.preview:
        # Just show what would be generated
        near_path = os.path.join(SESSIONS_DIR, "near_memory.json")
        try:
            with open(near_path, "r") as f:
                data = json.load(f)
            summaries = data.get("summaries", [])
            print(f"Session: {data.get('session_id', '?')[:8]}")
            print(f"Summaries: {len(summaries)}")
            for s in summaries[-5:]:
                print(f"  - {s.get('summary', '')}")
        except (json.JSONDecodeError, FileNotFoundError):
            print("No near_memory data found.")
    else:
        path = generate_session_notes(output_dir=args.output_dir)
        if path:
            print(f"Notes generated: {path}")
        else:
            print("No session data to generate notes from.")


if __name__ == "__main__":
    main()
