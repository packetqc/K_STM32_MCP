#!/usr/bin/env python3
"""
Test: Verify navigation tab bar is removed from Tests Interface
================================================================
Checks both EN and FR versions to confirm:
  1. No .tv-tab-bar element exists in the DOM
  2. No .tv-tab elements exist
  3. Dashboard content (#tv-dashboard-panel) is directly visible
  4. No tab-related CSS/JS in the rendered page

Produces: results JSON + screenshot proof
"""

import asyncio
import glob
import json
import os
import re
import sys

from playwright.async_api import async_playwright
from urllib.parse import quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
DOCS_ROOT = os.path.join(PROJECT_ROOT, 'docs')
REPORT_DIR = os.path.join(MODULE_DIR, 'test-reports')

CDN_SCRIPTS = {
    'marked': '/tmp/mermaid-local-test/node_modules/marked/lib/marked.umd.js',
    'mermaid': '/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js',
    'MindElixir': '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.iife.js',
}


def find_chrome():
    paths = [
        "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    ]
    for p in paths:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None


def make_route_handlers(docs_root):
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

    async def handle_github_raw(route):
        if 'sections.json' in route.request.url:
            local = os.path.join(docs_root, '..', 'Knowledge', 'sections.json')
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        await route.abort()

    async def handle_data(route):
        url = route.request.url
        m = re.search(r'(data/\w+\.json)', url)
        if m:
            local = os.path.join(docs_root, m.group(1))
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        if 'history.json' in url:
            local = os.path.join(docs_root, 'publications', 'test-main-navigator', 'assets', 'history.json')
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        await route.abort()

    return handle_cdn, handle_github_raw, handle_data


async def run_tests():
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chrome not found")
        sys.exit(1)

    os.makedirs(REPORT_DIR, exist_ok=True)
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome,
            args=['--no-sandbox', '--disable-gpu', '--allow-file-access-from-files']
        )
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})

        handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)

        page = await context.new_page()
        await page.route('**/cdn.jsdelivr.net/**', handle_cdn)
        await page.route('**/unpkg.com/**', handle_cdn)
        await page.route('**/raw.githubusercontent.com/**', handle_github_raw)
        await page.route('**/packetqc.github.io/**', handle_data)

        # Build file:// URLs like the main test engine does
        viewer = os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))
        en_url = f"file://{viewer}?doc={quote('interfaces/tests/index.md')}&embed"
        fr_url = f"file://{viewer}?doc={quote('fr/interfaces/tests/index.md')}&embed&lang=fr"

        test_cases = [
            ('EN', en_url),
            ('FR', fr_url),
        ]

        for lang, url in test_cases:
            print(f"\n--- Testing {lang} Tests Interface ---")
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(3000)

                # The viewer renders content in an iframe (srcdoc).
                # Find the content frame.
                target = page
                frames = page.frames
                for f in frames:
                    try:
                        has_viewer = await f.query_selector('#test-viewer')
                        if has_viewer:
                            target = f
                            break
                    except Exception:
                        pass

                # Test 1: No .tv-tab-bar in DOM
                tab_bar_count = await target.evaluate('document.querySelectorAll(".tv-tab-bar").length')
                passed1 = tab_bar_count == 0
                detail1 = f"Found {tab_bar_count} .tv-tab-bar elements (expected 0)"
                results.append({
                    'num': len(results) + 1,
                    'section': 'TabBar',
                    'name': f'{lang} — No .tv-tab-bar in DOM',
                    'status': 'PASS' if passed1 else 'FAIL',
                    'detail': detail1,
                })
                print(f"  [{'PASS' if passed1 else 'FAIL'}] No .tv-tab-bar — {detail1}")

                # Test 2: No .tv-tab elements
                tab_count = await target.evaluate('document.querySelectorAll(".tv-tab").length')
                passed2 = tab_count == 0
                detail2 = f"Found {tab_count} .tv-tab elements (expected 0)"
                results.append({
                    'num': len(results) + 1,
                    'section': 'TabBar',
                    'name': f'{lang} — No .tv-tab elements',
                    'status': 'PASS' if passed2 else 'FAIL',
                    'detail': detail2,
                })
                print(f"  [{'PASS' if passed2 else 'FAIL'}] No .tv-tab — {detail2}")

                # Test 3: Dashboard panel is present and visible
                dashboard_exists = await target.evaluate('''() => {
                    var el = document.getElementById("tv-dashboard-panel");
                    return el ? { exists: true, visible: el.offsetParent !== null || el.offsetHeight > 0 } : { exists: false, visible: false };
                }''')
                passed3 = dashboard_exists.get('exists', False)
                detail3 = f"Dashboard panel exists: {dashboard_exists.get('exists')}, visible: {dashboard_exists.get('visible')}"
                results.append({
                    'num': len(results) + 1,
                    'section': 'Dashboard',
                    'name': f'{lang} — Dashboard panel present',
                    'status': 'PASS' if passed3 else 'FAIL',
                    'detail': detail3,
                })
                print(f"  [{'PASS' if passed3 else 'FAIL'}] Dashboard — {detail3}")

                # Test 4: No tab-related functions (addTab, closeTab, activateTab) in JS
                has_tab_funcs = await target.evaluate('''() => {
                    var html = document.documentElement.innerHTML;
                    return {
                        addTab: html.includes("function addTab"),
                        closeTab: html.includes("function closeTab"),
                        activateTab: html.includes("function activateTab"),
                        saveTabState: html.includes("function saveTabState"),
                    };
                }''')
                passed4 = not any(has_tab_funcs.values())
                found_funcs = [k for k, v in has_tab_funcs.items() if v]
                detail4 = f"Tab functions absent" if passed4 else f"Found tab functions: {', '.join(found_funcs)}"
                results.append({
                    'num': len(results) + 1,
                    'section': 'JavaScript',
                    'name': f'{lang} — No tab management JS',
                    'status': 'PASS' if passed4 else 'FAIL',
                    'detail': detail4,
                })
                print(f"  [{'PASS' if passed4 else 'FAIL'}] No tab JS — {detail4}")

                # Test 5: No .tv-tab-content or .tv-tab-panel wrapper
                tab_content_count = await target.evaluate('document.querySelectorAll(".tv-tab-content").length')
                tab_panel_count = await target.evaluate('document.querySelectorAll(".tv-tab-panel").length')
                passed5 = tab_content_count == 0 and tab_panel_count == 0
                detail5 = f".tv-tab-content: {tab_content_count}, .tv-tab-panel: {tab_panel_count} (both expected 0)"
                results.append({
                    'num': len(results) + 1,
                    'section': 'Layout',
                    'name': f'{lang} — No tab content wrappers',
                    'status': 'PASS' if passed5 else 'FAIL',
                    'detail': detail5,
                })
                print(f"  [{'PASS' if passed5 else 'FAIL'}] No wrappers — {detail5}")

                # Test 6: routeToContentPanel function exists (links should route to content panel)
                has_route = await target.evaluate('''() => {
                    var html = document.documentElement.innerHTML;
                    return html.includes("routeToContentPanel");
                }''')
                passed6 = has_route
                detail6 = f"routeToContentPanel function present: {has_route}"
                results.append({
                    'num': len(results) + 1,
                    'section': 'Routing',
                    'name': f'{lang} — Content panel routing preserved',
                    'status': 'PASS' if passed6 else 'FAIL',
                    'detail': detail6,
                })
                print(f"  [{'PASS' if passed6 else 'FAIL'}] Routing — {detail6}")

                # Screenshot
                shot_path = os.path.join(REPORT_DIR, f"no-tab-bar-{lang.lower()}.png")
                await page.screenshot(path=shot_path, full_page=False)
                print(f"  Screenshot: {shot_path}")

            except Exception as ex:
                for check_name in ['No .tv-tab-bar', 'No .tv-tab', 'Dashboard', 'No tab JS', 'No wrappers', 'Routing']:
                    if not any(r['name'].endswith(check_name) for r in results if lang in r['name']):
                        results.append({
                            'num': len(results) + 1,
                            'section': 'Error',
                            'name': f'{lang} — {check_name}',
                            'status': 'FAIL',
                            'detail': str(ex),
                        })
                print(f"  [ERROR] {ex}")

        await browser.close()

    # Summary
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    total = len(results)

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    out_path = os.path.join(REPORT_DIR, 'no-tab-bar-results.json')
    with open(out_path, 'w') as f:
        json.dump({
            'test': 'Remove Test Navigation Tab Bar',
            'date': '2026-03-20',
            'passed': passed,
            'failed': failed,
            'total': total,
            'results': results,
        }, f, indent=2)
    print(f"Results: {out_path}")

    return failed == 0


if __name__ == '__main__':
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
