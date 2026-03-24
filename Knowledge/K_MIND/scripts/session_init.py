#!/usr/bin/env python3
"""
session_init.py — Initialize a new K_MIND session.

Creates fresh session files while preserving archives and mind_memory.
Called by Claude on new session start (bootstrap phase).

Usage:
    python3 scripts/session_init.py --session-id "Ka00B"
    python3 scripts/session_init.py --session-id "Ka00B" --preserve-active

Options:
    --preserve-active   Keep active messages in far_memory (for resume, not new session)
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')
ROUTING_STACK = os.path.join(SESSIONS_DIR, 'routing_stack.json')
DEPTH_CONFIG = os.path.join(BASE_DIR, 'conventions', 'depth_config.json')


def load_near_memory_window():
    """Load near_memory_window from depth_config.json (default 35)."""
    if os.path.exists(DEPTH_CONFIG):
        try:
            with open(DEPTH_CONFIG) as f:
                cfg = json.load(f)
            return cfg.get('near_memory_window', 35)
        except (json.JSONDecodeError, KeyError):
            pass
    return 35


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  written: {path}")


def topic_to_slug(topic):
    slug = topic.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug


def load_archive_index():
    """Load archive index from dedicated file."""
    if os.path.exists(ARCHIVE_INDEX):
        try:
            return load_json(ARCHIVE_INDEX)
        except (json.JSONDecodeError, KeyError):
            pass
    return {'archives': []}


def save_archive_index(index_data):
    """Save archive index to dedicated file."""
    save_json(ARCHIVE_INDEX, index_data)


def auto_archive_previous_session(far_data, near_data, index_data):
    """Auto-archive any existing messages before wiping for a new session."""
    messages = far_data.get('messages', [])
    if not messages:
        return 0

    old_session_id = far_data.get('session_id', 'unknown')
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    topic = f"session-{old_session_id}"
    slug = topic_to_slug(topic)
    archive_filename = f"far_memory_{slug}_{timestamp}.json"
    archive_path = os.path.join(ARCHIVES_DIR, archive_filename)

    msg_ids = [m['id'] for m in messages]
    start_msg, end_msg = min(msg_ids), max(msg_ids)

    summaries = near_data.get('summaries', [])
    if summaries:
        near_ids = [s['id'] for s in summaries]
        start_near, end_near = min(near_ids), max(near_ids)
    else:
        start_near, end_near = 0, 0

    archive_data = {
        'topic': topic,
        'session_id': old_session_id,
        'message_range': [start_msg, end_msg],
        'near_memory_range': [start_near, end_near],
        'messages': messages,
        'summaries': summaries
    }
    save_json(archive_path, archive_data)

    # Update archive index (separate file)
    index_data['archives'].append({
        'file': f"archives/{archive_filename}",
        'topic': topic,
        'message_range': [start_msg, end_msg],
        'near_memory_range': [start_near, end_near]
    })

    print(f"  auto-archived: {len(messages)} messages, {len(summaries)} summaries -> {archive_filename}")
    return len(messages)


def main():
    parser = argparse.ArgumentParser(description='Initialize K_MIND session')
    parser.add_argument('--session-id', required=True, help='New session identifier')
    parser.add_argument('--preserve-active', action='store_true',
                        help='Keep active messages (for resume)')
    args = parser.parse_args()

    os.makedirs(ARCHIVES_DIR, exist_ok=True)

    # Load existing files if present
    old_far = {'messages': []}
    old_near = {'summaries': []}
    if os.path.exists(FAR_MEMORY):
        try:
            old_far = load_json(FAR_MEMORY)
        except (json.JSONDecodeError, KeyError):
            pass
    if os.path.exists(NEAR_MEMORY):
        try:
            old_near = load_json(NEAR_MEMORY)
        except (json.JSONDecodeError, KeyError):
            pass

    # Load archive index (separate file)
    index_data = load_archive_index()

    # Resume mode: keep active messages, just update session_id
    if args.preserve_active:
        old_far['session_id'] = args.session_id
        save_json(FAR_MEMORY, old_far)
        old_near['session_id'] = args.session_id
        save_json(NEAR_MEMORY, old_near)
        pinned_count = len(old_near.get('pinned', []))
        print(f"OK: resumed session {args.session_id} (active messages preserved)")
        if pinned_count:
            print(f"    pinned: {pinned_count} entries preserved")
        return

    # Fresh session: auto-archive previous conversation before wiping
    archived_count = auto_archive_previous_session(old_far, old_near, index_data)

    # Capture last session summaries for continuity (windowed from config)
    nm_window = load_near_memory_window()
    last_session_summaries = old_near.get('summaries', [])[-nm_window:]
    last_session_id = old_near.get('session_id', None)
    # Pinned entries survive across sessions — never archived
    pinned = old_near.get('pinned', [])
    # WIP context carries forward (cleared on fresh session, preserved on resume)
    wip_context = {}

    # New session: fresh files (archive index is separate)
    far_data = {
        'session_id': args.session_id,
        'messages': [],
    }
    save_json(FAR_MEMORY, far_data)

    near_data = {
        'session_id': args.session_id,
        'pinned': pinned,
        'wip_context': wip_context,
        'summaries': []
    }
    # Carry forward last session context for continuity on start (windowed)
    if last_session_summaries:
        near_data['last_session'] = {
            'session_id': last_session_id,
            'summaries': last_session_summaries
        }
    save_json(NEAR_MEMORY, near_data)

    # Save archive index (updated by auto_archive if needed)
    save_archive_index(index_data)

    # Reset routing stack for fresh session
    if os.path.exists(ROUTING_STACK):
        os.remove(ROUTING_STACK)

    print(f"OK: initialized session {args.session_id}")
    print(f"    archives preserved: {len(index_data['archives'])}")
    if archived_count > 0:
        print(f"    auto-archived previous session: {archived_count} messages")
    print(f"    far_memory: empty (fresh)")
    print(f"    near_memory: empty (fresh)")
    if pinned:
        print(f"    pinned: {len(pinned)} entries preserved across sessions")
    if last_session_summaries:
        print(f"    last_session: {len(last_session_summaries)} summaries carried forward from {last_session_id}")


if __name__ == '__main__':
    main()
