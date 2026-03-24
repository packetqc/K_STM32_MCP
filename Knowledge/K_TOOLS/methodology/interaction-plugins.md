# Interaction Plugins — Methodology

## Purpose

Extend the web test engine with page-specific interaction knowledge. Plugins know HOW to interact with a specific interface — what to check, what to click, what to verify. They complement the engine's generic widget scan with targeted, meaningful checks.

## Three-Tier Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  GENERIC — Engine Built-in                                    │
│                                                              │
│  scan_frame_widgets() → trigger_widget()                     │
│  Works on ANY page. No plugin needed.                        │
│  Detects: buttons, links, selects, accordions, tabs,         │
│           checkboxes, radios, inputs                          │
│                                                              │
│  This is the baseline. Always runs during --detailed tests.  │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  REUSABLE — interactions/                                     │
│                                                              │
│  Stable page-specific checks. Built once for a known         │
│  interface. Runs automatically on every --detailed test       │
│  when the doc path matches.                                  │
│                                                              │
│  Example: tests_interface.py                                 │
│    - Dashboard stats render (Tests, Runs, Pass, Fail)        │
│    - LED matrix grid (rows × columns × LEDs)                 │
│    - Test links present and countable                        │
│    - Latest run LED status (color + score)                   │
│    - Click routing to content-frame (embedded mode)          │
│                                                              │
│  These persist because the interface is stable.              │
│  Built once, used forever. Knowledge accumulates.            │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  DISPOSABLE — interactions/disposable/                        │
│                                                              │
│  One-off verifications for ad-hoc requests.                  │
│  Created on demand when user asks to verify something.       │
│  Excluded from standard test flow.                           │
│                                                              │
│  Example: tab_bar_removed.py                                 │
│    - Confirms tab bar is gone after removal task             │
│    - Kept for reruns if someone needs to verify again        │
│    - Not part of daily testing                               │
│                                                              │
│  Lifecycle:                                                  │
│    Create → Verify → Keep for reruns → Delete when obsolete  │
│    OR: Create → Verify → Promote to reusable (move up)      │
└──────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
K_TOOLS/scripts/
  web_test_engine.py                ← generic engine (unchanged API)
  interactions/
    __init__.py                     ← discovery: walks both dirs, tier = directory
    tests_interface.py              ← REUSABLE: Tests Interface dashboard
    <future_interface>.py           ← REUSABLE: next interface plugin
    disposable/
      __init__.py
      tab_bar_removed.py            ← DISPOSABLE: tab bar verification
      <future_check>.py             ← DISPOSABLE: next one-off check
```

## Plugin Contract

```python
MATCH_PATTERNS = [r'regex/matching/doc/path']
DESCRIPTION = 'What this plugin checks'

async def run(frame, page, context: dict) -> list[dict]:
    """
    frame:   Playwright Frame with page content
    page:    top-level Playwright Page
    context: {
        'doc':   str,         # doc path being tested
        'panel': str,         # 'Center' or 'Content'
        'phase': str,         # test phase
        'nav':   Frame|None,  # navigator frame (embedded mode)
        'mode':  str,         # 'embedded' or 'standalone'
    }
    returns: [{'type': 'interaction', 'label': str, 'result': 'PASS'|'FAIL', 'detail': str}]
    """
```

## Discovery Rules

1. Engine calls `find_all_plugins(doc_path)` after generic widget scan
2. All plugins whose `MATCH_PATTERNS` match the doc path are returned
3. Multiple plugins can match the same page — all run
4. Reusable plugins always included; disposable only with `TEST_DISPOSABLE=1`
5. Tier is determined by directory location, not code attributes

## Execution Flow

```
--detailed test on a page
    │
    ├── Generic: scan_frame_widgets() → trigger each visible widget
    │
    ├── Reusable: find matching plugin in interactions/
    │   └── run() → page-specific interaction checks
    │
    └── Disposable (if TEST_DISPOSABLE=1): find in interactions/disposable/
        └── run() → one-off verification checks
```

## Build-Test-Plugin Cycle

Every new feature automatically produces its own reusable test plugin:

```
Build Feature → Test Feature → Plugin Born
     │                              │
     │         feature lives ───────┤── plugin runs on every test
     │                              │
     └── feature removed ───────────┘── plugin deleted
```

1. Build a new feature (interface, component, page)
2. Test it during development — the test code IS the plugin
3. Plugin is reusable from day one — runs on every `--detailed` test
4. Feature evolves → plugin evolves with it
5. Feature retired → plugin deleted (no orphan tests)

Plugins are NOT pre-created. They are born from actual work. The test library grows organically as features ship — never from pre-planning.

## Progressive Knowledge

Over time the plugin library mirrors the living feature set:

- New interface built → reusable plugin created during its first test
- Ad-hoc verification needed → disposable plugin, kept for reruns
- Disposable proves lasting value → promote to reusable (move up a dir)
- Feature removed → plugin removed (lifecycle tied to feature)

## Plugin Lifecycle

| Action | How |
|--------|-----|
| Create reusable | Add `<name>.py` to `interactions/` |
| Create disposable | Add `<name>.py` to `interactions/disposable/` |
| Run disposable | `TEST_DISPOSABLE=1 python3 web_test_engine.py --detailed ...` |
| Promote disposable | Move file from `disposable/` to `interactions/` |
| Retire plugin | Delete the file when the feature no longer exists |
| List all plugins | `from interactions import list_plugins; list_plugins()` |
