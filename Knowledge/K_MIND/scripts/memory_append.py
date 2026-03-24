#!/usr/bin/env python3
"""
memory_append.py — Append a message to far_memory and a summary to near_memory.

Called by Claude every turn with intelligent content as arguments.
Handles all mechanical file I/O deterministically.

Supports two-phase operation for the BEFORE/AFTER turn protocol:
  --phase before  Save user message to far_memory immediately (safety capture)
  --phase after   Save assistant response + near_memory summary (links back)
  (no --phase)    Legacy single-call mode (saves both at once)

Usage (single-call — legacy):
    python3 scripts/memory_append.py \
        --role user --content "verbatim message" \
        --role2 assistant --content2 "full assistant output" \
        --summary "one-line summary" \
        --mind-refs "knowledge::session,knowledge::work" \
        [--tools '[{"tool":"Edit","file":"path","action":"desc"},...]']

Usage (two-phase):
    # BEFORE — capture user message, returns msg_id
    python3 scripts/memory_append.py --phase before \
        --role user --content "exact user message"

    # AFTER — capture assistant response + summary, links to before msg_id
    python3 scripts/memory_append.py --phase after \
        --role2 assistant --content2 "full assistant output" \
        --summary "one-line summary" \
        --mind-refs "knowledge::session,knowledge::work" \
        [--tools '[...]']

Usage (stdin for large content — pipe JSON):
    echo '{"role":"user","content":"...","role2":"assistant","content2":"...","summary":"...","mind_refs":"...","tools":[]}' | \
    python3 scripts/memory_append.py --stdin

    # stdin also supports phase:
    echo '{"phase":"before","role":"user","content":"..."}' | python3 scripts/memory_append.py --stdin
    echo '{"phase":"after","role2":"assistant","content2":"...","summary":"...","mind_refs":"..."}' | python3 scripts/memory_append.py --stdin
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'sessions')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')


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


def detect_activity(content, activity_mode=None):
    """Detect whether user message is addon to current activity or a new activity.
    Returns ('addon', reason) or ('new', reason).
    activity_mode: None/'detect' = auto, 'new' = force new, 'addon' = force addon."""
    if activity_mode == 'new':
        return 'new', 'forced by --activity-mode new'
    if activity_mode == 'addon':
        return 'addon', 'forced by --activity-mode addon'

    near_data = load_json(NEAR_MEMORY)
    wip = near_data.get('wip_context', {})
    active_branch = wip.get('active_branch', '')
    summaries = near_data.get('summaries', [])

    # No active branch = new activity
    if not active_branch:
        return 'new', 'no active branch in wip_context'

    # Compare content words against last 3 summaries and active branch
    content_lower = content.lower()
    branch_words = set(active_branch.lower().replace('-', ' ').replace('_', ' ').split())

    # Check overlap with active branch name
    content_words = set(content_lower.replace('-', ' ').replace('_', ' ').split())
    overlap = branch_words & content_words
    if overlap:
        return 'addon', f'content shares words with active branch: {overlap}'

    # Check overlap with recent summaries
    recent = summaries[-3:] if summaries else []
    for s in recent:
        summary_words = set(s.get('summary', '').lower().split())
        if content_words & summary_words:
            return 'addon', f'content overlaps with recent summary id={s.get("id")}'

    # Short messages (< 20 words) are likely continuations
    if len(content_words) < 20:
        return 'addon', 'short message — likely continuation'

    return 'new', 'no overlap with active branch or recent summaries'


def verbatim_integrity_check(content, role):
    """Check that user message content looks like a verbatim capture, not a paraphrase.
    Emits warnings to stderr — does NOT block storage (data safety first)."""
    if role != 'user':
        return
    warnings = []
    # Heuristic 1: Suspiciously short for a user message with instructions
    word_count = len(content.split())
    if word_count < 8:
        warnings.append(f"VERY SHORT ({word_count} words) — is this really the full user message?")
    # Heuristic 2: Starts with labels that suggest paraphrasing
    paraphrase_prefixes = ['Bug report:', 'Feature request:', 'Task:', 'Request:', 'Summary:',
                           'The user wants', 'User asked', 'User requested']
    for prefix in paraphrase_prefixes:
        if content.startswith(prefix):
            warnings.append(f"Starts with '{prefix}' — this looks like a PARAPHRASE, not verbatim user text")
            break
    # Heuristic 3: Missing first-person markers when content is long enough to expect them
    first_person = any(w in content.lower().split() for w in ['i', "i'm", "i've", "i'd", 'my', 'me', 'we'])
    if word_count > 15 and not first_person and not content.startswith('/'):
        warnings.append("No first-person pronouns in a long message — possible paraphrase")
    if warnings:
        print("⚠ VERBATIM INTEGRITY WARNING:", file=sys.stderr)
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
        print("  Rule: far_memory stores the user's EXACT words — never paraphrase, summarize, or rephrase.", file=sys.stderr)
        print(f"  Content preview: \"{content[:120]}...\"" if len(content) > 120 else f"  Content: \"{content}\"", file=sys.stderr)


def phase_before(role, content, activity_mode=None):
    """BEFORE phase: save user message to far_memory only.
    Also detects activity type (addon vs new) and reports it.
    CRITICAL: content MUST be the user's VERBATIM message — never paraphrased."""
    # Integrity check — warn on suspected paraphrases (does not block storage)
    verbatim_integrity_check(content, role)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    far_data = load_json(FAR_MEMORY)

    # Detect activity type
    activity_type, activity_reason = detect_activity(content, activity_mode)

    msg_id = next_message_id(far_data)
    far_data['messages'].append({
        'id': msg_id,
        'role': role,
        'content': content,
        'timestamp': now,
        'activity': activity_type
    })

    save_json(FAR_MEMORY, far_data)
    print(f"OK: phase=before, far_memory id={msg_id}")
    print(f"ACTIVITY: {activity_type} — {activity_reason}")
    return msg_id


def phase_after(role2, content2, summary, mind_refs_str, tools_list):
    """AFTER phase: save assistant response + near_memory summary."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    # Find the last user message id (saved in BEFORE phase)
    user_msg_id = None
    for msg in reversed(far_data.get('messages', [])):
        if msg['role'] == 'user':
            user_msg_id = msg['id']
            break

    far_refs = []
    if user_msg_id is not None:
        far_refs.append(user_msg_id)

    # Save assistant response
    msg_id = next_message_id(far_data)
    msg = {
        'id': msg_id,
        'role': role2,
        'content': content2,
        'timestamp': now
    }
    if tools_list:
        msg['tools'] = tools_list
    far_data['messages'].append(msg)
    far_refs.append(msg_id)

    # Save near_memory summary linking both messages
    summary_id = next_summary_id(near_data)
    mind_refs = [r.strip() for r in mind_refs_str.split(',') if r.strip()]
    near_data['summaries'].append({
        'id': summary_id,
        'summary': summary,
        'far_memory_refs': far_refs,
        'mind_memory_refs': mind_refs,
        'timestamp': now
    })

    save_json(FAR_MEMORY, far_data)
    save_json(NEAR_MEMORY, near_data)
    print(f"OK: phase=after, far_memory id={msg_id}, near_memory id={summary_id}")


def single_call(role, content, role2, content2, summary, mind_refs_str, tools_list):
    """Legacy single-call mode: save both messages + summary at once."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    far_data = load_json(FAR_MEMORY)
    near_data = load_json(NEAR_MEMORY)

    # Append first message to far_memory
    msg_id_1 = next_message_id(far_data)
    far_data['messages'].append({
        'id': msg_id_1,
        'role': role,
        'content': content,
        'timestamp': now
    })

    far_refs = [msg_id_1]

    # Append second message if provided
    if role2 and content2:
        msg_id_2 = msg_id_1 + 1
        msg2 = {
            'id': msg_id_2,
            'role': role2,
            'content': content2,
            'timestamp': now
        }
        if tools_list:
            msg2['tools'] = tools_list
        far_data['messages'].append(msg2)
        far_refs.append(msg_id_2)

    # Append summary to near_memory
    summary_id = next_summary_id(near_data)
    mind_refs = [r.strip() for r in mind_refs_str.split(',') if r.strip()]
    near_data['summaries'].append({
        'id': summary_id,
        'summary': summary,
        'far_memory_refs': far_refs,
        'mind_memory_refs': mind_refs,
        'timestamp': now
    })

    # Save both files
    save_json(FAR_MEMORY, far_data)
    save_json(NEAR_MEMORY, near_data)

    print(f"OK: far_memory ids={far_refs}, near_memory id={summary_id}")


def wip_update(action, key, value):
    """Manage the WIP persistence layer in near_memory.
    Actions: set (set key=value), append (append value to list at key),
    clear (clear the entire wip_context), remove (remove key)."""
    near_data = load_json(NEAR_MEMORY)
    if 'wip_context' not in near_data:
        near_data['wip_context'] = {}
    wip = near_data['wip_context']

    if action == 'clear':
        near_data['wip_context'] = {}
        save_json(NEAR_MEMORY, near_data)
        print("OK: wip_context cleared")
        return

    if action == 'remove':
        if key in wip:
            del wip[key]
            save_json(NEAR_MEMORY, near_data)
            print(f"OK: removed wip_context.{key}")
        else:
            print(f"WARN: wip_context.{key} not found")
        return

    if action == 'set':
        wip[key] = value
        save_json(NEAR_MEMORY, near_data)
        print(f"OK: wip_context.{key} = {value}")
        return

    if action == 'append':
        if key not in wip:
            wip[key] = []
        if not isinstance(wip[key], list):
            print(f"ERROR: wip_context.{key} is not a list")
            return
        wip[key].append(value)
        save_json(NEAR_MEMORY, near_data)
        print(f"OK: appended to wip_context.{key} ({len(wip[key])} items)")
        return

    print(f"ERROR: unknown wip action '{action}'")


def show_wip():
    """Display current WIP context."""
    near_data = load_json(NEAR_MEMORY)
    wip = near_data.get('wip_context', {})
    if not wip:
        print("WIP context: empty")
        return
    print("WIP context:")
    for k, v in wip.items():
        if isinstance(v, list):
            print(f"  {k}: [{len(v)} items]")
            for item in v[-5:]:  # Show last 5
                print(f"    - {item}")
        else:
            print(f"  {k}: {v}")


def pin_entry(pin_id, category, content, mind_ref):
    """Add or update a pinned entry in near_memory."""
    near_data = load_json(NEAR_MEMORY)
    if 'pinned' not in near_data:
        near_data['pinned'] = []

    # Update existing or append new
    for p in near_data['pinned']:
        if p['id'] == pin_id:
            p['category'] = category
            p['content'] = content
            p['mind_ref'] = mind_ref
            save_json(NEAR_MEMORY, near_data)
            print(f"OK: updated pinned entry {pin_id}")
            return

    near_data['pinned'].append({
        'id': pin_id,
        'category': category,
        'content': content,
        'mind_ref': mind_ref
    })
    save_json(NEAR_MEMORY, near_data)
    print(f"OK: added pinned entry {pin_id}")


def unpin_entry(pin_id):
    """Remove a pinned entry from near_memory."""
    near_data = load_json(NEAR_MEMORY)
    pinned = near_data.get('pinned', [])
    before = len(pinned)
    near_data['pinned'] = [p for p in pinned if p['id'] != pin_id]
    after = len(near_data['pinned'])
    if before == after:
        print(f"WARN: pinned entry {pin_id} not found")
    else:
        save_json(NEAR_MEMORY, near_data)
        print(f"OK: removed pinned entry {pin_id}")


def list_pinned():
    """List all pinned entries."""
    near_data = load_json(NEAR_MEMORY)
    pinned = near_data.get('pinned', [])
    if not pinned:
        print("No pinned entries.")
        return
    print(f"Pinned entries ({len(pinned)}):")
    for p in pinned:
        print(f"  [{p['id']}] ({p['category']}) {p['content']}")
        print(f"    mind_ref: {p['mind_ref']}")


def main():
    parser = argparse.ArgumentParser(description='Append to far_memory and near_memory')
    parser.add_argument('--stdin', action='store_true', help='Read JSON input from stdin (for large content)')
    parser.add_argument('--phase', choices=['before', 'after'], help='Two-phase mode: before (user msg) or after (assistant + summary)')
    parser.add_argument('--pin', nargs=4, metavar=('ID', 'CATEGORY', 'CONTENT', 'MIND_REF'),
                        help='Add/update a pinned near_memory entry')
    parser.add_argument('--unpin', metavar='ID', help='Remove a pinned entry by ID')
    parser.add_argument('--list-pinned', action='store_true', help='List all pinned entries')
    parser.add_argument('--wip', nargs='*', metavar='ARG',
                        help='WIP context: --wip set KEY VALUE | --wip append KEY VALUE | --wip clear | --wip remove KEY | --wip show')
    parser.add_argument('--activity-mode', choices=['detect', 'new', 'addon'],
                        help='Activity classification: detect (auto), new (force new activity), addon (force continuation)')
    parser.add_argument('--role', help='Message role (user/assistant)')
    parser.add_argument('--content', help='Verbatim message content')
    parser.add_argument('--role2', help='Second message role (for assistant response)')
    parser.add_argument('--content2', help='Second message content (full output)')
    parser.add_argument('--tools', default='', help='JSON array of tool calls')
    parser.add_argument('--summary', help='Summary for near_memory')
    parser.add_argument('--mind-refs', default='', help='Comma-separated mind_memory refs')
    args = parser.parse_args()

    # Handle WIP operations
    if args.wip is not None:
        wip_args = args.wip
        if not wip_args or wip_args[0] == 'show':
            show_wip()
            return
        action = wip_args[0]
        if action == 'clear':
            wip_update('clear', None, None)
            return
        if action in ('set', 'append') and len(wip_args) >= 3:
            wip_update(action, wip_args[1], ' '.join(wip_args[2:]))
            return
        if action == 'remove' and len(wip_args) >= 2:
            wip_update('remove', wip_args[1], None)
            return
        parser.error(f'Invalid --wip usage: --wip {" ".join(wip_args)}')

    # Handle pinned operations
    if args.list_pinned:
        list_pinned()
        return
    if args.unpin:
        unpin_entry(args.unpin)
        return
    if args.pin:
        pin_entry(*args.pin)
        return

    # Support stdin mode for large content
    if args.stdin:
        data = json.load(sys.stdin)
        phase = data.get('phase', args.phase)
        role = data.get('role')
        content = data.get('content')
        role2 = data.get('role2')
        content2 = data.get('content2')
        tools_list = data.get('tools', [])
        summary = data.get('summary')
        mind_refs_str = data.get('mind_refs', '')
    else:
        phase = args.phase
        role = args.role
        content = args.content
        role2 = args.role2
        content2 = args.content2
        tools_list = []
        if args.tools:
            try:
                tools_list = json.loads(args.tools)
            except json.JSONDecodeError:
                tools_list = []
        summary = args.summary
        mind_refs_str = getattr(args, 'mind_refs', '') or ''

    # Get activity mode
    activity_mode = None
    if args.stdin:
        activity_mode = data.get('activity_mode', None)
    else:
        activity_mode = getattr(args, 'activity_mode', None)

    # Dispatch based on phase
    if phase == 'before':
        if not role or not content:
            parser.error('--role and --content are required for --phase before')
        phase_before(role, content, activity_mode)

    elif phase == 'after':
        if not role2 or not content2 or not summary:
            parser.error('--role2, --content2, and --summary are required for --phase after')
        phase_after(role2, content2, summary, mind_refs_str, tools_list)

    else:
        # Legacy single-call mode
        if not role or not content or not summary:
            parser.error('--role, --content, and --summary are required (or use --stdin)')
        single_call(role, content, role2, content2, summary, mind_refs_str, tools_list)


if __name__ == '__main__':
    main()
