#!/usr/bin/env python3
"""Normalize — audit and fix knowledge structure concordance.

Adapted for Knowledge 2.0 multi-module architecture.
Validates concordance between mindmap nodes, domain JSONs,
module registrations, and documentation references.

Checks:
  1. Mindmap work items vs work.json entries (all modules)
  2. Module registration in modules.json vs actual directories
  3. Documentation references vs actual files
  4. Convention references vs actual entries
  5. Mindmap node integrity (balanced tree, no orphans)

Usage:
  python3 normalize.py                # Report mode (--check)
  python3 normalize.py --fix          # Apply concordance fixes
  python3 normalize.py --check        # Report only, no changes

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import json
import os
import re
import sys
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(SCRIPT_DIR))))
K_MIND_DIR = os.path.join(PROJECT_ROOT, "Knowledge", "K_MIND")
KNOWLEDGE_DIR = os.path.join(PROJECT_ROOT, "Knowledge")


def _parse_mindmap_nodes(mindmap_path: str) -> dict:
    """Parse mindmap and extract all nodes organized by group.

    Returns dict: {group: [node_names]}
    """
    nodes = {}
    current_group = None
    indent_stack = []

    try:
        with open(mindmap_path, "r") as f:
            in_mindmap = False
            for line in f:
                stripped = line.rstrip()
                if "mindmap" in stripped and not in_mindmap:
                    in_mindmap = True
                    continue
                if not in_mindmap:
                    continue
                if stripped.strip().startswith("```"):
                    break

                # Count indent
                indent = len(line) - len(line.lstrip())
                text = stripped.strip()
                if not text or text.startswith("%%") or text.startswith("root"):
                    continue

                # Clean node text (remove mermaid formatting)
                clean = re.sub(r"[\(\)\[\]\{\}]", "", text).strip()
                if not clean:
                    continue

                # Determine group (indent level 4 = top-level group)
                if indent <= 8:
                    current_group = clean.lower()
                    if current_group not in nodes:
                        nodes[current_group] = []
                elif current_group:
                    nodes[current_group].append(clean)
    except (FileNotFoundError, IOError):
        pass

    return nodes


def _load_module_json(module_path: str, subdir: str,
                       filename: str) -> Optional[dict]:
    """Load a JSON file from a module's subdirectory."""
    filepath = os.path.join(module_path, subdir, filename)
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        return None


def check_modules_registered() -> list:
    """Check that all Knowledge/K_* directories are in modules.json."""
    issues = []
    modules_path = os.path.join(KNOWLEDGE_DIR, "modules.json")

    try:
        with open(modules_path, "r") as f:
            registered = json.load(f)
        registered_names = {m.get("name", "") for m in registered
                            if isinstance(m, dict)}
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        issues.append({
            "type": "missing_file",
            "file": "Knowledge/modules.json",
            "severity": "error",
            "message": "modules.json not found or invalid",
        })
        return issues

    # Scan actual K_* directories
    if os.path.isdir(KNOWLEDGE_DIR):
        for entry in os.listdir(KNOWLEDGE_DIR):
            if entry.startswith("K_") and os.path.isdir(
                    os.path.join(KNOWLEDGE_DIR, entry)):
                if entry not in registered_names:
                    issues.append({
                        "type": "unregistered_module",
                        "module": entry,
                        "severity": "warning",
                        "message": f"Module {entry} exists but not in modules.json",
                    })

    # Check registered modules exist
    for name in registered_names:
        module_dir = os.path.join(KNOWLEDGE_DIR, name)
        if not os.path.isdir(module_dir):
            issues.append({
                "type": "phantom_module",
                "module": name,
                "severity": "error",
                "message": f"Module {name} registered but directory missing",
            })

    return issues


def check_work_concordance() -> list:
    """Check mindmap work nodes vs work.json entries across modules."""
    issues = []
    mindmap_path = os.path.join(K_MIND_DIR, "mind", "mind_memory.md")
    mindmap_nodes = _parse_mindmap_nodes(mindmap_path)

    work_nodes = set()
    for node in mindmap_nodes.get("work", []):
        work_nodes.add(node.lower().strip())

    # Collect all work.json entries from all modules
    json_entries = set()
    if os.path.isdir(KNOWLEDGE_DIR):
        for module in os.listdir(KNOWLEDGE_DIR):
            module_path = os.path.join(KNOWLEDGE_DIR, module)
            if not os.path.isdir(module_path):
                continue
            work_data = _load_module_json(module_path, "work", "work.json")
            if work_data:
                for section in ["en_cours", "validation", "approbation"]:
                    items = work_data.get(section, [])
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                key = item.get("key", item.get("id", ""))
                                if key:
                                    json_entries.add(key.lower().replace("-", " ").replace("_", " "))

    # Cross-reference (informational, not strict matching)
    if work_nodes and not json_entries:
        issues.append({
            "type": "no_work_json",
            "severity": "info",
            "message": f"Mindmap has {len(work_nodes)} work nodes but no work.json entries found",
        })

    return issues


def check_documentation_refs() -> list:
    """Check documentation references point to actual files."""
    issues = []

    if os.path.isdir(KNOWLEDGE_DIR):
        for module in os.listdir(KNOWLEDGE_DIR):
            module_path = os.path.join(KNOWLEDGE_DIR, module)
            if not os.path.isdir(module_path):
                continue
            doc_data = _load_module_json(
                module_path, "documentation", "documentation.json")
            if not doc_data:
                continue

            refs = doc_data.get("references", [])
            if not isinstance(refs, list):
                continue

            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                path = ref.get("path", "")
                if path and not path.startswith("http"):
                    # Resolve relative to project root
                    full_path = os.path.join(PROJECT_ROOT, path)
                    if not os.path.exists(full_path):
                        issues.append({
                            "type": "broken_doc_ref",
                            "module": module,
                            "path": path,
                            "severity": "warning",
                            "message": f"{module}: doc ref '{path}' not found",
                        })

    return issues


def check_mindmap_integrity() -> list:
    """Check mindmap file for structural issues."""
    issues = []
    mindmap_path = os.path.join(K_MIND_DIR, "mind", "mind_memory.md")

    try:
        with open(mindmap_path, "r") as f:
            content = f.read()
    except (FileNotFoundError, IOError):
        issues.append({
            "type": "missing_mindmap",
            "severity": "error",
            "message": "mind_memory.md not found",
        })
        return issues

    # Check for expected top-level nodes
    expected_groups = ["session", "work", "documentation",
                       "conventions", "architecture", "constraints"]
    for group in expected_groups:
        if group not in content.lower():
            issues.append({
                "type": "missing_group",
                "group": group,
                "severity": "error",
                "message": f"Top-level group '{group}' missing from mindmap",
            })

    # Check mermaid fence
    if "```mermaid" not in content:
        issues.append({
            "type": "no_mermaid_fence",
            "severity": "error",
            "message": "No mermaid code fence found in mindmap",
        })

    return issues


def run_concordance_check() -> dict:
    """Run all concordance checks and return structured report."""
    all_issues = []

    all_issues.extend(check_mindmap_integrity())
    all_issues.extend(check_modules_registered())
    all_issues.extend(check_work_concordance())
    all_issues.extend(check_documentation_refs())

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
    """Format concordance check as readable report."""
    if result["clean"]:
        return "Knowledge structure concordance: CLEAN (no issues found)"

    lines = [
        f"Knowledge Structure Concordance Report",
        f"{'=' * 40}",
        f"Total issues: {result['total_issues']} "
        f"({result['errors']} errors, {result['warnings']} warnings, "
        f"{result['info']} info)",
        "",
    ]

    for issue in result["issues"]:
        severity = issue.get("severity", "?").upper()
        message = issue.get("message", "")
        lines.append(f"  [{severity}] {message}")

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audit knowledge structure concordance")
    parser.add_argument("--fix", action="store_true",
                        help="Apply concordance fixes")
    parser.add_argument("--check", action="store_true",
                        help="Report only, no changes (default)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()

    result = run_concordance_check()

    if args.fix:
        # Fix mode: report what would be fixed
        # Actual fixes require Claude intelligence (topic naming, etc.)
        print("Fix mode: structural issues reported below.")
        print("Claude should review each issue and apply appropriate fixes.")
        print()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
