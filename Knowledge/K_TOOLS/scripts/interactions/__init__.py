"""
Interaction Plugins for Web Test Engine
========================================

Directory-based tiers:

  interactions/              — REUSABLE plugins. Stable page-specific checks.
                               Built once for a known interface, runs every time.

  interactions/disposable/   — DISPOSABLE plugins. One-off verifications.
                               Kept for reruns but not part of standard flow.
                               Delete the file when no longer relevant.

Plugin contract:
    MATCH_PATTERNS = [r'regex/to/match/doc/path']
    DESCRIPTION = 'What this plugin checks'

    async def run(frame, page, context: dict) -> list[dict]

    - frame: the Playwright Frame containing the page content
    - page: the top-level Playwright Page
    - context: {
        'doc': str,           # doc path being tested
        'panel': str,         # 'Center' or 'Content'
        'phase': str,         # test phase name
        'nav': Frame|None,    # navigator frame (embedded mode)
        'mode': str,          # 'embedded' or 'standalone'
      }
    - returns: list of check results [{'type', 'label', 'result', 'detail'}]

The engine runs REUSABLE plugins automatically during --detailed tests.
DISPOSABLE plugins only run when explicitly requested via --disposable flag.
"""

import importlib
import os
import re

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_plugins = []


def _scan_dir(directory, tier, import_prefix):
    """Scan a directory for plugin modules."""
    found = []
    if not os.path.isdir(directory):
        return found
    for fname in sorted(os.listdir(directory)):
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        mod_name = fname[:-3]
        try:
            mod = importlib.import_module(f'{import_prefix}.{mod_name}')
            patterns = getattr(mod, 'MATCH_PATTERNS', [])
            run_fn = getattr(mod, 'run', None)
            if patterns and run_fn:
                found.append({
                    'name': mod_name,
                    'patterns': patterns,
                    'run': run_fn,
                    'tier': tier,
                    'description': getattr(mod, 'DESCRIPTION', ''),
                })
        except Exception as e:
            print(f"  [interactions] warn: failed to load {mod_name}: {e}")
    return found


def _load_plugins():
    """Discover plugins from both reusable and disposable directories."""
    global _plugins
    if _plugins:
        return
    _plugins.extend(_scan_dir(_PLUGIN_DIR, 'reusable', 'interactions'))
    _plugins.extend(_scan_dir(
        os.path.join(_PLUGIN_DIR, 'disposable'), 'disposable', 'interactions.disposable'))


def find_plugin(doc_path, include_disposable=False):
    """Find the interaction plugin matching a doc path.

    By default only returns reusable plugins. Pass include_disposable=True
    to also match disposable plugins (for explicit reruns).

    Returns (run_function, plugin_name) or (None, None).
    """
    _load_plugins()
    for plugin in _plugins:
        if plugin['tier'] == 'disposable' and not include_disposable:
            continue
        for pattern in plugin['patterns']:
            if re.search(pattern, doc_path):
                return plugin['run'], plugin['name']
    return None, None


def find_all_plugins(doc_path, include_disposable=False):
    """Find ALL plugins matching a doc path (reusable + optional disposable).

    Returns list of (run_function, plugin_name, tier) tuples.
    """
    _load_plugins()
    matches = []
    for plugin in _plugins:
        if plugin['tier'] == 'disposable' and not include_disposable:
            continue
        for pattern in plugin['patterns']:
            if re.search(pattern, doc_path):
                matches.append((plugin['run'], plugin['name'], plugin['tier']))
                break
    return matches


def list_plugins():
    """List all available interaction plugins with metadata."""
    _load_plugins()
    return [{
        'name': p['name'],
        'tier': p['tier'],
        'patterns': p['patterns'],
        'description': p['description'],
    } for p in _plugins]
