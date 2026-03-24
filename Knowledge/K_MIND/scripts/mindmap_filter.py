#!/usr/bin/env python3
"""Filter mindmap from mind_memory.md using depth_config.json.

Usage:
    python3 scripts/mindmap_filter.py                    # normal mode (apply depth config)
    python3 scripts/mindmap_filter.py --full             # full mode (all nodes)
    python3 scripts/mindmap_filter.py --path "session/near memory" --depth 5  # temp override

Reads mind/mind_memory.md and conventions/depth_config.json.
Outputs filtered mermaid mindmap to stdout.
"""
import argparse
import json
import os
import re
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
MIND_PATH = os.path.join(BASE_DIR, 'mind', 'mind_memory.md')
CONFIG_PATH = os.path.join(BASE_DIR, 'conventions', 'depth_config.json')

# Node classification: FRAMEWORK nodes are system rules, CONTENT nodes are searchable data
NODE_CLASSIFICATION = {
    'architecture': 'FRAMEWORK',
    'behaviors': 'FRAMEWORK',
    'constraints': 'FRAMEWORK',
    'conventions': 'FRAMEWORK',
    'work': 'CONTENT',
    'session': 'CONTENT',
    'documentation': 'CONTENT',
}

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def parse_mindmap(lines):
    """Parse mermaid mindmap lines into a tree structure.
    Returns list of (indent_level, text, line_index) tuples.
    indent_level is based on leading spaces (each 2 spaces = 1 level).
    """
    nodes = []
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        if not stripped.strip():
            continue
        # Count leading spaces
        content = stripped.lstrip()
        indent = len(stripped) - len(content)
        level = indent // 2  # 2 spaces per indent level
        nodes.append((level, content, i))
    return nodes

def get_node_path(nodes, idx):
    """Get the slash-separated path from root to node at index idx.
    Skips root node itself."""
    target_level = nodes[idx][0]
    path_parts = []

    # Walk backwards to find ancestors
    current_level = target_level
    for j in range(idx, -1, -1):
        node_level, text, _ = nodes[j]
        if node_level < current_level:
            path_parts.insert(0, text)
            current_level = node_level
        elif node_level == current_level and j == idx:
            path_parts.append(text)

    # Remove root((knowledge)) if present
    if path_parts and 'root(' in path_parts[0]:
        path_parts = path_parts[1:]

    return '/'.join(path_parts)

def get_depth_for_path(node_path, config):
    """Determine max depth for a node based on config.
    Returns (max_depth_from_toplevel, is_omitted).
    """
    omit = config.get('omit', [])
    overrides = config.get('overrides', {})
    default = config.get('default_depth', 3)

    # Check if this path or any ancestor is omitted
    for o in omit:
        if node_path == o or node_path.startswith(o + '/'):
            return 0, True

    # Check overrides (longest match wins)
    best_match = ''
    best_depth = default
    for path, depth in overrides.items():
        if node_path == path or node_path.startswith(path + '/'):
            if len(path) > len(best_match):
                best_match = path
                best_depth = depth

    return best_depth, False

def filter_mindmap(full_mode=False, temp_path=None, temp_depth=None):
    with open(MIND_PATH) as f:
        raw_lines = f.readlines()

    config = load_config()

    # Apply temp override if provided
    if temp_path and temp_depth is not None:
        if 'overrides' not in config:
            config['overrides'] = {}
        config['overrides'][temp_path] = temp_depth

    # Extract lines between ``` markers
    in_mermaid = False
    header_lines = []
    body_lines = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            if not in_mermaid:
                in_mermaid = True
                continue
            else:
                break
        if in_mermaid:
            # Keep header lines (%%{init...}, mindmap, root)
            if stripped.startswith('%%{') or stripped == 'mindmap' or 'root(' in stripped:
                header_lines.append(line.rstrip('\n'))
            else:
                body_lines.append(line.rstrip('\n'))

    if full_mode:
        # Output everything
        print('```mermaid')
        for h in header_lines:
            print(h)
        for b in body_lines:
            print(b)
        print('```')
        return

    # Parse body nodes
    nodes = parse_mindmap(body_lines)
    if not nodes:
        print('```mermaid')
        for h in header_lines:
            print(h)
        print('```')
        return

    # Determine root indent level (first node = top-level group)
    root_indent = nodes[0][0]

    # Build path for each node and decide inclusion
    output_lines = []
    for i, (level, text, line_idx) in enumerate(nodes):
        # Build this node's path
        path_parts = []
        target = level
        for j in range(i, -1, -1):
            nl, nt, _ = nodes[j]
            if nl < target:
                path_parts.insert(0, nt)
                target = nl
            elif j == i:
                path_parts.append(nt)
        node_path = '/'.join(path_parts)

        # Top-level group name (first path component)
        top_level = path_parts[0] if path_parts else text

        # Depth from top-level group (top-level = depth 1)
        depth_from_top = level - root_indent + 1

        # Check omit
        omit = config.get('omit', [])
        is_omitted = top_level in omit
        if is_omitted:
            continue

        # Find applicable depth limit
        overrides = config.get('overrides', {})
        default = config.get('default_depth', 3)
        max_depth = default

        # Check all overrides - longest matching prefix wins
        best_match_len = 0
        for opath, odepth in overrides.items():
            # Check if this override path matches node_path
            if node_path == opath or node_path.startswith(opath + '/'):
                if len(opath) > best_match_len:
                    best_match_len = len(opath)
                    # Depth is relative: override depth counted from the override point
                    override_parts = opath.split('/')
                    override_depth_from_top = len(override_parts)
                    # How deep is current node below the override point?
                    depth_below_override = depth_from_top - override_depth_from_top
                    # The override says show N levels from the override point
                    # So max depth_below_override = odepth - override_depth_from_top
                    max_depth = odepth

        if depth_from_top <= max_depth:
            output_lines.append(body_lines[line_idx])

    print('```mermaid')
    for h in header_lines:
        print(h)
    for line in output_lines:
        print(line)
    print('```')

def classify_nodes():
    """Output node classification table: which top-level nodes are FRAMEWORK vs CONTENT."""
    with open(MIND_PATH) as f:
        raw_lines = f.readlines()

    in_mermaid = False
    body_lines = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            if not in_mermaid:
                in_mermaid = True
                continue
            else:
                break
        if in_mermaid:
            if stripped.startswith('%%{') or stripped == 'mindmap' or 'root(' in stripped:
                continue
            body_lines.append(line.rstrip('\n'))

    nodes = parse_mindmap(body_lines)
    if not nodes:
        print("  No nodes found.")
        return

    root_indent = nodes[0][0]
    print(f"  {'NODE':<20} {'TYPE':<12} ROLE")
    print(f"  {'-'*20} {'-'*12} {'-'*30}")

    seen = set()
    for level, text, _ in nodes:
        if level == root_indent and text not in seen:
            seen.add(text)
            cls = NODE_CLASSIFICATION.get(text, 'UNKNOWN')
            if cls == 'FRAMEWORK':
                role = 'System rules — HOW things work'
            elif cls == 'CONTENT':
                role = 'Searchable data — WHAT exists'
            else:
                role = '(unclassified)'
            print(f"  {text:<20} {cls:<12} {role}")


def main():
    parser = argparse.ArgumentParser(description='Filter mindmap by depth config')
    parser.add_argument('--full', action='store_true', help='Full mode - show all nodes')
    parser.add_argument('--path', help='Temporary path override')
    parser.add_argument('--depth', type=int, help='Temporary depth for --path')
    parser.add_argument('--classify', action='store_true', help='Show FRAMEWORK/CONTENT node classification')
    parser.add_argument('--content-only', action='store_true', help='Filter to CONTENT nodes only')
    parser.add_argument('--framework-only', action='store_true', help='Filter to FRAMEWORK nodes only')
    args = parser.parse_args()

    if args.classify:
        classify_nodes()
        return

    # Apply type-based filtering via omit config
    if args.content_only or args.framework_only:
        target_type = 'CONTENT' if args.content_only else 'FRAMEWORK'
        # Temporarily omit nodes of the other type
        config = load_config()
        omit = list(config.get('omit', []))
        for node, cls in NODE_CLASSIFICATION.items():
            if cls != target_type and node not in omit:
                omit.append(node)
        config['omit'] = omit
        # Write temp config and run
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(config, tmp, indent=2)
            tmp_path = tmp.name
        # Swap config path temporarily
        global CONFIG_PATH
        orig = CONFIG_PATH
        CONFIG_PATH = tmp_path
        try:
            filter_mindmap(full_mode=args.full, temp_path=args.path, temp_depth=args.depth)
        finally:
            CONFIG_PATH = orig
            os.unlink(tmp_path)
        return

    filter_mindmap(
        full_mode=args.full,
        temp_path=args.path,
        temp_depth=args.depth
    )

if __name__ == '__main__':
    main()
