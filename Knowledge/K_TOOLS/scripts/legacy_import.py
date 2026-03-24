#!/usr/bin/env python3
"""
legacy_import.py — Import legacy v1 memory into K_MIND.

Scans the Knowledge/legacy/ folder for session notes, minds, methodology,
session runtimes, and lessons/patterns. Converts them into K_MIND far_memory
messages and near_memory summaries, archived by topic category.

All imported entries are tagged with source: "legacy" for traceability.

Usage:
    python3 scripts/legacy_import.py --list
    python3 scripts/legacy_import.py --dry
    python3 scripts/legacy_import.py
    python3 scripts/legacy_import.py --category session-notes
    python3 scripts/legacy_import.py --category minds
    python3 scripts/legacy_import.py --category methodology

Categories:
    session-notes     — Session note markdown files (knowledge/data/notes/)
    minds             — Mind/synthesis files (knowledge/data/minds/)
    methodology       — Methodology files (knowledge/methodology/)
    lessons-patterns  — Lessons and patterns (knowledge/methodology/lessons/ + patterns/)
    session-runtimes  — Session runtime JSON files (knowledge/state/sessions/)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# Path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.join(SCRIPT_DIR, '..')  # K_TOOLS
KNOWLEDGE_ROOT = os.path.join(MODULE_ROOT, '..')  # Knowledge/
K_MIND_ROOT = os.path.join(KNOWLEDGE_ROOT, 'K_MIND')
LEGACY_ROOT = os.path.join(KNOWLEDGE_ROOT, 'legacy')

SESSIONS_DIR = os.path.join(K_MIND_ROOT, 'sessions')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')

# Category definitions: (label, relative_path_from_legacy, file_pattern, file_type)
CATEGORIES = {
    'session-notes': {
        'label': 'Legacy Session Notes (v1)',
        'path': 'knowledge/data/notes',
        'pattern': r'.*\.md$',
        'type': 'markdown',
        'role': 'legacy-session-note',
    },
    'minds': {
        'label': 'Legacy Mind Files (v1)',
        'path': 'knowledge/data/minds',
        'pattern': r'.*\.md$',
        'type': 'markdown',
        'role': 'legacy-mind',
    },
    'methodology': {
        'label': 'Legacy Methodology (v1)',
        'path': 'knowledge/methodology',
        'pattern': r'^[^/]+\.md$',  # Top-level .md only
        'type': 'markdown',
        'role': 'legacy-methodology',
    },
    'lessons-patterns': {
        'label': 'Legacy Lessons & Patterns (v1)',
        'path': 'knowledge/methodology',
        'pattern': r'(lessons|patterns)/.*\.md$',
        'type': 'markdown',
        'role': 'legacy-lesson-pattern',
    },
    'session-runtimes': {
        'label': 'Legacy Session Runtimes (v1)',
        'path': 'knowledge/state/sessions',
        'pattern': r'session-runtime-.*\.json$',
        'type': 'json',
        'role': 'legacy-session-runtime',
    },
}


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def read_file(path):
    with open(path, 'r', errors='replace') as f:
        return f.read()


def extract_date_from_filename(filename):
    """Extract date from filenames like session-2026-02-17.md or session-runtime-0gnLF.json."""
    m = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if m:
        return m.group(1) + 'T00:00:00Z'
    return None


def extract_date_from_json(data):
    """Extract date from session runtime JSON."""
    for key in ('created', 'updated', 'started_at'):
        val = data.get(key) or (data.get('session_data', {}).get('task_workflow', {}) or {}).get(key)
        if val:
            return val
    return None


def summarize_session_note(content, filename):
    """Generate a one-line summary from a session note markdown."""
    lines = content.strip().split('\n')
    # Use the first heading as title
    title = filename
    for line in lines[:5]:
        if line.startswith('# '):
            title = line.lstrip('# ').strip()
            break
    # Count sections
    sections = [l for l in lines if l.startswith('## ')]
    return f"{title} ({len(sections)} sections, {len(lines)} lines)"


def summarize_mind_file(content, filename):
    """Generate a one-line summary from a mind file."""
    lines = content.strip().split('\n')
    title = filename
    for line in lines[:5]:
        if line.startswith('# '):
            title = line.lstrip('# ').strip()
            break
    return f"Mind: {title} ({len(lines)} lines)"


def summarize_methodology(content, filename):
    """Generate a one-line summary from a methodology file."""
    lines = content.strip().split('\n')
    title = filename
    for line in lines[:5]:
        if line.startswith('# '):
            title = line.lstrip('# ').strip()
            break
    return f"Methodology: {title} ({len(lines)} lines)"


def summarize_session_runtime(data, filename):
    """Generate a one-line summary from a session runtime JSON."""
    sid = data.get('session_id', 'unknown')
    issue = data.get('issue_title', data.get('issue_number', ''))
    mode = data.get('mode', '')
    branch = data.get('branch', '')
    parts = [f"Runtime {sid}"]
    if issue:
        parts.append(f"issue={issue}")
    if mode:
        parts.append(f"mode={mode}")
    if branch:
        parts.append(f"branch={branch}")
    return ' | '.join(parts)


def collect_files(category_key):
    """Collect all files for a given category."""
    cat = CATEGORIES[category_key]
    base_path = os.path.join(LEGACY_ROOT, cat['path'])
    if not os.path.isdir(base_path):
        return []

    files = []
    for root, dirs, filenames in os.walk(base_path):
        for fname in sorted(filenames):
            rel = os.path.relpath(os.path.join(root, fname), base_path)
            if re.match(cat['pattern'], rel):
                files.append(os.path.join(root, fname))
    return sorted(files)


def load_archive_index():
    if os.path.exists(ARCHIVE_INDEX):
        try:
            return load_json(ARCHIVE_INDEX)
        except (json.JSONDecodeError, KeyError):
            pass
    return {'archives': []}


def check_already_imported(index_data, far_data, category_key):
    """Check if legacy data for this category already exists in archives."""
    for archive in index_data.get('archives', []):
        topic = archive.get('topic', '')
        if 'legacy' in topic.lower() and category_key.replace('-', ' ') in topic.lower():
            return True
        if archive.get('quantum_source', '').startswith('legacy'):
            return True
    for m in far_data.get('messages', []):
        if m.get('source') == 'legacy' and m.get('legacy_category') == category_key:
            return True
    return False


def list_legacy():
    """List all legacy content available for import."""
    print("## Legacy v1 Memory — Available for Import\n")
    print("| Category | Files | Path |")
    print("|:---------|:------|:-----|")

    total = 0
    for key, cat in CATEGORIES.items():
        files = collect_files(key)
        total += len(files)
        print(f"| {cat['label']} | {len(files)} | `{cat['path']}` |")

    print(f"\n**Total legacy files: {total}**")
    print(f"\nLegacy root: `{os.path.relpath(LEGACY_ROOT)}`")

    # Show sample files per category
    for key, cat in CATEGORIES.items():
        files = collect_files(key)
        if files:
            print(f"\n### {cat['label']} ({len(files)} files)")
            for f in files[:10]:
                fname = os.path.basename(f)
                size = os.path.getsize(f)
                print(f"  - `{fname}` ({size:,} bytes)")
            if len(files) > 10:
                print(f"  - ... and {len(files) - 10} more")


def dry_run(index_data, far_data, near_data, categories_to_import):
    """Preview what would be imported without writing."""
    max_far_id = max((m['id'] for m in far_data.get('messages', [])), default=0)
    max_near_id = max((s['id'] for s in near_data.get('summaries', [])), default=0)

    print("## Legacy Import Preview (dry run)\n")
    print("| Category | Files | Far IDs | Archive |")
    print("|:---------|:------|:--------|:--------|")

    running_far = max_far_id
    running_near = max_near_id
    total_files = 0

    for key in categories_to_import:
        files = collect_files(key)
        cat = CATEGORIES[key]
        if not files:
            continue

        start_far = running_far + 1
        end_far = running_far + len(files)
        start_near = running_near + 1
        end_near = running_near + len(files)
        archive_name = f"legacy_{key.replace('-', '_')}"

        already = check_already_imported(index_data, far_data, key)
        status = " **(already imported)**" if already else ""

        print(f"| {cat['label']} | {len(files)} | {start_far}..{end_far} | `{archive_name}.json`{status} |")
        running_far = end_far
        running_near = end_near
        total_files += len(files)

    print(f"\n**Total: {total_files} files → {total_files} far_memory messages + {total_files} near_memory summaries**")
    print(f"All entries tagged with `source: \"legacy\"` for traceability.")


def execute_import(index_data, far_data, near_data, categories_to_import):
    """Import legacy files into K_MIND archives. Summaries stay in archive files only (not active near_memory)."""
    os.makedirs(ARCHIVES_DIR, exist_ok=True)

    max_far_id = max((m['id'] for m in far_data.get('messages', [])), default=0)
    max_near_id = max((s['id'] for s in near_data.get('summaries', [])), default=0)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    total_imported = 0
    archive_entries = []

    for key in categories_to_import:
        files = collect_files(key)
        cat = CATEGORIES[key]
        if not files:
            print(f"  SKIP {cat['label']}: no files found")
            continue

        if check_already_imported(index_data, far_data, key):
            print(f"  SKIP {cat['label']}: already imported")
            continue

        # Build messages and summaries for this category
        category_msgs = []
        category_summaries = []
        start_far_id = max_far_id + 1
        start_near_id = max_near_id + 1

        for filepath in files:
            fname = os.path.basename(filepath)
            rel_path = os.path.relpath(filepath, LEGACY_ROOT)

            max_far_id += 1
            max_near_id += 1

            if cat['type'] == 'json':
                try:
                    file_data = load_json(filepath)
                    content = json.dumps(file_data, indent=2, ensure_ascii=False)
                    timestamp = extract_date_from_json(file_data) or now
                    summary = summarize_session_runtime(file_data, fname)
                except (json.JSONDecodeError, KeyError):
                    content = read_file(filepath)
                    timestamp = extract_date_from_filename(fname) or now
                    summary = f"Legacy runtime: {fname}"
            else:
                content = read_file(filepath)
                timestamp = extract_date_from_filename(fname) or now
                if key == 'session-notes':
                    summary = summarize_session_note(content, fname)
                elif key == 'minds':
                    summary = summarize_mind_file(content, fname)
                else:
                    summary = summarize_methodology(content, fname)

            # Far memory message
            msg = {
                'id': max_far_id,
                'role': cat['role'],
                'content': content,
                'timestamp': timestamp,
                'source': 'legacy',
                'legacy_category': key,
                'legacy_file': rel_path,
            }
            category_msgs.append(msg)

            # Near memory summary (stored in archive only, not active near_memory)
            s = {
                'id': max_near_id,
                'summary': summary,
                'far_memory_refs': [max_far_id],
                'mind_memory_refs': [],
                'timestamp': timestamp,
                'source': 'legacy',
                'legacy_category': key,
                'legacy_file': rel_path,
            }
            category_summaries.append(s)

        end_far_id = max_far_id
        end_near_id = max_near_id

        # Write archive file directly (messages + summaries embedded)
        archive_slug = f"legacy_{key.replace('-', '_')}"
        archive_filename = f"far_memory_{archive_slug}.json"
        archive_path = os.path.join(ARCHIVES_DIR, archive_filename)

        archive_data = {
            'topic': cat['label'],
            'source': 'legacy',
            'legacy_category': key,
            'imported_at': now,
            'file_count': len(files),
            'message_range': [start_far_id, end_far_id],
            'near_memory_range': [start_near_id, end_near_id],
            'messages': category_msgs,
            'summaries': category_summaries,
        }
        save_json(archive_path, archive_data)

        # Add archive index entry (separate from far_memory)
        archive_entries.append({
            'file': f"archives/{archive_filename}",
            'topic': cat['label'],
            'source': 'legacy',
            'legacy_category': key,
            'message_range': [start_far_id, end_far_id],
            'near_memory_range': [start_near_id, end_near_id],
        })

        # Summaries stay in archive files only — NOT added to active near_memory
        # This keeps near_memory lean for current session use

        total_imported += len(files)
        print(f"  OK {cat['label']}: {len(files)} files → {archive_filename}")

    # Update archive index (separate file)
    index_data.setdefault('archives', []).extend(archive_entries)
    save_json(ARCHIVE_INDEX, index_data)

    # Report
    print(f"\n## Legacy Import Complete\n")
    print(f"| Metric | Value |")
    print(f"|:-------|:------|")
    print(f"| Files imported | {total_imported} |")
    print(f"| Archive files created | {len(archive_entries)} |")
    print(f"| Summaries (in archives) | {total_imported} |")
    print(f"| Source tag | `source: \"legacy\"` |")
    print(f"| Legacy root | `{os.path.relpath(LEGACY_ROOT)}` |")
    print(f"\nAll entries tagged with `source: \"legacy\"` and `legacy_category` for traceability.")
    print(f"Summaries embedded in archive files (not in active near_memory).")
    print(f"Use `python3 scripts/memory_recall.py --subject legacy` to search imported memories.")


def main():
    parser = argparse.ArgumentParser(
        description='Legacy v1 memory import into K_MIND')
    parser.add_argument('--list', action='store_true',
                        help='List legacy content available for import')
    parser.add_argument('--dry', action='store_true',
                        help='Preview what would be imported (no writes)')
    parser.add_argument('--category', choices=list(CATEGORIES.keys()),
                        help='Import only a specific category')
    args = parser.parse_args()

    if not os.path.isdir(LEGACY_ROOT):
        print(f"ERROR: Legacy root not found: {LEGACY_ROOT}")
        sys.exit(1)

    if args.list:
        list_legacy()
        return

    # Determine categories to import
    if args.category:
        categories = [args.category]
    else:
        categories = list(CATEGORIES.keys())

    # Load local memory and archive index
    index_data = load_archive_index()
    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    if args.dry:
        dry_run(index_data, far_data, near_data, categories)
        return

    execute_import(index_data, far_data, near_data, categories)


if __name__ == '__main__':
    main()
