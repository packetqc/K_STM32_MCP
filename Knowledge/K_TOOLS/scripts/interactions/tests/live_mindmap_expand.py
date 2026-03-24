"""
Live Mindmap — Expand/Collapse Bug Fix Test
============================================

Side-by-side comparison: BEFORE (all descendants expand) vs AFTER (1 level only).
Validates preCollapse + expandNode intercept enforcement.

Rerunnable module — invoke via:
    python3 interaction_test_driver.py --module live_mindmap_expand
"""

import os

TEST_ID = "live-mindmap-expand"
TITLE = "Live Mindmap — Expand/Collapse Bug Fix"
TITLE_FR = "Mindmap vivant — Correction expansion/réduction"
SLUG = "test-live-mindmap-expand"
OUTPUT_DIR = "docs/publications/test-live-mindmap-expand"

# Path to page override for BEFORE state (old buggy code)
_PLAN_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'test-plans')
_PAGE_OVERRIDE = os.path.join(_PLAN_DIR, 'live-mindmap-prefixed.md')


def get_test_plan():
    """Return the test plan for interaction_test_driver."""
    return {
        "title": TITLE,
        "subtitle": "Architecture node expansion",
        "description": "Clicking + on architecture: before fix shows all descendants, after fix shows only 1 level",
        "conclusion": "preCollapse + expandNode intercept enforces 1-level-at-a-time",
        "page": "interfaces/live-mindmap/index.md",
        "mode": "sidebyside",
        "parts": [
            {
                "label": "BEFORE — Bug",
                "page_override": "Knowledge/K_TOOLS/test-plans/live-mindmap-prefixed.md",
                "steps": [
                    {"action": "wait", "wait_ms": 500, "description": "Settle after load"},
                    {"action": "fit", "description": "Fit and center mindmap"},
                    {"action": "capture", "capture_as": "before-initial", "description": "Capture collapsed state"},
                    {"action": "wait", "wait_ms": 800, "description": "Pause — show collapsed"},
                    {"action": "click_expand", "target": "architecture", "wait_ms": 600, "description": "Click + on architecture"},
                    {"action": "fit", "description": "Fit expanded state"},
                    {"action": "wait", "wait_ms": 1000, "description": "Pause — show result"},
                    {"action": "capture", "capture_as": "before", "description": "Capture expanded state"},
                ]
            },
            {
                "label": "AFTER — Fix",
                "steps": [
                    {"action": "wait", "wait_ms": 500, "description": "Settle after load"},
                    {"action": "fit", "description": "Fit and center mindmap"},
                    {"action": "capture", "capture_as": "after-initial", "description": "Capture collapsed state"},
                    {"action": "wait", "wait_ms": 800, "description": "Pause — show collapsed"},
                    {"action": "click_expand", "target": "architecture", "wait_ms": 600, "description": "Click + on architecture"},
                    {"action": "fit", "description": "Fit expanded state"},
                    {"action": "wait", "wait_ms": 1000, "description": "Pause — show result"},
                    {"action": "capture", "capture_as": "after", "description": "Capture expanded state"},
                ]
            }
        ]
    }
