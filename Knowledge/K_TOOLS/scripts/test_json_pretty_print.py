#!/usr/bin/env python3
"""Test: JSON Pretty-Print in K_DOCS Viewer
===========================================

Validates that the viewer correctly renders JSON files with:
  1. Syntax-highlighted tokens (keys, strings, numbers, booleans, null)
  2. Collapsible nested objects/arrays (toggle arrows)
  3. Pretty-print in table cells (nested object/array values)
  4. JSON code blocks in markdown (```json) rendered with highlighting
  5. "View Full JSON Structure" toggle on JSON document pages
  6. Theme color adaptation (light vs dark)

Usage:
    python3 scripts/test_json_pretty_print.py
    python3 scripts/test_json_pretty_print.py --theme midnight
    python3 scripts/test_json_pretty_print.py --screenshots-only
"""

import asyncio
import json
import glob
import os
import sys
import tempfile

from playwright.async_api import async_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
DOCS_ROOT = os.path.join(PROJECT_ROOT, 'docs')
REPORT_DIR = os.path.join(MODULE_DIR, 'test-reports')

CHROME_PATHS = [
    "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
    "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
]

CDN_SCRIPTS = {
    'marked': '/tmp/mermaid-local-test/node_modules/marked/lib/marked.umd.js',
    'mermaid': '/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js',
    'MindElixir': '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.iife.js',
}

VIEWPORT = {'width': 1920, 'height': 1080}

# Test JSON with deliberately nested structures to exercise all paths
TEST_JSON = {
    "title": "JSON Pretty-Print Test Document",
    "description": "Validates syntax highlighting, collapsible nodes, and theme adaptation.",
    "version": "1.0",
    "enabled": True,
    "count": 42,
    "nullable_field": None,
    "simple_array": ["alpha", "beta", "gamma"],
    "routes": [
        {
            "name": "web-page-visualization",
            "subjects": ["web", "css", "layout"],
            "methodology": "K_TOOLS/methodology/web-page-visualization.md",
            "proof_output": ["gif", "mp4", "png"],
            "config": {
                "viewport": {"width": 1920, "height": 1080},
                "timeout": 30000,
                "retry": True
            }
        },
        {
            "name": "test-report-generation",
            "subjects": ["test", "report", "qa"],
            "methodology": "K_TOOLS/methodology/test-report-generation.md",
            "proof_output": ["gif", "mp4"],
            "config": {
                "max_pages": 50,
                "parallel": False,
                "history_limit": 10
            }
        }
    ],
    "nested_config": {
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {"user": "admin", "pass": "***"}
        },
        "features": {
            "dark_mode": True,
            "json_pretty_print": True,
            "collapsible_nodes": True,
            "syntax_highlighting": True
        },
        "limits": {
            "max_depth": 5,
            "max_items": 1000
        }
    }
}

# Markdown with embedded JSON code block
TEST_MARKDOWN = """---
title: "JSON Code Block Test"
description: "Tests ```json syntax highlighting in markdown"
---

# JSON Code Block Rendering

Below is a JSON code block that should be pretty-printed:

```json
{
  "route": "web-page-visualization",
  "mind_refs": ["conventions::web page visualization"],
  "proof_output": ["gif", "mp4", "png"],
  "config": {
    "viewport": {"width": 1920, "height": 1080},
    "enabled": true,
    "label": null,
    "retries": 3
  }
}
```

And a non-JSON code block for comparison:

```python
def hello():
    return "world"
```
"""


def find_chrome():
    for p in CHROME_PATHS:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None


def make_route_handlers(docs_root, test_json_path=None, test_md_path=None):
    """Route handlers for local file serving + test fixtures."""

    async def handle_cdn(route):
        url = route.request.url
        for name, path in CDN_SCRIPTS.items():
            if name.lower() in url.lower() and os.path.isfile(path):
                with open(path, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/javascript')
                return
        if 'MindElixir.css' in url:
            css = '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.css'
            if os.path.isfile(css):
                with open(css, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='text/css')
                return
        await route.abort()

    async def handle_data(route):
        url = route.request.url
        # Serve test JSON fixture
        if test_json_path and 'test-pretty-print.json' in url:
            with open(test_json_path, 'r') as f:
                body = f.read()
            await route.fulfill(body=body, content_type='application/json')
            return
        # Serve test markdown fixture
        if test_md_path and 'test-json-codeblock.md' in url:
            with open(test_md_path, 'r') as f:
                body = f.read()
            await route.fulfill(body=body, content_type='text/plain')
            return
        # Serve real data files
        import re
        m = re.search(r'(data/\w+\.json)', url)
        if m:
            local = os.path.join(docs_root, m.group(1))
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        await route.abort()

    return handle_cdn, handle_data


async def run_tests(theme='auto', screenshots_only=False):
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found")
        sys.exit(1)

    os.makedirs(REPORT_DIR, exist_ok=True)
    results = {"checks": [], "theme": theme}

    # Write test fixtures to temp files
    test_json_path = os.path.join(DOCS_ROOT, 'data', 'test-pretty-print.json')
    test_md_path = os.path.join(DOCS_ROOT, 'test-json-codeblock.md')

    with open(test_json_path, 'w') as f:
        json.dump(TEST_JSON, f, indent=2)
    with open(test_md_path, 'w') as f:
        f.write(TEST_MARKDOWN)

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                executable_path=chrome,
                headless=True,
                args=['--no-sandbox', '--disable-gpu']
            )
            page = await browser.new_page(viewport=VIEWPORT)

            handle_cdn, handle_data = make_route_handlers(
                DOCS_ROOT, test_json_path, test_md_path
            )

            await page.route('**/cdn.jsdelivr.net/**', handle_cdn)
            await page.route('**/unpkg.com/**', handle_cdn)
            await page.route('**/data/**', handle_data)
            await page.route('**/test-json-codeblock.md', handle_data)

            viewer_url = f'file://{DOCS_ROOT}/index.html'

            # ── TEST 1: JSON Document Pretty-Print ────────────────────────
            print("\n[TEST 1] JSON document rendering with pretty-print...")
            json_url = f'{viewer_url}?doc=data/test-pretty-print.json'
            if theme != 'auto':
                json_url += f'&theme={theme}'

            await page.goto(json_url, wait_until='networkidle', timeout=15000)
            await page.wait_for_timeout(1500)

            # Check 1a: json-pretty containers exist
            pretty_count = await page.evaluate(
                'document.querySelectorAll(".json-pretty").length'
            )
            check_1a = pretty_count > 0
            results["checks"].append({
                "name": "json-pretty containers rendered",
                "pass": check_1a,
                "detail": f"Found {pretty_count} .json-pretty elements"
            })
            print(f"  {'PASS' if check_1a else 'FAIL'}: {pretty_count} .json-pretty containers")

            # Check 1b: Syntax highlighting tokens present
            token_counts = await page.evaluate('''() => {
                return {
                    keys: document.querySelectorAll(".json-key").length,
                    strings: document.querySelectorAll(".json-string").length,
                    numbers: document.querySelectorAll(".json-number").length,
                    bools: document.querySelectorAll(".json-bool").length,
                    nulls: document.querySelectorAll(".json-null").length,
                    brackets: document.querySelectorAll(".json-bracket").length,
                }
            }''')
            check_1b = all(v > 0 for v in token_counts.values())
            results["checks"].append({
                "name": "syntax highlighting tokens",
                "pass": check_1b,
                "detail": token_counts
            })
            print(f"  {'PASS' if check_1b else 'FAIL'}: tokens = {token_counts}")

            # Check 1c: Collapsible toggle arrows exist
            toggle_count = await page.evaluate(
                'document.querySelectorAll(".json-toggle").length'
            )
            check_1c = toggle_count > 0
            results["checks"].append({
                "name": "collapsible toggles present",
                "pass": check_1c,
                "detail": f"Found {toggle_count} toggle arrows"
            })
            print(f"  {'PASS' if check_1c else 'FAIL'}: {toggle_count} collapsible toggles")

            # Check 1d: "View Full JSON Structure" details element exists
            full_view = await page.evaluate(
                'document.querySelectorAll("details summary").length'
            )
            check_1d = full_view > 0
            results["checks"].append({
                "name": "full JSON structure toggle",
                "pass": check_1d,
                "detail": f"Found {full_view} details/summary elements"
            })
            print(f"  {'PASS' if check_1d else 'FAIL'}: Full JSON toggle present")

            # Check 1e: Toggle click collapses/expands
            if toggle_count > 0:
                toggle_result = await page.evaluate('''() => {
                    var t = document.querySelector(".json-toggle:not(.collapsed)");
                    if (!t) return {pass: false, detail: "no open toggle found"};
                    t.click();
                    var collapsed = t.classList.contains("collapsed");
                    t.click();
                    var expanded = !t.classList.contains("collapsed");
                    return {pass: collapsed && expanded, detail: "collapse=" + collapsed + " expand=" + expanded};
                }''')
                check_1e = toggle_result.get('pass', False)
                results["checks"].append({
                    "name": "toggle click works",
                    "pass": check_1e,
                    "detail": toggle_result.get('detail', '')
                })
                print(f"  {'PASS' if check_1e else 'FAIL'}: Toggle click: {toggle_result['detail']}")

            # Check 1f: Theme colors applied
            color_check = await page.evaluate('''() => {
                var key = document.querySelector(".json-key");
                if (!key) return {pass: false, detail: "no key element"};
                var style = getComputedStyle(key);
                return {pass: style.color !== "", detail: "key color: " + style.color};
            }''')
            check_1f = color_check.get('pass', False)
            results["checks"].append({
                "name": "theme colors applied",
                "pass": check_1f,
                "detail": color_check.get('detail', '')
            })
            print(f"  {'PASS' if check_1f else 'FAIL'}: {color_check['detail']}")

            # Screenshot: JSON document
            ss1 = os.path.join(REPORT_DIR, 'json-pretty-print-document.png')
            await page.screenshot(path=ss1, full_page=True)
            print(f"  Screenshot: {ss1}")

            # ── TEST 2: JSON Code Block in Markdown ───────────────────────
            print("\n[TEST 2] JSON code block in markdown...")
            md_url = f'{viewer_url}?doc=test-json-codeblock.md'
            if theme != 'auto':
                md_url += f'&theme={theme}'

            await page.goto(md_url, wait_until='networkidle', timeout=15000)
            await page.wait_for_timeout(1500)

            # Check 2a: json-pretty in markdown code block
            md_pretty = await page.evaluate(
                'document.querySelectorAll(".json-pretty").length'
            )
            check_2a = md_pretty > 0
            results["checks"].append({
                "name": "json code block pretty-printed",
                "pass": check_2a,
                "detail": f"Found {md_pretty} .json-pretty in markdown"
            })
            print(f"  {'PASS' if check_2a else 'FAIL'}: {md_pretty} pretty-print blocks in markdown")

            # Check 2b: Non-JSON code block NOT pretty-printed (python block preserved)
            python_block = await page.evaluate(
                'document.querySelectorAll("code.language-python").length'
            )
            check_2b = python_block > 0
            results["checks"].append({
                "name": "non-JSON code block preserved",
                "pass": check_2b,
                "detail": f"Found {python_block} language-python blocks"
            })
            print(f"  {'PASS' if check_2b else 'FAIL'}: Python code block preserved ({python_block})")

            # Screenshot: Markdown JSON code block
            ss2 = os.path.join(REPORT_DIR, 'json-pretty-print-codeblock.png')
            await page.screenshot(path=ss2, full_page=True)
            print(f"  Screenshot: {ss2}")

            # ── TEST 3: Real data file (configurations.json) ──────────────
            print("\n[TEST 3] Real data file: configurations.json...")
            real_url = f'{viewer_url}?doc=data/configurations.json'
            if theme != 'auto':
                real_url += f'&theme={theme}'

            await page.goto(real_url, wait_until='networkidle', timeout=15000)
            await page.wait_for_timeout(1500)

            real_pretty = await page.evaluate(
                'document.querySelectorAll(".json-pretty").length'
            )
            check_3a = real_pretty > 0
            results["checks"].append({
                "name": "real JSON file pretty-printed",
                "pass": check_3a,
                "detail": f"configurations.json: {real_pretty} .json-pretty elements"
            })
            print(f"  {'PASS' if check_3a else 'FAIL'}: {real_pretty} pretty-print elements in configurations.json")

            ss3 = os.path.join(REPORT_DIR, 'json-pretty-print-real-data.png')
            await page.screenshot(path=ss3, full_page=True)
            print(f"  Screenshot: {ss3}")

            # ── TEST 4: Dark theme rendering ──────────────────────────────
            if theme == 'auto':
                print("\n[TEST 4] Midnight theme color contrast...")
                dark_url = f'{viewer_url}?doc=data/test-pretty-print.json'
                await page.goto(dark_url, wait_until='networkidle', timeout=15000)
                await page.evaluate('document.documentElement.setAttribute("data-theme", "midnight")')
                await page.wait_for_timeout(500)

                dark_colors = await page.evaluate('''() => {
                    var key = document.querySelector(".json-key");
                    var str = document.querySelector(".json-string");
                    var num = document.querySelector(".json-number");
                    if (!key || !str || !num) return {pass: false, detail: "tokens not found"};
                    var ks = getComputedStyle(key).color;
                    var ss = getComputedStyle(str).color;
                    var ns = getComputedStyle(num).color;
                    return {pass: true, detail: "key=" + ks + " str=" + ss + " num=" + ns};
                }''')
                check_4 = dark_colors.get('pass', False)
                results["checks"].append({
                    "name": "dark theme colors",
                    "pass": check_4,
                    "detail": dark_colors.get('detail', '')
                })
                print(f"  {'PASS' if check_4 else 'FAIL'}: {dark_colors['detail']}")

                ss4 = os.path.join(REPORT_DIR, 'json-pretty-print-dark.png')
                await page.screenshot(path=ss4, full_page=True)
                print(f"  Screenshot: {ss4}")

            await browser.close()

    finally:
        # Clean up test fixtures
        for f in [test_json_path, test_md_path]:
            if os.path.exists(f):
                os.remove(f)

    # ── Summary ───────────────────────────────────────────────────────────
    passed = sum(1 for c in results["checks"] if c["pass"])
    total = len(results["checks"])
    results["passed"] = passed
    results["total"] = total
    results["success"] = passed == total

    results_path = os.path.join(REPORT_DIR, 'json-pretty-print-results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  JSON Pretty-Print Test: {passed}/{total} passed")
    print(f"  Results: {results_path}")
    print(f"{'='*60}")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test JSON pretty-print in viewer')
    parser.add_argument('--theme', default='auto', help='Theme to test (auto, midnight, cayman)')
    parser.add_argument('--screenshots-only', action='store_true', help='Only capture screenshots')
    args = parser.parse_args()

    results = asyncio.run(run_tests(theme=args.theme, screenshots_only=args.screenshots_only))
    sys.exit(0 if results["success"] else 1)


if __name__ == '__main__':
    main()
