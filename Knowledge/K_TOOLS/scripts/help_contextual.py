#!/usr/bin/env python3
"""Contextual help — extract help for a specific command from commands.md.

Usage:
  python3 scripts/help_contextual.py "harvest --list"
  python3 scripts/help_contextual.py "pub check"
  python3 scripts/help_contextual.py "visual"

Searches K_TOOLS/methodology/commands.md for the command in table rows
and section headers. Returns: matching table row(s), parent section,
and publication link if available.
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> K_TOOLS/
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
COMMANDS_PATH = os.path.join(MODULE_DIR, "methodology", "commands.md")

# Publication links per group
PUB_LINKS = {
    "Session Management": "session-management",
    "Harvest": "harvest-protocol",
    "Content Management": "documentation-generation",
    "Project Management": "project-management",
    "Live Session Analysis": "live-session-analysis",
    "Visuals": "visual-documentation",
    "Live Network": "live-knowledge-network",
    "normalize": "normalize-structure-concordance",
    "webcard": "webcards-social-sharing",
}


def find_section_for_line(lines, target_idx):
    """Walk backwards from target_idx to find the nearest ### header."""
    for i in range(target_idx, -1, -1):
        if lines[i].startswith("### "):
            return lines[i].lstrip("# ").strip()
    return None


def find_h2_for_line(lines, target_idx):
    """Walk backwards from target_idx to find the nearest ## header."""
    for i in range(target_idx, -1, -1):
        if lines[i].startswith("## ") and not lines[i].startswith("### "):
            return lines[i].lstrip("# ").strip()
    return None


def get_pub_link(section_name):
    """Get publication slug for a section."""
    if not section_name:
        return None
    for key, slug in PUB_LINKS.items():
        if key.lower() in section_name.lower():
            return slug
    return None


def search_command(query):
    """Search for a command in commands.md."""
    if not os.path.exists(COMMANDS_PATH):
        print(f"Error: {COMMANDS_PATH} not found", file=sys.stderr)
        return None

    with open(COMMANDS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    query_lower = query.lower().strip()

    # Build set of line indices that belong to command tables
    command_table_lines = set()
    for i, line in enumerate(lines):
        if "| Command |" in line and "|" in line:
            for j in range(i, len(lines)):
                if lines[j].strip() == "" or lines[j].startswith("#"):
                    break
                command_table_lines.add(j)

    # Strategy 1: exact match in command table rows only
    matches = []
    for i, line in enumerate(lines):
        if i not in command_table_lines:
            continue
        if "|" not in line or line.strip().startswith("|---"):
            continue
        backtick_match = re.findall(r"`([^`]+)`", line)
        for cmd in backtick_match:
            if cmd.lower() == query_lower or query_lower in cmd.lower():
                section = find_section_for_line(lines, i)
                h2 = find_h2_for_line(lines, i)
                matches.append({
                    "line": line.strip(),
                    "line_num": i + 1,
                    "section": section,
                    "h2": h2,
                    "exact": cmd.lower() == query_lower,
                })

    # Strategy 2: search in section headers
    section_matches = []
    for i, line in enumerate(lines):
        if line.startswith("### ") and query_lower in line.lower():
            section_lines = [line]
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    break
                section_lines.append(lines[j])
            section_matches.append({
                "header": line.lstrip("# ").strip(),
                "content": "\n".join(section_lines),
                "line_num": i + 1,
            })

    return {"table_matches": matches, "section_matches": section_matches}


def format_output(query, results):
    """Format the contextual help output as markdown."""
    if not results:
        return f"No help found for `{query}`."

    table_matches = results["table_matches"]
    section_matches = results["section_matches"]

    if not table_matches and not section_matches:
        return f"No help found for `{query}`. Try `help` for the full command list."

    out = []
    out.append(f"## `{query}` — Contextual Help\n")

    exact = [m for m in table_matches if m["exact"]]
    partial = [m for m in table_matches if not m["exact"]]

    if exact:
        out.append("| Command | What Claude Does |")
        out.append("|---------|-----------------|")
        for m in exact:
            out.append(m["line"])
        out.append("")

        section = exact[0].get("section", "")
        if section:
            out.append(f"**Group**: {section}")
            pub = get_pub_link(section)
            if pub:
                out.append(f"**Publication**: {pub}")
        out.append("")

    if partial and not exact:
        out.append("### Related commands\n")
        out.append("| Command | What Claude Does |")
        out.append("|---------|-----------------|")
        seen = set()
        for m in partial:
            if m["line"] not in seen:
                out.append(m["line"])
                seen.add(m["line"])
        out.append("")

    if section_matches:
        for sm in section_matches:
            out.append(f"\n### {sm['header']}\n")
            content_lines = sm["content"].split("\n")[1:]
            out.append("\n".join(content_lines).strip())
            out.append("")

    if partial and exact:
        out.append("\n### See also\n")
        seen = set()
        for m in partial:
            if m["line"] not in seen and m["line"] not in [e["line"] for e in exact]:
                backticks = re.findall(r"`([^`]+)`", m["line"])
                if backticks:
                    out.append(f"- `{backticks[0]}`")
                seen.add(m["line"])

    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/help_contextual.py <command>", file=sys.stderr)
        print('Example: python3 scripts/help_contextual.py "harvest --list"', file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = search_command(query)
    output = format_output(query, results)

    print(output)


if __name__ == "__main__":
    main()
