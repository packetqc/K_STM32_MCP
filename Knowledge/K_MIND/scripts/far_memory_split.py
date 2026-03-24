#!/usr/bin/env python3
"""
far_memory_split.py — Archive completed conversation topics from far_memory.

Claude identifies topic boundaries and calls this script with the topic info.
The script handles all file extraction and index management.

Usage:
    python3 scripts/far_memory_split.py \
        --topic "Architecture Design" \
        --start-msg 1 --end-msg 24 \
        --start-near 1 --end-near 7

This extracts messages 1-24 into an archive file and updates the index.
"""

import argparse
import json
import os
import re

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'sessions')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')


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


def main():
    parser = argparse.ArgumentParser(description='Archive a topic from far_memory')
    parser.add_argument('--topic', required=True, help='Human-readable topic name')
    parser.add_argument('--start-msg', type=int, required=True, help='First message ID to archive')
    parser.add_argument('--end-msg', type=int, required=True, help='Last message ID to archive')
    parser.add_argument('--start-near', type=int, required=True, help='First near_memory ID in range')
    parser.add_argument('--end-near', type=int, required=True, help='Last near_memory ID in range')
    args = parser.parse_args()

    os.makedirs(ARCHIVES_DIR, exist_ok=True)

    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    # Load archive index (separate from far_memory)
    if os.path.exists(ARCHIVE_INDEX):
        index_data = load_json(ARCHIVE_INDEX)
    else:
        index_data = {'archives': []}

    # Extract messages in range
    archived_messages = [
        m for m in far_data['messages']
        if args.start_msg <= m['id'] <= args.end_msg
    ]

    if not archived_messages:
        print(f"ERROR: No messages found in range {args.start_msg}-{args.end_msg}")
        return

    # Extract near_memory summaries in range
    archived_summaries = [
        s for s in near_data.get('summaries', [])
        if args.start_near <= s['id'] <= args.end_near
    ]

    # Create archive file (with embedded summaries)
    slug = topic_to_slug(args.topic)
    archive_filename = f"far_memory_{slug}.json"
    archive_path = os.path.join(ARCHIVES_DIR, archive_filename)

    archive_data = {
        'topic': args.topic,
        'session_id': far_data.get('session_id', 'unknown'),
        'message_range': [args.start_msg, args.end_msg],
        'near_memory_range': [args.start_near, args.end_near],
        'messages': archived_messages,
        'summaries': archived_summaries,
    }
    save_json(archive_path, archive_data)

    # Remove archived messages from far_memory
    far_data['messages'] = [
        m for m in far_data['messages']
        if m['id'] < args.start_msg or m['id'] > args.end_msg
    ]
    save_json(FAR_MEMORY, far_data)

    # Remove archived summaries from near_memory
    near_data['summaries'] = [
        s for s in near_data.get('summaries', [])
        if s['id'] < args.start_near or s['id'] > args.end_near
    ]
    save_json(NEAR_MEMORY, near_data)

    # Update archive index (separate file)
    index_data['archives'].append({
        'file': f"archives/{archive_filename}",
        'topic': args.topic,
        'message_range': [args.start_msg, args.end_msg],
        'near_memory_range': [args.start_near, args.end_near]
    })
    save_json(ARCHIVE_INDEX, index_data)

    print(f"OK: archived {len(archived_messages)} messages + {len(archived_summaries)} summaries to {archive_filename}")
    print(f"    topic: {args.topic}")
    print(f"    messages: {args.start_msg}-{args.end_msg}")
    print(f"    near_memory: {args.start_near}-{args.end_near}")


if __name__ == '__main__':
    main()
