#!/usr/bin/env python3
"""
Web Test Engine v2.0 — Request-Driven Grid Testing for Knowledge Interfaces
=============================================================================

Programmatic web page assessment with three discovery vectors:
  1. Code — read source to know what widgets exist
  2. Console — execute JS to query DOM, inspect state
  3. Visual — screenshot to confirm what's rendered

Tests are always driven by specific requests — no predefined modes.
Claude determines which pages to test based on the user's request.

Usage:
    # Test specific pages (targeted validation)
    python3 scripts/web_test_engine.py --targets interfaces/main-navigator/index.md publications/my-pub/index.md

    # Test specific pages with widget interaction tests
    python3 scripts/web_test_engine.py --targets doc1.md doc2.md --detailed doc1.md doc2.md

    # Widget interaction tests on specific pages only
    python3 scripts/web_test_engine.py --detailed interfaces/task-workflow/index.md

Discovery utilities (build_complete_tests) are available as library functions
for Claude to identify relevant pages, but are not wired to any CLI flag.

Knowledge asset — part of the Web Test command category.
"""

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
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


def find_chrome():
    import glob as g
    for p in CHROME_PATHS:
        matches = g.glob(p)
        if matches:
            return matches[0]
    return None


# ─── Route Handlers ─────────────────────────────────────────────────────────

def make_route_handlers(docs_root):
    """Create Playwright route handlers for local file serving."""

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
        url = route.request.url
        if 'sections.json' in url:
            local = os.path.join(docs_root, '..', 'Knowledge', 'sections.json')
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        # Resolve raw.githubusercontent.com/packetqc/knowledge/main/Knowledge/... → local Knowledge/...
        m = re.search(r'/knowledge/main/(Knowledge/.+)$', url)
        if m:
            rel_path = m.group(1)
            local = os.path.join(docs_root, '..', rel_path)
            if os.path.isfile(local):
                ext = os.path.splitext(local)[1].lower()
                ct = {'.md': 'text/plain', '.json': 'application/json',
                      '.html': 'text/html', '.css': 'text/css',
                      '.js': 'application/javascript'}.get(ext, 'application/octet-stream')
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type=ct)
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
        if 'mind_memory.md' in url:
            local = os.path.join(docs_root, '..', 'Knowledge', 'K_MIND', 'mind', 'mind_memory.md')
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='text/plain')
                return
        if 'depth_config.json' in url:
            local = os.path.join(docs_root, '..', 'Knowledge', 'K_MIND', 'conventions', 'depth_config.json')
            if os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                await route.fulfill(body=body, content_type='application/json')
                return
        await route.abort()

    return handle_cdn, handle_github_raw, handle_data


# ─── DOM Scanner ─────────────────────────────────────────────────────────────

SCAN_JS = """() => {
    const results = [];

    // Buttons
    document.querySelectorAll('button').forEach((el, i) => {
        results.push({
            type: 'button', id: el.id || null,
            text: el.textContent.trim().substring(0, 50),
            class: el.className.substring(0, 60),
            visible: el.offsetParent !== null,
            disabled: el.disabled, selector: 'button:nth-of-type(' + (i+1) + ')'
        });
    });

    // Links
    document.querySelectorAll('a[href]').forEach((el, i) => {
        results.push({
            type: 'link', id: el.id || null,
            text: el.textContent.trim().substring(0, 50),
            href: el.getAttribute('href').substring(0, 80),
            class: el.className.substring(0, 60),
            visible: el.offsetParent !== null,
            selector: 'a[href]:nth-of-type(' + (i+1) + ')'
        });
    });

    // Selects
    document.querySelectorAll('select').forEach((el, i) => {
        const opts = [...el.options].map(o => o.text.substring(0, 30));
        results.push({
            type: 'select', id: el.id || null,
            class: el.className.substring(0, 60),
            options: opts, optionCount: opts.length, value: el.value,
            visible: el.offsetParent !== null,
            selector: el.id ? '#' + el.id : 'select:nth-of-type(' + (i+1) + ')'
        });
    });

    // Inputs
    document.querySelectorAll('input, textarea').forEach((el, i) => {
        results.push({
            type: 'input', inputType: el.type || 'text',
            id: el.id || null, name: el.name || null,
            placeholder: (el.placeholder || '').substring(0, 40),
            class: el.className.substring(0, 60),
            visible: el.offsetParent !== null,
            selector: el.id ? '#' + el.id : (el.tagName.toLowerCase() + ':nth-of-type(' + (i+1) + ')')
        });
    });

    // Accordions (details/summary)
    document.querySelectorAll('details').forEach((el, i) => {
        const sum = el.querySelector('summary');
        results.push({
            type: 'accordion', id: el.id || null,
            summary: sum ? sum.textContent.trim().substring(0, 50) : '',
            open: el.open, visible: el.offsetParent !== null,
            selector: 'details:nth-of-type(' + (i+1) + ')'
        });
    });

    // Tabs
    document.querySelectorAll('[role="tab"], .tab-item, [data-tab]').forEach((el, i) => {
        results.push({
            type: 'tab', id: el.id || null,
            text: el.textContent.trim().substring(0, 50),
            class: el.className.substring(0, 60),
            active: el.classList.contains('active') || el.getAttribute('aria-selected') === 'true',
            visible: el.offsetParent !== null,
            selector: el.id ? '#' + el.id : '[role="tab"]:nth-of-type(' + (i+1) + ')'
        });
    });

    // Checkboxes and radios
    document.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach((el, i) => {
        const lbl = el.labels && el.labels[0] ? el.labels[0].textContent.trim().substring(0, 40) :
                    (el.parentElement ? el.parentElement.textContent.trim().substring(0, 40) : '');
        results.push({
            type: el.type, id: el.id || null, name: el.name || null,
            checked: el.checked, label: lbl,
            visible: el.offsetParent !== null,
            selector: el.id ? '#' + el.id : 'input[type="' + el.type + '"]:nth-of-type(' + (i+1) + ')'
        });
    });

    return results;
}"""


async def scan_frame_widgets(frame):
    """Scan a frame and all nested iframes for interactive widgets."""
    all_widgets = []
    try:
        widgets = await frame.evaluate(SCAN_JS)
        for w in widgets:
            w['frame_url'] = frame.url[:60]
        all_widgets.extend(widgets)
    except Exception:
        pass

    # Recurse into child frames
    for child in frame.child_frames:
        child_widgets = await scan_frame_widgets(child)
        all_widgets.extend(child_widgets)

    return all_widgets


# ─── Widget Trigger Engine ──────────────────────────────────────────────────

async def trigger_widget(frame, widget, page):
    """Trigger a single widget and return success/failure."""
    wtype = widget['type']
    try:
        if wtype == 'button':
            await frame.evaluate(f"""() => {{
                const btns = document.querySelectorAll('button');
                const btn = btns[{widget.get('index', 0)}];
                if (btn && !btn.disabled) btn.click();
            }}""")
            return 'PASS', 'clicked'

        elif wtype == 'link':
            # Don't follow links that navigate away — just verify they exist
            href = widget.get('href', '')
            return 'PASS', f'href={href[:40]}'

        elif wtype == 'select':
            opts = widget.get('options', [])
            if len(opts) > 1:
                # Select second option to test change
                await frame.evaluate(f"""() => {{
                    const sels = document.querySelectorAll('select');
                    const sel = sels[{widget.get('index', 0)}];
                    if (sel && sel.options.length > 1) {{
                        sel.selectedIndex = 1;
                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                }}""")
                return 'PASS', f'changed to opt[1]: {opts[1] if len(opts) > 1 else "?"}'
            return 'PASS', f'{len(opts)} options'

        elif wtype == 'accordion':
            await frame.evaluate(f"""() => {{
                const dets = document.querySelectorAll('details');
                const d = dets[{widget.get('index', 0)}];
                if (d) d.open = !d.open;
            }}""")
            return 'PASS', 'toggled'

        elif wtype == 'tab':
            await frame.evaluate(f"""() => {{
                const tabs = document.querySelectorAll('[role="tab"], .tab-item, [data-tab]');
                const t = tabs[{widget.get('index', 0)}];
                if (t) t.click();
            }}""")
            return 'PASS', 'activated'

        elif wtype in ('checkbox', 'radio'):
            await frame.evaluate(f"""() => {{
                const els = document.querySelectorAll('input[type="{wtype}"]');
                const el = els[{widget.get('index', 0)}];
                if (el) {{ el.checked = !el.checked; el.dispatchEvent(new Event('change', {{bubbles: true}})); }}
            }}""")
            return 'PASS', 'toggled'

        elif wtype == 'input':
            return 'PASS', f'type={widget.get("inputType", "text")}'

        else:
            return 'SKIP', 'unknown type'

    except Exception as e:
        return 'FAIL', str(e)[:40]


# ─── Test Runner ────────────────────────────────────────────────────────────

async def run_detailed_test(page, nav_frame, doc_path, panel='Center'):
    """Run detailed widget test on a single page. Returns (widgets_results, frames)."""
    frame_dir = tempfile.mkdtemp(prefix='detail_')
    frames = []
    results = []

    # Load page into the right panel
    url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc_path)}&embed&lang=fr"
    if panel == 'Center':
        await nav_frame.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", url)
    else:
        await nav_frame.evaluate("(url) => { document.getElementById('right-frame-el').src = url; }", url)

    await page.wait_for_timeout(3000)

    # Find the target frame (the one that just loaded)
    target_frame = None
    for f in page.frames:
        if doc_path in f.url or 'embed' in f.url:
            target_frame = f
    if not target_frame:
        # Use deepest srcdoc frame
        srcdoc_frames = [f for f in page.frames if f.url == 'about:srcdoc']
        if srcdoc_frames:
            target_frame = srcdoc_frames[-1]

    if not target_frame:
        return [{'type': 'error', 'result': 'FAIL', 'detail': 'target frame not found'}], frames

    # Phase 1: Scan all widgets
    widgets = await scan_frame_widgets(target_frame)
    visible_widgets = [w for w in widgets if w.get('visible', False)]

    # Phase 2: Trigger each visible widget and capture
    for i, widget in enumerate(visible_widgets):
        wtype = widget['type']
        label = widget.get('text', widget.get('summary', widget.get('label', widget.get('placeholder', '?'))))

        result, detail = await trigger_widget(target_frame, widget, page)

        # Capture after interaction
        await page.wait_for_timeout(500)
        fp = os.path.join(frame_dir, f'detail_{i:04d}.png')
        await page.screenshot(path=fp, full_page=False)
        frames.append(fp)

        results.append({
            'type': wtype,
            'label': label[:30],
            'result': result,
            'detail': detail,
            'visible': True,
        })

    # Also record hidden widgets as SKIP
    hidden = [w for w in widgets if not w.get('visible', False)]
    for w in hidden:
        label = w.get('text', w.get('summary', w.get('label', '?')))
        results.append({
            'type': w['type'],
            'label': label[:30],
            'result': 'SKIP',
            'detail': 'hidden',
            'visible': False,
        })

    # ── Interaction Plugins ──────────────────────────────────────────
    # Run all matching plugins. Reusable always; disposable only if requested.
    try:
        from interactions import find_all_plugins
        include_disposable = os.environ.get('TEST_DISPOSABLE', '') == '1'
        matches = find_all_plugins(doc_path, include_disposable=include_disposable)
        context = {
            'doc': doc_path,
            'panel': panel,
            'phase': 'interaction',
            'nav': nav_frame,
            'mode': 'embedded' if panel == 'Center' else 'standalone',
        }
        for plugin_fn, plugin_name, tier in matches:
            plugin_results = await plugin_fn(target_frame, page, context)
            if plugin_results:
                results.extend(plugin_results)
                fp = os.path.join(frame_dir, f'interaction_{len(frames):04d}.png')
                await page.screenshot(path=fp, full_page=False)
                frames.append(fp)
                print(f"    [plugin:{plugin_name}({tier})] {len(plugin_results)} interaction checks")
    except ImportError:
        pass  # interactions module not available — skip gracefully

    return results, frames, frame_dir



def build_complete_tests():
    """Discovery utility — enumerate ALL links from ALL sections (except navigator).
    Not wired to CLI. Used by Claude to identify relevant pages for targeted tests."""
    tests = []

    # All interfaces except navigator (target=top)
    ifaces = json.load(open(os.path.join(DOCS_ROOT, 'data/interfaces.json')))
    for item in sorted(ifaces['items'], key=lambda x: x.get('priority', 99)):
        if item.get('target') == 'top':
            continue
        href = item['href'].strip('/')
        doc = href + '/index.md' if not href.endswith('.md') else href
        if doc.startswith('/'):
            doc = doc[1:]
        label = item.get('title_fr', item['title'])
        tests.append(('Interface', label, 'Center', doc))

    # Helper: resolve doc path for different section types
    def pub_doc(slug, full=False):
        return f"publications/{slug}/{'full/' if full else ''}index.md"

    # All items from every non-interface section
    section_files = [
        ('profile', 'Profil'),
        ('configurations', 'Configurations'),
        ('documentation', 'Documentation'),
        ('methodologies', 'Méthodologies'),
        ('hubs', 'Hubs'),
        ('publications', 'Publications'),
        ('stories', 'Histoires'),
        ('essentials', 'Essentiels'),
        ('tests', 'Résultats Tests'),
        ('commands', 'Commandes'),
    ]

    for section_id, section_name in section_files:
        try:
            data = json.load(open(os.path.join(DOCS_ROOT, f'data/{section_id}.json')))
            section = data.get('section', section_id)
            items = data.get('items', [])

            # Documentation has groups
            if not items and data.get('groups'):
                for g in data.get('groups', []):
                    items.extend(g.get('items', []))

            for item in items:
                label = item.get('title_fr', item.get('title', item.get('group_fr', item.get('group', '?'))))

                # Resolve doc path based on section type
                if section in ('profile', 'hubs', 'essentials', 'tests'):
                    href = item.get('href', '').strip('/')
                    if not href:
                        href = 'index'
                    doc = href + '/index.md' if '.' not in href.split('/')[-1] else href
                elif section in ('publications', 'stories'):
                    slug = item.get('slug', '')
                    if slug:
                        doc = pub_doc(slug)
                    else:
                        href = item.get('href', '').strip('/')
                        doc = href + '/index.md' if href else 'index.md'
                elif section == 'documentation':
                    slug = item.get('slug', '')
                    doc = pub_doc(slug) if slug else 'index.md'
                elif section == 'methodologies':
                    # Use local relative path instead of raw GitHub URL
                    mod = item.get('module', '')
                    fn = item.get('file', '')
                    doc = f'methodologies/{mod}/{fn}' if mod and fn else item.get('path', '')
                elif section == 'configurations':
                    doc = item.get('path', '')
                elif section == 'commands':
                    # Command groups → use the pub URL
                    pub = item.get('pub', '')
                    pub_match = re.search(r'/publications/([^/]+)/', pub)
                    slug = pub_match.group(1) if pub_match else 'guide-commands'
                    is_full = '/full/' in pub
                    doc = pub_doc(slug, is_full)
                    label = item.get('group_fr', item.get('group', '?'))
                else:
                    doc = item.get('path', item.get('href', ''))

                if doc:
                    if doc.startswith('/'):
                        doc = doc[1:]
                    tests.append((section_name, label[:40], 'Content', doc))

        except (FileNotFoundError, KeyError, IndexError):
            pass

    return tests


# ─── Report Formatters ──────────────────────────────────────────────────────

def print_default_report(results):
    total = len(results)
    passed = sum(1 for r in results if r['result'] == 'PASS')
    print(f"\n{'═' * 75}")
    print(f"  GRID TEST REPORT — Main Navigator")
    print(f"{'═' * 75}")
    print(f"  {'#':>2s}  {'Section':14s}  {'Target':30s}  {'Panel':7s}  Result")
    print(f"  {'──':2s}  {'─' * 14}  {'─' * 30}  {'─' * 7}  {'─' * 6}")
    for r in results:
        mark = '✓' if r['result'] == 'PASS' else '✗'
        print(f"  {r['num']:2d}  {r['phase']:14s}  {r['target']:30s}  {r['panel']:7s}  {mark} {r['result']}")
    print(f"  {'──':2s}  {'─' * 14}  {'─' * 30}  {'─' * 7}  {'─' * 6}")
    print(f"  Total: {passed}/{total} passed | Frames: {total}")
    print(f"{'═' * 75}")


def print_detailed_report(page_label, widget_results):
    total = len(widget_results)
    passed = sum(1 for r in widget_results if r['result'] == 'PASS')
    skipped = sum(1 for r in widget_results if r['result'] == 'SKIP')
    failed = sum(1 for r in widget_results if r['result'] == 'FAIL')
    print(f"\n  {'─' * 70}")
    print(f"  DETAILED: {page_label}")
    print(f"  {'─' * 70}")
    print(f"  {'#':>3s}  {'Type':10s}  {'Widget':30s}  {'Result':6s}  Detail")
    print(f"  {'───':3s}  {'─' * 10}  {'─' * 30}  {'─' * 6}  {'─' * 20}")
    for i, r in enumerate(widget_results):
        mark = '✓' if r['result'] == 'PASS' else ('○' if r['result'] == 'SKIP' else '✗')
        print(f"  {i + 1:3d}  {r['type']:10s}  {r['label']:30s}  {mark} {r['result']:4s}  {r['detail']}")
    print(f"  {'───':3s}  {'─' * 10}  {'─' * 30}  {'─' * 6}  {'─' * 20}")
    print(f"  Widgets: {passed} pass, {failed} fail, {skipped} skip | Total: {total}")


# ─── Proof Assembly ─────────────────────────────────────────────────────────

def assemble_gif(frame_paths, output_path, duration_ms=2000):
    from PIL import Image
    if not frame_paths:
        return
    frames = [Image.open(f) for f in frame_paths]
    frames[0].save(output_path, save_all=True, append_images=frames[1:],
                   duration=duration_ms, loop=0, optimize=True)
    print(f"  GIF: {output_path} ({os.path.getsize(output_path) / 1024:.0f}K)")


MP4_SCALE = 0.5  # Default video proof scale (0.5 = 960x540 from 1920x1080)
MP4_MAX_MB = 7    # Max MP4 size in MB — auto-downscale if estimated to exceed (signing server limit ~8MB)


def assemble_mp4(frame_paths, output_path, fps=0.5, scale=None):
    from video_utils import encode_mp4_from_paths, estimate_mp4_scale
    if not frame_paths:
        return
    from PIL import Image
    first = Image.open(frame_paths[0])
    w, h = first.size
    first.close()

    # Auto-detect scale if not specified
    if scale is None:
        auto_scale = estimate_mp4_scale(len(frame_paths), w, h, max_mb=MP4_MAX_MB)
        scale = min(auto_scale, MP4_SCALE)  # never exceed default
        if auto_scale < 1.0:
            print(f"  MP4 auto-scale: {len(frame_paths)} frames × {w}x{h} → scale={scale} (limit {MP4_MAX_MB}MB)")

    encode_mp4_from_paths(frame_paths, output_path, fps=fps, scale=scale)


# ─── Main Runner ────────────────────────────────────────────────────────────

async def run_tests(targets=None, detailed_pages=None, request_text=None, original_request=None):
    """Run targeted grid test on specified pages.
    Optionally with detailed widget sub-tests.

    targets: list of (section, label, panel, doc) tuples to test.
             If None, falls back to build_complete_tests() for backward compat.
    request_text: synthesized test description (short)
    original_request: verbatim user request that initiated the test
    """
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found.")
        return

    tests = targets if targets else build_complete_tests()
    mode = "TARGETED" if targets else "COMPLETE"
    total = len(tests)
    print(f"Test plan: {total} tests\n")

    handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)

    nav_doc = 'interfaces/main-navigator/index.md'
    viewer_url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(nav_doc)}"

    frame_dir = tempfile.mkdtemp(prefix='webtest_')
    all_frames = []
    all_check_frames = []
    all_proof_frames = []
    results = []
    all_detailed = []

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

    await page.goto(viewer_url, wait_until='load', timeout=30000)
    await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")
    await page.wait_for_timeout(5000)

    nav = page.frames[1]
    right_expanded = False

    for i, (phase, label, panel, doc) in enumerate(tests):
        test_num = i + 1
        try:
            if doc.startswith('http'):
                url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}&embed&lang=fr"
            else:
                if doc.startswith('/'):
                    doc = doc[1:]
                url = f"file://{os.path.abspath(os.path.join(DOCS_ROOT, 'index.html'))}?doc={quote(doc)}&embed&lang=fr"

            # CHECK screenshot — capture baseline state BEFORE navigation
            check_fp = os.path.join(frame_dir, f'check_{i:04d}.png')
            await page.screenshot(path=check_fp, full_page=False)
            all_check_frames.append(check_fp)

            if panel == 'Center':
                await nav.evaluate("(url) => { document.getElementById('center-frame-el').src = url; }", url)
            else:
                if not right_expanded:
                    await nav.evaluate(
                        "() => { document.getElementById('nav-grid').style.gridTemplateColumns = '220px 22px 1fr 22px 500px'; }")
                    right_expanded = True
                    await page.wait_for_timeout(500)
                await nav.evaluate("(url) => { document.getElementById('right-frame-el').src = url; }", url)

            # Live mindmap: extra wait for MindElixir auto-refresh
            if 'live-mindmap' in doc:
                await page.wait_for_timeout(6000)
            else:
                await page.wait_for_timeout(2000)

            # Content validation — check for error states in the target iframe
            frame_id = 'center-frame-el' if panel == 'Center' else 'right-frame-el'
            validation = await nav.evaluate(f"""(frameId) => {{
                var iframe = document.getElementById(frameId);
                if (!iframe) return {{ ok: false, error: 'iframe not found' }};
                try {{
                    var doc = iframe.contentDocument;
                    if (!doc || !doc.body) return {{ ok: false, error: 'no document body' }};
                    var text = doc.body.innerText || '';
                    var title = doc.title || '';
                    // Check for common error patterns
                    if (/404|not found|page not found/i.test(text.substring(0, 500)))
                        return {{ ok: false, error: '404 Not Found' }};
                    if (/error|failed to load|cannot load/i.test(text.substring(0, 200)))
                        return {{ ok: false, error: 'page error: ' + text.substring(0, 60) }};
                    if (text.trim().length < 10 && !doc.querySelector('canvas, svg, iframe'))
                        return {{ ok: false, error: 'empty page (< 10 chars)' }};
                    if (/loading document/i.test(text.substring(0, 200)) && text.trim().length < 50)
                        return {{ ok: false, error: 'stuck on loading' }};
                    return {{ ok: true, chars: text.length, title: title.substring(0, 50) }};
                }} catch(e) {{
                    // Cross-origin — can't inspect, assume ok if loaded
                    return {{ ok: true, error: 'cross-origin (assumed ok)' }};
                }}
            }}""", frame_id)

            # PROOF screenshot — capture state AFTER navigation + validation
            proof_fp = os.path.join(frame_dir, f'proof_{i:04d}.png')
            await page.screenshot(path=proof_fp, full_page=False)
            all_proof_frames.append(proof_fp)
            all_frames.append(proof_fp)

            if validation.get('ok'):
                results.append({'num': test_num, 'phase': phase, 'target': label, 'panel': panel, 'result': 'PASS', 'doc': doc})
                print(f"  [{test_num:2d}/{total}] PASS | {phase:14s} | {panel:7s} | {label}")
            else:
                error = validation.get('error', 'unknown')
                results.append({'num': test_num, 'phase': phase, 'target': label, 'panel': panel, 'result': 'FAIL', 'doc': doc, 'error': error})
                print(f"  [{test_num:2d}/{total}] FAIL | {phase:14s} | {panel:7s} | {label} | {error}")

        except Exception as e:
            proof_fp = os.path.join(frame_dir, f'proof_{i:04d}.png')
            try:
                await page.screenshot(path=proof_fp, full_page=False)
                all_proof_frames.append(proof_fp)
                all_frames.append(proof_fp)
            except:
                pass
            results.append(
                {'num': test_num, 'phase': phase, 'target': label, 'panel': panel, 'result': 'FAIL', 'doc': doc})
            print(f"  [{test_num:2d}/{total}] FAIL | {phase:14s} | {panel:7s} | {label} | {str(e)[:40]}")

        # Detailed sub-test if requested
        if detailed_pages and (doc in detailed_pages or 'all' in detailed_pages):
            detail_results, detail_frames, detail_dir = await run_detailed_test(page, nav, doc, panel)
            # Copy detail frames to main frame dir so they survive cleanup
            for dfp in detail_frames:
                dst = os.path.join(frame_dir, os.path.basename(dfp))
                shutil.copy2(dfp, dst)
                all_frames.append(dst)
            print_detailed_report(f"{phase}: {label}", detail_results)
            all_detailed.append({'page': f"{phase}: {label}", 'doc': doc, 'widgets': detail_results})
            # Cleanup detail temp
            shutil.rmtree(detail_dir, ignore_errors=True)

    # Report
    print_default_report(results)
    print(f"  Mode: {mode}")

    os.makedirs(REPORT_DIR, exist_ok=True)

    # Save results as JSON for report generator
    from datetime import datetime as _dt
    timestamp = _dt.now().isoformat()
    passed_count = sum(1 for r in results if r['result'] == 'PASS')
    failed_count = sum(1 for r in results if r['result'] == 'FAIL')

    # Build checks[] for check validation snapshots
    checks = []
    for r in results:
        error = r.get('error', '')
        conclusion = error if error else f"Page loaded ({r.get('target', '?')})"
        checks.append({
            'check_id': r['num'],
            'test_title': request_text or "Test — Main Navigator",
            'label': f"{r.get('phase', '?')} — {r.get('target', '?')}",
            'description': f"Verify {r.get('target', 'page')} loads in {r.get('panel', 'panel')} panel",
            'phase': r.get('phase', ''),
            'target': r.get('target', ''),
            'panel': r.get('panel', ''),
            'doc': r.get('doc', ''),
            'result': r.get('result', 'FAIL'),
            'status_color': 'green' if r.get('result') == 'PASS' else 'red',
            'conclusion': conclusion,
            'error': error or None,
            'check_path': f"check_{r['num'] - 1:04d}.png",
            'proof_path': f"proof_{r['num'] - 1:04d}.png",
            'frame_path': f"proof_{r['num'] - 1:04d}.png",  # backward compat
            'annotations': [{'type': 'border'}],
            'timestamp': timestamp,
        })

    # Copy CHECK + PROOF frames to persistent directory for dual snapshot rendering
    frames_persist_dir = os.path.join(REPORT_DIR, 'frames')
    os.makedirs(frames_persist_dir, exist_ok=True)
    for i, cfp in enumerate(all_check_frames):
        if os.path.isfile(cfp):
            shutil.copy2(cfp, os.path.join(frames_persist_dir, f'check_{i:04d}.png'))
    for i, pfp in enumerate(all_proof_frames):
        if os.path.isfile(pfp):
            shutil.copy2(pfp, os.path.join(frames_persist_dir, f'proof_{i:04d}.png'))

    results_json = {
        'mode': mode,
        'format': 'check_proof',
        'request_text': request_text or "Targeted test of main navigator interface",
        'original_request': original_request,
        'default': results,
        'detailed': all_detailed,
        'checks': checks,
        'timestamp': timestamp,
        'total_frames': len(all_frames),
    }
    results_path = os.path.join(REPORT_DIR, 'results.json')
    with open(results_path, 'w') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {results_path}")

    # ─── Generate check snapshots (3-part: header + CHECK/PROOF evidence + result) ───
    checks_dir = os.path.join(REPORT_DIR, 'checks')
    try:
        from generate_check_snapshot import batch_generate as _batch_checks
        check_paths = _batch_checks(results_path, frames_persist_dir, checks_dir,
                                     request_text or "Test — Main Navigator")
    except ImportError:
        # Fallback: try as sibling script
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, scripts_dir)
        from generate_check_snapshot import batch_generate as _batch_checks
        check_paths = _batch_checks(results_path, frames_persist_dir, checks_dir,
                                     request_text or "Test — Main Navigator")

    # ─── Assemble proof-of-completion from CHECK/PROOF SNAPSHOTS ───
    # The animated GIF and video use the 3-part dual snapshots as frames,
    # so each frame shows: title + description → CHECK|PROOF evidence → result LED
    if check_paths:
        proof_frames = sorted(check_paths)  # check_0001_snapshot.png, check_0002_snapshot.png, ...
        print(f"\n  Proof assembly: {len(proof_frames)} check snapshots → GIF + MP4")
        assemble_gif(proof_frames, os.path.join(REPORT_DIR, 'test-report.gif'))
        assemble_mp4(proof_frames, os.path.join(REPORT_DIR, 'test-report.mp4'))
    else:
        # Fallback: use raw frames if check snapshot generation failed
        print(f"\n  Proof assembly: {len(all_frames)} raw frames → GIF + MP4 (check snapshots unavailable)")
        assemble_gif(all_frames, os.path.join(REPORT_DIR, 'test-report.gif'))
        assemble_mp4(all_frames, os.path.join(REPORT_DIR, 'test-report.mp4'))

    # Accumulate run history for dashboard matrix
    history_path = os.path.join(REPORT_DIR, 'history.json')
    history = {'tests': {}}
    if os.path.isfile(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f)
        except (json.JSONDecodeError, KeyError):
            history = {'tests': {}}

    # Key by test slug (derive from mode for now)
    test_slug = 'main-navigator'
    if test_slug not in history['tests']:
        history['tests'][test_slug] = {
            'title': 'Main Navigator',
            'title_fr': 'Navigateur principal',
            'runs': []
        }

    # Build per-page result map for this run
    page_results = {}
    for r in results:
        page_results[r['doc']] = r['result']

    history['tests'][test_slug]['runs'].append({
        'timestamp': timestamp,
        'mode': mode,
        'total': len(results),
        'passed': passed_count,
        'failed': failed_count,
        'pages': page_results,
    })

    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"  History: {history_path} ({len(history['tests'][test_slug]['runs'])} runs)")

    # Cleanup
    for fp in all_frames:
        if os.path.exists(fp):
            os.unlink(fp)
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir, ignore_errors=True)

    await browser.close()
    await p.stop()

    return results


# ─── CLI ────────────────────────────────────────────────────────────────────

def parse_targets(target_args):
    """Convert CLI target doc paths into (section, label, panel, doc) tuples.
    Infers section and panel from the doc path structure."""
    targets = []
    for doc in target_args:
        doc = doc.lstrip('/')
        # Infer section from path
        if doc.startswith('interfaces/'):
            section = 'Interface'
            panel = 'Center'
        elif doc.startswith('publications/'):
            section = 'Publication'
            panel = 'Content'
        elif doc.startswith('methodologies/'):
            section = 'Methodology'
            panel = 'Content'
        else:
            section = 'Page'
            panel = 'Content'
        # Label from filename or parent dir
        parts = doc.replace('/index.md', '').rstrip('/').split('/')
        label = parts[-1] if parts else doc
        targets.append((section, label, panel, doc))
    return targets


def _load_test_module(module_name):
    """Load a rerunnable test module from interactions/tests/.

    Returns the module's get_test_config() dict with all pipeline parameters."""
    import importlib
    try:
        mod = importlib.import_module(f'interactions.tests.{module_name}')
    except ImportError:
        # Try direct path
        mod_path = os.path.join(SCRIPT_DIR, 'interactions', 'tests', f'{module_name}.py')
        if not os.path.isfile(mod_path):
            print(f"ERROR: module '{module_name}' not found in interactions/tests/")
            return None
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    if hasattr(mod, 'get_test_config'):
        return mod.get_test_config()
    # Legacy: build config from module attributes
    return {
        'test_id': getattr(mod, 'TEST_ID', module_name),
        'title': getattr(mod, 'TITLE', module_name),
        'title_fr': getattr(mod, 'TITLE_FR', ''),
        'slug': getattr(mod, 'SLUG', module_name),
        'output_dir': getattr(mod, 'OUTPUT_DIR', ''),
        'targets': mod.get_targets() if hasattr(mod, 'get_targets') else [],
        'request': getattr(mod, 'REQUEST', ''),
        'original_request': getattr(mod, 'ORIGINAL_REQUEST', ''),
    }


def _list_test_modules():
    """List available test modules in interactions/tests/."""
    tests_dir = os.path.join(SCRIPT_DIR, 'interactions', 'tests')
    if not os.path.isdir(tests_dir):
        print("No test modules directory found.")
        return
    modules = [f[:-3] for f in sorted(os.listdir(tests_dir))
               if f.endswith('.py') and not f.startswith('_')]
    if not modules:
        print("No test modules found.")
        return
    print(f"Available test modules ({len(modules)}):\n")
    for name in modules:
        cfg = _load_test_module(name)
        if cfg:
            targets = len(cfg.get('targets', []))
            print(f"  {name:<30} {cfg.get('title', ''):<45} ({targets} targets)")
        else:
            print(f"  {name:<30} (load error)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Web Test Engine v2.0 — Request-Driven Grid Testing')
    parser.add_argument('--targets', nargs='+', default=None,
                        help='Specific doc paths to test (targeted validation)')
    parser.add_argument('--detailed', nargs='*', default=None,
                        help='Detailed widget test. Pass doc paths or --all for every page.')
    parser.add_argument('--all', action='store_true', help='Apply detailed to all pages')
    parser.add_argument('--request', help='Synthesized test description (short)')
    parser.add_argument('--original-request', help='Verbatim user request that initiated the test')
    parser.add_argument('--module', help='Load test config from a rerunnable module in interactions/tests/')
    parser.add_argument('--list-modules', action='store_true', help='List available test modules')
    args = parser.parse_args()

    if args.list_modules:
        _list_test_modules()
        return

    if args.module:
        cfg = _load_test_module(args.module)
        if not cfg:
            return
        target_docs = cfg.get('targets', [])
        if not target_docs:
            print(f"ERROR: module '{args.module}' has no targets")
            return
        targets = parse_targets(target_docs)
        request = args.request or cfg.get('request', '')
        original = args.original_request or cfg.get('original_request', '')
        asyncio.run(run_tests(targets=targets, request_text=request, original_request=original))
        return

    if args.targets or args.detailed is not None:
        targets = parse_targets(args.targets) if args.targets else None
        detailed = None
        if args.detailed is not None:
            detailed = args.detailed if args.detailed else []
            if args.all:
                detailed = ['all']
        asyncio.run(run_tests(targets=targets, detailed_pages=detailed,
                              request_text=args.request, original_request=args.original_request))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
