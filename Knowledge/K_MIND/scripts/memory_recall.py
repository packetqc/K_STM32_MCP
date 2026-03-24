#!/usr/bin/env python3
"""
memory_recall.py — Recall archived memory by subject keyword.

Searches the archives index in far_memory.json and near_memory summaries
to find and return relevant conversation history.

Usage:
    python3 scripts/memory_recall.py --subject "architecture"
    python3 scripts/memory_recall.py --subject "theme" --full
    python3 scripts/memory_recall.py --list

Options:
    --list      List all archived topics
    --subject   Keyword to search for in topic names and near_memory summaries
    --full      Show full archived messages (default: show summaries only)
"""

import argparse
import json
import os

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'sessions')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def load_archive_index():
    if os.path.exists(ARCHIVE_INDEX):
        try:
            with open(ARCHIVE_INDEX, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {'archives': []}


def list_archives(far_data):
    index_data = load_archive_index()
    archives = index_data.get('archives', [])
    if not archives:
        print("No archived topics yet.")
        return
    print(f"Archived topics ({len(archives)}):")
    for a in archives:
        source = a.get('source', a.get('quantum_source', ''))
        source_tag = f" [source:{source}]" if source else ""
        print(f"  [{a['topic']}] messages {a['message_range']} | near {a['near_memory_range']} -> {a['file']}{source_tag}")


def search_archives(far_data, near_data, subject, full=False):
    subject_lower = subject.lower()
    found = False

    index_data = load_archive_index()

    # Search archive index (topic name + source + legacy_category)
    for archive in index_data.get('archives', []):
        topic_match = subject_lower in archive['topic'].lower()
        source_match = subject_lower in archive.get('source', '').lower()
        cat_match = subject_lower in archive.get('legacy_category', '').lower()
        if topic_match or source_match or cat_match:
            found = True
            source = archive.get('source', archive.get('quantum_source', ''))
            source_tag = f" [source:{source}]" if source else ""
            print(f"\n=== ARCHIVED TOPIC: {archive['topic']}{source_tag} ===")
            print(f"    messages: {archive['message_range']}, near: {archive['near_memory_range']}")

            # Show relevant near_memory summaries (check embedded in archive first, then active near_memory)
            archive_path = os.path.join(SESSIONS_DIR, archive['file'])
            embedded_summaries = []
            if os.path.exists(archive_path):
                try:
                    archive_file = load_json(archive_path)
                    embedded_summaries = archive_file.get('summaries', [])
                except (json.JSONDecodeError, KeyError):
                    pass

            if embedded_summaries:
                for s in embedded_summaries:
                    print(f"  [near:{s['id']}] {s['summary']}")
            else:
                start_near, end_near = archive['near_memory_range']
                for s in near_data.get('summaries', []):
                    if start_near <= s['id'] <= end_near:
                        print(f"  [near:{s['id']}] {s['summary']}")

            # Show full messages if requested
            if full:
                archive_path = os.path.join(SESSIONS_DIR, archive['file'])
                if os.path.exists(archive_path):
                    archive_data = load_json(archive_path)
                    print(f"\n  --- Full messages ({len(archive_data['messages'])}) ---")
                    for m in archive_data['messages']:
                        print(f"  [far:{m['id']}] {m['role']}: {m['content'][:200]}")

    # Also search near_memory summaries for matches in active memory
    for s in near_data.get('summaries', []):
        if subject_lower in s['summary'].lower():
            # Check if this summary is in an already-shown archive range
            in_archive = False
            for archive in index_data.get('archives', []):
                start_near, end_near = archive['near_memory_range']
                if start_near <= s['id'] <= end_near:
                    in_archive = True
                    break
            if not in_archive:
                if not found:
                    print(f"\n=== ACTIVE MEMORY matches for '{subject}' ===")
                found = True
                source = s.get('source', '')
                source_tag = f" [source:{source}]" if source else ""
                legacy_file = s.get('legacy_file', '')
                file_tag = f" ({legacy_file})" if legacy_file else ""
                print(f"  [near:{s['id']}] {s['summary']}{source_tag}{file_tag}")
                print(f"    far_refs: {s['far_memory_refs']}")

    # Also search ephemeral captures (plans, todos)
    for m in far_data.get('messages', []):
        if m.get('type') in ('plan', 'todo') and subject_lower in m['content'].lower():
            if not found:
                print(f"\n=== EPHEMERAL CAPTURES matching '{subject}' ===")
            found = True
            label = 'PLAN' if m.get('type') == 'plan' else 'TODO'
            print(f"  [far:{m['id']}] [{label}] {m['content'][:200]}")

    if not found:
        print(f"No memories found matching '{subject}'")


def main():
    parser = argparse.ArgumentParser(description='Recall memory by subject')
    parser.add_argument('--subject', help='Subject keyword to search')
    parser.add_argument('--list', action='store_true', help='List all archived topics')
    parser.add_argument('--full', action='store_true', help='Show full archived messages')
    args = parser.parse_args()

    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    if args.list:
        list_archives(far_data)
    elif args.subject:
        search_archives(far_data, near_data, args.subject, args.full)
    else:
        print("Use --list to see archived topics or --subject to search")


if __name__ == '__main__':
    main()
