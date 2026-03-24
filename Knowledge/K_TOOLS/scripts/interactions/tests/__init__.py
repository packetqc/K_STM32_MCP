"""
Rerunnable Test Modules for Interaction Test Driver
====================================================

Test modules are self-contained Python files that define a test plan
and metadata. They integrate with interaction_test_driver.py via
the --module flag.

Each module exports:
    TEST_ID    — unique slug (matches publication directory)
    TITLE      — display title (EN)
    TITLE_FR   — display title (FR)
    SLUG       — publication slug (directory name under docs/publications/)
    OUTPUT_DIR — relative path to publication assets

    def get_test_plan() -> dict:
        Returns the test plan JSON structure for interaction_test_driver.

Usage:
    python3 interaction_test_driver.py --module live_mindmap_expand
    python3 interaction_test_driver.py --module qa_live_mindmap_expand
    python3 interaction_test_driver.py --list-modules
"""

import importlib
import os

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_modules = None


def _scan_modules():
    """Discover test modules in this directory."""
    global _modules
    if _modules is not None:
        return
    _modules = {}
    for fname in sorted(os.listdir(_MODULE_DIR)):
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        mod_name = fname[:-3]
        try:
            mod = importlib.import_module(f'interactions.tests.{mod_name}')
            test_id = getattr(mod, 'TEST_ID', None)
            get_plan = getattr(mod, 'get_test_plan', None)
            if test_id and get_plan:
                _modules[mod_name] = {
                    'name': mod_name,
                    'test_id': test_id,
                    'title': getattr(mod, 'TITLE', mod_name),
                    'title_fr': getattr(mod, 'TITLE_FR', ''),
                    'slug': getattr(mod, 'SLUG', ''),
                    'output_dir': getattr(mod, 'OUTPUT_DIR', ''),
                    'get_test_plan': get_plan,
                }
        except Exception as e:
            print(f"  [tests] warn: failed to load {mod_name}: {e}")


def get_module(name):
    """Get a test module by name. Returns dict or None."""
    _scan_modules()
    return _modules.get(name)


def list_modules():
    """List all available test modules."""
    _scan_modules()
    return [{
        'name': m['name'],
        'test_id': m['test_id'],
        'title': m['title'],
        'slug': m['slug'],
    } for m in _modules.values()]
