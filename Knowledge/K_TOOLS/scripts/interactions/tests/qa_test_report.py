"""
QA Test Report — Generic Interaction Report Validator
=====================================================

Reusable QA module for validating ANY interaction test report page.
Runs the same 6-check MAC+FIX pattern on any target:

  MAC (page structure):
    CHECK 1 — Summary table, run panels, metadata
    CHECK 2 — Before/After images + proof GIF

  FIX (interactions):
    CHECK 3 — Row expand/collapse toggle
    CHECK 4 — Video seek from paused state
    CHECK 5 — Video seek while playing
    CHECK 6 — Run history metadata

Usage:
    # QA a specific test report page
    python3 interaction_test_driver.py --module qa_test_report \\
        --page publications/test-live-mindmap-expand/index.md

    # Or use a registered target (see TARGETS dict)
    python3 interaction_test_driver.py --module qa_test_report

The module can also be imported and called with a custom target:
    from interactions.tests.qa_test_report import build_plan
    plan = build_plan("publications/my-test/index.md", "My Test QA")
"""

TEST_ID = "qa-test-report"
TITLE = "QA — Test Report Validation"
TITLE_FR = "QA — Validation de rapport de test"
SLUG = "qa-live-mindmap-expand"  # Default target output
OUTPUT_DIR = "docs/publications/qa-live-mindmap-expand"

# ═══ Registered QA targets ═══
# Add new targets here as test reports are created.
# Key = short name, value = page path relative to docs/
TARGETS = {
    "live-mindmap-expand": "publications/test-live-mindmap-expand/index.md",
}

# Default target when --page is not provided
DEFAULT_TARGET = "live-mindmap-expand"


# ═══ MAC Pre-Checks (page structure validation) ═══

MAC_PRE_CHECKS = [
    {"type": "selector_exists", "selector": "h1, h2", "min_count": 1,
     "description": "Page has headings (content rendered)"},
    {"type": "selector_exists", "selector": ".tg-summary",
     "description": "Summary table exists"},
    {"type": "selector_exists", "selector": ".ba-row",
     "description": "Before/After comparison section exists"},
    {"type": "selector_exists", "selector": "video",
     "description": "Video element exists"},
    {"type": "selector_exists", "selector": ".tg-interactive",
     "description": "Interactive steps table exists"},
    {"type": "selector_exists", "selector": ".step-checkpoint", "min_count": 1,
     "description": "Parent check rows (collapsible) exist"},
    {"type": "selector_exists", "selector": ".step-checkpoint .step-arrow", "min_count": 1,
     "description": "Parent rows have expand arrows"},
    {"type": "selector_exists", "selector": ".step-context", "min_count": 1,
     "description": "Child step rows exist"},
    {"type": "assert_js",
     "js": "(() => { var tbl = document.querySelector('.tg-interactive'); var arrow = document.querySelector('.step-checkpoint .step-arrow'); if (!tbl || !arrow) return false; var grp = document.querySelector('.step-checkpoint').getAttribute('data-toggle'); var before = document.querySelectorAll('.' + grp + '.visible').length; arrow.click(); var after = document.querySelectorAll('.' + grp + '.visible').length; arrow.click(); return after > before; })()",
     "description": "Click listener active \u2014 arrow toggles child visibility"},
]


# ═══ FIX Steps (interaction validation) ═══

FIX_STEPS = [
    {"action": "wait", "wait_ms": 1000, "description": "Wait for page to settle"},
    {"action": "evaluate_js",
     "js": "(() => { var t = document.querySelector('.tg-interactive'); if (t) t.scrollIntoView({block: 'center'}); return true; })()",
     "wait_ms": 500, "description": "Scroll to interaction steps table"},

    # CHECK 1 — Page structure
    {"action": "assert_js",
     "js": "(() => { var sum = document.querySelector('.tg-summary'); if (!sum) return false; var cells = sum.querySelectorAll('td'); var text = Array.from(cells).map(c => c.textContent.trim()).join('|'); return text.includes('Parts') && text.includes('Total steps') && text.includes('Steps passed'); })()",
     "description": "Summary table has Parts, Total steps, Steps passed"},
    {"action": "assert_js",
     "js": "(() => { var panels = document.querySelectorAll('.run-panel'); return panels.length >= 1; })()",
     "description": "At least 1 run panel exists"},
    {"action": "assert_js",
     "js": "(() => { var p = document.querySelector('.run-panel.active'); if (!p) return false; var text = p.textContent; return /Date:/.test(text) && /Parts:/.test(text) && /Steps:/.test(text); })()",
     "description": "Active run shows Date, Parts, Steps metadata"},
    {"action": "capture", "capture_as": "before",
     "description": "CHECK 1 \u2014 Page structure: summary, runs, metadata all present"},

    # CHECK 2 — Before/After + proof GIF
    {"action": "assert_js",
     "js": "(() => { var ba = document.querySelector('.ba-row'); if (!ba) return false; var imgs = ba.querySelectorAll('img'); return imgs.length >= 2; })()",
     "description": "Before/After has at least 2 images"},
    {"action": "assert_js",
     "js": "(() => { var labels = document.querySelectorAll('.ba-label'); return labels.length >= 2 && labels[0].textContent.includes('BEFORE') && labels[1].textContent.includes('AFTER'); })()",
     "description": "Before/After labels read BEFORE and AFTER"},
    {"action": "assert_js",
     "js": "(() => { var gif = document.querySelector('img[src*=\"proof.gif\"]'); return !!gif; })()",
     "description": "Proof GIF is embedded"},
    {"action": "capture", "capture_as": "check2-before-after-proof",
     "description": "CHECK 2 \u2014 Before/After comparison + proof GIF present"},

    # CHECK 3 — Expand/collapse toggle
    {"action": "assert_js",
     "js": "(() => { var rows = document.querySelectorAll('.step-context'); return rows.length > 0 && Array.from(rows).every(r => !r.classList.contains('visible')); })()",
     "description": "Child steps initially collapsed"},
    {"action": "click_selector", "selector": ".step-checkpoint .step-arrow", "wait_ms": 500,
     "description": "Click arrow to expand first check"},
    {"action": "assert_js",
     "js": "(() => { var grp = document.querySelector('.step-checkpoint').getAttribute('data-toggle'); var rows = document.querySelectorAll('.' + grp); return rows.length > 0 && Array.from(rows).every(r => r.classList.contains('visible')); })()",
     "description": "Child steps now visible"},
    {"action": "click_selector", "selector": ".step-checkpoint .step-arrow", "wait_ms": 500,
     "description": "Click arrow to collapse"},
    {"action": "assert_js",
     "js": "(() => { var grp = document.querySelector('.step-checkpoint').getAttribute('data-toggle'); var rows = document.querySelectorAll('.' + grp); return rows.length > 0 && Array.from(rows).every(r => !r.classList.contains('visible')); })()",
     "description": "Child steps collapsed again"},
    {"action": "capture", "capture_as": "check3-expand-collapse",
     "description": "CHECK 3 \u2014 Row expand/collapse toggle works"},

    # CHECK 4 — Video seek from paused
    {"action": "click_selector", "selector": ".step-checkpoint .step-arrow", "wait_ms": 500,
     "description": "Expand to reveal child steps"},
    {"action": "assert_js",
     "js": "(() => { var v = document.querySelector('video'); return v && v.paused; })()",
     "description": "Video is paused"},
    {"action": "click_selector", "selector": ".step-context.visible", "wait_ms": 800,
     "description": "Click child step while video PAUSED"},
    {"action": "assert_js",
     "js": "(() => { var v = document.querySelector('video'); var row = document.querySelector('tr.step-active'); if (!v || !row) return false; var ts = parseFloat(row.getAttribute('data-ts')); return !isNaN(ts) && Math.abs(v.currentTime - ts) < 1.0; })()",
     "description": "Video seeked to step timestamp"},
    {"action": "capture", "capture_as": "check4-seek-paused",
     "description": "CHECK 4 \u2014 Child step click seeks video from paused"},

    # CHECK 5 — Video seek while playing
    {"action": "evaluate_js",
     "js": "(() => { var v = document.querySelector('video'); if (v && v.paused) { var p = v.play(); if (p && p.catch) p.catch(function(){}); } return true; })()",
     "wait_ms": 500, "description": "Start video playback"},
    {"action": "click_selector", "selector": "tr.step-context.visible ~ tr.step-context.visible",
     "wait_ms": 800, "description": "Click different child step while PLAYING"},
    {"action": "assert_js",
     "js": "(() => { var v = document.querySelector('video'); var row = document.querySelector('tr.step-active'); if (!v || !row) return false; var ts = parseFloat(row.getAttribute('data-ts')); return !isNaN(ts) && Math.abs(v.currentTime - ts) < 1.0; })()",
     "description": "Video seeked to new timestamp while playing"},
    {"action": "capture", "capture_as": "check5-seek-playing",
     "description": "CHECK 5 \u2014 Child step click seeks video while playing"},

    # CHECK 6 — Run history
    {"action": "assert_js",
     "js": "(() => { var panels = document.querySelectorAll('.run-panel'); var runs = panels.length; var activePanel = document.querySelector('.run-panel.active'); if (!activePanel) return false; var text = activePanel.textContent; var dateMatch = text.match(/Date:\\s*(\\d{4}-\\d{2}-\\d{2})/); return !!dateMatch && runs >= 1; })()",
     "description": "Run count and date are readable from the page"},
    {"action": "assert_js",
     "js": "(() => { var panels = document.querySelectorAll('.run-panel'); var activePanel = document.querySelector('.run-panel.active'); var text = activePanel.textContent; var dateMatch = text.match(/Date:\\s*(\\d{4}-\\d{2}-\\d{2})/); var partsMatch = text.match(/Parts:\\s*(\\d+)/); var stepsMatch = text.match(/Steps:\\s*(\\d+)/); return dateMatch && partsMatch && stepsMatch && parseInt(stepsMatch[1]) > 0; })()",
     "description": "Run metadata has valid date, parts count, steps count"},
    {"action": "evaluate_js",
     "js": "(() => { var panels = document.querySelectorAll('.run-panel'); var runs = panels.length; var tabs = document.querySelectorAll('.run-tab'); var activePanel = document.querySelector('.run-panel.active'); var text = activePanel.textContent; var dateMatch = text.match(/Date:\\s*(\\d{4}-\\d{2}-\\d{2})/); var tabDates = Array.from(tabs).map(t => t.querySelector('.run-tab-date')?.textContent || ''); window.__qaRunInfo = { total_runs: runs, tabs: tabs.length, date: dateMatch ? dateMatch[1] : 'not found', tab_dates: tabDates }; return true; })()",
     "wait_ms": 300, "description": "Capture run history metadata"},
    {"action": "capture", "capture_as": "after",
     "description": "CHECK 6 \u2014 Run history: count, dates, and timestamps verified"},
]


def build_plan(page, title=None):
    """Build a QA test plan for any interaction test report page.

    Args:
        page: doc path relative to docs/ (e.g. 'publications/test-live-mindmap-expand/index.md')
        title: optional custom title (auto-generated if None)
    """
    if not title:
        # Extract slug from page path for title
        slug = page.replace('publications/', '').replace('/index.md', '')
        title = f"QA — {slug}"

    return {
        "title": title,
        "page": page,
        "mode": "single",
        "pre_checks": list(MAC_PRE_CHECKS),
        "steps": list(FIX_STEPS),
    }


def get_test_plan():
    """Return the default test plan (targets live-mindmap-expand)."""
    target = TARGETS[DEFAULT_TARGET]
    return build_plan(target, TITLE)
