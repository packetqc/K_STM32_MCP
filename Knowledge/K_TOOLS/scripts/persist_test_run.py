#!/usr/bin/env python3
"""
Test Run Persistence — Complete Publication Gate Distribution
==============================================================

After a test report is generated, this script distributes the test run
across ALL system surfaces required by the Publication Gate methodology.

Distribution surfaces (mandatory — partial distribution = broken system):
  1. history.json (primary) — Tests Interface dashboard data source
  2. test-history.json (fallback) — Dashboard fallback
  3. index.html DOCS array — Viewer document selection list (source of truth)
  4. tests.json — Left panel TESTS section entry
  5. (Future: LINKS.md, HTML redirect, mindmap)

The index.html DOCS array is the authoritative source for viewer resolution.
The path/path_fr convention drives bilingual link building in the main
interface and tests interface.

Usage:
    # Full distribution — persist run + register across all surfaces
    python3 scripts/persist_test_run.py \
        --test-id tests-interface-no-tab-bar \
        --title "Tests Interface — Tab Bar Removal" \
        --title-fr "Interface Tests — Suppression de la barre d'onglets" \
        --slug test-tests-interface-no-tab-bar \
        --results /path/to/results.json

    # Explicit values (no results file needed)
    python3 scripts/persist_test_run.py \
        --test-id tests-interface-no-tab-bar \
        --title "Tests Interface — Tab Bar Removal" \
        --title-fr "Interface Tests — Suppression de la barre d'onglets" \
        --slug test-tests-interface-no-tab-bar \
        --mode VERIFICATION --total 12 --passed 12 --failed 0

    # Sync from local runs.json to history (after generate_test_report.py)
    python3 scripts/persist_test_run.py \
        --test-id tests-interface-no-tab-bar \
        --sync-from-runs docs/publications/test-tests-interface-no-tab-bar/assets/runs.json

    # List all tests in history
    python3 scripts/persist_test_run.py --list

    # Check distribution status for a test
    python3 scripts/persist_test_run.py --check-distribution --slug test-main-navigator

Knowledge asset — part of the Test Report methodology.
"""

import argparse
import json
import os
import sys
from datetime import datetime

import shutil
import glob as globmod

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

# Dashboard history file paths (relative to project root)
PRIMARY_HISTORY = os.path.join(PROJECT_ROOT, "docs", "publications",
                               "test-main-navigator", "assets", "history.json")
FALLBACK_HISTORY = os.path.join(PROJECT_ROOT, "docs", "data", "test-history.json")


def load_history(path):
    """Load history file or create empty structure."""
    if os.path.isfile(path):
        try:
            with open(path) as f:
                data = json.load(f)
            if "tests" not in data:
                data["tests"] = {}
            return data
        except (json.JSONDecodeError, ValueError):
            pass
    return {"tests": {}}


def save_history(path, data):
    """Save history file with consistent formatting."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def make_run_summary(run):
    """Extract dashboard-compatible run summary from a full run entry.

    The dashboard only needs: timestamp, mode, total, passed, failed, pages.
    The local runs.json has full test grids (default, detailed) that we don't
    need in the dashboard.
    """
    summary = {
        "timestamp": run.get("timestamp", datetime.now().isoformat()),
        "mode": run.get("mode", "DEFAULT"),
        "total": run.get("total", 0),
        "passed": run.get("passed", 0),
        "failed": run.get("failed", 0),
    }
    # Include pages map if available (per-check pass/fail)
    if "pages" in run:
        summary["pages"] = run["pages"]
    return summary


def append_run(history, test_id, title, title_fr, slug, run_summary):
    """Append a run to a history structure. Creates test entry if needed."""
    tests = history.setdefault("tests", {})

    if test_id not in tests:
        tests[test_id] = {
            "title": title,
            "title_fr": title_fr or title,
            "href": f"publications/{slug}/index.md" if slug else "",
            "runs": []
        }

    test_entry = tests[test_id]

    # Update metadata if provided (in case title/slug changed)
    if title:
        test_entry["title"] = title
    if title_fr:
        test_entry["title_fr"] = title_fr
    if slug:
        test_entry["href"] = f"publications/{slug}/index.md"

    # Check for duplicate (same timestamp)
    ts = run_summary.get("timestamp", "")
    for existing in test_entry["runs"]:
        if existing.get("timestamp") == ts:
            # Update in place instead of duplicating
            existing.update(run_summary)
            return False  # not a new run

    test_entry["runs"].append(run_summary)
    return True  # new run appended


def persist_run(test_id, title, title_fr, slug, run_summary, proof_source=None):
    """Persist a run to both history files AND distribute across all surfaces.

    This is the COMPLETE Publication Gate — one call handles everything:
      1. history.json (primary + fallback) — dashboard data
      2. index.html DOCS array — viewer document selection
      3. tests.json — left panel navigation
      4. proof.gif — animated proof recording from test engine
    """
    results = []

    for label, path in [("PRIMARY", PRIMARY_HISTORY), ("FALLBACK", FALLBACK_HISTORY)]:
        history = load_history(path)
        is_new = append_run(history, test_id, title, title_fr, slug, run_summary)
        save_history(path, history)

        test = history["tests"][test_id]
        run_count = len(test["runs"])
        status = "appended" if is_new else "updated (duplicate timestamp)"
        results.append((label, path, run_count, status))
        print(f"  [{label}] {status} → {run_count} runs in {os.path.basename(path)}")

    # Publication Gate — distribute to remaining surfaces + proof
    distribute_all(slug, title, title_fr, proof_source)

    return results


# ═══════════════════════════════════════════════════════════
# Publication Gate — Additional Distribution Surfaces
# ═══════════════════════════════════════════════════════════

INDEX_HTML = os.path.join(PROJECT_ROOT, "docs", "index.html")
TESTS_JSON = os.path.join(PROJECT_ROOT, "docs", "data", "tests.json")


def _detect_fr_path(slug):
    """Detect the correct path_fr for a publication slug.

    Convention: if fr/ mirror exists, use fr/ prefix.
    Otherwise, use same path as EN (no translation available)."""
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    en_path = f"publications/{slug}/index.md"
    fr_path = f"fr/publications/{slug}/index.md"

    if os.path.isfile(os.path.join(docs_dir, fr_path)):
        return fr_path
    # Fallback: same as EN path (viewer handles gracefully)
    return en_path


def register_in_index_html(slug, title):
    """Register a test publication in the index.html DOCS array.

    This is the SOURCE OF TRUTH for viewer document selection.
    The entry follows the pattern:
      { group: 'Test Reports', name: 'Title', path: 'publications/<slug>/index.md', path_fr: '<fr-path>' }

    Returns True if entry was added, False if already exists."""
    if not os.path.isfile(INDEX_HTML):
        print(f"  [INDEX.HTML] SKIP — {INDEX_HTML} not found")
        return False

    with open(INDEX_HTML, 'r') as f:
        content = f.read()

    en_path = f"publications/{slug}/index.md"

    # Check if already registered (any entry with this path)
    if en_path in content:
        print(f"  [INDEX.HTML] already registered — {en_path}")
        return False

    fr_path = _detect_fr_path(slug)

    # Build the new entry
    entry = f"      {{ group: 'Test Reports', name: '{title}', path: '{en_path}', path_fr: '{fr_path}' }},"

    # Insert before the "// --- Reports ---" marker or after last Test Reports entry
    marker = "      // --- Reports ---"
    if marker in content:
        content = content.replace(marker, entry + "\n" + marker)
    else:
        # Fallback: insert after the last Test Reports entry
        import re
        last_test = list(re.finditer(r"group: 'Test Reports'.*?\n", content))
        if last_test:
            pos = last_test[-1].end()
            content = content[:pos] + entry + "\n" + content[pos:]
        else:
            print(f"  [INDEX.HTML] ERROR — cannot find Test Reports section")
            return False

    with open(INDEX_HTML, 'w') as f:
        f.write(content)

    print(f"  [INDEX.HTML] registered — {en_path} (fr: {fr_path})")
    return True


def register_in_tests_json(slug, title, title_fr):
    """Register a test publication in the left panel tests.json.

    Uses the index.html convention for href building:
      href = "/publications/<slug>/" (folder path resolved by main navigator)

    Returns True if entry was added, False if already exists."""
    if not os.path.isfile(TESTS_JSON):
        print(f"  [TESTS.JSON] SKIP — {TESTS_JSON} not found")
        return False

    with open(TESTS_JSON) as f:
        data = json.load(f)

    items = data.get("items", [])
    href = f"/publications/{slug}/"

    # Check if already registered
    for item in items:
        if item.get("href") == href:
            print(f"  [TESTS.JSON] already registered — {href}")
            return False

    # Determine priority (next available)
    max_priority = max((item.get("priority", 0) for item in items), default=0)

    items.append({
        "title": title,
        "title_fr": title_fr or title,
        "href": href,
        "priority": max_priority + 1
    })

    data["items"] = items

    with open(TESTS_JSON, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    f_name = os.path.basename(TESTS_JSON)
    print(f"  [TESTS.JSON] registered — {href} (priority {max_priority + 1})")
    return True


def check_distribution(slug, title=None):
    """Check distribution status across all Publication Gate surfaces.

    Returns dict of surface → status."""
    en_path = f"publications/{slug}/index.md"
    href = f"/publications/{slug}/"
    results = {}

    # 1. index.html
    if os.path.isfile(INDEX_HTML):
        with open(INDEX_HTML) as f:
            results['index.html'] = en_path in f.read()
    else:
        results['index.html'] = None

    # 2. tests.json
    if os.path.isfile(TESTS_JSON):
        with open(TESTS_JSON) as f:
            data = json.load(f)
        results['tests.json'] = any(
            item.get('href') == href for item in data.get('items', [])
        )
    else:
        results['tests.json'] = None

    # 3. history.json (primary)
    if os.path.isfile(PRIMARY_HISTORY):
        history = load_history(PRIMARY_HISTORY)
        results['history.json'] = any(
            t.get('href', '').startswith(f'publications/{slug}/')
            for t in history.get('tests', {}).values()
        )
    else:
        results['history.json'] = None

    # 4. Publication markdown exists
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    results['publication'] = os.path.isfile(os.path.join(docs_dir, en_path))

    # 5. FR mirror
    fr_path = _detect_fr_path(slug)
    results['fr_mirror'] = os.path.isfile(os.path.join(docs_dir, fr_path)) if fr_path != en_path else None

    # 6. Proof GIF
    proof_path = os.path.join(docs_dir, "publications", slug, "assets", "proof.gif")
    results['proof.gif'] = os.path.isfile(proof_path)

    return results


def distribute_proof(slug, proof_source=None):
    """Copy proof artifacts (GIF, MP4, snapshots) to publication assets.

    Generic — works for ANY test publication. Searches for proof in this order:
      1. Explicit proof_source path (if provided)
      2. Default test engine output: K_TOOLS/test-reports/test-report.gif
      3. Any .gif in K_TOOLS/test-reports/ (newest first)

    Also copies check snapshots if available.
    Returns True if proof was distributed, False if no proof found."""
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    assets_dir = os.path.join(docs_dir, "publications", slug, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    report_dir = os.path.join(MODULE_DIR, "test-reports")
    dest_gif = os.path.join(assets_dir, "proof.gif")

    # Find proof GIF source
    gif_source = None
    if proof_source and os.path.isfile(proof_source):
        gif_source = proof_source
    else:
        # Default test engine output
        default_gif = os.path.join(report_dir, "test-report.gif")
        if os.path.isfile(default_gif):
            gif_source = default_gif
        else:
            # Fallback: newest .gif in test-reports/
            gifs = sorted(globmod.glob(os.path.join(report_dir, "*.gif")),
                          key=os.path.getmtime, reverse=True)
            if gifs:
                gif_source = gifs[0]

    if not gif_source:
        print(f"  [PROOF] no proof GIF found — skipped")
        return False

    # Copy GIF
    shutil.copy2(gif_source, dest_gif)
    size_kb = os.path.getsize(dest_gif) // 1024
    print(f"  [PROOF] {os.path.basename(gif_source)} → assets/proof.gif ({size_kb}K)")

    # Copy MP4 if available (same directory as GIF source)
    mp4_source = os.path.splitext(gif_source)[0] + ".mp4"
    if not os.path.isfile(mp4_source):
        mp4_source = os.path.join(report_dir, "test-report.mp4")
    if os.path.isfile(mp4_source):
        dest_mp4 = os.path.join(assets_dir, "proof.mp4")
        shutil.copy2(mp4_source, dest_mp4)
        print(f"  [PROOF] → assets/proof.mp4")

    # Copy check snapshots if available
    checks_dir = os.path.join(report_dir, "checks")
    if os.path.isdir(checks_dir):
        snapshots = sorted(globmod.glob(os.path.join(checks_dir, "check_*_snapshot.png")))
        if snapshots:
            dest_checks = os.path.join(assets_dir, "checks")
            os.makedirs(dest_checks, exist_ok=True)
            for snap in snapshots:
                shutil.copy2(snap, os.path.join(dest_checks, os.path.basename(snap)))
            print(f"  [PROOF] → assets/checks/ ({len(snapshots)} snapshots)")

    return True


def distribute_all(slug, title, title_fr, proof_source=None):
    """Run the complete Publication Gate distribution.

    Registers across all surfaces. Idempotent — skips if already registered.
    Automatically distributes proof artifacts (GIF, MP4, snapshots)."""
    print(f"\n  Publication Gate — distributing '{slug}':")
    register_in_index_html(slug, title)
    register_in_tests_json(slug, title, title_fr)
    distribute_proof(slug, proof_source)
    print()


def _load_runs_from_path(runs_path):
    """Load runs from runs.json — supports both split (index+files) and legacy (flat) format."""
    if not os.path.isfile(runs_path):
        return None
    with open(runs_path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        return None
    if not data:
        return []
    # Split format: entries have 'file' key but no 'default'
    if isinstance(data[0], dict) and 'file' in data[0] and 'default' not in data[0]:
        assets_dir = os.path.dirname(runs_path)
        runs = []
        for entry in data:
            run_file = os.path.join(assets_dir, entry['file'])
            if os.path.isfile(run_file):
                with open(run_file) as f:
                    runs.append(json.load(f))
            else:
                runs.append(entry)
        return runs
    return data


def sync_from_runs(test_id, runs_path, title=None, title_fr=None, slug=None):
    """Sync all runs from a local runs.json to both history files.

    Only adds runs that aren't already in history (by timestamp).
    Supports both split (index+files) and legacy (flat) format.
    """
    runs = _load_runs_from_path(runs_path)
    if runs is None:
        print(f"ERROR: {runs_path} not found or invalid")
        return False

    # Try to infer test metadata from history if not provided
    if not title or not slug:
        history = load_history(PRIMARY_HISTORY)
        if test_id in history.get("tests", {}):
            existing = history["tests"][test_id]
            title = title or existing.get("title", test_id)
            title_fr = title_fr or existing.get("title_fr", title)
            slug = slug or existing.get("href", "").replace("publications/", "").replace("/index.md", "")

    if not title:
        title = test_id
    if not slug:
        slug = test_id

    print(f"Syncing {len(runs)} runs for '{test_id}' from {runs_path}")

    new_count = 0
    for run in runs:
        summary = make_run_summary(run)
        for _, path in [("PRIMARY", PRIMARY_HISTORY), ("FALLBACK", FALLBACK_HISTORY)]:
            history = load_history(path)
            if append_run(history, test_id, title, title_fr, slug, summary):
                new_count += 1
            save_history(path, history)

    print(f"  Synced: {new_count // 2} new runs added to both history files")
    return True


def backfill_local():
    """Backfill local runs.json files from dashboard history.

    For each test in history.json, write/merge runs into the publication's
    local assets/runs.json so the report page can show run history tabs.
    Also ensures both history files (primary + fallback) are in sync.
    """
    history = load_history(PRIMARY_HISTORY)
    fallback = load_history(FALLBACK_HISTORY)
    tests = history.get("tests", {})

    if not tests:
        print("No tests in history to backfill.")
        return

    docs_dir = os.path.join(PROJECT_ROOT, "docs")

    print(f"Backfilling {len(tests)} tests from dashboard → local runs.json\n")

    for test_id, test in tests.items():
        href = test.get("href", "")
        runs = test.get("runs", [])
        title = test.get("title", test_id)

        # Derive publication directory from href
        # href is like "publications/test-main-navigator/index.md"
        if href:
            pub_dir = os.path.join(docs_dir, os.path.dirname(href))
        else:
            pub_dir = os.path.join(docs_dir, "publications", f"test-{test_id}")

        assets_dir = os.path.join(pub_dir, "assets")
        runs_path = os.path.join(assets_dir, "runs.json")

        # Load existing local runs (supports split format)
        local_runs = _load_runs_from_path(runs_path) or []

        # Merge: add any dashboard runs missing from local (by timestamp)
        local_timestamps = {r.get("timestamp") for r in local_runs}
        added = 0
        for run in runs:
            ts = run.get("timestamp", "")
            if ts not in local_timestamps:
                # Dashboard runs are summaries; convert to runs.json format
                local_run = {
                    "timestamp": ts,
                    "mode": run.get("mode", "DEFAULT"),
                    "total": run.get("total", 0),
                    "passed": run.get("passed", 0),
                    "failed": run.get("failed", 0),
                    "default": [],  # no grid data available from dashboard
                    "detailed": [],
                }
                # Copy optional fields
                for key in ("widgets_total", "widgets_passed", "widgets_failed",
                            "widgets_skipped", "pages"):
                    if key in run:
                        local_run[key] = run[key]
                local_runs.append(local_run)
                added += 1

        # Sort by timestamp and cap at MAX_RUNS
        local_runs.sort(key=lambda r: r.get("timestamp", ""))
        local_runs = local_runs[-10:]  # MAX_RUNS = 10

        # Write local runs in split format (index + per-run files)
        if added > 0 or not os.path.isfile(runs_path):
            os.makedirs(assets_dir, exist_ok=True)
            runs_subdir = os.path.join(assets_dir, 'runs')
            os.makedirs(runs_subdir, exist_ok=True)
            index = []
            for ri, run in enumerate(local_runs):
                rn = ri + 1
                fname = f'run-{rn}.json'
                with open(os.path.join(runs_subdir, fname), 'w') as f:
                    json.dump(run, f, indent=2, ensure_ascii=False)
                index.append({
                    'run': rn,
                    'timestamp': run.get('timestamp', ''),
                    'mode': run.get('mode', ''),
                    'total': run.get('total', 0),
                    'passed': run.get('passed', 0),
                    'failed': run.get('failed', 0),
                    'widgets_total': run.get('widgets_total', 0),
                    'widgets_passed': run.get('widgets_passed', 0),
                    'widgets_failed': run.get('widgets_failed', 0),
                    'widgets_skipped': run.get('widgets_skipped', 0),
                    'file': f'runs/{fname}',
                })
            with open(runs_path, 'w') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)

        # Sync fallback history too
        fb_tests = fallback.setdefault("tests", {})
        if test_id not in fb_tests:
            fb_tests[test_id] = dict(test)  # copy from primary
        else:
            fb_entry = fb_tests[test_id]
            fb_timestamps = {r.get("timestamp") for r in fb_entry.get("runs", [])}
            for run in runs:
                if run.get("timestamp") not in fb_timestamps:
                    fb_entry.setdefault("runs", []).append(run)

        status = f"+{added}" if added > 0 else "ok"
        print(f"  {test_id:<40} {len(local_runs):>3} local runs  [{status}]  {title}")

    # Save fallback
    save_history(FALLBACK_HISTORY, fallback)
    print(f"\nBackfill complete. Fallback history synced.")


def list_tests():
    """List all tests in the primary history file."""
    history = load_history(PRIMARY_HISTORY)
    tests = history.get("tests", {})

    if not tests:
        print("No tests in history.")
        return

    print(f"{'ID':<40} {'Title':<45} {'Runs':>5}  {'Last':>10}")
    print("-" * 105)

    for test_id, test in tests.items():
        title = test.get("title", test_id)[:44]
        runs = test.get("runs", [])
        run_count = len(runs)
        if runs:
            last = runs[-1]
            last_str = f"{last.get('passed', 0)}/{last.get('total', 0)}"
        else:
            last_str = "—"
        print(f"{test_id:<40} {title:<45} {run_count:>5}  {last_str:>10}")


def _load_test_module(module_name):
    """Load a rerunnable test module from interactions/tests/."""
    import importlib.util
    mod_path = os.path.join(SCRIPT_DIR, '..', 'scripts', 'interactions', 'tests', f'{module_name}.py')
    if not os.path.isfile(mod_path):
        # Try from SCRIPT_DIR directly
        mod_path = os.path.join(SCRIPT_DIR, 'interactions', 'tests', f'{module_name}.py')
    if not os.path.isfile(mod_path):
        print(f"ERROR: module '{module_name}' not found in interactions/tests/")
        return None
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, 'get_test_config'):
        return mod.get_test_config()
    return {
        'test_id': getattr(mod, 'TEST_ID', module_name),
        'title': getattr(mod, 'TITLE', module_name),
        'title_fr': getattr(mod, 'TITLE_FR', ''),
        'slug': getattr(mod, 'SLUG', module_name),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Persist test runs to dashboard history files"
    )
    parser.add_argument("--test-id", help="Test identifier (e.g. tests-interface-no-tab-bar)")
    parser.add_argument("--title", help="Test title (EN)")
    parser.add_argument("--title-fr", help="Test title (FR)")
    parser.add_argument("--slug", help="Publication slug (e.g. test-tests-interface-no-tab-bar)")
    parser.add_argument("--module", help="Load config from rerunnable test module in interactions/tests/")

    # Run data — from results file
    parser.add_argument("--results", help="Path to results JSON (web_test_engine output)")

    # Run data — explicit values
    parser.add_argument("--mode", help="Test mode (DEFAULT, COMPLETE, VERIFICATION, etc.)")
    parser.add_argument("--total", type=int, help="Total checks")
    parser.add_argument("--passed", type=int, help="Passed checks")
    parser.add_argument("--failed", type=int, help="Failed checks")
    parser.add_argument("--pages", help="Pages JSON dict string (optional)")
    parser.add_argument("--timestamp", help="ISO timestamp (defaults to now)")

    # Proof artifact
    parser.add_argument("--proof", help="Path to proof GIF (default: auto-detect from test-reports/)")

    # Sync mode
    parser.add_argument("--sync-from-runs", help="Path to local runs.json to sync from")

    # List / Backfill / Distribution check
    parser.add_argument("--list", action="store_true", help="List all tests in history")
    parser.add_argument("--backfill", action="store_true",
                        help="Backfill local runs.json from dashboard history + sync fallback")
    parser.add_argument("--check-distribution", action="store_true",
                        help="Check Publication Gate distribution status for a test (requires --slug)")

    args = parser.parse_args()

    if args.list:
        list_tests()
        return 0

    if args.backfill:
        backfill_local()
        return 0

    if args.check_distribution:
        if not args.slug:
            print("ERROR: --slug required with --check-distribution")
            return 1
        status = check_distribution(args.slug, args.title)
        print(f"\n  Publication Gate — distribution status for '{args.slug}':\n")
        all_ok = True
        for surface, ok in status.items():
            if ok is None:
                icon = "-"
                label = "N/A"
            elif ok:
                icon = "x"
                label = "registered"
            else:
                icon = " "
                label = "MISSING"
                all_ok = False
            print(f"  [{icon}] {surface:<20} {label}")
        print()
        if all_ok:
            print("  All surfaces registered.")
        else:
            print("  INCOMPLETE — run persist_test_run.py to complete distribution.")
        return 0 if all_ok else 1

    if args.sync_from_runs:
        if not args.test_id:
            print("ERROR: --test-id required with --sync-from-runs")
            return 1
        ok = sync_from_runs(args.test_id, args.sync_from_runs,
                           args.title, args.title_fr, args.slug)
        return 0 if ok else 1

    # Module mode — load config from module
    if args.module:
        cfg = _load_test_module(args.module)
        if not cfg:
            return 1
        if not args.test_id:
            args.test_id = cfg.get('test_id')
        if not args.title:
            args.title = cfg.get('title')
        if not args.title_fr:
            args.title_fr = cfg.get('title_fr', '')
        if not args.slug:
            args.slug = cfg.get('slug')

    if not args.test_id:
        parser.print_help()
        return 1

    # Build run summary
    if args.results and os.path.isfile(args.results):
        with open(args.results) as f:
            data = json.load(f)
        run_summary = {
            "timestamp": data.get("timestamp", args.timestamp or datetime.now().isoformat()),
            "mode": data.get("mode", args.mode or "DEFAULT"),
            "total": data.get("total", args.total or 0),
            "passed": data.get("passed", args.passed or 0),
            "failed": data.get("failed", args.failed or 0),
        }
        # Build pages map from default results if available
        if "default" in data and not args.pages:
            pages = {}
            for r in data["default"]:
                key = r.get("doc") or r.get("target") or f"check-{r.get('num', 0)}"
                pages[key] = r.get("result", "FAIL")
            if pages:
                run_summary["pages"] = pages
    elif args.total is not None:
        run_summary = {
            "timestamp": args.timestamp or datetime.now().isoformat(),
            "mode": args.mode or "DEFAULT",
            "total": args.total,
            "passed": args.passed or 0,
            "failed": args.failed or 0,
        }
        if args.pages:
            try:
                run_summary["pages"] = json.loads(args.pages)
            except json.JSONDecodeError:
                pass
    else:
        print("ERROR: Provide --results or --total/--passed/--failed")
        return 1

    print(f"Persisting run for '{args.test_id}':")
    print(f"  Mode: {run_summary['mode']} | {run_summary['passed']}/{run_summary['total']} pass")

    persist_run(args.test_id, args.title or args.test_id,
                args.title_fr, args.slug or args.test_id, run_summary,
                proof_source=args.proof)

    return 0


if __name__ == "__main__":
    sys.exit(main())
