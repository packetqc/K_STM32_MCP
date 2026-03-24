#!/usr/bin/env python3
"""
compile_projects.py — Compile project data from registry + runtime caches + tasks.json

Reads .claude/projects.json (registry), aggregates tasks and metrics per project
from docs/data/tasks.json, and writes docs/data/projects.json for the Project
Viewer interface (I4).

Usage:
    python3 scripts/compile_projects.py
    python3 scripts/compile_projects.py --output docs/data/projects.json
"""

import os
import json
import sys
from datetime import datetime


def find_project_root():
    """Find the project root by looking for CLAUDE.md."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != '/':
        if os.path.exists(os.path.join(d, 'CLAUDE.md')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def normalize_project_name(name):
    """Normalize project name for matching (handles variants)."""
    if not name:
        return ""
    import re
    n = name.strip().lower()
    # Normalize P0 variants
    if n in ("p0", "p0 knowledge", "p0 — knowledge", "p0 - knowledge"):
        return "p0 knowledge"
    # Normalize punctuation variants (apostrophe, period, etc.)
    n = re.sub(r'[.\u2019\u2018`]', "'", n)
    return n


def load_registry(root):
    """Load .claude/projects.json registry."""
    path = os.path.join(root, ".claude", "projects.json")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("projets", [])
    except (json.JSONDecodeError, OSError):
        return []


def load_tasks(root):
    """Load compiled tasks.json."""
    path = os.path.join(root, "docs", "data", "tasks.json")
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get("tasks", [])
    except (json.JSONDecodeError, OSError):
        return []


def load_sessions(root):
    """Load compiled sessions.json."""
    path = os.path.join(root, "docs", "data", "sessions.json")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("sessions", [])
    except (json.JSONDecodeError, OSError):
        return []


def aggregate_grid(tasks):
    """Aggregate knowledge grids across tasks into a project-level summary.

    Counts Vrai/Faux/-- per cell across all tasks.
    """
    cell_counts = {}
    for task in tasks:
        kg = task.get("knowledge_grid", {})
        resultats = kg.get("resultats", {})
        for section_name, section_vals in resultats.items():
            if section_name not in cell_counts:
                cell_counts[section_name] = {}
            for cell_id, val in section_vals.items():
                if cell_id not in cell_counts[section_name]:
                    cell_counts[section_name][cell_id] = {"Vrai": 0, "Faux": 0, "--": 0, "Passer": 0}
                key = val if val in ("Vrai", "Faux", "Passer") else "--"
                cell_counts[section_name][cell_id][key] += 1

    # Compute percentage and dominant value per cell
    grid_summary = {}
    total_vrai = 0
    total_cells = 0
    for section_name, cells in cell_counts.items():
        grid_summary[section_name] = {}
        for cell_id, counts in cells.items():
            total = sum(counts.values())
            dominant = max(counts, key=counts.get)
            pct_vrai = (counts["Vrai"] / total * 100) if total > 0 else 0
            grid_summary[section_name][cell_id] = {
                "dominant": dominant,
                "pct_vrai": round(pct_vrai),
                "counts": counts,
            }
            total_vrai += counts["Vrai"]
            total_cells += total

    return grid_summary, total_vrai, total_cells


def compile_projects(root, output_path):
    """Main compilation: registry + tasks + sessions → projects.json."""
    registry = load_registry(root)
    tasks = load_tasks(root)
    sessions = load_sessions(root)

    # Build normalized project name → registry entry mapping
    registry_by_name = {}
    for entry in registry:
        norm = normalize_project_name(entry.get("titre", ""))
        registry_by_name[norm] = entry

    # Group tasks by normalized project name
    tasks_by_project = {}
    for task in tasks:
        project_name = task.get("project") or ""
        if not project_name:
            continue
        norm = normalize_project_name(project_name)
        if norm not in tasks_by_project:
            tasks_by_project[norm] = {"name": project_name, "tasks": []}
        tasks_by_project[norm]["tasks"].append(task)

    # Also include registered projects with no tasks yet
    for entry in registry:
        norm = normalize_project_name(entry.get("titre", ""))
        if norm and norm not in tasks_by_project:
            tasks_by_project[norm] = {"name": entry["titre"], "tasks": []}

    # Build project objects
    projects = []
    all_stages = [
        "initial", "plan", "analyze", "implement",
        "validation", "documentation", "approval", "completion",
    ]

    for norm_name, group in sorted(tasks_by_project.items()):
        project_tasks = group["tasks"]
        display_name = group["name"]

        # Registry data
        reg = registry_by_name.get(norm_name, {})

        # Aggregate metrics
        total_prs = 0
        total_additions = 0
        total_deletions = 0
        total_files = 0
        all_pr_numbers = set()
        branches = set()

        for t in project_tasks:
            mc = t.get("metrics_compilation") or {}
            total_prs += mc.get("prs", 0)
            total_additions += mc.get("additions", 0)
            total_deletions += mc.get("deletions", 0)
            total_files += mc.get("files_changed", 0)
            for pr_num in mc.get("pr_numbers", []):
                all_pr_numbers.add(pr_num)
            if t.get("branch"):
                branches.add(t["branch"])

        # Stage distribution
        stage_dist = {s: 0 for s in all_stages}
        for t in project_tasks:
            stage = t.get("current_stage", "initial")
            if stage in stage_dist:
                stage_dist[stage] += 1

        # Completion rate
        completed = sum(1 for t in project_tasks if t.get("current_stage") == "completion")
        completion_pct = round((completed / len(project_tasks)) * 100) if project_tasks else 0

        # Aggregate knowledge grid
        grid_summary, grid_vrai, grid_total = aggregate_grid(project_tasks)
        grid_pct = round((grid_vrai / grid_total) * 100) if grid_total > 0 else 0

        # Task summaries for the project
        task_summaries = []
        for t in project_tasks:
            mc = t.get("metrics_compilation") or {}
            kg = t.get("knowledge_grid", {})
            res = kg.get("resultats", {})
            vrai_count = sum(1 for s in res.values() for v in s.values() if v == "Vrai")
            task_summaries.append({
                "id": t.get("id"),
                "issue_number": t.get("issue_number"),
                "title": t.get("title", ""),
                "current_stage": t.get("current_stage", "initial"),
                "current_stage_index": t.get("current_stage_index", 0),
                "branch": t.get("branch", ""),
                "prs": mc.get("prs", 0),
                "additions": mc.get("additions", 0),
                "deletions": mc.get("deletions", 0),
                "grid_score": vrai_count,
                "grid_total": 19,
                "synthesized": bool(kg.get("synthesized")),
                "started_at": t.get("started_at"),
                "updated_at": t.get("updated_at"),
            })

        # Sort tasks: most recent first
        task_summaries.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

        # Find linked sessions by branch
        session_ids = []
        for s in sessions:
            if s.get("branch") in branches:
                session_ids.append(s["id"])

        # Dates
        dates = [t.get("started_at") or "" for t in project_tasks if t.get("started_at")]
        started_at = min(dates) if dates else None
        updated_dates = [t.get("updated_at") or "" for t in project_tasks if t.get("updated_at")]
        updated_at = max(updated_dates) if updated_dates else None

        project = {
            "id": f"project-{reg.get('id', norm_name.replace(' ', '-'))}",
            "title": reg.get("titre") or display_name,
            "registry_id": reg.get("id"),
            "board_number": reg.get("board_number"),
            "board_url": reg.get("board_url"),
            "issue_number": reg.get("issue_number"),
            "issue_url": reg.get("issue_url"),
            "repo": reg.get("repo", "packetqc/knowledge"),
            "task_count": len(project_tasks),
            "completed_tasks": completed,
            "completion_pct": completion_pct,
            "stage_distribution": stage_dist,
            "metrics": {
                "prs": total_prs,
                "pr_numbers": sorted(all_pr_numbers),
                "additions": total_additions,
                "deletions": total_deletions,
                "files_changed": total_files,
            },
            "branches": sorted(branches),
            "session_ids": session_ids,
            "grid_summary": grid_summary,
            "grid_pct": grid_pct,
            "tasks": task_summaries,
            "started_at": started_at,
            "updated_at": updated_at,
        }
        projects.append(project)

    # Sort: most tasks first, then by updated_at
    projects.sort(key=lambda p: (p["task_count"], p.get("updated_at") or ""), reverse=True)

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "meta": {
            "generated_at": now,
            "total_projects": len(projects),
            "total_tasks": sum(p["task_count"] for p in projects),
            "sources": [".claude/projects.json", "docs/data/tasks.json", "docs/data/sessions.json"],
        },
        "projects": projects,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return len(projects)


def main():
    root = find_project_root()
    output = os.path.join(root, "docs", "data", "projects.json")
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    count = compile_projects(root, output)
    print(f"Compiled {count} projects → {output}")


if __name__ == "__main__":
    main()
