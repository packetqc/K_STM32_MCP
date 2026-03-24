#!/usr/bin/env python3
"""Route subject+action to methodology, skills, and scripts.

Usage:
    python3 scripts/routing_lookup.py --subject web --action troubleshoot
    python3 scripts/routing_lookup.py --skill render-web-page
    python3 scripts/routing_lookup.py --list
"""
import argparse
import json
import os
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
ROUTING_PATH = os.path.join(BASE_DIR, 'conventions', 'routing.json')
BEHAVIORS_PATH = os.path.join(BASE_DIR, 'behaviors', 'behaviors.json')


def load_routing():
    with open(ROUTING_PATH) as f:
        return json.load(f)['routes']


def lookup_by_subject_action(routes, subject, action=None):
    """Find routes matching subject and optionally action."""
    matches = []
    subject = subject.lower()
    for name, route in routes.items():
        if subject in route['subjects']:
            if action is None:
                matches.append((name, route))
            elif action.lower() in route['actions']:
                matches.append((name, route))
    return matches


def lookup_by_skill(routes, skill):
    """Find routes containing the given skill."""
    skill = skill.lower()
    matches = []
    for name, route in routes.items():
        if skill in route['skills']:
            matches.append((name, route))
    return matches


def lookup_by_script(routes, script):
    """Find routes containing the given script name."""
    script = script.lower()
    matches = []
    for name, route in routes.items():
        for s in route['scripts']:
            if script in s.lower():
                matches.append((name, route))
                break
    return matches


def load_behaviors():
    """Load behaviors.json and index by mind_memory_ref leaf text."""
    if not os.path.exists(BEHAVIORS_PATH):
        return {}
    with open(BEHAVIORS_PATH) as f:
        data = json.load(f)
    index = {}
    for ref in data.get('references', []):
        for mr in ref.get('mind_memory_refs', []):
            leaf = mr.split('::')[-1].lower()
            index[leaf] = ref
        index[ref['name']] = ref
    return index


def find_governing_behaviors(route, behaviors_index):
    """Find behaviors governing a route via mind_refs."""
    if not behaviors_index:
        return []
    governing = []
    seen = set()
    for ref in route.get('mind_refs', []):
        leaf = ref.split('::')[-1].lower()
        if leaf in behaviors_index:
            behav = behaviors_index[leaf]
            if behav['id'] not in seen:
                seen.add(behav['id'])
                governing.append(behav)
    return governing


def print_route(name, route, behaviors_index=None):
    print(f"\n  route: {name}")
    if route.get('methodology'):
        print(f"  methodology: {route['methodology']}")
    if route.get('skills'):
        print(f"  skills: {', '.join(route['skills'])}")
    if route.get('scripts'):
        print(f"  scripts: {', '.join(route['scripts'])}")
    if route.get('proof_output'):
        print(f"  proof_output: {', '.join(route['proof_output'])} [MANDATORY]")
    print(f"  subjects: {', '.join(route['subjects'])}")
    print(f"  actions: {', '.join(route['actions'])}")

    # Show governing behaviors grouped by category
    if behaviors_index:
        governing = find_governing_behaviors(route, behaviors_index)
        if governing:
            by_cat = {}
            for g in governing:
                cat = g.get('category', 'unknown')
                by_cat.setdefault(cat, []).append(g['name'])
            for cat in ['rules', 'routes', 'guides', 'cycles']:
                if cat in by_cat:
                    print(f"  {cat}: {', '.join(by_cat[cat])}")


def parse_methodology_steps(methodology_path):
    """Extract machine-readable step list from a methodology markdown file.

    Parses '### Step N.N: Title' and '### LOOP N' / '### PUBLICATION GATE'
    headings into a structured step list that routing_stack.py can enforce.

    Returns list of dicts: [{"id": "1.2", "slug": "test-engine", "title": "Test Engine", "phase": "loop-1"}, ...]
    """
    import re

    # Resolve path relative to Knowledge/ root
    repo_root = os.path.join(BASE_DIR, '..')  # K_MIND/.. = Knowledge/
    full_path = os.path.join(repo_root, methodology_path)
    if not os.path.exists(full_path):
        # Try relative to repo root (docs root)
        full_path = os.path.join(repo_root, '..', methodology_path)
    if not os.path.exists(full_path):
        return []

    with open(full_path) as f:
        content = f.read()

    steps = []
    current_phase = 'main'

    for line in content.split('\n'):
        # Detect phase markers
        loop_match = re.match(r'^###\s+LOOP\s+(\d+)', line)
        if loop_match:
            current_phase = f'loop-{loop_match.group(1)}'
            continue

        gate_match = re.match(r'^###\s+PUBLICATION GATE', line, re.IGNORECASE)
        if gate_match:
            current_phase = 'publication-gate'
            steps.append({
                'id': 'pub-gate',
                'slug': 'publication-gate',
                'title': 'Publication Gate',
                'phase': 'publication-gate'
            })
            continue

        # Detect step headings: "#### Step 1.2: Title" or "#### Step 1.2 Title"
        step_match = re.match(r'^####\s+Step\s+(\d+\.\d+)[:\s]+(.+)', line)
        if step_match:
            step_id = step_match.group(1)
            title = step_match.group(2).strip()
            # Generate slug from title
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            steps.append({
                'id': step_id,
                'slug': slug,
                'title': title,
                'phase': current_phase
            })

    return steps


def dispatch_info(name, route, behaviors_index=None):
    """Return machine-readable dispatch dict for programmatic use."""
    info = {
        'route': name,
        'methodology': route.get('methodology'),
        'skills': route.get('skills', []),
        'scripts': route.get('scripts', []),
        'proof_output': route.get('proof_output', []),
        'proof_required': bool(route.get('proof_output')),
    }

    # Parse methodology steps for enforcement
    if route.get('methodology'):
        steps = parse_methodology_steps(route['methodology'])
        if steps:
            info['steps'] = steps
            info['step_slugs'] = [s['slug'] for s in steps]

    if behaviors_index:
        governing = find_governing_behaviors(route, behaviors_index)
        if governing:
            info['governing_behaviors'] = [
                {'name': g['name'], 'category': g['category']}
                for g in governing
            ]
    return info


def main():
    parser = argparse.ArgumentParser(description='Route lookup')
    parser.add_argument('--subject', help='Subject keyword to match')
    parser.add_argument('--action', help='Action keyword to match')
    parser.add_argument('--skill', help='Skill name to reverse-lookup')
    parser.add_argument('--script', help='Script name to reverse-lookup')
    parser.add_argument('--list', action='store_true', help='List all routes')
    parser.add_argument('--json', action='store_true', help='Output dispatch info as JSON')
    args = parser.parse_args()

    routes = load_routing()
    behaviors_index = load_behaviors()

    if args.list:
        for name, route in routes.items():
            print_route(name, route, behaviors_index)
        return

    matches = []
    if args.subject:
        matches = lookup_by_subject_action(routes, args.subject, args.action)
    elif args.skill:
        matches = lookup_by_skill(routes, args.skill)
    elif args.script:
        matches = lookup_by_script(routes, args.script)
    else:
        parser.print_help()
        sys.exit(1)

    if not matches:
        print("no matching route found")
        sys.exit(1)

    if args.json:
        result = [dispatch_info(n, r, behaviors_index) for n, r in matches]
        print(json.dumps(result, indent=2))
    else:
        for name, route in matches:
            print_route(name, route, behaviors_index)


if __name__ == '__main__':
    main()
