#!/usr/bin/env python3
"""
routing_approve.py — Persist an approved proposed route and scaffold its artifacts.

When a no-route proposal succeeds and the user approves, this script:
1. Adds the route to routing.json
2. Scaffolds missing methodology file (if declared but doesn't exist)
3. Scaffolds missing skill directory (if declared but doesn't exist)
4. Adds mindmap node for the new capability
5. Tracks all proposals for audit

Usage (approve with full scaffolding):
    echo '{"name":"doc-translate","subjects":["documentation"],...}' | \
    python3 scripts/routing_approve.py --stdin --scaffold

Usage (approve route only — no scaffolding):
    echo '{"name":"doc-translate",...}' | python3 scripts/routing_approve.py --stdin

Usage (dry run — preview what would be created):
    echo '{"name":"doc-translate",...}' | python3 scripts/routing_approve.py --stdin --scaffold --dry

Usage (list proposals):
    python3 scripts/routing_approve.py --list
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
ROUTING_PATH = os.path.join(BASE_DIR, 'conventions', 'routing.json')
PROPOSALS_PATH = os.path.join(BASE_DIR, 'sessions', 'proposed_routes.json')
METRICS_PATH = os.path.join(BASE_DIR, 'conventions', 'route_metrics.json')

# Project root — two levels up from K_MIND/scripts/
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', '..'))
SKILLS_DIR = os.path.join(PROJECT_ROOT, '.claude', 'skills')
MINDMAP_PATH = os.path.join(BASE_DIR, 'mind', 'mind_memory.md')
BEHAVIORS_PATH = os.path.join(BASE_DIR, 'behaviors', 'behaviors.json')


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  written: {path}")


def validate_route(route):
    """Validate a route has required fields."""
    required = ['name', 'subjects', 'actions']
    missing = [f for f in required if f not in route or not route[f]]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    if not isinstance(route['subjects'], list):
        return False, "subjects must be a list"
    if not isinstance(route['actions'], list):
        return False, "actions must be a list"

    return True, "OK"


def check_conflicts(routing_data, route):
    """Check if the new route conflicts with existing routes."""
    conflicts = []
    for name, existing in routing_data['routes'].items():
        shared_subjects = set(route['subjects']) & set(existing['subjects'])
        shared_actions = set(route['actions']) & set(existing['actions'])
        if shared_subjects and shared_actions:
            conflicts.append({
                'route': name,
                'shared_subjects': list(shared_subjects),
                'shared_actions': list(shared_actions)
            })
    return conflicts


def save_proposal(route, status='pending'):
    """Save a proposal to the proposals tracking file."""
    proposals = load_json(PROPOSALS_PATH) or {'proposals': []}
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    proposals['proposals'].append({
        'route': route,
        'status': status,
        'timestamp': now
    })
    save_json(PROPOSALS_PATH, proposals)


def resolve_metrics(route_name, route):
    """Mark unrouted_hits as resolved when a route is approved.

    Matches hits where the subject appears in the new route's subjects
    or the action appears in the new route's actions.
    """
    if not os.path.exists(METRICS_PATH):
        return 0

    with open(METRICS_PATH, 'r') as f:
        metrics = json.load(f)

    subjects = set(route.get('subjects', []))
    actions = set(route.get('actions', []))
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    resolved_count = 0

    for hit in metrics.get('unrouted_hits', []):
        if hit.get('resolved_by'):
            continue  # already resolved
        # Resolve if subject matches OR action matches the new route
        hit_subject = hit.get('subject', '').lower()
        hit_action = (hit.get('action') or '').lower()
        if hit_subject in subjects or any(s in hit_subject for s in subjects):
            hit['resolved_by'] = route_name
            hit['resolved_at'] = now
            resolved_count += 1
        elif hit_action and (hit_action in actions or any(a in hit_action for a in actions)):
            hit['resolved_by'] = route_name
            hit['resolved_at'] = now
            resolved_count += 1

    if resolved_count > 0:
        # Move resolved entries to the resolved list
        still_unrouted = []
        for hit in metrics['unrouted_hits']:
            if hit.get('resolved_by'):
                metrics['resolved'].append(hit)
            else:
                still_unrouted.append(hit)
        metrics['unrouted_hits'] = still_unrouted
        metrics['stats']['total_misses'] = len(still_unrouted)
        metrics['stats']['total_resolved'] = len(metrics['resolved'])
        metrics['stats']['last_updated'] = now

        with open(METRICS_PATH, 'w') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    return resolved_count


def scaffold_methodology(route_name, route, dry=False):
    """Create methodology file if declared but missing."""
    meth_path = route.get('methodology')
    if not meth_path:
        return None

    # Resolve relative to Knowledge/
    full_path = os.path.join(PROJECT_ROOT, 'Knowledge', meth_path)
    if os.path.exists(full_path):
        return None  # already exists

    if dry:
        return f"WOULD CREATE: {full_path}"

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    subjects = ', '.join(route.get('subjects', []))
    actions = ', '.join(route.get('actions', []))
    skills = ', '.join(route.get('skills', []))
    proof = ', '.join(route.get('proof_output', []))
    chain = ', '.join(route.get('chain_deps', []))

    content = f"""# {route_name.replace('-', ' ').title()} — Methodology

## Purpose

<!-- Describe what this methodology governs and when it applies -->
Route: `{route_name}`
Subjects: {subjects}
Actions: {actions}

## When to Use

This methodology is activated when the routing table matches:
- Subject keywords: {subjects}
- Action keywords: {actions}

## Execution Steps

<!-- Define the step-by-step procedure -->

### Step 1: Assess

<!-- What to check before starting -->

### Step 2: Execute

<!-- Core work procedure -->

### Step 3: Verify

<!-- How to validate the work -->
"""

    if proof:
        content += f"""
### Step 4: Proof

Mandatory proof artifacts: **{proof}**

<!-- This route requires visual proof delivery -->
"""

    if skills:
        content += f"""
## Skills

Available skills for this route: `{skills}`
"""

    if chain:
        content += f"""
## Chain Dependencies

This route may trigger: {chain}
"""

    content += f"""
## Related

- `K_MIND/conventions/routing.json` — route definition: `{route_name}`
- `K_MIND/mind/mind_memory.md` — governing mindmap nodes
"""

    with open(full_path, 'w') as f:
        f.write(content)

    return f"CREATED: {full_path}"


def scaffold_skill(route_name, route, dry=False):
    """Create skill SKILL.md if declared but missing."""
    skills = route.get('skills', [])
    created = []

    for skill_name in skills:
        skill_dir = os.path.join(SKILLS_DIR, skill_name)
        skill_file = os.path.join(skill_dir, 'SKILL.md')

        if os.path.exists(skill_file):
            continue  # already exists

        if dry:
            created.append(f"WOULD CREATE: {skill_file}")
            continue

        os.makedirs(skill_dir, exist_ok=True)

        subjects = ', '.join(route.get('subjects', []))
        actions = ', '.join(route.get('actions', []))
        meth = route.get('methodology', '')
        meth_ref = f"\nMethodology: `{meth}`" if meth else ""

        content = f"""---
name: {skill_name}
user_invocable: true
description: "{route_name.replace('-', ' ').title()}. Usage: /{skill_name} $ARGUMENTS"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

## /{skill_name} — {route_name.replace('-', ' ').title()}

Arguments: $ARGUMENTS
{meth_ref}

### Purpose

<!-- Describe what this skill does -->
Route: `{route_name}` | Subjects: {subjects} | Actions: {actions}

### Execution

<!-- Define execution steps — Claude follows these when the skill is invoked -->

1. **Parse arguments**: `$ARGUMENTS`
2. **Execute**: <!-- core logic -->
3. **Verify**: <!-- validation -->
4. **Report**: Output results to user
"""

        with open(skill_file, 'w') as f:
            f.write(content)

        created.append(f"CREATED: {skill_file}")

    return created if created else None


def scaffold_mindmap_node(route_name, route, dry=False):
    """Add a mindmap node for the new route under conventions::methodologies."""
    if not os.path.exists(MINDMAP_PATH):
        return None

    with open(MINDMAP_PATH, 'r') as f:
        content = f.read()

    # Check if node already exists
    node_text = route_name.replace('-', ' ')
    if node_text in content:
        return None  # already exists

    if dry:
        return f"WOULD ADD mindmap node: '{node_text}' under conventions::methodologies"

    # Find the methodologies section and add the new node
    # Look for the pattern of methodology entries in the mindmap
    lines = content.split('\n')
    insert_idx = None
    indent = None

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if 'methodologies' in stripped.lower() and not stripped.startswith('```'):
            # Found methodologies section — next lines are the entries
            # Detect indent of children
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                indent = len(next_line) - len(next_line.lstrip())
            insert_idx = i + 1
            # Scan forward to find end of methodologies children
            for j in range(i + 1, len(lines)):
                child = lines[j]
                if not child.strip():
                    continue
                child_indent = len(child) - len(child.lstrip())
                if child_indent >= indent:
                    insert_idx = j + 1
                else:
                    break
            break

    if insert_idx is not None and indent is not None:
        new_line = ' ' * indent + node_text
        lines.insert(insert_idx, new_line)
        with open(MINDMAP_PATH, 'w') as f:
            f.write('\n'.join(lines))
        return f"ADDED mindmap node: '{node_text}'"

    return "SKIPPED: could not find methodologies section in mindmap"


def scaffold_behavior(route_name, route, dry=False):
    """Add a behavior entry to behaviors.json for the new route.

    Maps the route to the most appropriate behavior category based on its
    characteristics. Only adds if no existing behavior references this route.
    """
    behaviors_data = load_json(BEHAVIORS_PATH)
    if not behaviors_data:
        return None

    # Check if a behavior already references this route via mind_refs
    mind_refs = route.get('mind_refs', [])
    existing_refs = set()
    for ref in behaviors_data.get('references', []):
        for mr in ref.get('mind_memory_refs', []):
            existing_refs.add(mr)

    # Skip if any of the route's mind_refs already exist in behaviors
    for mr in mind_refs:
        if mr in existing_refs:
            return None

    # Determine category from route characteristics
    # Routes with proof_output or methodology tend to be guides/cycles
    # Routes matching system mechanics are routes category
    category = 'guides'  # default
    subjects = set(route.get('subjects', []))
    routing_subjects = {'routing', 'route', 'dispatch', 'behavior', 'directive'}
    cycle_subjects = {'test', 'build', 'cycle', 'pipeline', 'deploy'}
    if subjects & routing_subjects:
        category = 'routes'
    elif subjects & cycle_subjects and route.get('chain_deps'):
        category = 'cycles'

    # Generate next ID
    max_id = 0
    for ref in behaviors_data.get('references', []):
        bid = ref.get('id', '')
        if bid.startswith('behav-'):
            try:
                num = int(bid.split('-')[1])
                max_id = max(max_id, num)
            except ValueError:
                pass
    new_id = f"behav-{max_id + 1:03d}"

    # Build mind_memory_ref from route name
    node_text = route_name.replace('-', ' ')
    new_mind_ref = f"knowledge::behaviors::{category}::{node_text}"

    new_entry = {
        'id': new_id,
        'category': category,
        'name': route_name.replace('-', '_'),
        'description': f"Route: {route_name}. Subjects: {', '.join(route.get('subjects', []))}. Actions: {', '.join(route.get('actions', []))}.",
        'mind_memory_refs': [new_mind_ref]
    }

    if dry:
        return f"WOULD ADD behavior: {new_id} ({category}) for route '{route_name}'"

    behaviors_data['references'].append(new_entry)
    save_json(BEHAVIORS_PATH, behaviors_data)
    return f"ADDED behavior: {new_id} ({category}) '{new_entry['name']}'"


def main():
    parser = argparse.ArgumentParser(description='Approve and persist a proposed route')
    parser.add_argument('--stdin', action='store_true', help='Read route JSON from stdin')
    parser.add_argument('--dry', action='store_true', help='Preview without saving')
    parser.add_argument('--scaffold', action='store_true', help='Create missing methodology, skill, mindmap node')
    parser.add_argument('--list', action='store_true', help='List pending proposals')
    parser.add_argument('--name', help='Route name (slug)')
    parser.add_argument('--subjects', help='Comma-separated subjects')
    parser.add_argument('--actions', help='Comma-separated actions')
    parser.add_argument('--methodology', default=None, help='Methodology file path')
    parser.add_argument('--skills', default='', help='Comma-separated skills')
    parser.add_argument('--scripts', default='', help='Comma-separated scripts')
    parser.add_argument('--proof', default='', help='Comma-separated proof types')
    parser.add_argument('--mind-refs', default='', help='Comma-separated mind_refs')
    parser.add_argument('--chain-deps', default='', help='Comma-separated chain_deps')
    args = parser.parse_args()

    if args.list:
        proposals = load_json(PROPOSALS_PATH)
        if not proposals or not proposals.get('proposals'):
            print("  No pending proposals.")
            return
        print(f"  PROPOSED ROUTES ({len(proposals['proposals'])} total)")
        print()
        for i, p in enumerate(proposals['proposals'], 1):
            r = p['route']
            status = p['status']
            ts = p['timestamp']
            print(f"  {i}. [{r['name']}]  status: {status}  ({ts})")
            print(f"     subjects: {', '.join(r['subjects'])}")
            print(f"     actions: {', '.join(r['actions'])}")
        return

    # Build route from stdin or args
    if args.stdin:
        route = json.load(sys.stdin)
    else:
        if not args.name or not args.subjects or not args.actions:
            parser.error('--name, --subjects, and --actions are required (or use --stdin)')
        route = {
            'name': args.name,
            'subjects': [s.strip() for s in args.subjects.split(',') if s.strip()],
            'actions': [a.strip() for a in args.actions.split(',') if a.strip()],
            'methodology': args.methodology,
            'skills': [s.strip() for s in args.skills.split(',') if s.strip()],
            'scripts': [s.strip() for s in args.scripts.split(',') if s.strip()],
            'proof_output': [p.strip() for p in args.proof.split(',') if p.strip()],
            'mind_refs': [r.strip() for r in args.mind_refs.split(',') if r.strip()],
            'chain_deps': [c.strip() for c in args.chain_deps.split(',') if c.strip()],
        }

    # Validate
    valid, msg = validate_route(route)
    if not valid:
        print(f"  ERROR: {msg}")
        sys.exit(1)

    # Load routing data
    routing_data = load_json(ROUTING_PATH)

    # Extract name, build the route entry (name is the key, not a field)
    route_name = route.pop('name')

    # Check for duplicate name
    if route_name in routing_data['routes']:
        print(f"  ERROR: Route '{route_name}' already exists in routing.json")
        sys.exit(1)

    # Normalize fields with defaults
    route.setdefault('methodology', None)
    route.setdefault('skills', [])
    route.setdefault('scripts', [])
    route.setdefault('proof_output', [])
    route.setdefault('mind_refs', [])
    route.setdefault('chain_deps', [])

    # Check conflicts
    conflicts = check_conflicts(routing_data, route)

    # Display the route
    print(f"  ROUTE TO APPROVE: [{route_name}]")
    print(f"     subjects: {', '.join(route['subjects'])}")
    print(f"     actions: {', '.join(route['actions'])}")
    print(f"     methodology: {route['methodology'] or 'direct'}")
    if route['skills']:
        print(f"     skills: {', '.join(route['skills'])}")
    if route['scripts']:
        print(f"     scripts: {', '.join(route['scripts'])}")
    if route['proof_output']:
        print(f"     proof: {', '.join(route['proof_output'])}")
    if route['mind_refs']:
        short_refs = [r.split('::')[-1] for r in route['mind_refs'][:3]]
        print(f"     nodes: {', '.join(short_refs)}")
    if route['chain_deps']:
        print(f"     chains: {', '.join(route['chain_deps'])}")

    if conflicts:
        print()
        print(f"  CONFLICTS ({len(conflicts)}):")
        for c in conflicts:
            print(f"    [{c['route']}] shares subjects={c['shared_subjects']}, actions={c['shared_actions']}")

    # Scaffolding analysis (run for both dry and live)
    scaffold_results = []
    if args.scaffold:
        # We need the full route with name for scaffolding
        route_with_name = dict(route)
        route_with_name['name'] = route_name

        meth_result = scaffold_methodology(route_name, route, dry=args.dry)
        if meth_result:
            scaffold_results.append(meth_result)

        skill_results = scaffold_skill(route_name, route, dry=args.dry)
        if skill_results:
            scaffold_results.extend(skill_results)

        mindmap_result = scaffold_mindmap_node(route_name, route, dry=args.dry)
        if mindmap_result:
            scaffold_results.append(mindmap_result)

        behavior_result = scaffold_behavior(route_name, route, dry=args.dry)
        if behavior_result:
            scaffold_results.append(behavior_result)

    if args.dry:
        print()
        if scaffold_results:
            print("  SCAFFOLD PREVIEW:")
            for r in scaffold_results:
                print(f"    {r}")
            print()
        print("  DRY RUN — not saved. Remove --dry to persist.")
        # Save as pending proposal for tracking
        route_copy = dict(route)
        route_copy['name'] = route_name
        save_proposal(route_copy, status='dry-run')
        return

    # Persist to routing.json
    routing_data['routes'][route_name] = route
    save_json(ROUTING_PATH, routing_data)

    # Track as approved proposal
    route_copy = dict(route)
    route_copy['name'] = route_name
    status = 'approved+scaffolded' if args.scaffold else 'approved'
    save_proposal(route_copy, status=status)

    # Resolve matching metrics entries
    resolved = resolve_metrics(route_name, route)

    # Report scaffolding results
    if scaffold_results:
        print()
        print("  SCAFFOLDED:")
        for r in scaffold_results:
            print(f"    {r}")

    print()
    total = len(routing_data['routes'])
    artifacts = len(scaffold_results)
    print(f"  OK: Route '{route_name}' added to routing.json ({total} total routes)")
    if artifacts:
        print(f"  OK: {artifacts} artifact(s) scaffolded — Claude should fill templates with specifics")
    if resolved:
        print(f"  OK: {resolved} unrouted metric(s) resolved — self-evolution complete")


if __name__ == '__main__':
    main()
