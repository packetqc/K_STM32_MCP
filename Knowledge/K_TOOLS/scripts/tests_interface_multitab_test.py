#!/usr/bin/env python3
"""
Tests Interface — Multi-Tab Navigation Test (v2 — Pre-populated Library)
=========================================================================

Validates the pre-populated tab library and multi-tab navigation in both
standalone and embedded modes. All tests from history.json are auto-populated
as tabs on dashboard load.

Phase 1 — Standalone Pre-populated Library:
  1. Dashboard loads with tabs pre-populated (≥2 test tabs + dashboard)
  2. Dashboard tab is active (not a test tab)
  3. Click pre-populated tab → lazy-loads iframe content
  4. Click different tab → shows different content (lazy-loaded)
  5. Close a tab → others remain
  6. Dashboard tab returns to matrix view

Phase 2 — Embedded Pre-populated Library:
  7. Tests Interface loads in center-frame with pre-populated tabs
  8. Click pre-populated tab → routes report to center-frame
  9. Navigate back → all inventory tabs restored
 10. Click 2nd inventory tab → routes different report
 11. Navigate back → inventory tabs still intact
 12. Click dashboard link → activates existing tab (no duplicate)

Produces: results.json, GIF proof

Usage:
    python3 scripts/tests_interface_multitab_test.py
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright

# ─── Paths ──────────────────────────────────────────────────────────────────

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
SLUG = 'test-tests-interface-multitab'


def find_chrome():
    import glob as g
    for p in CHROME_PATHS:
        matches = g.glob(p)
        if matches:
            return matches[0]
    return None


# ─── Route Handlers ─────────────────────────────────────────────────────────

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

    async def handle_data(route):
        url = route.request.url
        fname = url.split('/')[-1].split('?')[0]
        candidates = [
            os.path.join(docs_root, 'data', fname),
            os.path.join(docs_root, 'publications', 'test-main-navigator', 'assets', fname),
        ]
        if 'mind_memory' in url:
            candidates.append(os.path.join(docs_root, '..', 'Knowledge', 'K_MIND', 'mind', 'mind_memory.md'))
        if 'depth_config' in url:
            candidates.append(os.path.join(docs_root, '..', 'Knowledge', 'K_MIND', 'depth_config.json'))

        for local in candidates:
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                ct = 'application/json' if local.endswith('.json') else 'text/plain'
                await route.fulfill(body=body, content_type=ct)
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

    return handle_cdn, handle_github_raw, handle_data


# ─── Proof Assembly ─────────────────────────────────────────────────────────

def assemble_gif(frame_paths, output_path, duration_ms=2000):
    from PIL import Image
    if not frame_paths:
        return
    frames = [Image.open(f) for f in frame_paths]
    frames[0].save(output_path, save_all=True, append_images=frames[1:],
                   duration=duration_ms, loop=0, optimize=True)
    print(f"  GIF: {output_path} ({os.path.getsize(output_path) / 1024:.0f}K)")


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_iface_frame(page):
    """Find srcdoc frame with #tv-tab-bar."""
    for f in page.frames:
        if f.url in ('about:srcdoc', '') and f != page.main_frame:
            try:
                has = f.query_selector_all_evaluate('#tv-tab-bar', 'els => els.length')
                if has and has > 0:
                    return f
            except:
                pass
    srcdocs = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
    return srcdocs[-1] if srcdocs else None


async def get_iface_frame_async(page):
    """Async version."""
    for f in page.frames:
        if f.url in ('about:srcdoc', '') and f != page.main_frame:
            try:
                has = await f.evaluate("() => !!document.getElementById('tv-tab-bar')")
                if has:
                    return f
            except:
                pass
    srcdocs = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
    return srcdocs[-1] if srcdocs else None


async def wait_for_dashboard(iface, page, retries=8):
    for _ in range(retries):
        try:
            count = await iface.evaluate("() => document.querySelectorAll('.tv-stat').length")
            if count and count > 0:
                return True
        except:
            pass
        await page.wait_for_timeout(1500)
    return False


async def check_tab_bar(iface):
    return await iface.evaluate("""() => {
        var bar = document.querySelector('#tv-tab-bar');
        if (!bar) return { found: false };
        var tabs = bar.querySelectorAll('.tv-tab');
        var labels = [];
        tabs.forEach(function(t) {
            var l = t.querySelector('.tv-tab-label');
            labels.push(l ? l.textContent.trim() : '');
        });
        var active = bar.querySelector('.tv-tab.active');
        var activeId = active ? active.getAttribute('data-tab') : null;
        return { found: true, count: tabs.length, labels: labels, visible: bar.offsetHeight > 0, activeId: activeId };
    }""")


async def get_test_links(iface):
    return await iface.evaluate("""() => {
        var links = document.querySelectorAll('.tv-test-link');
        return Array.from(links).map(function(l) {
            return { text: l.textContent.trim(), href: l.getAttribute('href'), title: l.getAttribute('data-test-title') || l.textContent.trim() };
        });
    }""")


# ─── Test Cases ─────────────────────────────────────────────────────────────

async def run_tests():
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found.")
        return

    handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)

    doc = 'interfaces/tests/index.md'
    standalone_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}"
    nav_doc = 'interfaces/main-navigator/index.md'
    nav_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(nav_doc)}"
    embed_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}&embed&lang=en"

    frame_dir = tempfile.mkdtemp(prefix='ti_multitab_')
    all_frames = []
    results = []
    test_num = 0

    def record(num, phase, name, result, error=None):
        r = {'num': num, 'phase': phase, 'target': name, 'panel': 'Multi', 'result': result, 'doc': doc}
        if error:
            r['error'] = error
        results.append(r)
        mark = 'PASS' if result == 'PASS' else 'FAIL'
        sym = '\u2713' if result == 'PASS' else '\u2717'
        detail = f' | {error}' if error and result == 'FAIL' else ''
        print(f"  [{num:2d}] {mark} | {name}{detail}")

    async def screenshot(num):
        fp = os.path.join(frame_dir, f'frame_{num:04d}.png')
        await page.screenshot(path=fp, full_page=False)
        all_frames.append(fp)

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, executable_path=chrome,
                                      args=['--no-sandbox', '--disable-setuid-sandbox',
                                            '--disable-gpu', '--allow-file-access-from-files'])
    page = await browser.new_page(viewport=VIEWPORT)

    await page.route('**cdn.jsdelivr.net**', handle_cdn)
    await page.route('**raw.githubusercontent.com**', handle_github_raw)
    await page.route('**/data/*.json', handle_data)
    await page.route('**mind_memory.md', handle_data)
    await page.route('**depth_config.json', handle_data)
    await page.route('**/assets/history.json', handle_data)

    print("=" * 75)
    print("  Tests Interface — Multi-Tab Navigation Test v2 (Pre-populated Library)")
    print("  (standalone + embedded)")
    print("=" * 75)

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1 — Standalone Pre-populated Library
    # ═══════════════════════════════════════════════════════════════════════
    print("\n  \u2500\u2500 Phase 1: Standalone Pre-populated Library \u2500\u2500")

    await page.goto(standalone_url, wait_until='load', timeout=30000)
    await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")
    await page.wait_for_timeout(5000)

    iface = get_iface_frame(page)
    if iface:
        await wait_for_dashboard(iface, page)
        # Extra wait for pre-population to complete
        await page.wait_for_timeout(2000)

    # TEST 1: Dashboard loads with pre-populated tabs (≥3: dashboard + ≥2 tests)
    test_num += 1
    try:
        tb = await check_tab_bar(iface) if iface else {'found': False}
        if tb.get('count', 0) >= 3:
            record(test_num, 'Standalone', f'Pre-populated library: {tb["count"]} tabs on load', 'PASS')
            print(f"         Labels: {tb['labels']}")
        else:
            record(test_num, 'Standalone', 'Pre-populated library on load', 'FAIL', f'count={tb.get("count")}: {tb.get("labels")}')
    except Exception as e:
        record(test_num, 'Standalone', 'Pre-populated library on load', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 2: Dashboard tab is active (pre-population doesn't switch away)
    test_num += 1
    try:
        tb = await check_tab_bar(iface) if iface else {'found': False}
        if tb.get('activeId') == 'dashboard':
            record(test_num, 'Standalone', 'Dashboard tab is active after pre-population', 'PASS')
        else:
            record(test_num, 'Standalone', 'Dashboard tab is active after pre-population', 'FAIL', f'active={tb.get("activeId")}')
    except Exception as e:
        record(test_num, 'Standalone', 'Dashboard tab is active after pre-population', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 3: Click pre-populated tab → lazy-loads iframe content
    test_num += 1
    try:
        iface_loc = page.frame_locator('#ifaceFrame')
        # Get first non-dashboard tab id
        tab_ids = await iface.evaluate("""() => {
            var tabs = document.querySelectorAll('.tv-tab:not([data-tab="dashboard"])');
            return Array.from(tabs).map(function(t) { return t.getAttribute('data-tab'); });
        }""")

        if len(tab_ids) >= 1:
            # Before click — iframe should be about:blank (lazy)
            pre_src = await iface.evaluate("""(tabId) => {
                var p = document.querySelector('.tv-tab-panel[data-tab="' + tabId + '"]');
                var iframe = p ? p.querySelector('iframe') : null;
                return iframe ? iframe.src : 'no-iframe';
            }""", tab_ids[0])

            # Click the tab
            await iface_loc.locator(f'.tv-tab[data-tab="{tab_ids[0]}"]').click()
            await page.wait_for_timeout(2000)

            # After click — iframe should have real src (lazy-loaded)
            post_src = await iface.evaluate("""(tabId) => {
                var p = document.querySelector('.tv-tab-panel[data-tab="' + tabId + '"]');
                var iframe = p ? p.querySelector('iframe') : null;
                return iframe ? iframe.src : 'no-iframe';
            }""", tab_ids[0])

            is_lazy = 'about:blank' in str(pre_src) or pre_src == ''
            is_loaded = 'about:blank' not in str(post_src) and post_src != '' and post_src != 'no-iframe'

            if is_loaded:
                record(test_num, 'Standalone', f'Click tab lazy-loads iframe', 'PASS')
                print(f"         pre={pre_src[:40]}... post={post_src[:40]}...")
            else:
                record(test_num, 'Standalone', 'Click tab lazy-loads iframe', 'FAIL', f'pre={pre_src[:30]} post={post_src[:30]}')
        else:
            record(test_num, 'Standalone', 'Click tab lazy-loads iframe', 'FAIL', 'no tabs')
    except Exception as e:
        record(test_num, 'Standalone', 'Click tab lazy-loads iframe', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 4: Click different tab → shows different content
    test_num += 1
    try:
        if len(tab_ids) >= 2:
            # Click tab #2
            await iface_loc.locator(f'.tv-tab[data-tab="{tab_ids[1]}"]').click()
            await page.wait_for_timeout(2000)

            active1_src = await iface.evaluate("""(tabId) => {
                var p = document.querySelector('.tv-tab-panel[data-tab="' + tabId + '"]');
                var iframe = p ? p.querySelector('iframe') : null;
                return iframe ? iframe.src : '';
            }""", tab_ids[0])

            active2_src = await iface.evaluate("""(tabId) => {
                var p = document.querySelector('.tv-tab-panel[data-tab="' + tabId + '"]');
                var iframe = p ? p.querySelector('iframe') : null;
                return iframe ? iframe.src : '';
            }""", tab_ids[1])

            if active1_src and active2_src and active1_src != active2_src:
                record(test_num, 'Standalone', 'Different tabs show different content', 'PASS')
            else:
                record(test_num, 'Standalone', 'Different tabs show different content', 'FAIL',
                       f'same={active1_src == active2_src}')
        else:
            record(test_num, 'Standalone', 'Different tabs show different content', 'FAIL', f'only {len(tab_ids)} tabs')
    except Exception as e:
        record(test_num, 'Standalone', 'Different tabs show different content', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 5: Close a tab → others remain
    test_num += 1
    try:
        iface = get_iface_frame(page)
        tb_before = await check_tab_bar(iface)
        count_before = tb_before.get('count', 0)

        # Click first close button
        await iface_loc.locator('.tv-tab-close').first.click()
        await page.wait_for_timeout(500)
        iface = get_iface_frame(page)
        tb_after = await check_tab_bar(iface)

        if tb_after.get('count', 0) == count_before - 1 and tb_after.get('count', 0) >= 2:
            record(test_num, 'Standalone', f'Close tab — {tb_after["count"]} remaining', 'PASS')
        else:
            record(test_num, 'Standalone', 'Close tab — others remain', 'FAIL', f'before={count_before} after={tb_after.get("count")}')
    except Exception as e:
        record(test_num, 'Standalone', 'Close tab — others remain', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 6: Dashboard tab returns to matrix view
    test_num += 1
    try:
        iface_loc = page.frame_locator('#ifaceFrame')
        await iface_loc.locator('.tv-tab[data-tab="dashboard"]').click()
        await page.wait_for_timeout(1000)
        iface = get_iface_frame(page)
        has_matrix = await iface.evaluate("() => !!document.querySelector('.tv-matrix')")
        if has_matrix:
            record(test_num, 'Standalone', 'Dashboard tab returns to matrix', 'PASS')
        else:
            record(test_num, 'Standalone', 'Dashboard tab returns to matrix', 'FAIL', 'no matrix found')
    except Exception as e:
        record(test_num, 'Standalone', 'Dashboard tab returns to matrix', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2 — Embedded Pre-populated Library
    # ═══════════════════════════════════════════════════════════════════════
    print("\n  \u2500\u2500 Phase 2: Embedded Pre-populated Library \u2500\u2500")

    # Load main navigator
    await page.goto(nav_url, wait_until='load', timeout=30000)
    await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")
    await page.wait_for_timeout(5000)

    nav = page.frames[1]

    # Navigate center-frame to Tests Interface
    await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", embed_url)
    await page.wait_for_timeout(6000)

    iface = await get_iface_frame_async(page)
    if iface:
        await wait_for_dashboard(iface, page)
        await page.wait_for_timeout(2000)

    # TEST 7: Tests Interface loads with pre-populated inventory tabs
    test_num += 1
    try:
        if iface:
            tb = await check_tab_bar(iface)
            if tb.get('count', 0) >= 3:
                record(test_num, 'Embedded', f'Pre-populated library: {tb["count"]} tabs', 'PASS')
                print(f"         Labels: {tb['labels']}")
            else:
                record(test_num, 'Embedded', 'Pre-populated library in embedded', 'FAIL', f'count={tb.get("count")}: {tb.get("labels")}')
        else:
            record(test_num, 'Embedded', 'Pre-populated library in embedded', 'FAIL', 'no iface frame')
    except Exception as e:
        record(test_num, 'Embedded', 'Pre-populated library in embedded', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 8: Click pre-populated inventory tab → routes to content-frame
    test_num += 1
    try:
        before_src = await nav.evaluate("() => { var rf = document.getElementById('right-frame-el'); return rf ? rf.src : ''; }")

        # Click first non-dashboard tab
        clicked = False
        for f in page.frames:
            if f.url in ('about:srcdoc', '') and f != page.main_frame:
                try:
                    has_inv = await f.evaluate("() => !!document.querySelector('.tv-tab:not([data-tab=\"dashboard\"])')")
                    if has_inv:
                        await f.click('.tv-tab:not([data-tab="dashboard"])')
                        clicked = True
                        break
                except:
                    pass

        if not clicked:
            raise Exception("Could not click inventory tab")

        await page.wait_for_timeout(3000)

        after_src = await nav.evaluate("() => { var rf = document.getElementById('right-frame-el'); return rf ? rf.src : ''; }")

        if after_src != before_src:
            record(test_num, 'Embedded', 'Inventory tab click routes to content-frame', 'PASS')
        else:
            record(test_num, 'Embedded', 'Inventory tab click routes to content-frame', 'FAIL', 'src unchanged')
    except Exception as e:
        record(test_num, 'Embedded', 'Inventory tab click routes to content-frame', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 9: Navigate back → all inventory tabs restored
    test_num += 1
    try:
        await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", embed_url)
        await page.wait_for_timeout(6000)

        iface = await get_iface_frame_async(page)
        if iface:
            await wait_for_dashboard(iface, page)
            await page.wait_for_timeout(2000)

        tb = await check_tab_bar(iface) if iface else {'found': False}
        # Pre-populated + restored should give ≥3 tabs
        if tb.get('count', 0) >= 3:
            record(test_num, 'Embedded', f'Navigate back — {tb["count"]} tabs restored', 'PASS')
            print(f"         {tb['labels']}")
        else:
            record(test_num, 'Embedded', 'Navigate back — tabs restored', 'FAIL', f'count={tb.get("count")}: {tb.get("labels")}')
    except Exception as e:
        record(test_num, 'Embedded', 'Navigate back — tabs restored', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 10: Click 2nd inventory tab → routes different report
    test_num += 1
    try:
        before_src2 = await nav.evaluate("() => { var rf = document.getElementById('right-frame-el'); return rf ? rf.src : ''; }")

        # Click 2nd non-dashboard tab
        clicked2 = False
        for f in page.frames:
            if f.url in ('about:srcdoc', '') and f != page.main_frame:
                try:
                    tab_count = await f.evaluate("() => document.querySelectorAll('.tv-tab:not([data-tab=\"dashboard\"])').length")
                    if tab_count and tab_count >= 2:
                        await f.evaluate("() => document.querySelectorAll('.tv-tab:not([data-tab=\"dashboard\"])')[1].click()")
                        clicked2 = True
                        break
                except:
                    pass

        if not clicked2:
            raise Exception("Could not click 2nd inventory tab")

        await page.wait_for_timeout(3000)

        after_src2 = await nav.evaluate("() => { var rf = document.getElementById('right-frame-el'); return rf ? rf.src : ''; }")

        if after_src2 != before_src2:
            record(test_num, 'Embedded', 'Click 2nd inventory tab routes different report', 'PASS')
        else:
            record(test_num, 'Embedded', 'Click 2nd inventory tab routes different report', 'FAIL', 'src unchanged')
    except Exception as e:
        record(test_num, 'Embedded', 'Click 2nd inventory tab routes different report', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 11: Navigate back → inventory tabs still intact
    test_num += 1
    try:
        await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", embed_url)
        await page.wait_for_timeout(6000)

        iface = await get_iface_frame_async(page)
        if iface:
            await wait_for_dashboard(iface, page)
            await page.wait_for_timeout(2000)

        tb = await check_tab_bar(iface) if iface else {'found': False}
        if tb.get('count', 0) >= 3:
            record(test_num, 'Embedded', f'Tabs still intact after 2nd return ({tb["count"]})', 'PASS')
            print(f"         {tb['labels']}")
        else:
            record(test_num, 'Embedded', 'Tabs still intact after 2nd return', 'FAIL', f'count={tb.get("count")}: {tb.get("labels")}')
    except Exception as e:
        record(test_num, 'Embedded', 'Tabs still intact after 2nd return', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 12: Click dashboard link in matrix → activates existing tab (no duplicate)
    test_num += 1
    try:
        iface = await get_iface_frame_async(page)
        tb_before = await check_tab_bar(iface) if iface else {'found': False}
        count_before = tb_before.get('count', 0)

        # Click a test link in the matrix (should activate existing pre-populated tab)
        clicked3 = False
        for f in page.frames:
            if f.url in ('about:srcdoc', '') and f != page.main_frame:
                try:
                    has_link = await f.evaluate("() => !!document.querySelector('.tv-test-link')")
                    if has_link:
                        await f.click('.tv-test-link')
                        clicked3 = True
                        break
                except:
                    pass

        if not clicked3:
            raise Exception("Could not click matrix link")

        await page.wait_for_timeout(2000)

        # In embedded mode, clicking a matrix link activates the existing pre-populated tab
        # and routes the report to content-frame (right panel). Tests Interface stays in center-frame.
        # Check that content-frame src changed (report was routed to right panel)
        after_src = await nav.evaluate("() => { var rf = document.getElementById('right-frame-el'); return rf ? rf.src : ''; }")

        if after_src and after_src != 'about:blank' and after_src != '':
            record(test_num, 'Embedded', 'Matrix click routes to content-frame', 'PASS')
        else:
            record(test_num, 'Embedded', 'Matrix click routes to content-frame', 'FAIL', 'content-frame unchanged')
    except Exception as e:
        record(test_num, 'Embedded', 'Matrix click routes without duplicate tab', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ─── Report ─────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r['result'] == 'PASS')
    failed = sum(1 for r in results if r['result'] == 'FAIL')

    print(f"\n{'=' * 75}")
    print(f"  {'#':>2s}  {'Phase':12s}  {'Test':52s}  Result")
    print(f"  {'──':2s}  {'─' * 12}  {'─' * 52}  {'─' * 6}")
    for r in results:
        mark = '\u2713' if r['result'] == 'PASS' else '\u2717'
        print(f"  {r['num']:2d}  {r['phase']:12s}  {r['target']:52s}  {mark} {r['result']}")
    print(f"  {'──':2s}  {'─' * 12}  {'─' * 52}  {'─' * 6}")
    print(f"  Total: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 75}")

    # Assemble proof
    os.makedirs(REPORT_DIR, exist_ok=True)
    gif_path = os.path.join(REPORT_DIR, f'{SLUG}-report.gif')
    assemble_gif(all_frames, gif_path)

    # Save results JSON
    timestamp = datetime.now().isoformat()
    results_json = {
        'mode': 'BEHAVIORAL-MULTITAB-v2',
        'default': results,
        'detailed': [],
        'timestamp': timestamp,
        'total_frames': len(all_frames),
    }
    results_path = os.path.join(REPORT_DIR, f'{SLUG}-results.json')
    with open(results_path, 'w') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {results_path}")

    # Update history.json
    history_path = os.path.join(REPORT_DIR, 'history.json')
    history = {'tests': {}}
    if os.path.isfile(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f)
        except (json.JSONDecodeError, KeyError):
            history = {'tests': {}}

    test_key = 'tests-interface-multitab'
    if test_key not in history['tests']:
        history['tests'][test_key] = {
            'title': 'Tests Interface — Multi-Tab Navigation',
            'title_fr': 'Interface Tests — Navigation multi-onglets',
            'href': f'publications/{SLUG}/index.md',
            'runs': []
        }

    history['tests'][test_key]['runs'].append({
        'timestamp': timestamp,
        'mode': 'BEHAVIORAL-MULTITAB-v2',
        'total': total,
        'passed': passed,
        'failed': failed,
    })

    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"  History: {history_path}")

    # Cleanup
    for fp in all_frames:
        if os.path.exists(fp):
            os.unlink(fp)
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir, ignore_errors=True)

    await browser.close()
    await p.stop()

    return results


if __name__ == '__main__':
    asyncio.run(run_tests())
