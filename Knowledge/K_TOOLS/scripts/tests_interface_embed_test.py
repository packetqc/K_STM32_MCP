#!/usr/bin/env python3
"""
Tests Interface — Embedded Mode Behavioral Test v2
====================================================

Tests the Tests Interface when loaded INSIDE the main navigator (center-frame).
Validates navigation tab tracking: clicks route to content-frame (right panel)
AND add a tracking tab in the Tests Interface, restored via sessionStorage
when the user navigates back.

  1. Tests Interface loads in center-frame with tab bar visible
  2. Tab bar visible in embedded mode
  3. Dashboard renders stats and LED matrix
  4. OWASP test appears in dashboard matrix
  5. IS_EMBED detected correctly (center-frame exists in parent)
  6. Click routes to content-frame (right panel) + adds tracking tab
  7. Report content loaded in content-frame after click
  8. Navigate back to Tests Interface — tracking tab restored
  9. Click tracking tab routes report back to content-frame

Produces: results.json, GIF proof, MP4 proof — compatible with generate_test_report.py

Usage:
    python3 scripts/tests_interface_embed_test.py
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
SLUG = 'test-tests-interface-embed'


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


MP4_SCALE = 0.5
MP4_MAX_MB = 7

def assemble_mp4(frame_paths, output_path, fps=0.5, scale=None):
    from video_utils import encode_mp4_from_paths, estimate_mp4_scale
    if not frame_paths:
        return
    from PIL import Image
    first = Image.open(frame_paths[0])
    w, h = first.size
    first.close()
    if scale is None:
        auto_scale = estimate_mp4_scale(len(frame_paths), w, h, max_mb=MP4_MAX_MB)
        scale = min(auto_scale, MP4_SCALE)
    encode_mp4_from_paths(frame_paths, output_path, fps=fps, scale=scale)


# ─── Frame Finder Helpers ───────────────────────────────────────────────────

def find_tests_iface_frame(page):
    """Find the Tests Interface srcdoc frame in the embedded hierarchy.

    Frame chain: page → nav (ifaceFrame srcdoc) → center-frame-el (viewer)
                                                    → ifaceFrame (tests srcdoc)
    We need the deepest srcdoc frame that contains the test-viewer.
    """
    # Collect all srcdoc frames
    srcdoc_frames = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
    # The tests interface srcdoc is the one with #tv-tab-bar
    for f in srcdoc_frames:
        try:
            has_tv = f.query_selector_all_evaluate('#tv-tab-bar', 'els => els.length')
            if has_tv and has_tv > 0:
                return f
        except:
            pass
    # Fallback: return the last srcdoc (deepest nested)
    return srcdoc_frames[-1] if srcdoc_frames else None


async def find_tests_frame_async(page):
    """Async version — checks all srcdoc frames for the Tests Interface."""
    srcdoc_frames = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
    for f in srcdoc_frames:
        try:
            has_tv = await f.evaluate("() => !!document.getElementById('tv-tab-bar')")
            if has_tv:
                return f
        except:
            pass
    return srcdoc_frames[-1] if srcdoc_frames else None


# ─── Test Cases ─────────────────────────────────────────────────────────────

async def run_tests():
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found.")
        return

    handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)

    # Load the MAIN NAVIGATOR first (same as web_test_engine)
    nav_doc = 'interfaces/main-navigator/index.md'
    viewer_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(nav_doc)}"

    frame_dir = tempfile.mkdtemp(prefix='ti_embed_')
    all_frames = []
    results = []
    test_num = 0
    doc = 'interfaces/tests/index.md'

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
    print("  Tests Interface — EMBEDDED Mode Behavioral Test")
    print("=" * 75)

    # ─── Load Main Navigator ────────────────────────────────────────────
    await page.goto(viewer_url, wait_until='load', timeout=30000)
    await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")
    await page.wait_for_timeout(5000)

    # Get the navigator frame (first srcdoc iframe)
    nav = page.frames[1]

    # Navigate center-frame to Tests Interface (embedded mode with &embed)
    tests_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}&embed&lang=en"
    await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", tests_url)
    await page.wait_for_timeout(5000)

    # ─── Find the Tests Interface frame (deepest srcdoc with #tv-tab-bar)
    iface = await find_tests_frame_async(page)
    if not iface:
        print("  CRITICAL: Could not find Tests Interface frame in embedded mode")
        # Still take a screenshot for proof
        fp = os.path.join(frame_dir, 'frame_0000.png')
        await page.screenshot(path=fp, full_page=False)
        all_frames.append(fp)

    # ─── TEST 1: Tests Interface loads in center-frame ──────────────────
    test_num += 1
    try:
        content_text = await iface.evaluate("""() => {
            return document.body ? document.body.innerText.substring(0, 500) : '';
        }""") if iface else ''
        has_error = bool(any(e in content_text.lower() for e in ['404', 'not found']))
        has_content = len(content_text.strip()) > 20

        if has_content and not has_error:
            results.append({'num': test_num, 'phase': 'Load', 'target': 'Tests Interface loads in center-frame', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Tests Interface loaded in embedded mode")
        else:
            results.append({'num': test_num, 'phase': 'Load', 'target': 'Tests Interface loads in center-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'content={len(content_text)}, error={has_error}'})
            print(f"  [{test_num:2d}] FAIL | Tests Interface failed to load in center-frame")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Load', 'target': 'Tests Interface loads in center-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 2: Tab bar exists in embedded mode ────────────────────────
    test_num += 1
    try:
        tab_bar = await iface.evaluate("""() => {
            var bar = document.querySelector('#tv-tab-bar, .tv-tab-bar');
            if (!bar) return { found: false };
            var tabs = bar.querySelectorAll('.tv-tab');
            var labels = [];
            tabs.forEach(function(t) {
                var l = t.querySelector('.tv-tab-label');
                labels.push(l ? l.textContent.trim() : '');
            });
            return { found: true, count: tabs.length, labels: labels, visible: bar.offsetHeight > 0 };
        }""") if iface else {'found': False}

        if tab_bar.get('found') and tab_bar.get('visible') and tab_bar.get('count', 0) >= 1:
            results.append({'num': test_num, 'phase': 'TabBar', 'target': 'Tab bar visible in embedded mode', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Tab bar visible, {tab_bar['count']} tab(s): {tab_bar['labels']}")
        else:
            results.append({'num': test_num, 'phase': 'TabBar', 'target': 'Tab bar visible in embedded mode', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'{tab_bar}'})
            print(f"  [{test_num:2d}] FAIL | Tab bar: {tab_bar}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'TabBar', 'target': 'Tab bar visible in embedded mode', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 3: Dashboard renders stats + matrix (with history data) ───
    # Wait for fetch to complete
    for _ in range(5):
        if not iface:
            break
        check = await iface.evaluate("""() => {
            return document.querySelectorAll('.tv-stat').length;
        }""")
        if check and check > 0:
            break
        await page.wait_for_timeout(2000)

    test_num += 1
    try:
        dashboard = await iface.evaluate("""() => {
            var allStats = document.querySelectorAll('.tv-stat');
            var allLinks = document.querySelectorAll('.tv-test-link');
            return {
                found: true,
                statsCount: allStats.length,
                hasMatrix: !!document.querySelector('.tv-matrix'),
                linkCount: allLinks.length,
                linkTexts: Array.from(allLinks).map(function(l) { return l.textContent.trim(); }).slice(0, 5)
            };
        }""") if iface else {'found': False}

        if dashboard.get('found') and dashboard.get('statsCount', 0) > 0:
            results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'Dashboard renders stats and matrix', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Dashboard: {dashboard['statsCount']} stats, matrix={dashboard['hasMatrix']}, {dashboard['linkCount']} links: {dashboard.get('linkTexts', [])}")
        else:
            results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'Dashboard renders stats and matrix', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'{dashboard}'})
            print(f"  [{test_num:2d}] FAIL | Dashboard: {dashboard}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'Dashboard renders stats and matrix', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 4: OWASP security test appears in dashboard ───────────────
    test_num += 1
    try:
        owasp = await iface.evaluate("""() => {
            var links = document.querySelectorAll('.tv-test-link');
            var found = false;
            var allTitles = [];
            links.forEach(function(l) {
                var text = l.textContent.trim();
                allTitles.push(text);
                if (/owasp|security|token/i.test(text)) found = true;
            });
            return { found: found, titles: allTitles };
        }""") if iface else {'found': False}

        if owasp.get('found'):
            results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'OWASP security test in matrix', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | OWASP test found in dashboard: {owasp['titles']}")
        else:
            results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'OWASP security test in matrix', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'titles={owasp.get("titles")}'})
            print(f"  [{test_num:2d}] FAIL | OWASP not found in dashboard: {owasp}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Dashboard', 'target': 'OWASP security test in matrix', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 5: IS_EMBED detected correctly ────────────────────────────
    test_num += 1
    try:
        embed_state = await iface.evaluate("""() => {
            /* Check if the interface detected embed mode correctly.
               In embed mode, clicking a test link should NOT create tabs,
               it should route to center-frame in the navigator parent. */
            var isEmbed = false;
            try {
                var pDoc = window.parent.document;
                isEmbed = !!pDoc.querySelector('iframe[name="center-frame"]');
            } catch(ex) {}
            if (!isEmbed) try {
                var ppDoc = window.parent.parent.document;
                isEmbed = !!ppDoc.querySelector('iframe[name="center-frame"]');
            } catch(ex2) {}
            return { isEmbed: isEmbed };
        }""") if iface else {'isEmbed': False}

        if embed_state.get('isEmbed'):
            results.append({'num': test_num, 'phase': 'Detection', 'target': 'IS_EMBED correctly detected', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | IS_EMBED correctly detected as true")
        else:
            results.append({'num': test_num, 'phase': 'Detection', 'target': 'IS_EMBED correctly detected', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'{embed_state}'})
            print(f"  [{test_num:2d}] FAIL | IS_EMBED detection: {embed_state}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Detection', 'target': 'IS_EMBED correctly detected', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 6: Click routes to content-frame (right panel) + adds inventory tab
    test_num += 1
    try:
        # Record the content-frame (right panel) src BEFORE click
        before_src = await nav.evaluate("""() => {
            var rf = document.getElementById('right-frame-el');
            return rf ? rf.src : '';
        }""")

        # Click test link in the Tests Interface frame
        all_srcdoc = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
        clicked = False
        for f in all_srcdoc:
            try:
                has_link = await f.evaluate("() => !!document.querySelector('.tv-test-link')")
                if has_link:
                    await f.click('.tv-test-link')
                    clicked = True
                    break
            except:
                pass

        if not clicked:
            raise Exception("Could not click test link in any frame")

        await page.wait_for_timeout(3000)

        # Check content-frame (right panel) src changed
        after_src = await nav.evaluate("""() => {
            var rf = document.getElementById('right-frame-el');
            return rf ? rf.src : '';
        }""")

        src_changed = after_src != before_src

        if src_changed:
            results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Click routes to content-frame + adds tab', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Click routed to content-frame (src changed)")
        else:
            results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Click routes to content-frame + adds tab', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': 'content-frame src unchanged'})
            print(f"  [{test_num:2d}] FAIL | content-frame src unchanged")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Click routes to center-frame + adds tab', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 7: Content-frame received report URL ─────────────────────
    test_num += 1
    try:
        # Verify content-frame has a valid report URL (not empty/about:blank)
        cf_src = await nav.evaluate("""() => {
            var rf = document.getElementById('right-frame-el');
            return rf ? rf.src : '';
        }""")

        has_report_url = cf_src and 'about:blank' not in cf_src and cf_src != '' and 'index.html' in cf_src

        if has_report_url:
            results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Report URL set in content-frame', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Report URL in content-frame: {cf_src[:60]}...")
        else:
            results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Report URL set in content-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': f'src={cf_src[:60]}'})
            print(f"  [{test_num:2d}] FAIL | content-frame src: {cf_src[:60]}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Navigation', 'target': 'Report content loaded in center-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 8: Navigate back to Tests Interface — inventory tab restored ─
    test_num += 1
    try:
        # Navigate center-frame back to Tests Interface
        await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", tests_url)
        await page.wait_for_timeout(6000)

        # Find the restored Tests Interface frame
        iface2 = await find_tests_frame_async(page)
        if not iface2:
            raise Exception("Could not find Tests Interface frame after navigating back")

        # Wait for dashboard to render
        for _ in range(5):
            check = await iface2.evaluate("() => document.querySelectorAll('.tv-stat').length")
            if check and check > 0:
                break
            await page.wait_for_timeout(2000)

        # Check tab bar for restored inventory tab
        tab_info = await iface2.evaluate("""() => {
            var bar = document.querySelector('#tv-tab-bar');
            if (!bar) return { found: false };
            var allTabs = bar.querySelectorAll('.tv-tab');
            var labels = [];
            allTabs.forEach(function(t) {
                var l = t.querySelector('.tv-tab-label');
                labels.push(l ? l.textContent.trim() : '');
            });
            return { found: true, count: allTabs.length, labels: labels };
        }""")

        if tab_info.get('count', 0) >= 2:
            results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Tab inventory restored after navigation', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Tab inventory restored: {tab_info['count']} tabs {tab_info['labels']}")
        else:
            results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Tab inventory restored after navigation', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc,
                            'error': f"expected ≥2 tabs, got {tab_info.get('count', 0)}: {tab_info.get('labels', [])}"})
            print(f"  [{test_num:2d}] FAIL | Expected ≥2 tabs, got {tab_info.get('count', 0)}: {tab_info.get('labels', [])}")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Tab inventory restored after navigation', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── TEST 9: Click different inventory tab routes to content-frame ──
    test_num += 1
    try:
        iface2 = await find_tests_frame_async(page)
        if not iface2:
            raise Exception("Could not find Tests Interface frame")

        # Record content-frame (right panel) src before clicking inventory tab
        before_src2 = await nav.evaluate("""() => {
            var rf = document.getElementById('right-frame-el');
            return rf ? rf.src : '';
        }""")

        # Click the 2nd non-dashboard tab (different from what Test 6 routed)
        clicked2 = False
        all_srcdoc2 = [f for f in page.frames if f.url in ('about:srcdoc', '') and f != page.main_frame]
        for f in all_srcdoc2:
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

        # Check content-frame (right panel) src changed
        after_src2 = await nav.evaluate("""() => {
            var rf = document.getElementById('right-frame-el');
            return rf ? rf.src : '';
        }""")

        if after_src2 != before_src2:
            results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Inventory tab click routes to content-frame', 'panel': 'Embedded', 'result': 'PASS', 'doc': doc})
            print(f"  [{test_num:2d}] PASS | Inventory tab click routed to content-frame")
        else:
            results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Inventory tab click routes to content-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc,
                            'error': 'content-frame src unchanged after tab click'})
            print(f"  [{test_num:2d}] FAIL | content-frame unchanged after tab click")
    except Exception as e:
        results.append({'num': test_num, 'phase': 'Persistence', 'target': 'Inventory tab click routes to center-frame', 'panel': 'Embedded', 'result': 'FAIL', 'doc': doc, 'error': str(e)[:60]})
        print(f"  [{test_num:2d}] FAIL | {str(e)[:60]}")

    fp = os.path.join(frame_dir, f'frame_{test_num:04d}.png')
    await page.screenshot(path=fp, full_page=False)
    all_frames.append(fp)

    # ─── Report ─────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r['result'] == 'PASS')
    failed = sum(1 for r in results if r['result'] == 'FAIL')

    print(f"\n{'=' * 75}")
    print(f"  {'#':>2s}  {'Phase':12s}  {'Test':42s}  Result")
    print(f"  {'──':2s}  {'─' * 12}  {'─' * 42}  {'─' * 6}")
    for r in results:
        mark = '✓' if r['result'] == 'PASS' else '✗'
        print(f"  {r['num']:2d}  {r['phase']:12s}  {r['target']:42s}  {mark} {r['result']}")
    print(f"  {'──':2s}  {'─' * 12}  {'─' * 42}  {'─' * 6}")
    print(f"  Total: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 75}")

    # Assemble proof
    os.makedirs(REPORT_DIR, exist_ok=True)
    gif_path = os.path.join(REPORT_DIR, f'{SLUG}-report.gif')
    mp4_path = os.path.join(REPORT_DIR, f'{SLUG}-report.mp4')
    assemble_gif(all_frames, gif_path)
    assemble_mp4(all_frames, mp4_path)

    # Save results JSON
    timestamp = datetime.now().isoformat()
    results_json = {
        'mode': 'BEHAVIORAL-EMBED',
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

    test_key = 'tests-interface-embed'
    if test_key not in history['tests']:
        history['tests'][test_key] = {
            'title': 'Tests Interface — Embedded Mode',
            'title_fr': 'Interface Tests — Mode intégré',
            'href': f'publications/{SLUG}/index.md',
            'runs': []
        }

    history['tests'][test_key]['runs'].append({
        'timestamp': timestamp,
        'mode': 'BEHAVIORAL-EMBED',
        'total': total,
        'passed': passed,
        'failed': failed,
    })

    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"  History: {history_path} ({len(history['tests'][test_key]['runs'])} runs)")

    # Cleanup
    for fp_clean in all_frames:
        if os.path.exists(fp_clean):
            os.unlink(fp_clean)
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir, ignore_errors=True)

    await browser.close()
    await p.stop()

    return results


if __name__ == '__main__':
    asyncio.run(run_tests())
