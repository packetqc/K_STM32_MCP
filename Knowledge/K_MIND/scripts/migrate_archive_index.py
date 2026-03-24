#!/usr/bin/env python3
"""
migrate_archive_index.py — One-time migration: extract archive index from far_memory.json.

Creates sessions/archive_index.json with all archive entries.
Removes 'archives' key from far_memory.json.
Cleans near_memory.json by removing summaries that exist in archive files.

This reduces far_memory.json from ~264KB to <1KB and near_memory.json
by removing fully-archived summaries.

Usage:
    python3 scripts/migrate_archive_index.py
    python3 scripts/migrate_archive_index.py --dry
"""

import argparse
import json
import os
import sys

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'sessions')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f"  written: {path} ({os.path.getsize(path):,} bytes)")


def main():
    parser = argparse.ArgumentParser(description='Migrate archive index from far_memory')
    parser.add_argument('--dry', action='store_true', help='Preview only')
    args = parser.parse_args()

    if not os.path.exists(FAR_MEMORY):
        print("ERROR: far_memory.json not found")
        sys.exit(1)

    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    archives = far_data.get('archives', [])
    messages = far_data.get('messages', [])
    summaries = near_data.get('summaries', [])

    fm_size_before = os.path.getsize(FAR_MEMORY)
    nm_size_before = os.path.getsize(NEAR_MEMORY)

    # Build set of near_memory ID ranges that are fully archived
    # (their summaries exist in archive files with embedded summaries)
    archived_near_ids = set()
    for archive_entry in archives:
        archive_path = os.path.join(SESSIONS_DIR, archive_entry['file'])
        if os.path.exists(archive_path):
            try:
                archive_file = load_json(archive_path)
                embedded = archive_file.get('summaries', [])
                if embedded:
                    for s in embedded:
                        archived_near_ids.add(s['id'])
            except (json.JSONDecodeError, KeyError):
                pass

    # Summaries to keep: those NOT in any archive's embedded summaries
    kept_summaries = [s for s in summaries if s['id'] not in archived_near_ids]
    removed_count = len(summaries) - len(kept_summaries)

    print(f"## Archive Index Migration\n")
    print(f"| Metric | Before | After |")
    print(f"|:-------|:-------|:------|")
    print(f"| far_memory.json | {fm_size_before:,} bytes | ~{len(json.dumps({'session_id': far_data.get('session_id', ''), 'messages': messages})):,} bytes |")
    print(f"| archive_index.json | (new) | ~{len(json.dumps({'archives': archives})):,} bytes |")
    print(f"| archive entries | {len(archives)} in far_memory | {len(archives)} in archive_index |")
    print(f"| near_memory summaries | {len(summaries)} | {len(kept_summaries)} (removed {removed_count} archived) |")
    print(f"| near_memory.json | {nm_size_before:,} bytes | ~{len(json.dumps({'session_id': near_data.get('session_id', ''), 'summaries': kept_summaries})):,} bytes |")

    # Token savings estimate
    old_fm_tokens = fm_size_before // 4
    new_fm_size = len(json.dumps({'session_id': far_data.get('session_id', ''), 'messages': messages}))
    new_fm_tokens = new_fm_size // 4
    saved = old_fm_tokens - new_fm_tokens
    print(f"| **Token savings (conversation)** | ~{old_fm_tokens:,} | ~{new_fm_tokens:,} (**saved ~{saved:,}**) |")

    if args.dry:
        print(f"\n(dry run — no files written)")
        return

    # Write archive_index.json
    save_json(ARCHIVE_INDEX, {'archives': archives})

    # Update far_memory.json (remove archives key)
    slim_far = {
        'session_id': far_data.get('session_id', ''),
        'messages': messages,
    }
    save_json(FAR_MEMORY, slim_far)

    # Update near_memory.json (remove archived summaries)
    slim_near = {
        'session_id': near_data.get('session_id', ''),
        'summaries': kept_summaries,
    }
    # Preserve last_session if present
    if 'last_session' in near_data:
        slim_near['last_session'] = near_data['last_session']
    save_json(NEAR_MEMORY, slim_near)

    print(f"\nMigration complete.")
    print(f"  archive_index.json created with {len(archives)} entries")
    print(f"  far_memory.json slimmed: {fm_size_before:,} → {os.path.getsize(FAR_MEMORY):,} bytes")
    print(f"  near_memory.json cleaned: {nm_size_before:,} → {os.path.getsize(NEAR_MEMORY):,} bytes")


if __name__ == '__main__':
    main()
