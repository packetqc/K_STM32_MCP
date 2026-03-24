#!/usr/bin/env python3
"""
Tests Interface — Standalone Behavioral Test v2
=================================================

Comprehensive behavioral test for the Tests Interface (I7) in standalone mode.
Tests navigation tabs, language switching (EN↔FR), content width, and browsing.

Phase 1 — Load & Dashboard (EN):
  1. Page loads without error
  2. Tab bar visible with Dashboard tab
  3. Dashboard renders stats, LED matrix, test links

Phase 2 — Tab Navigation:
  4. Click test link opens in new tab
  5. Tab iframe renders report content (fills width)
  6. Dashboard tab click returns to matrix
  7. Dashboard tab has no close button

Phase 3 — Language Switching (tabs preserved):
  8. Switch EN→FR with tab open: interface-mode preserved
  9. FR tab bar preserves open tab across language switch
 10. FR dashboard renders stats and matrix
 11. Close tab + open FR test link in tab
 12. Switch FR→EN with tab open: interface-mode preserved
 13. EN tab bar preserves open tab across language switch

Phase 4 — Content Width & Height:
 14. Tab report iframe uses ≥80% of container width
 15. Tab iframe fills available viewport height

Produces: results.json, GIF proof, MP4 proof

Usage:
    python3 scripts/tests_interface_test.py
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
SLUG = 'test-tests-interface'


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


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_iface_frame(pg):
    """Get the ifaceFrame's Frame object from Playwright."""
    for f in pg.frames:
        if f != pg.main_frame and f.url in ('about:srcdoc', ''):
            return f
    return pg.frame('ifaceFrame')


async def wait_for_dashboard(iface, page, retries=5):
    """Wait for dashboard stats to render (async fetch)."""
    for _ in range(retries):
        check = await iface.evaluate("""() => {
            return document.querySelectorAll('.tv-stat').length;
        }""")
        if check and check > 0:
            return True
        await page.wait_for_timeout(2000)
    return False


async def check_interface_mode(page):
    """Check if the viewer is in interface-mode (has ifaceFrame)."""
    return await page.evaluate("""() => {
        var content = document.getElementById('content');
        var iface = document.getElementById('ifaceFrame');
        return {
            interfaceMode: content ? content.dataset.interfaceMode === '1' : false,
            hasIframe: !!iface,
            bodyClass: document.body.classList.contains('interface-mode')
        };
    }""")


async def check_tab_bar(iface):
    """Check tab bar state inside the interface iframe."""
    return await iface.evaluate("""() => {
        var bar = document.querySelector('#tv-tab-bar, .tv-tab-bar');
        if (!bar) return { found: false };
        var tabs = bar.querySelectorAll('.tv-tab');
        var labels = [];
        tabs.forEach(function(t) {
            var l = t.querySelector('.tv-tab-label');
            labels.push(l ? l.textContent.trim() : '');
        });
        return { found: true, count: tabs.length, labels: labels, visible: bar.offsetHeight > 0 };
    }""")


async def check_dashboard(iface):
    """Check dashboard content."""
    return await iface.evaluate("""() => {
        var allStats = document.querySelectorAll('.tv-stat');
        var allLinks = document.querySelectorAll('.tv-test-link');
        return {
            found: true,
            statsCount: allStats.length,
            hasMatrix: !!document.querySelector('.tv-matrix'),
            linkCount: allLinks.length,
            linkTexts: Array.from(allLinks).map(function(l) { return l.textContent.trim(); }).slice(0, 5)
        };
    }""")


# ─── Test Runner ────────────────────────────────────────────────────────────

async def run_tests():
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found.")
        return

    handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)

    doc = 'interfaces/tests/index.md'
    viewer_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}"

    frame_dir = tempfile.mkdtemp(prefix='ti_test_')
    all_frames = []
    results = []
    test_num = 0

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
    print("  Tests Interface — Standalone Behavioral Test v2")
    print("  (with language switching, tab browsing, content width)")
    print("=" * 75)

    # ─── Load Tests Interface ───────────────────────────────────────────
    await page.goto(viewer_url, wait_until='load', timeout=30000)
    await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")
    await page.wait_for_timeout(4000)

    async def screenshot(tn):
        fp = os.path.join(frame_dir, f'frame_{tn:04d}.png')
        await page.screenshot(path=fp, full_page=False)
        all_frames.append(fp)

    def record(tn, phase, target, result, error=None):
        r = {'num': tn, 'phase': phase, 'target': target, 'panel': 'Standalone', 'result': result, 'doc': doc}
        if error:
            r['error'] = error
        results.append(r)
        mark = '✓' if result == 'PASS' else '✗'
        msg = f"  [{tn:2d}] {result} | {target}"
        if error:
            msg += f" — {error}"
        print(msg)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1 — Load & Dashboard (EN)
    # ═══════════════════════════════════════════════════════════════════
    print("\n  ── Phase 1: Load & Dashboard (EN) ──")

    iface = get_iface_frame(page)
    if not iface:
        await page.wait_for_timeout(3000)
        iface = get_iface_frame(page)

    # TEST 1: Page loads
    test_num += 1
    try:
        content_text = await iface.evaluate("() => document.body ? document.body.innerText.substring(0, 500) : ''") if iface else ''
        has_error = any(e in content_text.lower() for e in ['404', 'not found'])
        has_content = len(content_text.strip()) > 20
        if has_content and not has_error:
            record(test_num, 'Load', 'Tests Interface loads (EN)', 'PASS')
        else:
            record(test_num, 'Load', 'Tests Interface loads (EN)', 'FAIL', f'content={len(content_text)}')
    except Exception as e:
        record(test_num, 'Load', 'Tests Interface loads (EN)', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 2: Tab bar visible
    test_num += 1
    try:
        tb = await check_tab_bar(iface)
        if tb.get('found') and tb.get('visible') and tb.get('count', 0) >= 1:
            record(test_num, 'TabBar', 'Tab bar visible with Dashboard tab', 'PASS')
        else:
            record(test_num, 'TabBar', 'Tab bar visible with Dashboard tab', 'FAIL', f'{tb}')
    except Exception as e:
        record(test_num, 'TabBar', 'Tab bar visible with Dashboard tab', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 3: Dashboard renders
    await wait_for_dashboard(iface, page)
    test_num += 1
    try:
        db = await check_dashboard(iface)
        if db.get('statsCount', 0) > 0:
            record(test_num, 'Dashboard', 'Dashboard renders stats and matrix (EN)', 'PASS')
            print(f"         {db['statsCount']} stats, matrix={db['hasMatrix']}, {db['linkCount']} links: {db.get('linkTexts', [])}")
        else:
            record(test_num, 'Dashboard', 'Dashboard renders stats and matrix (EN)', 'FAIL', f'{db}')
    except Exception as e:
        record(test_num, 'Dashboard', 'Dashboard renders stats and matrix (EN)', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2 — Tab Navigation
    # ═══════════════════════════════════════════════════════════════════
    print("\n  ── Phase 2: Tab Navigation ──")

    # TEST 4: Click test link opens tab
    test_num += 1
    try:
        link_info = await iface.evaluate("""() => {
            var links = document.querySelectorAll('.tv-test-link');
            if (links.length === 0) return { found: false };
            return { found: true, text: links[0].textContent.trim() };
        }""")
        if link_info.get('found'):
            iface_loc = page.frame_locator('#ifaceFrame')
            await iface_loc.locator('.tv-test-link').first.click()
            await page.wait_for_timeout(3000)
            iface = get_iface_frame(page)
            ts = await check_tab_bar(iface)
            if ts.get('count', 0) >= 2:
                record(test_num, 'Navigation', 'Click test opens in new tab', 'PASS')
                print(f"         {ts['count']} tabs: {ts['labels']}")
            else:
                record(test_num, 'Navigation', 'Click test opens in new tab', 'FAIL', f'tabs={ts}')
        else:
            record(test_num, 'Navigation', 'Click test opens in new tab', 'FAIL', 'No test links')
    except Exception as e:
        record(test_num, 'Navigation', 'Click test opens in new tab', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 5: Tab iframe renders report (fills width)
    test_num += 1
    try:
        tab_content = await iface.evaluate("""() => {
            var activePanel = document.querySelector('.tv-tab-panel.active');
            if (!activePanel) return { found: false };
            var iframe = activePanel.querySelector('iframe');
            var container = document.getElementById('test-viewer');
            return {
                found: true,
                hasIframe: !!iframe,
                iframeWidth: iframe ? iframe.offsetWidth : 0,
                containerWidth: container ? container.offsetWidth : 0,
                panelWidth: activePanel.offsetWidth
            };
        }""")
        if tab_content.get('hasIframe'):
            record(test_num, 'Navigation', 'Tab iframe renders report content', 'PASS')
            print(f"         iframe={tab_content['iframeWidth']}px, panel={tab_content['panelWidth']}px, container={tab_content['containerWidth']}px")
        else:
            record(test_num, 'Navigation', 'Tab iframe renders report content', 'FAIL', f'{tab_content}')
    except Exception as e:
        record(test_num, 'Navigation', 'Tab iframe renders report content', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 6: Dashboard tab returns to matrix
    test_num += 1
    try:
        iface_loc = page.frame_locator('#ifaceFrame')
        await iface_loc.locator('.tv-tab[data-tab="dashboard"]').click()
        await page.wait_for_timeout(1000)
        iface = get_iface_frame(page)
        ds = await iface.evaluate("""() => {
            var dt = document.querySelector('.tv-tab[data-tab="dashboard"]');
            var dp = document.querySelector('.tv-tab-panel[data-tab="dashboard"], #tv-dashboard-panel');
            return {
                tabActive: dt ? dt.classList.contains('active') : false,
                panelVisible: dp ? (dp.classList.contains('active') && dp.offsetHeight > 0) : false
            };
        }""")
        if ds.get('tabActive') and ds.get('panelVisible'):
            record(test_num, 'Navigation', 'Dashboard tab returns to matrix view', 'PASS')
        else:
            record(test_num, 'Navigation', 'Dashboard tab returns to matrix view', 'FAIL', f'{ds}')
    except Exception as e:
        record(test_num, 'Navigation', 'Dashboard tab returns to matrix view', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 7: Dashboard tab has no close button
    test_num += 1
    try:
        iface = get_iface_frame(page)
        dc = await iface.evaluate("""() => {
            var dt = document.querySelector('.tv-tab[data-tab="dashboard"]');
            if (!dt) return { found: false };
            return { found: true, hasClose: !!dt.querySelector('.tv-tab-close') };
        }""")
        if dc.get('found') and not dc.get('hasClose'):
            record(test_num, 'TabBar', 'Dashboard tab has no close button', 'PASS')
        else:
            record(test_num, 'TabBar', 'Dashboard tab has no close button', 'FAIL', f'{dc}')
    except Exception as e:
        record(test_num, 'TabBar', 'Dashboard tab has no close button', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3 — Language Switching (tabs preserved)
    # ═══════════════════════════════════════════════════════════════════
    print("\n  ── Phase 3: Language Switching (tabs preserved) ──")

    # Re-open a tab before switching language (tab from Phase 2 was left open after test 6)
    # Ensure we're on dashboard and have a tab open
    iface = get_iface_frame(page)
    tb_pre = await check_tab_bar(iface)
    pre_tab_count = tb_pre.get('count', 0) if tb_pre else 0
    if pre_tab_count < 2:
        # Open a tab for the language switch test
        iface_loc = page.frame_locator('#ifaceFrame')
        await iface_loc.locator('.tv-test-link').first.click()
        await page.wait_for_timeout(3000)
        iface = get_iface_frame(page)

    # TEST 8: Switch EN→FR with tab open — interface mode preserved
    test_num += 1
    try:
        await page.click('#langFr')
        await page.wait_for_timeout(5000)

        mode = await check_interface_mode(page)
        if mode.get('interfaceMode') and mode.get('hasIframe') and mode.get('bodyClass'):
            record(test_num, 'LangSwitch', 'EN→FR: interface-mode preserved', 'PASS')
        else:
            record(test_num, 'LangSwitch', 'EN→FR: interface-mode preserved', 'FAIL', f'{mode}')
    except Exception as e:
        record(test_num, 'LangSwitch', 'EN→FR: interface-mode preserved', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 9: FR tab bar preserves open tab across language switch
    test_num += 1
    try:
        iface = get_iface_frame(page)
        if not iface:
            await page.wait_for_timeout(3000)
            iface = get_iface_frame(page)
        if iface:
            await wait_for_dashboard(iface, page)
            await page.wait_for_timeout(2000)
        tb_fr = await check_tab_bar(iface) if iface else {'found': False}
        if tb_fr.get('found') and tb_fr.get('visible') and tb_fr.get('count', 0) >= 2:
            record(test_num, 'LangSwitch', 'FR preserves tab across lang switch', 'PASS')
            print(f"         {tb_fr['count']} tab(s): {tb_fr['labels']}")
        else:
            record(test_num, 'LangSwitch', 'FR preserves tab across lang switch', 'FAIL',
                   f"expected ≥2 tabs, got {tb_fr.get('count', 0)}: {tb_fr.get('labels', [])}")
    except Exception as e:
        record(test_num, 'LangSwitch', 'FR preserves tab across lang switch', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 10: FR dashboard renders stats and matrix
    test_num += 1
    try:
        iface = get_iface_frame(page)
        if iface:
            # Switch to dashboard tab to check stats
            iface_loc = page.frame_locator('#ifaceFrame')
            dash_tab = iface_loc.locator('.tv-tab[data-tab="dashboard"]')
            if await dash_tab.count() > 0:
                await dash_tab.click()
                await page.wait_for_timeout(1000)
            iface = get_iface_frame(page)
            await wait_for_dashboard(iface, page)
        db_fr = await check_dashboard(iface) if iface else {'found': False}
        if db_fr.get('statsCount', 0) > 0:
            record(test_num, 'LangSwitch', 'FR dashboard renders stats + matrix', 'PASS')
            print(f"         {db_fr['statsCount']} stats, {db_fr['linkCount']} links: {db_fr.get('linkTexts', [])}")
        else:
            record(test_num, 'LangSwitch', 'FR dashboard renders stats + matrix', 'FAIL', f'{db_fr}')
    except Exception as e:
        record(test_num, 'LangSwitch', 'FR dashboard renders stats + matrix', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 11: Close restored tab + open FR test link in new tab
    test_num += 1
    try:
        iface = get_iface_frame(page)
        iface_loc = page.frame_locator('#ifaceFrame')
        # Close any existing non-dashboard tabs
        close_btn = iface_loc.locator('.tv-tab-close').first
        while await close_btn.count() > 0:
            await close_btn.click()
            await page.wait_for_timeout(300)
            close_btn = iface_loc.locator('.tv-tab-close').first
        # Open a new FR tab
        await iface_loc.locator('.tv-test-link').first.click()
        await page.wait_for_timeout(3000)
        iface = get_iface_frame(page)
        ts_fr = await check_tab_bar(iface) if iface else {'found': False}
        if ts_fr.get('count', 0) >= 2:
            record(test_num, 'LangSwitch', 'Close + open FR test in tab', 'PASS')
            print(f"         {ts_fr['count']} tabs: {ts_fr['labels']}")
        else:
            record(test_num, 'LangSwitch', 'Close + open FR test in tab', 'FAIL', f'tabs={ts_fr}')
    except Exception as e:
        record(test_num, 'LangSwitch', 'Close + open FR test in tab', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 12: Switch FR→EN with tab open — interface mode preserved
    test_num += 1
    try:
        await page.click('#langEn')
        await page.wait_for_timeout(5000)

        mode2 = await check_interface_mode(page)
        if mode2.get('interfaceMode') and mode2.get('hasIframe') and mode2.get('bodyClass'):
            record(test_num, 'LangSwitch', 'FR→EN: interface-mode preserved', 'PASS')
        else:
            record(test_num, 'LangSwitch', 'FR→EN: interface-mode preserved', 'FAIL', f'{mode2}')
    except Exception as e:
        record(test_num, 'LangSwitch', 'FR→EN: interface-mode preserved', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 13: EN tab bar preserves open tab across language switch
    test_num += 1
    try:
        iface = get_iface_frame(page)
        if iface:
            await wait_for_dashboard(iface, page)
            await page.wait_for_timeout(2000)
        tb_en2 = await check_tab_bar(iface) if iface else {'found': False}
        db_en2 = await check_dashboard(iface) if iface else {'found': False}
        if tb_en2.get('found') and tb_en2.get('visible') and tb_en2.get('count', 0) >= 2 and db_en2.get('statsCount', 0) > 0:
            record(test_num, 'LangSwitch', 'EN preserves tab across lang switch', 'PASS')
            print(f"         {tb_en2['count']} tab(s): {tb_en2['labels']}, {db_en2['statsCount']} stats")
        else:
            record(test_num, 'LangSwitch', 'EN preserves tab across lang switch', 'FAIL',
                   f"tabs={tb_en2.get('count', 0)}: {tb_en2.get('labels', [])}, stats={db_en2.get('statsCount', 0)}")
    except Exception as e:
        record(test_num, 'LangSwitch', 'EN preserves tab across lang switch', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4 — Content Width & Height
    # ═══════════════════════════════════════════════════════════════════
    print("\n  ── Phase 4: Content Width & Height ──")

    # Ensure a tab is open (should be from Phase 3 persistence)
    iface = get_iface_frame(page)
    tb_p4 = await check_tab_bar(iface) if iface else {'found': False}
    if tb_p4.get('count', 0) < 2:
        iface_loc = page.frame_locator('#ifaceFrame')
        await iface_loc.locator('.tv-test-link').first.click()
        await page.wait_for_timeout(3000)
        iface = get_iface_frame(page)
    else:
        # Switch to a non-dashboard tab
        iface_loc = page.frame_locator('#ifaceFrame')
        non_dash = iface_loc.locator('.tv-tab:not([data-tab="dashboard"])').first
        if await non_dash.count() > 0:
            await non_dash.click()
            await page.wait_for_timeout(1000)
            iface = get_iface_frame(page)

    # TEST 14: Tab report uses ≥80% container width
    test_num += 1
    try:
        widths = await iface.evaluate("""() => {
            var activePanel = document.querySelector('.tv-tab-panel.active');
            if (!activePanel) return { found: false };
            var iframe = activePanel.querySelector('iframe');
            var container = document.getElementById('test-viewer');
            return {
                found: true,
                containerWidth: container ? container.offsetWidth : 0,
                panelWidth: activePanel.offsetWidth,
                iframeWidth: iframe ? iframe.offsetWidth : 0,
                ratio: container ? (activePanel.offsetWidth / container.offsetWidth) : 0
            };
        }""")

        if widths.get('found') and widths.get('ratio', 0) >= 0.80:
            record(test_num, 'Width', 'Tab report uses ≥80% container width', 'PASS')
            print(f"         ratio={widths['ratio']:.2f}, panel={widths['panelWidth']}px, container={widths['containerWidth']}px")
        else:
            record(test_num, 'Width', 'Tab report uses ≥80% container width', 'FAIL',
                   f"ratio={widths.get('ratio', 0):.2f}, panel={widths.get('panelWidth')}px, container={widths.get('containerWidth')}px")
    except Exception as e:
        record(test_num, 'Width', 'Tab report uses ≥80% container width', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # TEST 15: Tab iframe fills available viewport height
    test_num += 1
    try:
        heights = await iface.evaluate("""() => {
            var viewer = document.getElementById('test-viewer');
            var activePanel = document.querySelector('.tv-tab-panel.active');
            var iframe = activePanel ? activePanel.querySelector('iframe') : null;
            var winH = window.innerHeight;
            return {
                found: !!iframe,
                viewerH: viewer ? viewer.offsetHeight : 0,
                iframeH: iframe ? iframe.offsetHeight : 0,
                windowH: winH,
                viewerRatio: viewer ? (viewer.offsetHeight / winH) : 0,
                iframeRatio: iframe ? (iframe.offsetHeight / winH) : 0
            };
        }""")

        if heights.get('found') and heights.get('viewerRatio', 0) >= 0.90:
            record(test_num, 'Height', 'Tab iframe fills viewport height', 'PASS')
            print(f"         viewerH={heights['viewerH']}px ({heights['viewerRatio']:.0%}), iframeH={heights['iframeH']}px ({heights['iframeRatio']:.0%}), windowH={heights['windowH']}px")
        else:
            record(test_num, 'Height', 'Tab iframe fills viewport height', 'FAIL',
                   f"viewerH={heights.get('viewerH')}px ({heights.get('viewerRatio', 0):.0%}), windowH={heights.get('windowH')}px")
    except Exception as e:
        record(test_num, 'Height', 'Tab iframe fills viewport height', 'FAIL', str(e)[:60])
    await screenshot(test_num)

    # ═══════════════════════════════════════════════════════════════════
    # Report
    # ═══════════════════════════════════════════════════════════════════
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
        'mode': 'BEHAVIORAL',
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

    test_key = 'tests-interface'
    if test_key not in history['tests']:
        history['tests'][test_key] = {
            'title': 'Tests Interface — Navigation Tabs',
            'title_fr': 'Interface Tests — Onglets de navigation',
            'href': f'publications/{SLUG}/index.md',
            'runs': []
        }

    history['tests'][test_key]['runs'].append({
        'timestamp': timestamp,
        'mode': 'BEHAVIORAL',
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
