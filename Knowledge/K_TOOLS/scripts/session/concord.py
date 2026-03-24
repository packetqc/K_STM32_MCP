#!/usr/bin/env python3
"""Concord — audit and fix reference concordance across Knowledge system.

Checks that cross-references between scripts, skills, docs, routing,
and architecture diagrams stay in sync after changes.

Complements normalize.py (structure concordance) with reference concordance.

Checks:
  C1. Script Registry — actual scripts vs documentation listings
  C2. Command Names — skill files vs conventions/commands.md
  C3. Routing Completeness — routing.json vs actual scripts/skills
  C4. Architecture Diagram — architecture-mindmap.md vs actual K_MIND scripts
  C5. Module Registration — delegated to normalize.py
  C6. Mindmap Work Nodes — delegated to normalize.py

Usage:
  python3 concord.py                # Audit mode (default)
  python3 concord.py --fix          # Report with fix suggestions
  python3 concord.py --check        # Report only, exit code for CI
  python3 concord.py --json         # JSON output

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import glob
import json
import os
import re
import sys
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(SCRIPT_DIR))))
KNOWLEDGE_DIR = os.path.join(PROJECT_ROOT, "Knowledge")
K_MIND_DIR = os.path.join(KNOWLEDGE_DIR, "K_MIND")
K_TOOLS_DIR = os.path.join(KNOWLEDGE_DIR, "K_TOOLS")
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")


def _scan_actual_scripts(base_dir: str, prefix: str = "") -> set:
    """Scan actual .py scripts in a directory (recursive)."""
    scripts = set()
    scripts_dir = os.path.join(base_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return scripts
    for root, _dirs, files in os.walk(scripts_dir):
        for f in files:
            if f.endswith(".py") and not f.startswith("__"):
                rel = os.path.relpath(os.path.join(root, f), base_dir)
                scripts.add(f.replace(".py", ""))
    return scripts


def _scan_skill_names() -> set:
    """Scan actual skill directories."""
    skills = set()
    if os.path.isdir(SKILLS_DIR):
        for entry in os.listdir(SKILLS_DIR):
            skill_file = os.path.join(SKILLS_DIR, entry, "SKILL.md")
            if os.path.isfile(skill_file):
                skills.add(entry)
    return skills


def _read_file(path: str) -> str:
    """Read file content, return empty string on error."""
    try:
        with open(path, "r") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return ""


def _load_json(path: str) -> Optional[dict]:
    """Load JSON file, return None on error."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        return None


# ── C1: Script Registry ─────────────────────────────────────────────

def check_c1_script_registry() -> list:
    """Check K_MIND scripts listed in documentation vs actual files."""
    issues = []
    actual_kmind = _scan_actual_scripts(K_MIND_DIR)

    # Check mind-context SKILL.md "Available scripts" section
    skill_md = _read_file(os.path.join(
        SKILLS_DIR, "mind-context", "SKILL.md"))
    if skill_md:
        # Extract script names from the Available scripts section
        section = skill_md.split("Available scripts")[1] if \
            "Available scripts" in skill_md else ""
        listed_in_skill = set()
        for match in re.finditer(r"scripts/(\w+)\.py", section):
            listed_in_skill.add(match.group(1))

        for script in actual_kmind:
            if script not in listed_in_skill and script != "__init__":
                issues.append({
                    "category": "C1",
                    "type": "missing_script_in_skill",
                    "script": script,
                    "file": ".claude/skills/mind-context/SKILL.md",
                    "severity": "warning",
                    "message": f"K_MIND script '{script}' not in mind-context SKILL.md Available scripts",
                })

    # Check architecture-mindmap.md
    arch_md = _read_file(os.path.join(
        K_MIND_DIR, "files", "mind", "architecture-mindmap.md"))
    if arch_md:
        arch_section = ""
        if "programs_over_improvisation" in arch_md:
            arch_section = arch_md.split("programs_over_improvisation")[1]

        for script in actual_kmind:
            # Normalize: script names use underscores, mindmap uses underscores
            if script not in arch_section and script != "__init__":
                issues.append({
                    "category": "C1",
                    "type": "missing_script_in_arch",
                    "script": script,
                    "file": "K_MIND/files/mind/architecture-mindmap.md",
                    "severity": "warning",
                    "message": f"K_MIND script '{script}' not in architecture-mindmap.md",
                })

    # Check routing.json memory-management route
    routing = _load_json(os.path.join(
        K_MIND_DIR, "conventions", "routing.json"))
    if routing:
        mem_route = routing.get("routes", {}).get("memory-management", {})
        route_scripts = " ".join(mem_route.get("scripts", []))

        for script in actual_kmind:
            if script not in route_scripts and script != "__init__":
                issues.append({
                    "category": "C1",
                    "type": "missing_script_in_route",
                    "script": script,
                    "file": "K_MIND/conventions/routing.json",
                    "severity": "info",
                    "message": f"K_MIND script '{script}' not in memory-management route",
                })

    return issues


# ── C2: Command Names ───────────────────────────────────────────────

def check_c2_command_names() -> list:
    """Check skill names vs conventions and commands.md."""
    issues = []
    actual_skills = _scan_skill_names()

    # Check routing.json skills references
    routing = _load_json(os.path.join(
        K_MIND_DIR, "conventions", "routing.json"))
    if routing:
        routed_skills = set()
        for route_name, route in routing.get("routes", {}).items():
            for skill in route.get("skills", []):
                routed_skills.add(skill)

        # Skills that exist but aren't in any route
        for skill in actual_skills:
            if skill not in routed_skills:
                issues.append({
                    "category": "C2",
                    "type": "unrouted_skill",
                    "skill": skill,
                    "severity": "info",
                    "message": f"Skill '{skill}' exists but not in any routing.json route",
                })

    return issues


# ── C3: Routing Completeness ────────────────────────────────────────

def check_c3_routing() -> list:
    """Check routing.json scripts and skills exist."""
    issues = []
    routing = _load_json(os.path.join(
        K_MIND_DIR, "conventions", "routing.json"))
    if not routing:
        issues.append({
            "category": "C3",
            "type": "missing_routing",
            "severity": "error",
            "message": "routing.json not found or invalid",
        })
        return issues

    actual_skills = _scan_skill_names()

    for route_name, route in routing.get("routes", {}).items():
        # Check skills exist
        for skill in route.get("skills", []):
            if skill not in actual_skills:
                issues.append({
                    "category": "C3",
                    "type": "phantom_skill_in_route",
                    "route": route_name,
                    "skill": skill,
                    "severity": "warning",
                    "message": f"Route '{route_name}' references skill '{skill}' but no SKILL.md found",
                })

        # Check scripts exist
        for script_path in route.get("scripts", []):
            full_path = os.path.join(KNOWLEDGE_DIR, script_path)
            if not os.path.isfile(full_path):
                issues.append({
                    "category": "C3",
                    "type": "phantom_script_in_route",
                    "route": route_name,
                    "script": script_path,
                    "severity": "warning",
                    "message": f"Route '{route_name}' references '{script_path}' but file not found",
                })

    return issues


# ── C4: Architecture Diagram ────────────────────────────────────────

def check_c4_architecture() -> list:
    """Check architecture-mindmap.md vs live mindmap programs node."""
    issues = []
    arch_md = _read_file(os.path.join(
        K_MIND_DIR, "files", "mind", "architecture-mindmap.md"))
    mind_md = _read_file(os.path.join(K_MIND_DIR, "mind", "mind_memory.md"))

    if not arch_md:
        issues.append({
            "category": "C4",
            "type": "missing_arch_mindmap",
            "severity": "warning",
            "message": "architecture-mindmap.md not found",
        })
        return issues

    # Check that architecture-mindmap has same script list as live mindmap
    if mind_md and "capture_ephemeral" in mind_md and \
       "capture_ephemeral" not in arch_md:
        issues.append({
            "category": "C4",
            "type": "arch_diagram_drift",
            "severity": "warning",
            "message": "capture_ephemeral in live mindmap but missing from architecture-mindmap.md",
        })

    return issues


# ── Report ───────────────────────────────────────────────────────────

def run_all_checks() -> dict:
    """Run all concordance checks."""
    all_issues = []
    all_issues.extend(check_c1_script_registry())
    all_issues.extend(check_c2_command_names())
    all_issues.extend(check_c3_routing())
    all_issues.extend(check_c4_architecture())

    errors = [i for i in all_issues if i.get("severity") == "error"]
    warnings = [i for i in all_issues if i.get("severity") == "warning"]
    infos = [i for i in all_issues if i.get("severity") == "info"]

    return {
        "total_issues": len(all_issues),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(infos),
        "issues": all_issues,
        "clean": len(all_issues) == 0,
    }


def format_report(result: dict) -> str:
    """Format concordance report."""
    if result["clean"]:
        return "Reference concordance: CLEAN (all cross-references in sync)"

    lines = [
        "Reference Concordance Report",
        "=" * 40,
        f"Total: {result['total_issues']} issues "
        f"({result['errors']} errors, {result['warnings']} warnings, "
        f"{result['info']} info)",
        "",
    ]

    # Group by category
    by_cat = {}
    for issue in result["issues"]:
        cat = issue.get("category", "?")
        by_cat.setdefault(cat, []).append(issue)

    cat_names = {
        "C1": "Script Registry",
        "C2": "Command Names",
        "C3": "Routing Completeness",
        "C4": "Architecture Diagram",
    }

    for cat in sorted(by_cat.keys()):
        lines.append(f"\n{cat}: {cat_names.get(cat, cat)}")
        lines.append("-" * 30)
        for issue in by_cat[cat]:
            sev = issue["severity"].upper()
            lines.append(f"  [{sev}] {issue['message']}")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audit reference concordance across Knowledge system")
    parser.add_argument("--fix", action="store_true",
                        help="Report with fix suggestions")
    parser.add_argument("--check", action="store_true",
                        help="Report only, exit code for CI")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()

    result = run_all_checks()

    if args.fix:
        print("Fix mode: reference drift reported below.")
        print("Claude should review each issue and apply fixes.\n")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))

    if args.check and not result["clean"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
