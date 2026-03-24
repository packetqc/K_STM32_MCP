#!/usr/bin/env python3
"""
capture_ephemeral.py — Capture ephemeral Claude Code artifacts (plans, todos)
into K_MIND memory for persistence across compaction and session boundaries.

Claude Code stores plans in .claude/plans/ as markdown files and todos are
in-session only. Both are lost on compaction/session end. This script captures
them into far_memory + near_memory so they survive and become recallable.

Usage:
    # Scan and capture all plans from .claude/plans/
    python3 scripts/capture_ephemeral.py --plans

    # Capture current todo state (pass JSON via stdin)
    python3 scripts/capture_ephemeral.py --todos --stdin

    # Capture both plans + todos from stdin
    python3 scripts/capture_ephemeral.py --plans --todos --stdin

    # List previously captured ephemeral artifacts
    python3 scripts/capture_ephemeral.py --list

    # Recall captured plans/todos by keyword
    python3 scripts/capture_ephemeral.py --recall "elevation"

Stdin JSON format for todos:
    {"todos": [{"content": "task desc", "status": "completed", "activeForm": "..."}]}
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
K_MIND_ROOT = os.path.join(SCRIPT_DIR, '..')
SESSIONS_DIR = os.path.join(K_MIND_ROOT, 'sessions')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
EPHEMERAL_DIR = os.path.join(SESSIONS_DIR, 'ephemeral')

# Walk up to find project root (where .claude/ lives)
PROJECT_ROOT = os.path.abspath(os.path.join(K_MIND_ROOT, '..', '..'))
PLANS_DIR = os.path.join(PROJECT_ROOT, '.claude', 'plans')


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  written: {path}")


def next_message_id(far_data):
    if not far_data.get('messages'):
        return 1
    return max(m['id'] for m in far_data['messages']) + 1


def next_summary_id(near_data):
    if not near_data.get('summaries'):
        return 1
    return max(s['id'] for s in near_data['summaries']) + 1


def load_ephemeral_index():
    """Load the ephemeral capture index (tracks what's already been captured)."""
    os.makedirs(EPHEMERAL_DIR, exist_ok=True)
    index_path = os.path.join(EPHEMERAL_DIR, 'capture_index.json')
    if os.path.exists(index_path):
        return load_json(index_path)
    return {'plans': {}, 'todos': []}


def save_ephemeral_index(index):
    index_path = os.path.join(EPHEMERAL_DIR, 'capture_index.json')
    save_json(index_path, index)


def capture_plans(far_data, near_data, index):
    """Scan .claude/plans/ and capture any new/modified plan files."""
    if not os.path.isdir(PLANS_DIR):
        print(f"  no plans directory found at {PLANS_DIR}")
        return far_data, near_data, index, 0

    plan_files = sorted(glob.glob(os.path.join(PLANS_DIR, '*.md')))
    if not plan_files:
        print("  no plan files found")
        return far_data, near_data, index, 0

    captured = 0
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    for plan_path in plan_files:
        filename = os.path.basename(plan_path)
        mtime = os.path.getmtime(plan_path)

        # Skip if already captured with same mtime
        if filename in index['plans'] and index['plans'][filename]['mtime'] == mtime:
            print(f"  skip (unchanged): {filename}")
            continue

        with open(plan_path, 'r') as f:
            content = f.read()

        if not content.strip():
            continue

        # Append plan to far_memory
        msg_id = next_message_id(far_data)
        far_data['messages'].append({
            'id': msg_id,
            'role': 'system',
            'content': f"[PLAN CAPTURE: {filename}]\n{content}",
            'timestamp': now,
            'type': 'plan',
            'source': plan_path
        })

        # Generate summary for near_memory
        # Extract first meaningful line as plan title
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
        title_hint = lines[0][:100] if lines else filename
        summary_id = next_summary_id(near_data)
        near_data['summaries'].append({
            'id': summary_id,
            'summary': f"[PLAN] {filename}: {title_hint}",
            'far_memory_refs': [msg_id],
            'mind_memory_refs': ['knowledge::work'],
            'timestamp': now,
            'type': 'plan'
        })

        # Update index
        index['plans'][filename] = {
            'mtime': mtime,
            'far_memory_id': msg_id,
            'near_memory_id': summary_id,
            'captured_at': now
        }

        captured += 1
        print(f"  captured plan: {filename} -> far:{msg_id}, near:{summary_id}")

    return far_data, near_data, index, captured


def capture_todos(far_data, near_data, index, todos_data):
    """Capture current todo list state into memory."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    todos = todos_data.get('todos', [])
    if not todos:
        print("  no todos to capture")
        return far_data, near_data, index, 0

    # Format todos as readable text
    lines = []
    for t in todos:
        status_icon = {'pending': '[ ]', 'in_progress': '[~]', 'completed': '[x]'}.get(t['status'], '[ ]')
        lines.append(f"  {status_icon} {t['content']}")
    todo_text = '\n'.join(lines)

    # Count by status
    completed = sum(1 for t in todos if t['status'] == 'completed')
    pending = sum(1 for t in todos if t['status'] == 'pending')
    in_progress = sum(1 for t in todos if t['status'] == 'in_progress')

    # Append to far_memory
    msg_id = next_message_id(far_data)
    far_data['messages'].append({
        'id': msg_id,
        'role': 'system',
        'content': f"[TODO CAPTURE]\n{todo_text}",
        'timestamp': now,
        'type': 'todo',
        'stats': {'completed': completed, 'pending': pending, 'in_progress': in_progress}
    })

    # Summary for near_memory
    summary_id = next_summary_id(near_data)
    near_data['summaries'].append({
        'id': summary_id,
        'summary': f"[TODO] {completed}/{len(todos)} done, {in_progress} active, {pending} pending",
        'far_memory_refs': [msg_id],
        'mind_memory_refs': ['knowledge::work'],
        'timestamp': now,
        'type': 'todo'
    })

    # Update index
    index['todos'].append({
        'far_memory_id': msg_id,
        'near_memory_id': summary_id,
        'count': len(todos),
        'completed': completed,
        'captured_at': now
    })

    print(f"  captured todos: {len(todos)} items -> far:{msg_id}, near:{summary_id}")
    return far_data, near_data, index, 1


def list_captured(index):
    """List all previously captured ephemeral artifacts."""
    plans = index.get('plans', {})
    todos = index.get('todos', [])

    if not plans and not todos:
        print("No ephemeral artifacts captured yet.")
        return

    if plans:
        print(f"\nCaptured Plans ({len(plans)}):")
        for filename, info in plans.items():
            print(f"  {filename} -> far:{info['far_memory_id']} near:{info['near_memory_id']} @ {info['captured_at']}")

    if todos:
        print(f"\nCaptured Todos ({len(todos)} snapshots):")
        for t in todos:
            print(f"  {t['count']} items ({t['completed']} done) -> far:{t['far_memory_id']} @ {t['captured_at']}")


def recall_captured(index, far_data, keyword):
    """Search captured ephemeral artifacts by keyword."""
    keyword_lower = keyword.lower()
    found = False

    # Search plans
    for filename, info in index.get('plans', {}).items():
        if keyword_lower in filename.lower():
            found = True
            # Find the far_memory message
            for m in far_data.get('messages', []):
                if m['id'] == info['far_memory_id']:
                    print(f"\n=== PLAN: {filename} ===")
                    print(m['content'][:500])
                    if len(m['content']) > 500:
                        print(f"  ... ({len(m['content'])} chars total, use --full for complete)")
                    break

    # Search plan content in far_memory
    for m in far_data.get('messages', []):
        if m.get('type') == 'plan' and keyword_lower in m['content'].lower():
            if not any(keyword_lower in fn.lower() for fn in index.get('plans', {})):
                found = True
                print(f"\n=== PLAN (content match) far:{m['id']} ===")
                print(m['content'][:500])

    # Search todos in far_memory
    for m in far_data.get('messages', []):
        if m.get('type') == 'todo' and keyword_lower in m['content'].lower():
            found = True
            print(f"\n=== TODO SNAPSHOT far:{m['id']} @ {m['timestamp']} ===")
            print(m['content'])

    if not found:
        print(f"No ephemeral artifacts found matching '{keyword}'")


def main():
    parser = argparse.ArgumentParser(description='Capture ephemeral Claude Code artifacts')
    parser.add_argument('--plans', action='store_true', help='Capture plan files from .claude/plans/')
    parser.add_argument('--todos', action='store_true', help='Capture todo list (from stdin JSON)')
    parser.add_argument('--stdin', action='store_true', help='Read todo JSON from stdin')
    parser.add_argument('--list', action='store_true', help='List captured artifacts')
    parser.add_argument('--recall', help='Search captured artifacts by keyword')
    parser.add_argument('--full', action='store_true', help='Show full content in recall')
    args = parser.parse_args()

    if not any([args.plans, args.todos, args.list, args.recall]):
        parser.error('Specify --plans, --todos, --list, or --recall')

    index = load_ephemeral_index()

    if args.list:
        list_captured(index)
        return

    if args.recall:
        far_data = load_json(FAR_MEMORY)
        recall_captured(index, far_data, args.recall)
        return

    # Capture mode: load memory files
    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)
    total_captured = 0

    if args.plans:
        far_data, near_data, index, count = capture_plans(far_data, near_data, index)
        total_captured += count

    if args.todos:
        todos_data = {}
        if args.stdin:
            todos_data = json.load(sys.stdin)
        else:
            print("  --todos requires --stdin with JSON input")
            return
        far_data, near_data, index, count = capture_todos(far_data, near_data, index, todos_data)
        total_captured += count

    if total_captured > 0:
        save_json(FAR_MEMORY, far_data)
        save_json(NEAR_MEMORY, near_data)
        save_ephemeral_index(index)
        print(f"OK: captured {total_captured} ephemeral artifacts")
    else:
        print("OK: no new artifacts to capture")


if __name__ == '__main__':
    main()
