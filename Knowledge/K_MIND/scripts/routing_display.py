#!/usr/bin/env python3
"""Generate behavioral routing traces in vertical flow format (Option C).

Claude MUST output these traces as its own text — never hidden inside
a tool result. The vertical flow reads top-to-bottom with reasons at
each node and a <<< ACTIVE marker on the current route.

Usage:
    python3 scripts/routing_display.py --callout --subject web --action fix
    python3 scripts/routing_display.py --compact --subject web --action fix
    python3 scripts/routing_display.py --startup
    python3 scripts/routing_display.py --summary
    python3 scripts/routing_display.py --chain test-report-generation
    python3 scripts/routing_display.py --chain-map
    python3 scripts/routing_display.py --subject web --action fix --json
    python3 scripts/routing_display.py --propose --subject cooking --action bake
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
ROUTING_PATH = os.path.join(BASE_DIR, 'conventions', 'routing.json')
BEHAVIORS_PATH = os.path.join(BASE_DIR, 'behaviors', 'behaviors.json')
METRICS_PATH = os.path.join(BASE_DIR, 'conventions', 'route_metrics.json')

BEHAVIORAL_GROUPS = {
    'architecture': {'role': 'HOW you work', 'directive': 'Follow as implementation constraints', 'type': 'FRAMEWORK'},
    'behaviors':    {'role': 'WHAT you do and WHY', 'directive': 'Follow as behavioral directives', 'type': 'FRAMEWORK',
                     'subcategories': {
                         'rules': 'Mandatory hard behaviors — never skip',
                         'routes': 'Routing mechanics — resolution, display, discovery',
                         'guides': 'Operational patterns — day-to-day',
                         'cycles': 'Repeatable work patterns',
                     }},
    'constraints':  {'role': 'BOUNDARIES',   'directive': 'Never violate', 'type': 'FRAMEWORK'},
    'conventions':  {'role': 'HOW you execute', 'directive': 'Apply consistently', 'type': 'FRAMEWORK'},
    'work':         {'role': 'STATE',        'directive': 'Continuity anchor', 'type': 'CONTENT'},
    'session':      {'role': 'CONTEXT',      'directive': 'References work for concordance', 'type': 'CONTENT'},
    'documentation':{'role': 'STRUCTURE',    'directive': 'Reference for output', 'type': 'CONTENT'},
}


def load_behaviors():
    """Load behaviors.json and index references by mind_memory_ref for fast lookup."""
    if not os.path.exists(BEHAVIORS_PATH):
        return {}
    with open(BEHAVIORS_PATH) as f:
        data = json.load(f)
    # Index by mind_memory_ref for matching against route mind_refs
    index = {}
    for ref in data.get('references', []):
        for mr in ref.get('mind_memory_refs', []):
            # Extract the leaf part after last :: for matching
            leaf = mr.split('::')[-1].lower()
            index[leaf] = ref
        # Also index by name
        index[ref['name']] = ref
    return index


def find_governing_rules(route, behaviors_index):
    """Find behavior rules that govern a route via mind_refs overlap."""
    if not behaviors_index:
        return []
    mind_refs = route.get('mind_refs', [])
    governing = []
    seen = set()
    for ref in mind_refs:
        leaf = ref.split('::')[-1].lower()
        if leaf in behaviors_index:
            behav = behaviors_index[leaf]
            if behav['id'] not in seen:
                seen.add(behav['id'])
                governing.append(behav)
    return governing


def load_routing():
    with open(ROUTING_PATH) as f:
        return json.load(f)


def find_routes(routes, subject, action=None):
    matches = []
    subject = subject.lower()
    for name, route in routes.items():
        if subject in route['subjects']:
            if action is None or action.lower() in route['actions']:
                matches.append((name, route))
    return matches


def format_routing_callout(name, route, compact=False, behaviors_index=None):
    """Format a route as vertical flow (Option C)."""
    mind_refs = route.get('mind_refs', [])
    methodology = route.get('methodology', '') or ''
    skills = route.get('skills', [])
    proof = route.get('proof_output', [])
    chain_deps = route.get('chain_deps', [])

    # Find governing behaviors
    governing = find_governing_rules(route, behaviors_index) if behaviors_index else []
    rules = [g for g in governing if g.get('category') == 'rules']

    if compact:
        # One-liner Claude can paste into its text
        proof_str = f"  proof: {', '.join(proof)}" if proof else ""
        meth = methodology.split('/')[-1] if methodology else "direct"
        rules_str = f"  rules: {', '.join(r['name'] for r in rules)}" if rules else ""
        return f"[{name}]  method: {meth}{proof_str}{rules_str}"

    # Full vertical flow block
    lines = []
    lines.append(f'  [{name}]')

    # Details indented under the node
    if mind_refs:
        short_refs = [r.split('::')[-1] for r in mind_refs[:2]]
        lines.append(f'     nodes: {", ".join(short_refs)}')
    if methodology:
        lines.append(f'     method: {methodology.split("/")[-1]}')
    if skills:
        lines.append(f'     skills: {", ".join(skills)}')
    if proof:
        lines.append(f'     proof: {", ".join(proof)}  <<<')
    if chain_deps:
        lines.append(f'     may chain: {" > ".join(chain_deps)}')

    # Show governing behaviors by category
    if governing:
        by_cat = {}
        for g in governing:
            cat = g.get('category', 'unknown')
            by_cat.setdefault(cat, []).append(g['name'])
        for cat in ['rules', 'routes', 'guides', 'cycles']:
            if cat in by_cat:
                lines.append(f'     {cat}: {", ".join(by_cat[cat])}')

    return '\n'.join(lines)


def format_startup():
    """Startup behavioral groups as vertical flow with FRAMEWORK/CONTENT classification."""
    lines = []
    lines.append('  MINDMAP BEHAVIORAL ROUTING — ACTIVE')
    lines.append('')

    # Group by type
    for node_type in ['FRAMEWORK', 'CONTENT']:
        lines.append(f'  --- {node_type} ---')
        for group, info in BEHAVIORAL_GROUPS.items():
            if info.get('type') != node_type:
                continue
            lines.append(f'  [{group}]  {info["role"]} — {info["directive"]}')
            # Show subcategories for behaviors
            if 'subcategories' in info:
                for sub, desc in info['subcategories'].items():
                    lines.append(f'       {sub}: {desc}')
        lines.append('')

    lines.append('  7 groups (4 FRAMEWORK, 3 CONTENT) internalized.')
    return '\n'.join(lines)


def format_summary(routing_data):
    """Routing table as vertical list with key details."""
    routes = routing_data['routes']
    lines = []
    lines.append('  ROUTING TABLE — Subject+Action -> Methodology')
    lines.append('')

    for name, route in routes.items():
        subjects = ', '.join(route['subjects'][:3])
        meth = route.get('methodology', '') or '-'
        if meth != '-':
            meth = meth.split('/')[-1]
        proof = '  [PROOF]' if route.get('proof_output') else ''
        chain = route.get('chain_deps', [])
        chain_str = f'  chain: {" > ".join(chain)}' if chain else ''

        lines.append(f'  [{name}]{proof}')
        lines.append(f'     {subjects} -> {meth}{chain_str}')

    return '\n'.join(lines)


def build_chain_tree(routes, route_name, visited=None, depth=0, max_depth=5):
    if visited is None:
        visited = set()
    result = []
    is_cycle = route_name in visited
    result.append((depth, route_name, is_cycle))
    if is_cycle or depth >= max_depth:
        return result
    visited = visited | {route_name}
    route = routes.get(route_name, {})
    for dep in route.get('chain_deps', []):
        result.extend(build_chain_tree(routes, dep, visited, depth + 1, max_depth))
    return result


def format_chain(routes, route_name):
    """Chain dependency as vertical flow with indented children."""
    tree = build_chain_tree(routes, route_name)
    lines = []
    lines.append(f'  CHAIN: {route_name}')
    lines.append('')

    for depth, name, is_cycle in tree:
        indent = '     ' * depth
        route = routes.get(name, {})
        proof = '  [PROOF]' if route.get('proof_output') else ''
        cycle = '  <<< CYCLE' if is_cycle else ''
        if depth == 0:
            lines.append(f'  [{name}]{proof}')
        else:
            lines.append(f'  {indent}|')
            lines.append(f'  {indent}v')
            lines.append(f'  {indent}[{name}]{proof}{cycle}')

    unique = set(n for _, n, _ in tree)
    max_d = max(d for d, _, _ in tree)
    lines.append('')
    lines.append(f'  {len(unique)} routes, depth {max_d}')
    return '\n'.join(lines)


def find_nearby_routes(routes, subject, action=None):
    """Find routes with partial subject or action overlap for proposal context."""
    subject = subject.lower()
    action = action.lower() if action else None
    scored = []

    for name, route in routes.items():
        score = 0
        reasons = []

        # Check subject overlap (partial match — subject appears in any route subject)
        for s in route['subjects']:
            if subject in s or s in subject:
                score += 3
                reasons.append(f"subject overlap: '{s}'")
                break

        # Check action overlap
        if action:
            for a in route['actions']:
                if action in a or a in action:
                    score += 2
                    reasons.append(f"action overlap: '{a}'")
                    break

        # Check if subject appears in route name
        if subject in name:
            score += 1
            reasons.append(f"name contains '{subject}'")

        if score > 0:
            scored.append((score, name, route, reasons))

    scored.sort(key=lambda x: -x[0])
    return scored[:3]  # top 3 nearest


def find_related_mindmap_nodes(subject, action=None):
    """Search mind_memory.md for nodes related to the subject."""
    mindmap_path = os.path.join(BASE_DIR, 'mind', 'mind_memory.md')
    if not os.path.exists(mindmap_path):
        return []

    with open(mindmap_path) as f:
        lines = f.readlines()

    subject = subject.lower()
    matches = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('```') or stripped.startswith('%%'):
            continue
        if subject in stripped.lower():
            matches.append(stripped)
        elif action and action.lower() in stripped.lower():
            matches.append(stripped)

    return matches[:5]  # top 5 relevant nodes


def load_metrics():
    """Load route metrics file."""
    if not os.path.exists(METRICS_PATH):
        return {"version": "1.0", "unrouted_hits": [], "resolved": [],
                "stats": {"total_misses": 0, "total_resolved": 0, "last_updated": None}}
    with open(METRICS_PATH, 'r') as f:
        return json.load(f)


def save_metrics(metrics):
    """Save route metrics file."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    metrics['stats']['last_updated'] = now
    with open(METRICS_PATH, 'w') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)


def track_unrouted(subject, action, nearby_names):
    """Record a NO ROUTE miss in metrics. Returns hit count for this subject+action."""
    metrics = load_metrics()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Count previous hits for this subject+action pair
    key = f"{subject}|{action or '*'}"
    hit_count = sum(1 for h in metrics['unrouted_hits'] if h['key'] == key)

    metrics['unrouted_hits'].append({
        'key': key,
        'subject': subject,
        'action': action,
        'nearby_routes': nearby_names,
        'timestamp': now,
        'resolved_by': None
    })
    metrics['stats']['total_misses'] = len(metrics['unrouted_hits'])
    save_metrics(metrics)

    return hit_count + 1  # including this one


def find_equivalent_route(routes, subject, action=None):
    """Check if a nearby route is close enough to be an equivalent (score >= 4).
    Returns (route_name, route, score) or None."""
    nearby = find_nearby_routes(routes, subject, action)
    if nearby:
        top_score, top_name, top_route, top_reasons = nearby[0]
        # Score >= 4 means both subject AND action overlap — strong equivalent
        if top_score >= 4:
            return (top_name, top_route, top_score, top_reasons)
    return None


def get_metrics_frequency(subject, action=None):
    """Get frequency data for a subject+action from metrics."""
    metrics = load_metrics()
    key = f"{subject}|{action or '*'}"

    # Exact key matches
    exact = [h for h in metrics['unrouted_hits'] if h['key'] == key and not h['resolved_by']]

    # Similar subject matches (partial)
    similar = [h for h in metrics['unrouted_hits']
               if h['subject'] == subject and h['key'] != key and not h['resolved_by']]

    return {
        'exact_count': len(exact),
        'similar_count': len(similar),
        'total_unresolved': sum(1 for h in metrics['unrouted_hits'] if not h['resolved_by'])
    }


def format_proposal(routes, subject, action=None):
    """Generate a route proposal when no exact match exists.

    Self-evolution logic:
    1. Check for equivalent route (strong match) → shortcut
    2. Track the miss in metrics
    3. Show frequency data → system learns from patterns
    4. Propose generic route → user approves → persist after success
    """
    action_str = f" action='{action}'" if action else ""

    # --- Step 1: Check for equivalent route ---
    equivalent = find_equivalent_route(routes, subject, action)
    if equivalent:
        eq_name, eq_route, eq_score, eq_reasons = equivalent
        lines = []
        lines.append(f"  [EQUIVALENT ROUTE FOUND]  subject='{subject}'{action_str}")
        lines.append(f"     matched: [{eq_name}]  (score: {eq_score})")
        lines.append(f"     why: {', '.join(eq_reasons)}")
        lines.append(f"")
        lines.append(f"  SHORTCUT: Use [{eq_name}] for this request.")
        lines.append(f"  If this match is wrong, tell the user and propose a new route instead.")
        # Still track it — equivalent hits inform whether the route needs broader subjects
        track_unrouted(subject, action, [eq_name])
        return '\n'.join(lines)

    # --- Step 2: Track the miss ---
    nearby = find_nearby_routes(routes, subject, action)
    nearby_names = [n for _, n, _, _ in nearby]
    hit_count = track_unrouted(subject, action, nearby_names)

    # --- Step 3: Build proposal with frequency context ---
    freq = get_metrics_frequency(subject, action)

    lines = []
    lines.append(f"  [NO ROUTE]  subject='{subject}'{action_str}")
    lines.append(f"     nodes: (none matched in routing.json)")
    lines.append(f"     method: NONE — no methodology governs this")
    lines.append(f"     proof: (none required)")
    lines.append(f"     mindmap: NOT ENFORCED — behavior untracked")
    lines.append(f"")

    # Frequency data — self-evolution signal
    lines.append(f"  METRICS:")
    lines.append(f"    this request seen: {hit_count} time(s)")
    if freq['similar_count'] > 0:
        lines.append(f"    similar subject misses: {freq['similar_count']}")
    lines.append(f"    total unresolved misses: {freq['total_unresolved']}")
    if hit_count >= 2:
        lines.append(f"    >>> RECURRING PATTERN — this should become a route <<<")
    lines.append(f"")

    # Nearby routes for context
    if nearby:
        lines.append(f"  NEARBY ROUTES (partial match):")
        for score, name, route, reasons in nearby:
            meth = route.get('methodology', '') or 'direct'
            if meth != 'direct':
                meth = meth.split('/')[-1]
            proof = route.get('proof_output', [])
            proof_str = f"  proof: {', '.join(proof)}" if proof else ""
            lines.append(f"    [{name}]  method: {meth}{proof_str}")
            lines.append(f"      why: {', '.join(reasons)}")
        lines.append(f"")

    # Related mindmap nodes
    related_nodes = find_related_mindmap_nodes(subject, action)
    if related_nodes:
        lines.append(f"  RELATED MINDMAP NODES:")
        for node in related_nodes:
            lines.append(f"    - {node}")
        lines.append(f"")

    # --- Step 4: Proposed generic route ---
    slug = subject.replace(' ', '-').lower()
    if action:
        slug = f"{slug}-{action.replace(' ', '-').lower()}"

    lines.append(f"  PROPOSED ROUTE TEMPLATE:")
    lines.append(f"    name: \"{slug}\"")
    lines.append(f"    subjects: [\"{subject}\"]")
    lines.append(f"    actions: [\"{action or '...'}\"{'  <-- Claude: expand with related actions' if action else ''}]")
    lines.append(f"    methodology: null  <-- Claude: propose if a methodology fits")
    lines.append(f"    skills: []  <-- Claude: propose matching skills")
    lines.append(f"    scripts: []  <-- Claude: propose matching scripts")
    lines.append(f"    proof_output: []  <-- Claude: add if visual proof needed")
    lines.append(f"    mind_refs: []  <-- Claude: link to governing mindmap nodes")
    lines.append(f"    chain_deps: []  <-- Claude: declare collateral routes")
    lines.append(f"")
    lines.append(f"  SELF-EVOLUTION FLOW:")
    lines.append(f"    1. Claude proposes generic route above (filled with specifics)")
    lines.append(f"    2. User approves → Claude proceeds with work")
    lines.append(f"    3. Work completes → \"Was that what you expected?\"")
    lines.append(f"    4. User confirms → persist as official route:")
    lines.append(f"       python3 scripts/routing_approve.py --stdin --scaffold")

    return '\n'.join(lines)


def format_chain_map(routes):
    """All routes with chain info."""
    lines = []
    lines.append('  CHAIN MAP — which routes may trigger others')
    lines.append('')
    lines.append(f'  {"ROUTE":<30} {"DEPTH":<7} {"PROOF":<7} DEPS')
    lines.append(f'  {"-"*30} {"-"*7} {"-"*7} {"-"*20}')

    for name, route in routes.items():
        deps = route.get('chain_deps', [])
        deps_str = ', '.join(deps) if deps else '-'
        proof = 'yes' if route.get('proof_output') else '-'
        tree = build_chain_tree(routes, name)
        max_d = max(d for d, _, _ in tree)
        lines.append(f'  {name:<30} {max_d:<7} {proof:<7} {deps_str}')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Behavioral routing display (Option C)')
    parser.add_argument('--subject', help='Subject keyword')
    parser.add_argument('--action', help='Action keyword')
    parser.add_argument('--callout', action='store_true', help='Full vertical flow')
    parser.add_argument('--compact', action='store_true', help='Single-line')
    parser.add_argument('--summary', action='store_true', help='Routing table')
    parser.add_argument('--startup', action='store_true', help='Startup groups')
    parser.add_argument('--chain', metavar='ROUTE', help='Chain dependency graph')
    parser.add_argument('--chain-map', action='store_true', help='Full chain map')
    parser.add_argument('--propose', action='store_true', help='Propose a route when no match found')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()

    routing_data = load_routing()
    routes = routing_data['routes']

    if args.startup:
        print(format_startup())
        return
    if args.summary:
        print(format_summary(routing_data))
        return
    if args.chain_map:
        print(format_chain_map(routes))
        return
    if args.chain:
        if args.chain not in routes:
            print(f"Unknown route: '{args.chain}'")
            sys.exit(1)
        print(format_chain(routes, args.chain))
        return

    if args.subject:
        behaviors_index = load_behaviors()
        matches = find_routes(routes, args.subject, args.action)
        if not matches:
            # Always use proposal mode — provides context for Claude to propose a route
            print(format_proposal(routes, args.subject, args.action))
            sys.exit(0)
        if args.json:
            result = []
            for n, r in matches:
                entry = {
                    'route': n, 'mind_refs': r.get('mind_refs', []),
                    'methodology': r.get('methodology'),
                    'skills': r.get('skills', []),
                    'scripts': r.get('scripts', []),
                    'proof_output': r.get('proof_output', []),
                    'chain_deps': r.get('chain_deps', []),
                }
                governing = find_governing_rules(r, behaviors_index)
                if governing:
                    entry['governing_behaviors'] = [
                        {'name': g['name'], 'category': g['category']}
                        for g in governing
                    ]
                result.append(entry)
            print(json.dumps(result, indent=2))
        elif args.compact:
            for n, r in matches:
                print(format_routing_callout(n, r, compact=True, behaviors_index=behaviors_index))
        else:
            for n, r in matches:
                print(format_routing_callout(n, r, behaviors_index=behaviors_index))
                print()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
