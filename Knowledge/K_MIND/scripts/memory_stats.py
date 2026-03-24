#!/usr/bin/env python3
"""Output K_MIND memory stats table with context availability.

Usage:
    python3 scripts/memory_stats.py              # Full stats table
    python3 scripts/memory_stats.py --available   # Just the available tokens number
    python3 scripts/memory_stats.py --context-mode # Just the context mode (200k or 1m)
"""
import json
import os
import glob
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
DEPTH_CONFIG = os.path.join(BASE_DIR, 'conventions', 'depth_config.json')

# Context window profiles
CONTEXT_PROFILES = {
    '200k': {
        'limit': 200_000,
        'autocompact_buffer': 33_000,
        'system_overhead': 34_000,
        'label': '200K'
    },
    '1m': {
        'limit': 1_000_000,
        'autocompact_buffer': 100_000,
        'system_overhead': 34_000,
        'label': '1M'
    }
}


def detect_context_mode():
    """Detect context window from CLAUDE_MODEL_ID env var or depth_config override.
    Model ID containing '[1m]' suffix indicates 1M context."""
    # Check depth_config override first
    if os.path.exists(DEPTH_CONFIG):
        try:
            with open(DEPTH_CONFIG) as f:
                cfg = json.load(f)
            override = cfg.get('context_mode')
            if override in CONTEXT_PROFILES:
                return override
        except (json.JSONDecodeError, KeyError):
            pass
    # Detect from model ID
    model_id = os.environ.get('CLAUDE_MODEL_ID', '')
    if '[1m]' in model_id or '1m' in model_id.lower().replace('-', ''):
        return '1m'
    return '200k'


# Legacy constants (kept for backward compat, use profile instead)
MODEL_CONTEXT_LIMIT = 200_000
AUTOCOMPACT_BUFFER = 33_000
SYSTEM_OVERHEAD = 34_000

def load_near_memory_window():
    """Load near_memory_window from depth_config.json."""
    if os.path.exists(DEPTH_CONFIG):
        try:
            with open(DEPTH_CONFIG) as f:
                cfg = json.load(f)
            return cfg.get('near_memory_window', 20)
        except (json.JSONDecodeError, KeyError):
            pass
    return 20


def main():
    os.chdir(BASE_DIR)

    # Detect context mode
    context_mode = detect_context_mode()
    profile = CONTEXT_PROFILES[context_mode]

    # --context-mode flag: output just the detected mode
    if '--context-mode' in sys.argv:
        print(f'{profile["label"]} ({context_mode})')
        return

    with open('sessions/far_memory.json') as f:
        fm = json.load(f)
    fm_msgs = len(fm.get('messages', []))
    fm_size = os.path.getsize('sessions/far_memory.json')

    with open('sessions/near_memory.json') as f:
        nm = json.load(f)
    nm_summaries = len(nm.get('summaries', []))
    nm_size = os.path.getsize('sessions/near_memory.json')

    # Archive index (separate from far_memory)
    ai_path = 'sessions/archive_index.json'
    ai_entries = 0
    if os.path.exists(ai_path):
        with open(ai_path) as f:
            ai = json.load(f)
        ai_entries = len(ai.get('archives', []))

    archive_files = glob.glob('sessions/archives/far_memory_*.json')
    archive_count = len(archive_files)
    arc_size = sum(os.path.getsize(f) for f in archive_files)

    mm_size = os.path.getsize('mind/mind_memory.md')
    with open('mind/mind_memory.md') as f:
        lines = f.readlines()
    bt = chr(96) * 3
    node_count = sum(1 for l in lines if l.strip() and not l.strip().startswith(bt)
                     and not l.strip().startswith('%%') and 'mindmap' not in l.strip()
                     and 'root(' not in l.strip())

    # Scan K_MIND domain files
    domain_files = [f for f in glob.glob('*/**/**.json', recursive=True)
                    if not f.startswith('sessions/') and not f.startswith('node_modules/')]
    # Scan sibling modules (Knowledge/K_*/) for their domain files
    knowledge_root = os.path.join(BASE_DIR, '..')
    for module_dir in sorted(glob.glob(os.path.join(knowledge_root, 'K_*'))):
        mod_name = os.path.basename(module_dir)
        if mod_name == 'K_MIND':
            continue  # already scanned above
        for mf in glob.glob(os.path.join(module_dir, '**', '*.json'), recursive=True):
            domain_files.append(mf)
    domain_size = sum(os.path.getsize(f) for f in domain_files)
    domain_count = len(domain_files)

    claude_md = os.path.getsize('CLAUDE.md') if os.path.exists('CLAUDE.md') else 0
    # Aggregate convention sizes from all modules for loaded tokens
    conv_size = 0
    if os.path.exists('conventions/conventions.json'):
        conv_size += os.path.getsize('conventions/conventions.json')
    for module_dir in sorted(glob.glob(os.path.join(knowledge_root, 'K_*'))):
        mod_name = os.path.basename(module_dir)
        if mod_name == 'K_MIND':
            continue
        mod_conv = os.path.join(module_dir, 'conventions', 'conventions.json')
        if os.path.exists(mod_conv):
            conv_size += os.path.getsize(mod_conv)

    def kb(b):
        return f'{b / 1024:.1f} KB'

    def tk(b):
        return f'~{b // 4:,}'

    def tk_raw(b):
        return b // 4

    disk_total = fm_size + nm_size + mm_size + arc_size + domain_size + claude_md
    # near_memory is on-demand (loaded by /mind-context, not auto-loaded at startup)
    loaded_total = mm_size + claude_md + conv_size
    loaded_tokens = tk_raw(loaded_total)
    # Estimate conversation tokens: far_memory tracks the full conversation,
    # so its size approximates the conversation history occupying the context window.
    conversation_tokens = tk_raw(fm_size)
    total_context_used = profile['system_overhead'] + loaded_tokens + conversation_tokens
    usable_limit = profile['limit'] - profile['autocompact_buffer']
    available = usable_limit - total_context_used
    nm_window = load_near_memory_window()

    # WIP context stats
    wip_items = 0
    wip_decisions = 0
    nm_data_for_wip = nm
    wip_ctx = nm_data_for_wip.get('wip_context', {})
    if wip_ctx:
        wip_items = len(wip_ctx.get('work_items', []))
        wip_decisions = len(wip_ctx.get('decision_log', []))

    # --available flag: output just the available tokens number
    if '--available' in sys.argv:
        print(f'~{available:,}')
        return

    print(f'**Context mode: {profile["label"]}** (detected: {context_mode})')
    print()
    print('| Store | Count | Size | ~Tokens | Loaded |')
    print('|:------|:------|:-----|:--------|:-------|')
    print(f'| far_memory | {fm_msgs} msgs | {kb(fm_size)} | {tk(fm_size)} | 0 |')
    print(f'| near_memory | {nm_summaries}/{nm_window} summaries | {kb(nm_size)} | {tk(nm_size)} | on-demand |')
    if wip_items or wip_decisions:
        print(f'| wip_context | {wip_items} items, {wip_decisions} decisions | — | — | {"warm" if context_mode == "1m" else "on-demand"} |')
    print(f'| archives | {ai_entries} topics ({archive_count} files) | {kb(arc_size)} | {tk(arc_size)} | 0 |')
    print(f'| mind_memory | {node_count} nodes | {kb(mm_size)} | {tk(mm_size)} | {tk(mm_size)} |')
    print(f'| domain JSONs | {domain_count} refs | {kb(domain_size)} | {tk(domain_size)} | {tk(conv_size)} |')
    print(f'| CLAUDE.md | 1 file | {kb(claude_md)} | {tk(claude_md)} | {tk(claude_md)} |')
    print(f'| **Subtotal (all modules)** | | **{kb(disk_total)}** | **{tk(disk_total)}** | **~{loaded_tokens:,}** |')
    print(f'| **System overhead** | tools+MCP | | | **~{profile["system_overhead"]:,}** |')
    print(f'| **Conversation** | {fm_msgs} msgs | {kb(fm_size)} | | **~{conversation_tokens:,}** |')
    print(f'| **Context used** | | | | **~{total_context_used:,}** |')
    print(f'| **Usable limit** | {profile["label"]} - {profile["autocompact_buffer"]//1000}k buffer | | | **~{usable_limit:,}** |')
    print(f'| **Available** | | | | **~{available:,}** |')

if __name__ == '__main__':
    main()
