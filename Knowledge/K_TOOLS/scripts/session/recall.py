#!/usr/bin/env python3
"""Recall — deep memory search across all knowledge channels.

Adapted for Knowledge 2.0 multi-module architecture.
Uses K_MIND memory system (near/far/archives) as primary layer,
then git memory, GitHub memory, and deep file search.

Search layers (in order):
  1. K_MIND memory (~5s): near_memory, far_memory, archives
  2. Git memory (~10s): commit messages, branch names
  3. GitHub memory (~15s, requires GH_TOKEN): issues, PR descriptions
  4. Deep memory (~30s): methodology, publications, conventions, domain JSONs

Usage:
  python3 recall.py --query "search term"
  python3 recall.py --query "search term" --layers near git
  python3 recall.py --query "search term" --repo packetqc/K_DOCS

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional


# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# K_TOOLS/scripts/session/ -> K_TOOLS -> Knowledge -> PROJECT_ROOT
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


# ── Layer 1: K_MIND Memory ─────────────────────────────────────────

def search_near_memory(query: str, max_results: int = 10) -> list:
    """Search near_memory summaries (current + last session)."""
    results = []
    query_lower = query.lower()
    near_path = os.path.join(SESSIONS_DIR, "near_memory.json")

    try:
        with open(near_path, "r") as f:
            data = json.load(f)

        # Current session summaries
        for s in data.get("summaries", []):
            if query_lower in s.get("summary", "").lower():
                results.append({
                    "source": "near_memory",
                    "session": data.get("session_id", "")[:8],
                    "id": s.get("id"),
                    "summary": s["summary"],
                    "mind_refs": s.get("mind_memory_refs", []),
                    "far_refs": s.get("far_memory_refs", []),
                })
                if len(results) >= max_results:
                    return results

        # Last session summaries
        last = data.get("last_session", {})
        for s in last.get("summaries", []):
            if query_lower in s.get("summary", "").lower():
                results.append({
                    "source": "near_memory_last",
                    "session": last.get("session_id", "")[:8],
                    "id": s.get("id"),
                    "summary": s["summary"],
                    "mind_refs": s.get("mind_memory_refs", []),
                })
                if len(results) >= max_results:
                    return results
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        pass

    return results


def search_far_memory(query: str, max_results: int = 10) -> list:
    """Search far_memory messages (current session)."""
    results = []
    query_lower = query.lower()
    far_path = os.path.join(SESSIONS_DIR, "far_memory.json")

    try:
        with open(far_path, "r") as f:
            data = json.load(f)

        for msg in data.get("messages", []):
            content = msg.get("content", "")
            if query_lower in content.lower():
                results.append({
                    "source": "far_memory",
                    "session": data.get("session_id", "")[:8],
                    "id": msg.get("id"),
                    "role": msg.get("role", ""),
                    "match_text": _truncate(content, 200),
                })
                if len(results) >= max_results:
                    return results
    except (json.JSONDecodeError, FileNotFoundError, IOError):
        pass

    return results


def search_archives(query: str, max_results: int = 10) -> list:
    """Search archived far_memory topics."""
    results = []
    query_lower = query.lower()
    archives_dir = os.path.join(SESSIONS_DIR, "archives")

    if not os.path.isdir(archives_dir):
        return results

    try:
        archive_files = sorted(
            [f for f in os.listdir(archives_dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(archives_dir, f)),
            reverse=True
        )

        for filename in archive_files:
            if len(results) >= max_results:
                break
            filepath = os.path.join(archives_dir, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                topic = data.get("topic", filename)
                for msg in data.get("messages", []):
                    content = msg.get("content", "")
                    if query_lower in content.lower():
                        results.append({
                            "source": "archive",
                            "file": filename,
                            "topic": topic,
                            "id": msg.get("id"),
                            "role": msg.get("role", ""),
                            "match_text": _truncate(content, 200),
                        })
                        if len(results) >= max_results:
                            break
            except (json.JSONDecodeError, IOError):
                continue
    except OSError:
        pass

    return results


# ── Layer 2: Git Memory ─────────────────────────────────────────────

def search_commit_messages(query: str, max_results: int = 10) -> list:
    """Search git commit messages across all branches."""
    results = []
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--grep", query, "-i",
             "--format=%H\t%ci\t%D\t%s",
             f"-{max_results}"],
            capture_output=True, text=True, timeout=15,
            cwd=PROJECT_ROOT
        )
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t", 3)
            results.append({
                "source": "git_commit",
                "hash": parts[0][:8],
                "full_hash": parts[0],
                "date": parts[1][:10] if len(parts) > 1 else "",
                "branch": _extract_branch(parts[2] if len(parts) > 2 else ""),
                "subject": parts[3] if len(parts) > 3 else "",
            })
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return results[:max_results]


def search_file_content(query: str, paths: list = None,
                        max_results: int = 10) -> list:
    """Search file content using git grep."""
    results = []
    cmd = ["git", "grep", "-i", "-n", "--max-count", "3", query]
    if paths:
        cmd.append("--")
        cmd.extend(paths)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=15, cwd=PROJECT_ROOT)
        for line in result.stdout.strip().splitlines():
            if not line or len(results) >= max_results:
                break
            match = re.match(r"^(.+?):(\d+):(.*)$", line)
            if match:
                results.append({
                    "source": "file_content",
                    "file": match.group(1),
                    "line_number": int(match.group(2)),
                    "match_text": _truncate(match.group(3).strip(), 200),
                })
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return results[:max_results]


# ── Layer 3: GitHub Memory ──────────────────────────────────────────

def search_github_issues(query: str, repo: str = "packetqc/K_DOCS",
                         max_results: int = 10) -> list:
    """Search GitHub issues by title and body. Requires GH_TOKEN."""
    gh = _get_gh_helper()
    if not gh:
        return []

    results = []
    try:
        import urllib.parse
        search_query = f"{query} repo:{repo} is:issue"
        response = gh._request(
            "GET",
            f"/search/issues?q={urllib.parse.quote(search_query, safe='')}&per_page={max_results}"
        )
        for item in response.get("items", [])[:max_results]:
            labels = [lb.get("name", "") for lb in item.get("labels", [])]
            results.append({
                "source": "github_issue",
                "number": item.get("number"),
                "title": item.get("title", ""),
                "state": item.get("state", ""),
                "labels": labels,
                "url": item.get("html_url", ""),
                "created": item.get("created_at", "")[:10],
            })
    except Exception:
        pass

    return results[:max_results]


# ── Layer 4: Deep Memory ────────────────────────────────────────────

def search_domain_jsons(query: str, max_results: int = 10) -> list:
    """Search all Knowledge module domain JSON files."""
    results = []
    query_lower = query.lower()
    knowledge_dir = os.path.join(PROJECT_ROOT, "Knowledge")

    if not os.path.isdir(knowledge_dir):
        return results

    for module in os.listdir(knowledge_dir):
        module_path = os.path.join(knowledge_dir, module)
        if not os.path.isdir(module_path):
            continue
        for subdir in ["conventions", "work", "documentation"]:
            json_dir = os.path.join(module_path, subdir)
            if not os.path.isdir(json_dir):
                continue
            for fname in os.listdir(json_dir):
                if not fname.endswith(".json"):
                    continue
                filepath = os.path.join(json_dir, fname)
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                    if query_lower in content.lower():
                        results.append({
                            "source": "domain_json",
                            "module": module,
                            "file": f"{subdir}/{fname}",
                            "match_text": _truncate(
                                _find_matching_line(content, query_lower), 200),
                        })
                        if len(results) >= max_results:
                            return results
                except (IOError, UnicodeDecodeError):
                    continue

    return results


def search_methodology(query: str, max_results: int = 10) -> list:
    """Search methodology files across all Knowledge modules."""
    paths = []
    knowledge_dir = os.path.join(PROJECT_ROOT, "Knowledge")
    if os.path.isdir(knowledge_dir):
        for module in os.listdir(knowledge_dir):
            meth_dir = os.path.join(knowledge_dir, module, "methodology")
            if os.path.isdir(meth_dir):
                paths.append(f"Knowledge/{module}/methodology/")
    # Also search legacy methodology if present
    if os.path.isdir(os.path.join(PROJECT_ROOT, "Knowledge", "legacy",
                                   "knowledge", "methodology")):
        paths.append("Knowledge/legacy/knowledge/methodology/")

    return search_file_content(query, paths=paths, max_results=max_results)


# ── Full Recall (Progressive Search) ───────────────────────────────

def recall(query: str, repo: str = "packetqc/K_DOCS",
           layers: list = None, max_per_layer: int = 5) -> dict:
    """Execute a progressive deep memory search.

    Args:
        query: The search query.
        repo: GitHub repo for API searches.
        layers: Optional list of layer names to search.
                Default: ["near", "git", "github", "deep"]
        max_per_layer: Max results per search function.

    Returns:
        Dict with layer results and metadata.
    """
    if layers is None:
        layers = ["near", "git", "github", "deep"]

    all_results = {}
    total = 0

    # Layer 1: K_MIND memory
    if "near" in layers:
        near = {}
        nm = search_near_memory(query, max_per_layer)
        if nm:
            near["near_memory"] = nm
            total += len(nm)
        fm = search_far_memory(query, max_per_layer)
        if fm:
            near["far_memory"] = fm
            total += len(fm)
        ar = search_archives(query, max_per_layer)
        if ar:
            near["archives"] = ar
            total += len(ar)
        if near:
            all_results["near"] = near

    # Layer 2: Git memory
    if "git" in layers:
        git = {}
        commits = search_commit_messages(query, max_per_layer)
        if commits:
            git["commits"] = commits
            total += len(commits)
        if git:
            all_results["git"] = git

    # Layer 3: GitHub memory (requires GH_TOKEN)
    if "github" in layers:
        github = {}
        issues = search_github_issues(query, repo, max_per_layer)
        if issues:
            github["issues"] = issues
            total += len(issues)
        if github:
            all_results["github"] = github

    # Layer 4: Deep memory
    if "deep" in layers:
        deep = {}
        domain = search_domain_jsons(query, max_per_layer)
        if domain:
            deep["domain_jsons"] = domain
            total += len(domain)
        methodology = search_methodology(query, max_per_layer)
        if methodology:
            deep["methodology"] = methodology
            total += len(methodology)
        files = search_file_content(
            query,
            paths=["Knowledge/K_DOCS/methodology/",
                   "docs/publications/"],
            max_results=max_per_layer
        )
        if files:
            deep["publications"] = files
            total += len(files)
        if deep:
            all_results["deep"] = deep

    return {
        "query": query,
        "layers_searched": layers,
        "total_results": total,
        "results": all_results,
    }


def format_recall_report(recall_result: dict) -> str:
    """Format recall results as a readable report."""
    q = recall_result["query"]
    total = recall_result["total_results"]
    results = recall_result["results"]

    if total == 0:
        return (f'No results found for "{q}" across '
                f'{len(recall_result["layers_searched"])} layer(s).')

    lines = [f'Found {total} result(s) for "{q}":\n']

    layer_names = {
        "near": "K_MIND Memory (near + far + archives)",
        "git": "Git Memory (commits)",
        "github": "GitHub Memory (issues)",
        "deep": "Deep Memory (domain JSONs + methodology + publications)",
    }

    for layer, layer_data in results.items():
        lines.append(f"### {layer_names.get(layer, layer)}")

        for category, items in layer_data.items():
            lines.append(f"  **{category}** "
                         f"({len(items)} match{'es' if len(items) != 1 else ''}):")

            for item in items:
                source = item.get("source", "")
                if source in ("near_memory", "near_memory_last"):
                    session = item.get("session", "")
                    tag = " (last session)" if source == "near_memory_last" else ""
                    lines.append(
                        f"    - [{session}{tag}] #{item['id']}: "
                        f"{item['summary']}"
                    )
                elif source in ("far_memory", "archive"):
                    lines.append(
                        f"    - [{item.get('role', '')}] "
                        f"{item['match_text']}"
                    )
                elif source == "git_commit":
                    lines.append(
                        f"    - {item['hash']} ({item['date']}) "
                        f"{item['subject']}"
                    )
                elif source == "github_issue":
                    labels_str = ", ".join(item.get("labels", []))
                    suffix = f" ({labels_str})" if labels_str else ""
                    lines.append(
                        f"    - #{item['number']} [{item.get('state', '')}] "
                        f"{item.get('title', '')}{suffix}"
                    )
                elif source in ("file_content", "domain_json"):
                    lines.append(
                        f"    - {item.get('file', '')}: "
                        f"{item['match_text']}"
                    )

        lines.append("")

    # Check for stranded branch work → suggest recover
    git_results = results.get("git", {})
    if git_results.get("commits"):
        branch_commits = [c for c in git_results["commits"]
                          if "claude/" in c.get("branch", "")
                          or "backup-" in c.get("branch", "")]
        if branch_commits:
            lines.append(
                "**Stranded branch work detected** — use `recover` "
                "to cherry-pick/apply commits from claude/* branches."
            )

    return "\n".join(lines)


# ── Helpers ─────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _extract_branch(ref_string: str) -> str:
    if not ref_string:
        return ""
    for ref in ref_string.split(","):
        ref = ref.strip()
        if "claude/" in ref or "backup-" in ref:
            return ref.replace("origin/", "")
    for ref in ref_string.split(","):
        ref = ref.strip()
        if ref and "HEAD" not in ref:
            return ref.replace("origin/", "")
    return ""


def _find_matching_line(text: str, query_lower: str) -> str:
    for line in text.splitlines():
        if query_lower in line.lower():
            return line.strip()
    return text[:200]


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Deep memory search")
    parser.add_argument("--query", "-q", required=True,
                        help="Search query")
    parser.add_argument("--layers", nargs="*",
                        default=["near", "git", "github", "deep"],
                        help="Layers to search")
    parser.add_argument("--repo", default="packetqc/K_DOCS",
                        help="GitHub repo for API searches")
    parser.add_argument("--max", type=int, default=5,
                        help="Max results per layer")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()
    result = recall(args.query, repo=args.repo,
                    layers=args.layers, max_per_layer=args.max)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_recall_report(result))


if __name__ == "__main__":
    main()
