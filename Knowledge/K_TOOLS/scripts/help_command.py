#!/usr/bin/env python3
"""Multipart help — print knowledge commands + project-specific commands (concatenated).

Reads Part 1 from K_TOOLS/methodology/commands.md and outputs the command tables.
Part 2 is project-specific and would come from the active project's CLAUDE.md.

Output is printed to stdout for Claude to display.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> K_TOOLS/
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
COMMANDS_PATH = os.path.join(MODULE_DIR, "methodology", "commands.md")


def main():
    if not os.path.exists(COMMANDS_PATH):
        print(f"Error: commands file not found: {COMMANDS_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(COMMANDS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Collect command tables (Part 1) — stop before Full Details sections
    output_lines = []
    for line in lines:
        if line.startswith("## Live Session — Full Details"):
            break
        output_lines.append(line)

    content = "".join(output_lines)

    # Print to stdout
    print(content, end="")
    sys.exit(0)


if __name__ == "__main__":
    main()
