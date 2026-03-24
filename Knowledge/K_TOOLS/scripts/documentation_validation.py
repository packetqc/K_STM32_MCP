#!/usr/bin/env python3
"""Documentation validation — D1 (system) and D2 (user) execution functions.

Called by the knowledge-validation skill when the user selects D1, D2, or D3 (Tous).
Detects changes from the current session and identifies what documentation needs updating.

Returns structured JSON that Claude uses to perform the actual updates.

Authors: Martin Paquet, Claude (Anthropic)
"""

import json
import os
import subprocess
import sys
import glob
from datetime import datetime, timezone

# ── Project root ──────────────────────────────────────────────────────

def _find_project_root():
    """Find project root by looking for CLAUDE.md."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != '/':
        if os.path.exists(os.path.join(d, 'CLAUDE.md')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


ROOT = _find_project_root()


# ── Session cache loader ─────────────────────────────────────────────

def _load_latest_cache():
    """Load the most recent session runtime cache."""
    pattern = os.path.join(ROOT, "notes", "session-runtime-*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not files:
        return None
    try:
        with open(files[0], 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _load_knowledge_resultats():
    """Load knowledge_resultats.json."""
    path = os.path.join(ROOT, ".claude", "knowledge_resultats.json")
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


# ── Git change detection ─────────────────────────────────────────────

def _get_session_changes():
    """Detect files changed in the current session via git.

    Looks at recent commits on the current branch.
    Returns dict with files_changed, additions, deletions, commit_messages.
    """
    result = {
        "files_changed": [],
        "additions": 0,
        "deletions": 0,
        "commit_messages": [],
        "has_changes": False
    }

    try:
        # Get current branch
        branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, cwd=ROOT, timeout=5
        ).stdout.strip()

        # Get recent commits on this branch (last 10)
        log = subprocess.run(
            ['git', 'log', '--oneline', '-10', '--format=%H %s'],
            capture_output=True, text=True, cwd=ROOT, timeout=5
        )
        for line in log.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    result["commit_messages"].append(parts[1])

        # Get changed files with stats
        numstat = subprocess.run(
            ['git', 'diff', '--numstat', 'HEAD~10..HEAD'],
            capture_output=True, text=True, cwd=ROOT, timeout=10
        )
        for line in numstat.stdout.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 3:
                try:
                    adds = int(parts[0]) if parts[0] != '-' else 0
                    dels = int(parts[1]) if parts[1] != '-' else 0
                    result["additions"] += adds
                    result["deletions"] += dels
                    result["files_changed"].append(parts[2])
                except ValueError:
                    pass

        result["has_changes"] = len(result["files_changed"]) > 0

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


# ── Essential files detection ────────────────────────────────────────

ESSENTIAL_FILES = {
    "NEWS.md": {
        "trigger": "any deliverable produced",
        "action": "Add entry under current date section"
    },
    "PLAN.md": {
        "trigger": "new feature, capability, or roadmap change",
        "action": "Update What's New and/or Ongoing sections"
    },
    "LINKS.md": {
        "trigger": "new web page URL created",
        "action": "Add URL to Essentials or Hubs; update counters"
    },
    "CHANGELOG.md": {
        "trigger": "issue created or PR merged",
        "action": "Add entry to current date section"
    },
    "VERSION.md": {
        "trigger": "version bump needed",
        "action": "Update version number"
    }
}


def _check_essential_files(changes):
    """Check which essential files need updating based on session changes.

    Returns list of {file, needs_update, reason}.
    """
    results = []
    changed_set = set(changes.get("files_changed", []))

    for filename, info in ESSENTIAL_FILES.items():
        already_updated = filename in changed_set
        needs_update = False
        reason = ""

        if already_updated:
            reason = f"Already updated in this session"
            needs_update = False
        elif changes["has_changes"]:
            # Check specific triggers
            if filename == "NEWS.md":
                needs_update = True
                reason = f"{len(changes['files_changed'])} files changed — add NEWS entry"
            elif filename == "CHANGELOG.md":
                # Check for PR merges in commit messages
                pr_msgs = [m for m in changes["commit_messages"] if "merge" in m.lower() or "PR" in m]
                if pr_msgs:
                    needs_update = True
                    reason = f"PR activity detected — add CHANGELOG entry"
            elif filename == "PLAN.md":
                # Check for methodology/feature changes
                feature_files = [f for f in changes["files_changed"]
                                if "methodology/" in f or "scripts/" in f or "SKILL.md" in f]
                if feature_files:
                    needs_update = True
                    reason = f"Feature/methodology changes — check PLAN"
            elif filename == "LINKS.md":
                # Check for new web pages
                web_files = [f for f in changes["files_changed"] if "docs/" in f]
                if web_files:
                    needs_update = True
                    reason = f"Web pages modified — check LINKS"

        results.append({
            "file": filename,
            "needs_update": needs_update,
            "already_updated": already_updated,
            "reason": reason
        })

    return results


# ── D1: System Documentation ─────────────────────────────────────────

def validate_system_documentation():
    """D1 — Validate and identify system documentation updates needed.

    Checks:
    1. Essential files (NEWS.md, CHANGELOG.md, PLAN.md, LINKS.md, VERSION.md)
    2. Session notes / cache
    3. Methodology files if changed
    4. CLAUDE.md if infrastructure changed

    Returns structured result for Claude to act on.
    """
    changes = _get_session_changes()
    essential = _check_essential_files(changes)
    cache = _load_latest_cache()
    kr = _load_knowledge_resultats()

    # Check if methodology files were modified
    methodology_changed = [f for f in changes["files_changed"] if "methodology/" in f]

    # Check if CLAUDE.md needs update
    claude_md_changed = "CLAUDE.md" in changes["files_changed"]
    infra_changed = any(f.startswith("scripts/") or f.startswith(".claude/") for f in changes["files_changed"])

    # Session notes from cache
    session_summary = ""
    if cache:
        sd = cache.get("session_data", {})
        session_summary = sd.get("work_summary", {}).get("summary", "")

    # Build action items
    action_items = []
    for ess in essential:
        if ess["needs_update"]:
            action_items.append({
                "type": "essential_file",
                "target": ess["file"],
                "reason": ess["reason"],
                "priority": "high" if ess["file"] in ("NEWS.md", "CHANGELOG.md") else "medium"
            })

    if methodology_changed:
        action_items.append({
            "type": "methodology",
            "target": ", ".join(methodology_changed),
            "reason": f"{len(methodology_changed)} methodology file(s) modified — verify consistency",
            "priority": "medium"
        })

    if infra_changed and not claude_md_changed:
        action_items.append({
            "type": "claude_md",
            "target": "CLAUDE.md",
            "reason": "Infrastructure changed but CLAUDE.md not updated",
            "priority": "low"
        })

    # Session cache update
    if cache and not cache.get("session_data", {}).get("work_summary"):
        action_items.append({
            "type": "session_cache",
            "target": "session cache (work_summary)",
            "reason": "No work summary in session cache",
            "priority": "medium"
        })

    success = True  # D1 succeeds if we can detect and report

    result = {
        "success": success,
        "has_changes": changes["has_changes"],
        "files_changed_count": len(changes["files_changed"]),
        "additions": changes["additions"],
        "deletions": changes["deletions"],
        "essential_files": essential,
        "action_items": action_items,
        "action_items_count": len(action_items),
        "methodology_changed": methodology_changed,
        "session_summary": session_summary,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }

    return result


# ── D2: User Documentation ──────────────────────────────────────────

def validate_user_documentation():
    """D2 — Validate and identify user documentation updates needed.

    Checks:
    1. Publications that may be affected by session changes
    2. Web pages (docs/) freshness
    3. Success stories opportunity
    4. Bilingual mirrors (EN/FR)

    Returns structured result for Claude to act on.
    """
    changes = _get_session_changes()
    cache = _load_latest_cache()

    # Map changed files to potentially affected publications
    affected_pubs = set()
    pub_mapping = {
        "scripts/session_agent/": "session-management",
        "scripts/gh_helper": "session-management",
        ".claude/skills/knowledge": "knowledge-system",
        "methodology/methodology-documentation": "documentation-generation",
        "scripts/generate_og": "webcards-social-sharing",
        "interfaces/": "main-interface",
        "scripts/harvest": "harvest-protocol",
        "methodology/methodology-interactive": "interactive-work-sessions",
        "scripts/session_agent/documentation": "documentation-generation",
        "scripts/session_agent/task_workflow": "knowledge-system",
    }

    for changed_file in changes.get("files_changed", []):
        for pattern, pub_slug in pub_mapping.items():
            if pattern in changed_file:
                affected_pubs.add(pub_slug)

    # Check for docs/ pages that were modified
    docs_changed = [f for f in changes["files_changed"] if f.startswith("docs/")]

    # Check for publication source files changed
    pub_sources_changed = [f for f in changes["files_changed"] if f.startswith("publications/")]

    # Success story opportunity
    kr = _load_knowledge_resultats()
    has_successful_execution = kr.get("demande_executee", False)
    commit_count = len(changes.get("commit_messages", []))
    success_story_candidate = has_successful_execution and commit_count >= 3

    # Build action items
    action_items = []

    for pub_slug in affected_pubs:
        # Check if this publication exists
        pub_path = os.path.join(ROOT, "publications", pub_slug)
        if os.path.isdir(pub_path):
            action_items.append({
                "type": "publication_update",
                "target": f"publications/{pub_slug}/",
                "reason": f"Source files affected — verify publication reflects changes",
                "priority": "medium"
            })

    if docs_changed:
        action_items.append({
            "type": "web_pages",
            "target": ", ".join(docs_changed[:5]),
            "reason": f"{len(docs_changed)} web page(s) modified — verify consistency",
            "priority": "low"
        })

    if pub_sources_changed:
        # Check if corresponding docs/ pages exist and need sync
        for ps in pub_sources_changed:
            slug = ps.split("/")[1] if "/" in ps else ""
            doc_path = os.path.join(ROOT, "docs", "publications", slug)
            if slug and os.path.isdir(doc_path):
                action_items.append({
                    "type": "pub_sync",
                    "target": f"docs/publications/{slug}/",
                    "reason": f"Publication source updated — web pages may need sync",
                    "priority": "high"
                })

    if success_story_candidate:
        action_items.append({
            "type": "success_story",
            "target": "publications/success-stories/",
            "reason": f"Successful execution with {commit_count} commits — success story candidate",
            "priority": "low"
        })

    # Check bilingual mirror completeness
    en_docs = set()
    fr_docs = set()
    for f in changes["files_changed"]:
        if f.startswith("docs/fr/"):
            fr_docs.add(f.replace("docs/fr/", ""))
        elif f.startswith("docs/") and not f.startswith("docs/fr/"):
            en_docs.add(f.replace("docs/", ""))

    missing_mirrors = en_docs.symmetric_difference(fr_docs)
    if missing_mirrors:
        action_items.append({
            "type": "bilingual_mirror",
            "target": ", ".join(list(missing_mirrors)[:3]),
            "reason": f"{len(missing_mirrors)} page(s) without bilingual mirror",
            "priority": "medium"
        })

    success = True

    result = {
        "success": success,
        "has_changes": changes["has_changes"],
        "affected_publications": sorted(affected_pubs),
        "docs_changed": docs_changed,
        "pub_sources_changed": pub_sources_changed,
        "success_story_candidate": success_story_candidate,
        "action_items": action_items,
        "action_items_count": len(action_items),
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }

    return result


# ── CLI entry point ──────────────────────────────────────────────────

def main():
    """CLI entry point. Usage: python3 documentation_validation.py [d1|d2|both]"""
    import argparse
    parser = argparse.ArgumentParser(description="Documentation validation for Knowledge D")
    parser.add_argument("action", choices=["d1", "d2", "both"],
                       help="Which validation to run: d1 (system), d2 (user), both")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = {}

    if args.action in ("d1", "both"):
        results["D1"] = validate_system_documentation()
        if not args.json:
            print("\n=== D1: Documentation système ===")
            r = results["D1"]
            print(f"Changements détectés: {r['has_changes']} ({r['files_changed_count']} fichiers)")
            print(f"Actions requises: {r['action_items_count']}")
            for item in r["action_items"]:
                print(f"  [{item['priority'].upper()}] {item['target']}: {item['reason']}")

    if args.action in ("d2", "both"):
        results["D2"] = validate_user_documentation()
        if not args.json:
            print("\n=== D2: Documentation utilisateur ===")
            r = results["D2"]
            print(f"Changements détectés: {r['has_changes']}")
            print(f"Publications affectées: {', '.join(r['affected_publications']) or 'aucune'}")
            print(f"Success story candidat: {r['success_story_candidate']}")
            print(f"Actions requises: {r['action_items_count']}")
            for item in r["action_items"]:
                print(f"  [{item['priority'].upper()}] {item['target']}: {item['reason']}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    # Exit code: 0 if all succeeded
    all_success = all(r.get("success", False) for r in results.values())
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
