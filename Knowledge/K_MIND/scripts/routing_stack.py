#!/usr/bin/env python3
"""Routing stack — track reentrant route chains with loop protection.

Manages a runtime routing stack that records the path of routes taken
during complex tasks. Provides loop detection, max depth enforcement,
and chain visualization for the user.

The stack persists in sessions/routing_stack.json and is reset on session init.

Usage:
    # Push a route onto the stack (returns error if loop/depth exceeded)
    python3 scripts/routing_stack.py --push web-page-visualization --reason "need screenshot for test report"

    # Pop the current route (mark completed)
    python3 scripts/routing_stack.py --pop

    # Pop with a specific result status
    python3 scripts/routing_stack.py --pop --status completed
    python3 scripts/routing_stack.py --pop --status skipped --reason "not needed"

    # Show current stack state
    python3 scripts/routing_stack.py --show

    # Show chain trace (full path visualization)
    python3 scripts/routing_stack.py --trace

    # Check if a route can be entered (dry-run push)
    python3 scripts/routing_stack.py --check web-page-visualization

    # Reroute — unwind collateral routes back to primary
    python3 scripts/routing_stack.py --reroute

    # Reroute full — nuclear reset: clear stack + force /mind-context full reinit
    python3 scripts/routing_stack.py --reroute --full

    # Mark a methodology step as completed
    python3 scripts/routing_stack.py --step route-lookup --note "confirmed methodology"
    python3 scripts/routing_stack.py --step test-engine --note "11/11 pass"

    # Show step progress for the active route
    python3 scripts/routing_stack.py --steps

    # Pop will BLOCK if methodology steps are incomplete (enforcement)
    python3 scripts/routing_stack.py --pop                   # blocked if steps missing
    python3 scripts/routing_stack.py --pop --force            # override enforcement
    python3 scripts/routing_stack.py --pop --status skipped   # exit without completing (not blocked)

    # Reset stack (called by session_init.py)
    python3 scripts/routing_stack.py --reset

    # JSON output for programmatic use
    python3 scripts/routing_stack.py --show --json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
STACK_PATH = os.path.join(BASE_DIR, 'sessions', 'routing_stack.json')
ROUTING_PATH = os.path.join(BASE_DIR, 'conventions', 'routing.json')

# Safety limits
MAX_STACK_DEPTH = 5       # max nested routes before refusing
MAX_SAME_ROUTE = 2        # max times the same route can appear in the stack
MAX_TOTAL_ENTRIES = 20     # max total entries in history before auto-trim


def load_stack():
    """Load or initialize the routing stack."""
    if os.path.exists(STACK_PATH):
        with open(STACK_PATH) as f:
            return json.load(f)
    return new_stack()


def new_stack():
    return {
        'active': [],       # current stack (list of frame dicts)
        'history': [],      # completed chains (for audit trail)
        'stats': {
            'total_pushes': 0,
            'total_pops': 0,
            'loops_prevented': 0,
            'depth_exceeded': 0,
            'max_depth_reached': 0
        }
    }


def save_stack(stack, commit=True):
    """Save routing stack to filesystem.

    When commit=True (default), also commits to git for resilience.
    This ensures stack state survives crashes, compaction, and session loss.
    Consistency + resilience over performance."""
    os.makedirs(os.path.dirname(STACK_PATH), exist_ok=True)
    with open(STACK_PATH, 'w') as f:
        json.dump(stack, f, indent=2)

    if commit:
        _git_commit_stack()


def _git_commit_stack():
    """Commit routing stack to git for resilience. Silent on failure."""
    import subprocess
    try:
        # Stage only the stack file
        subprocess.run(
            ['git', 'add', STACK_PATH],
            capture_output=True, timeout=10
        )
        # Commit with a deterministic message (no user input needed)
        active_routes = []
        if os.path.exists(STACK_PATH):
            with open(STACK_PATH) as f:
                data = json.load(f)
            active_routes = [f['route'] for f in data.get('active', [])]
        route_info = ', '.join(active_routes) if active_routes else 'empty'
        subprocess.run(
            ['git', 'commit', '-m', f'stack: {route_info}'],
            capture_output=True, timeout=10
        )
    except Exception:
        pass  # resilience: never block work on git failure


def load_routing():
    with open(ROUTING_PATH) as f:
        return json.load(f)


def load_methodology_steps(route_name):
    """Load methodology steps for a route from routing_lookup.py.
    Returns list of step slug strings, or [] if no methodology."""
    try:
        from routing_lookup import load_routing as load_routes, load_behaviors, dispatch_info
        routes = load_routes()
        if route_name in routes:
            behaviors_index = load_behaviors()
            info = dispatch_info(route_name, routes[route_name], behaviors_index)
            return info.get('step_slugs', [])
    except Exception:
        pass
    return []


def make_frame(route_name, reason=None, parent=None):
    """Create a stack frame for a route entry.
    Automatically loads methodology steps for enforcement."""
    steps_required = load_methodology_steps(route_name)
    frame = {
        'route': route_name,
        'reason': reason or '',
        'parent': parent,
        'entered_at': datetime.now(timezone.utc).isoformat(),
        'status': 'active'
    }
    if steps_required:
        frame['steps_required'] = steps_required
        frame['steps_completed'] = {}
    return frame


def check_loop(stack, route_name):
    """Check if pushing this route would create a loop.
    Returns (allowed: bool, reason: str)."""
    active = stack['active']

    # Check stack depth
    if len(active) >= MAX_STACK_DEPTH:
        return False, f"max stack depth ({MAX_STACK_DEPTH}) reached"

    # Count occurrences of this route in active stack
    same_count = sum(1 for f in active if f['route'] == route_name)
    if same_count >= MAX_SAME_ROUTE:
        return False, f"route '{route_name}' already appears {same_count}x in stack (max {MAX_SAME_ROUTE})"

    # Check for direct recursion (same route is current top)
    if active and active[-1]['route'] == route_name:
        return False, f"direct recursion: '{route_name}' is already the active route"

    return True, "ok"


def push_route(stack, route_name, reason=None):
    """Push a route onto the stack. Returns (success, message)."""
    allowed, msg = check_loop(stack, route_name)
    if not allowed:
        stack['stats']['loops_prevented'] += 1
        if 'depth' in msg:
            stack['stats']['depth_exceeded'] += 1
        save_stack(stack)
        return False, msg

    parent = stack['active'][-1]['route'] if stack['active'] else None
    frame = make_frame(route_name, reason, parent)
    stack['active'].append(frame)
    stack['stats']['total_pushes'] += 1
    stack['stats']['max_depth_reached'] = max(
        stack['stats']['max_depth_reached'],
        len(stack['active'])
    )
    save_stack(stack)
    return True, f"entered route '{route_name}' (depth {len(stack['active'])})"


def mark_step(stack, step_slug, note=None):
    """Mark a methodology step as completed on the active route.
    Returns (success, message)."""
    if not stack['active']:
        return False, "stack is empty — no active route to mark step on"

    frame = stack['active'][-1]
    if 'steps_required' not in frame:
        return False, f"route '{frame['route']}' has no methodology steps to track"

    if step_slug not in frame['steps_required']:
        return False, f"step '{step_slug}' is not a required step for route '{frame['route']}'"

    if step_slug in frame.get('steps_completed', {}):
        return True, f"step '{step_slug}' already completed"

    frame.setdefault('steps_completed', {})[step_slug] = {
        'at': datetime.now(timezone.utc).isoformat(),
        'note': note or ''
    }

    save_stack(stack)

    done = len(frame['steps_completed'])
    total = len(frame['steps_required'])
    return True, f"step '{step_slug}' completed ({done}/{total})"


def get_missing_steps(frame):
    """Return list of required steps not yet completed."""
    if 'steps_required' not in frame:
        return []
    completed = set(frame.get('steps_completed', {}).keys())
    return [s for s in frame['steps_required'] if s not in completed]


def pop_route(stack, status='completed', reason=None, force=False):
    """Pop the top route from the stack. Returns (success, message, frame).

    ENFORCEMENT: If the route has methodology steps, pop is BLOCKED unless
    all steps are completed (or force=True / status is skipped/failed)."""
    if not stack['active']:
        return False, "stack is empty — nothing to pop", None

    frame = stack['active'][-1]

    # Enforce methodology steps on normal completion
    if status == 'completed' and not force:
        missing = get_missing_steps(frame)
        if missing:
            done = len(frame.get('steps_completed', {}))
            total = len(frame.get('steps_required', []))
            msg = (f"BLOCKED: cannot pop '{frame['route']}' as completed — "
                   f"{len(missing)}/{total} steps incomplete:\n"
                   f"  missing: {', '.join(missing)}\n"
                   f"  completed: {done}/{total}\n"
                   f"  Use --force to override or --status skipped/failed to exit without completing")
            return False, msg, None

    frame = stack['active'].pop()
    frame['status'] = status
    frame['exited_at'] = datetime.now(timezone.utc).isoformat()
    if reason:
        frame['exit_reason'] = reason

    # Add to history
    stack['history'].append(frame)
    stack['stats']['total_pops'] += 1

    # Auto-trim history
    if len(stack['history']) > MAX_TOTAL_ENTRIES:
        stack['history'] = stack['history'][-MAX_TOTAL_ENTRIES:]

    save_stack(stack)
    return True, f"exited route '{frame['route']}' ({status})", frame


def format_stack_display(stack):
    """Option C vertical flow — Claude outputs this as its own text."""
    active = stack['active']
    if not active:
        return 'STACK: empty (no active chain)'

    lines = []
    for i, frame in enumerate(active):
        reason = frame.get('reason', '')
        is_current = (i == len(active) - 1)

        # Build step progress indicator
        step_info = ''
        if 'steps_required' in frame:
            done = len(frame.get('steps_completed', {}))
            total = len(frame['steps_required'])
            step_info = f'  steps: {done}/{total}'

        if is_current:
            lines.append(f'  [{frame["route"]}]  "{reason}"    <<< ACTIVE ({len(active)}/{MAX_STACK_DEPTH}){step_info}')
            # Show step checklist for active route
            if 'steps_required' in frame:
                completed = set(frame.get('steps_completed', {}).keys())
                for step in frame['steps_required']:
                    mark = 'x' if step in completed else ' '
                    lines.append(f'     [{mark}] {step}')
        else:
            lines.append(f'  [{frame["route"]}]  "{reason}"{step_info}')
            lines.append(f'       |')
            lines.append(f'       v')

    return '\n'.join(lines)


def format_chain_trace(stack):
    """Option C vertical flow for audit trace."""
    lines = []

    # Active chain
    active = stack['active']
    if active:
        lines.append('  ACTIVE:')
        for i, frame in enumerate(active):
            reason = frame.get('reason', '')
            is_current = (i == len(active) - 1)
            if is_current:
                lines.append(f'  [{frame["route"]}]  "{reason}"    <<< ACTIVE')
            else:
                lines.append(f'  [{frame["route"]}]  "{reason}"')
                lines.append(f'       |')
                lines.append(f'       v')
        lines.append('')

    # Recent history
    history = stack['history'][-10:]
    if history:
        lines.append('  COMPLETED:')
        for frame in reversed(history):
            parent = frame.get('parent', '-') or 'root'
            status = frame['status']
            icon = 'ok' if status == 'completed' else 'REROUTED' if status == 'rerouted' else status
            duration = '-'
            if frame.get('entered_at') and frame.get('exited_at'):
                try:
                    entered = datetime.fromisoformat(frame['entered_at'])
                    exited = datetime.fromisoformat(frame['exited_at'])
                    secs = int((exited - entered).total_seconds())
                    duration = f"{secs}s" if secs < 60 else f"{secs // 60}m{secs % 60}s"
                except (ValueError, TypeError):
                    pass
            lines.append(f'  [{frame["route"]}]  {icon}  (from {parent}, {duration})')
        lines.append('')

    stats = stack['stats']
    lines.append(f'  stats: {stats["total_pushes"]} pushes, {stats["total_pops"]} pops, '
                 f'{stats["loops_prevented"]} blocked, max depth {stats["max_depth_reached"]}')

    return '\n'.join(lines)


def suspend_route(stack, reason=None):
    """Suspend the current active route (mark as suspended, not popped).
    Used when a new user prompt interrupts mid-processing."""
    if not stack['active']:
        return False, "stack is empty — nothing to suspend"

    top = stack['active'][-1]
    if top.get('status') == 'suspended':
        return False, f"route '{top['route']}' is already suspended"

    top['status'] = 'suspended'
    top['suspended_at'] = datetime.now(timezone.utc).isoformat()
    if reason:
        top['suspend_reason'] = reason

    save_stack(stack)
    return True, f"suspended route '{top['route']}'"


def resume_route(stack):
    """Resume the most recently suspended route on the stack."""
    if not stack['active']:
        return False, "stack is empty — nothing to resume"

    # Find the topmost suspended route
    for frame in reversed(stack['active']):
        if frame.get('status') == 'suspended':
            frame['status'] = 'active'
            frame.pop('suspended_at', None)
            frame.pop('suspend_reason', None)
            save_stack(stack)
            return True, f"resumed route '{frame['route']}'"

    return False, "no suspended routes found"


def format_suspend_display(stack):
    """Show stack with suspended routes marked."""
    active = stack['active']
    if not active:
        return 'STACK: empty'

    lines = []
    for i, frame in enumerate(active):
        reason = frame.get('reason', '')
        status = frame.get('status', 'active')
        is_current = (i == len(active) - 1)

        if status == 'suspended':
            lines.append(f'  [{frame["route"]}]  "{reason}"    ⏸ SUSPENDED')
        elif is_current:
            lines.append(f'  [{frame["route"]}]  "{reason}"    <<< ACTIVE ({len(active)}/{MAX_STACK_DEPTH})')
        else:
            lines.append(f'  [{frame["route"]}]  "{reason}"')

        if i < len(active) - 1:
            lines.append(f'       |')
            lines.append(f'       v')

    return '\n'.join(lines)


def reroute(stack, full=False):
    """Unwind all collateral routes back to the original parent route.
    Pops everything except the bottom-most (original) route, marking
    derailed routes as 'rerouted'. Returns the route we're back on.

    If full=True, clears the ENTIRE stack (nuclear reset) and signals
    Claude to re-read CLAUDE.md and reinitialize on the mindmap."""
    if full:
        # Nuclear reset — clear everything
        derailed = [f['route'] for f in stack['active']]
        for frame in stack['active']:
            frame['status'] = 'rerouted'
            frame['exited_at'] = datetime.now(timezone.utc).isoformat()
            frame['exit_reason'] = 'full reroute — nuclear reset'
            stack['history'].append(frame)
            stack['stats']['total_pops'] += 1
        stack['active'] = []
        save_stack(stack)
        return 'FULL_RESET', derailed

    if len(stack['active']) <= 1:
        if full:
            # Even with empty stack, full reroute triggers reinit
            stack['active'] = []
            save_stack(stack)
            return 'FULL_RESET', []
        return None, "already on the primary route (nothing to reroute)"

    # The bottom of the stack is the original route
    original = stack['active'][0]
    derailed = []

    # Pop all collateral routes (everything above the bottom)
    while len(stack['active']) > 1:
        frame = stack['active'].pop()
        frame['status'] = 'rerouted'
        frame['exited_at'] = datetime.now(timezone.utc).isoformat()
        frame['exit_reason'] = 'rerouted by user'
        stack['history'].append(frame)
        stack['stats']['total_pops'] += 1
        derailed.append(frame['route'])

    save_stack(stack)
    return original, derailed


def format_reroute_display(original, derailed):
    """Option C vertical flow for reroute — unwound routes crossed out."""
    lines = []

    # Full reset — nuclear option
    if original == 'FULL_RESET':
        lines.append('  FULL REROUTE — NUCLEAR RESET')
        lines.append('')
        if derailed:
            for route in derailed:
                lines.append(f'  x--x [{route}]  (unwound)')
            lines.append('')
        lines.append('  Stack cleared. Reinitializing on mindmap behavior graph.')
        lines.append('  >>> CLAUDE MUST NOW RUN: /mind-context full <<<')
        return '\n'.join(lines)

    # Normal reroute — back to primary
    lines.append('  REROUTED')
    lines.append('')
    reason = original.get('reason', '')
    lines.append(f'  [{original["route"]}]  "{reason}"    <<< BACK HERE')
    for route in derailed:
        lines.append(f'       |')
        lines.append(f'       x')
        lines.append(f'  x--x [{route}]  (unwound)')
    lines.append('')
    lines.append(f'  Resume [{original["route"]}] from where it was interrupted.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Routing stack management')
    parser.add_argument('--push', metavar='ROUTE', help='Push a route onto the stack')
    parser.add_argument('--pop', action='store_true', help='Pop the top route')
    parser.add_argument('--status', default='completed', help='Status for pop (completed/skipped/failed)')
    parser.add_argument('--reason', help='Reason for push or pop')
    parser.add_argument('--force', action='store_true', help='Force pop even with incomplete methodology steps')
    parser.add_argument('--step', metavar='SLUG', help='Mark a methodology step as completed on the active route')
    parser.add_argument('--note', help='Optional note for the step completion')
    parser.add_argument('--steps', action='store_true', help='Show step progress for the active route')
    parser.add_argument('--check', metavar='ROUTE', help='Check if a route can be entered (dry-run)')
    parser.add_argument('--show', action='store_true', help='Show current stack')
    parser.add_argument('--trace', action='store_true', help='Show full chain trace')
    parser.add_argument('--suspend', action='store_true', help='Suspend the current active route (interrupt stacking)')
    parser.add_argument('--resume', action='store_true', help='Resume the most recently suspended route')
    parser.add_argument('--reroute', action='store_true', help='Unwind all collateral routes back to original task')
    parser.add_argument('--full', action='store_true', help='Nuclear reset: clear entire stack + trigger /mind-context full reinit')
    parser.add_argument('--reset', action='store_true', help='Reset the stack')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()

    stack = load_stack()

    if args.reset:
        stack = new_stack()
        save_stack(stack, commit=False)  # session_init handles its own commit
        print("routing stack reset")
        return

    if args.suspend:
        success, msg = suspend_route(stack, args.reason)
        if args.json:
            print(json.dumps({'success': success, 'message': msg}))
        else:
            print(msg)
            if success:
                print()
                print(format_suspend_display(stack))
        sys.exit(0 if success else 1)

    if args.resume:
        success, msg = resume_route(stack)
        if args.json:
            print(json.dumps({'success': success, 'message': msg}))
        else:
            print(msg)
            if success:
                print()
                print(format_suspend_display(stack))
        sys.exit(0 if success else 1)

    if args.reroute:
        original, derailed = reroute(stack, full=args.full)
        if original is None:
            print(derailed)  # derailed contains the message string
        elif original == 'FULL_RESET':
            if args.json:
                print(json.dumps({
                    'rerouted_to': 'FULL_RESET',
                    'derailed': derailed,
                    'action': '/mind-context full'
                }))
            else:
                print(format_reroute_display(original, derailed))
        else:
            if args.json:
                print(json.dumps({
                    'rerouted_to': original['route'],
                    'derailed': derailed,
                    'reason': original.get('reason', '')
                }))
            else:
                print(format_reroute_display(original, derailed))
        return

    if args.full and not args.reroute:
        # --full without --reroute: treat as full reroute anyway
        original, derailed = reroute(stack, full=True)
        if args.json:
            print(json.dumps({
                'rerouted_to': 'FULL_RESET',
                'derailed': derailed,
                'action': '/mind-context full'
            }))
        else:
            print(format_reroute_display(original, derailed))
        return

    if args.step:
        success, msg = mark_step(stack, args.step, args.note)
        if args.json:
            print(json.dumps({'success': success, 'message': msg}))
        else:
            print(msg)
            if success and stack['active']:
                frame = stack['active'][-1]
                if 'steps_required' in frame:
                    completed = set(frame.get('steps_completed', {}).keys())
                    for step in frame['steps_required']:
                        mark = 'x' if step in completed else ' '
                        print(f'  [{mark}] {step}')
        sys.exit(0 if success else 1)

    if args.steps:
        if not stack['active']:
            print("stack is empty — no active route")
            sys.exit(1)
        frame = stack['active'][-1]
        if 'steps_required' not in frame:
            print(f"route '{frame['route']}' has no methodology steps")
        else:
            done = len(frame.get('steps_completed', {}))
            total = len(frame['steps_required'])
            completed = set(frame.get('steps_completed', {}).keys())
            print(f"  [{frame['route']}]  steps: {done}/{total}")
            for step in frame['steps_required']:
                mark = 'x' if step in completed else ' '
                print(f'  [{mark}] {step}')
            missing = get_missing_steps(frame)
            if missing:
                print(f"\n  BLOCKED from pop: {len(missing)} steps remaining")
            else:
                print(f"\n  READY to pop: all steps completed")
        sys.exit(0)

    if args.push:
        success, msg = push_route(stack, args.push, args.reason)
        if args.json:
            print(json.dumps({'success': success, 'message': msg, 'depth': len(stack['active'])}))
        else:
            if success:
                print(msg)
                print()
                print(format_stack_display(stack))
            else:
                print(f"BLOCKED: {msg}")
                print()
                print(format_stack_display(stack))
        sys.exit(0 if success else 1)

    if args.pop:
        success, msg, frame = pop_route(stack, args.status, args.reason, force=args.force)
        if args.json:
            print(json.dumps({'success': success, 'message': msg, 'frame': frame}))
        else:
            print(msg)
            if stack['active']:
                print()
                print(format_stack_display(stack))
            else:
                print("stack now empty — chain complete")
        sys.exit(0 if success else 1)

    if args.check:
        allowed, msg = check_loop(stack, args.check)
        if args.json:
            print(json.dumps({'allowed': allowed, 'reason': msg, 'current_depth': len(stack['active'])}))
        else:
            if allowed:
                print(f"OK: route '{args.check}' can be entered (current depth: {len(stack['active'])})")
            else:
                print(f"BLOCKED: {msg}")
        sys.exit(0 if allowed else 1)

    if args.trace:
        if args.json:
            print(json.dumps(stack, indent=2))
        else:
            print(format_chain_trace(stack))
        return

    if args.show:
        if args.json:
            print(json.dumps({'active': stack['active'], 'depth': len(stack['active'])}, indent=2))
        else:
            print(format_stack_display(stack))
        return

    parser.print_help()


if __name__ == '__main__':
    main()
