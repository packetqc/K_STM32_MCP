#!/usr/bin/env python3
"""
memory_quantum.py — Cross-branch memory merge.

Fetches K_MIND memory files from a remote repository branch and merges
them into the current session without breaking local state. Far memory
messages and near memory summaries are appended with remapped IDs.
Archives are imported as distinct topic files.

Uses GitHubHelper (gh_helper.py) for all GitHub API access — no gh CLI dependency.

Usage:
    python3 scripts/memory_quantum.py <repository> <branch> [options]

Options:
    --list      List remote memory contents without merging
    --dry       Preview what would be imported (no writes)
    --full      Include full far_memory messages in list output

Examples:
    python3 scripts/memory_quantum.py packetqc/K_MIND main --list
    python3 scripts/memory_quantum.py packetqc/knowledge claude/feature-x --dry
    python3 scripts/memory_quantum.py packetqc/knowledge claude/feature-x
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# K_MIND paths — resolve relative to this script's module parent
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# K_TOOLS is the parent of this script; K_MIND is a sibling module
MODULE_ROOT = os.path.join(SCRIPT_DIR, '..')
KNOWLEDGE_ROOT = os.path.join(MODULE_ROOT, '..')
K_MIND_ROOT = os.path.join(KNOWLEDGE_ROOT, 'K_MIND')

SESSIONS_DIR = os.path.join(K_MIND_ROOT, 'sessions')
ARCHIVES_DIR = os.path.join(SESSIONS_DIR, 'archives')
FAR_MEMORY = os.path.join(SESSIONS_DIR, 'far_memory.json')
NEAR_MEMORY = os.path.join(SESSIONS_DIR, 'near_memory.json')
ARCHIVE_INDEX = os.path.join(SESSIONS_DIR, 'archive_index.json')


def _get_gh_helper():
    """Get GitHubHelper instance if GH_TOKEN is available."""
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        return None
    try:
        gh_path = os.path.join(K_MIND_ROOT, "scripts")
        if gh_path not in sys.path:
            sys.path.insert(0, gh_path)
        from gh_helper import GitHubHelper
        return GitHubHelper()
    except (ImportError, ValueError):
        return None


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def detect_kmind_prefix(gh, repo, branch):
    """Detect whether K_MIND is at root or under Knowledge/K_MIND/."""
    # Try Knowledge/K_MIND/ first (imported module)
    content = gh.repo_file_content(repo, 'Knowledge/K_MIND/sessions/far_memory.json', ref=branch)
    if content:
        return 'Knowledge/K_MIND/'
    # Try root (standalone K_MIND repo)
    content = gh.repo_file_content(repo, 'sessions/far_memory.json', ref=branch)
    if content:
        return ''
    return None


def fetch_remote_memory(gh, repo, branch, prefix):
    """Fetch all memory files from remote using GitHubHelper."""
    result = {}

    # Far memory
    content = gh.repo_file_content(repo, prefix + 'sessions/far_memory.json', ref=branch)
    if content:
        result['far_memory'] = json.loads(content)

    # Near memory
    content = gh.repo_file_content(repo, prefix + 'sessions/near_memory.json', ref=branch)
    if content:
        result['near_memory'] = json.loads(content)

    # Archives — list files in archives directory
    archives = {}
    archive_files = gh.repo_tree_list(repo, prefix + 'sessions/archives', ref=branch)
    if archive_files:
        for fname in archive_files:
            if fname.endswith('.json'):
                acontent = gh.repo_file_content(
                    repo, prefix + 'sessions/archives/' + fname, ref=branch)
                if acontent:
                    archives[fname] = json.loads(acontent)
    result['archives'] = archives

    return result


def list_remote(remote, full=False):
    """Display remote memory contents."""
    far = remote.get('far_memory', {})
    near = remote.get('near_memory', {})
    archives = remote.get('archives', {})

    msgs = far.get('messages', [])
    summaries = near.get('summaries', [])
    archive_index = far.get('archives', [])

    print(f"## Remote Memory Contents\n")
    print(f"| Store | Count |")
    print(f"|:------|:------|")
    print(f"| far_memory messages | {len(msgs)} |")
    print(f"| near_memory summaries | {len(summaries)} |")
    print(f"| archive topics | {len(archive_index)} |")
    print(f"| archive files | {len(archives)} |")
    print(f"| session_id | {far.get('session_id', 'unknown')} |")

    if archive_index:
        print(f"\n### Archived Topics")
        for a in archive_index:
            print(f"  - **{a['topic']}** — messages {a['message_range']}, near {a['near_memory_range']}")

    if summaries:
        print(f"\n### Near Memory Summaries (last 10)")
        for s in summaries[-10:]:
            print(f"  - [{s['id']}] {s['summary']}")

    if full and msgs:
        print(f"\n### Far Memory Messages")
        for m in msgs:
            preview = m.get('content', '')[:150]
            print(f"  - [{m['id']}] {m['role']}: {preview}")


def preview_merge(local_far, local_near, remote):
    """Show what would be imported without writing."""
    remote_far = remote.get('far_memory', {})
    remote_near = remote.get('near_memory', {})
    remote_archives = remote.get('archives', {})

    local_msgs = local_far.get('messages', [])
    local_summaries = local_near.get('summaries', [])
    remote_msgs = remote_far.get('messages', [])
    remote_summaries = remote_near.get('summaries', [])

    max_far_id = max((m['id'] for m in local_msgs), default=0)
    max_near_id = max((s['id'] for s in local_summaries), default=0)

    # Check for existing archive files
    existing_archives = set()
    if os.path.isdir(ARCHIVES_DIR):
        existing_archives = set(os.listdir(ARCHIVES_DIR))

    new_archives = {k: v for k, v in remote_archives.items()
                    if k not in existing_archives}

    print(f"## Quantum Merge Preview (dry run)\n")
    print(f"| Action | Count | Details |")
    print(f"|:-------|:------|:--------|")
    print(f"| Import far_memory messages | {len(remote_msgs)} | IDs remapped: {max_far_id + 1}..{max_far_id + len(remote_msgs)} |")
    print(f"| Import near_memory summaries | {len(remote_summaries)} | IDs remapped: {max_near_id + 1}..{max_near_id + len(remote_summaries)} |")
    print(f"| Import archive files | {len(new_archives)} | {', '.join(new_archives.keys()) or '(none new)'} |")
    print(f"| Skip existing archives | {len(remote_archives) - len(new_archives)} | Already present locally |")

    # Show what archive topics would be added to the index
    remote_archive_index = remote_far.get('archives', [])
    if remote_archive_index:
        print(f"\n### Archive topics to import")
        for a in remote_archive_index:
            print(f"  - **{a['topic']}** → file: {a['file']}")


def load_archive_index():
    if os.path.exists(ARCHIVE_INDEX):
        try:
            with open(ARCHIVE_INDEX, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {'archives': []}


def execute_merge(local_far, local_near, remote, source_label):
    """Merge remote memory into local, remapping all IDs."""
    remote_far = remote.get('far_memory', {})
    remote_near = remote.get('near_memory', {})
    remote_archives = remote.get('archives', {})

    local_msgs = local_far.get('messages', [])
    local_summaries = local_near.get('summaries', [])
    remote_msgs = remote_far.get('messages', [])
    remote_summaries = remote_near.get('summaries', [])

    max_far_id = max((m['id'] for m in local_msgs), default=0)
    max_near_id = max((s['id'] for s in local_summaries), default=0)

    # Build ID remap tables
    far_remap = {}
    for i, m in enumerate(remote_msgs):
        old_id = m['id']
        new_id = max_far_id + 1 + i
        far_remap[old_id] = new_id

    near_remap = {}
    for i, s in enumerate(remote_summaries):
        old_id = s['id']
        new_id = max_near_id + 1 + i
        near_remap[old_id] = new_id

    # Remap and append far_memory messages
    imported_msgs = []
    for m in remote_msgs:
        new_msg = dict(m)
        new_msg['id'] = far_remap[m['id']]
        new_msg['quantum_source'] = source_label
        new_msg['quantum_original_id'] = m['id']
        imported_msgs.append(new_msg)

    # Remap and append near_memory summaries
    imported_summaries = []
    for s in remote_summaries:
        new_s = dict(s)
        new_s['id'] = near_remap[s['id']]
        # Remap far_memory_refs
        new_refs = [far_remap.get(r, r) for r in s.get('far_memory_refs', [])]
        new_s['far_memory_refs'] = new_refs
        new_s['quantum_source'] = source_label
        new_s['quantum_original_id'] = s['id']
        imported_summaries.append(new_s)

    # Import archive files (skip existing)
    os.makedirs(ARCHIVES_DIR, exist_ok=True)
    existing_archives = set(os.listdir(ARCHIVES_DIR)) if os.path.isdir(ARCHIVES_DIR) else set()
    imported_archive_files = []

    for filename, data in remote_archives.items():
        # Prefix with quantum source to avoid collisions
        safe_name = 'quantum_' + source_label.replace('/', '_').replace(' ', '_') + '_' + filename
        if safe_name not in existing_archives and filename not in existing_archives:
            # Remap message IDs in archive data
            if 'messages' in data:
                for m in data['messages']:
                    if m['id'] in far_remap:
                        m['id'] = far_remap[m['id']]
            if 'summaries' in data:
                for s in data['summaries']:
                    if s['id'] in near_remap:
                        s['id'] = near_remap[s['id']]
                    s['far_memory_refs'] = [far_remap.get(r, r)
                                            for r in s.get('far_memory_refs', [])]
            save_json(os.path.join(ARCHIVES_DIR, safe_name), data)
            imported_archive_files.append(safe_name)

    # Import archive index entries (remap ranges)
    imported_archive_index = []
    for a in remote_far.get('archives', []):
        new_entry = dict(a)
        start, end = a['message_range']
        new_entry['message_range'] = [far_remap.get(start, start), far_remap.get(end, end)]
        ns, ne = a['near_memory_range']
        new_entry['near_memory_range'] = [near_remap.get(ns, ns), near_remap.get(ne, ne)]
        # Update file reference to quantum-prefixed name
        orig_file = a['file']
        safe_file = 'archives/quantum_' + source_label.replace('/', '_').replace(' ', '_') + '_' + os.path.basename(orig_file)
        new_entry['file'] = safe_file
        new_entry['quantum_source'] = source_label
        imported_archive_index.append(new_entry)

    # Write merged files
    local_far['messages'].extend(imported_msgs)
    save_json(FAR_MEMORY, local_far)

    local_near['summaries'].extend(imported_summaries)
    save_json(NEAR_MEMORY, local_near)

    # Update archive index (separate file)
    index_data = load_archive_index()
    index_data.setdefault('archives', []).extend(imported_archive_index)
    save_json(ARCHIVE_INDEX, index_data)

    # Report
    print(f"## Quantum Merge Complete\n")
    print(f"| Action | Count |")
    print(f"|:-------|:------|")
    print(f"| Far memory messages imported | {len(imported_msgs)} |")
    print(f"| Near memory summaries imported | {len(imported_summaries)} |")
    print(f"| Archive files imported | {len(imported_archive_files)} |")
    print(f"| Archive index entries added | {len(imported_archive_index)} |")
    print(f"| Source | {source_label} |")
    print(f"\nAll imported entries tagged with `quantum_source: \"{source_label}\"` for traceability.")


def main():
    parser = argparse.ArgumentParser(
        description='Quantum — cross-branch memory merge')
    parser.add_argument('repository', help='GitHub repository (e.g. packetqc/knowledge)')
    parser.add_argument('branch', help='Remote branch name')
    parser.add_argument('--list', action='store_true',
                        help='List remote memory contents without merging')
    parser.add_argument('--dry', action='store_true',
                        help='Preview what would be imported (no writes)')
    parser.add_argument('--full', action='store_true',
                        help='Show full messages in list mode')
    args = parser.parse_args()

    source_label = f"{args.repository}:{args.branch}"
    print(f"Fetching memory from {source_label}...")

    # Initialize GitHubHelper (requires GH_TOKEN env var)
    gh = _get_gh_helper()
    if gh is None:
        print("ERROR: GH_TOKEN environment variable not set.")
        print("  Set it in your Claude Code cloud environment configuration.")
        print("  Generate a classic PAT with 'repo' scope at:")
        print("  GitHub > Settings > Developer settings > Personal access tokens (classic)")
        sys.exit(1)

    # Detect K_MIND location in remote repo
    prefix = detect_kmind_prefix(gh, args.repository, args.branch)
    if prefix is None:
        print(f"ERROR: Could not find K_MIND sessions in {source_label}")
        print("  Tried: Knowledge/K_MIND/sessions/ and sessions/")
        sys.exit(1)

    print(f"  K_MIND prefix: {prefix or '(root)'}")

    # Fetch remote memory
    remote = fetch_remote_memory(gh, args.repository, args.branch, prefix)
    if not remote.get('far_memory') and not remote.get('near_memory'):
        print(f"ERROR: No memory files found at {source_label}")
        sys.exit(1)

    if args.list:
        list_remote(remote, full=args.full)
        return

    # Load local memory
    local_far = load_json(FAR_MEMORY)
    local_near = load_json(NEAR_MEMORY)

    if args.dry:
        preview_merge(local_far, local_near, remote)
        return

    execute_merge(local_far, local_near, remote, source_label)


if __name__ == '__main__':
    main()
