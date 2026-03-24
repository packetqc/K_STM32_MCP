#!/usr/bin/env python3
"""
Interaction Test Driver — MP4-First Proof of Completion
========================================================

Records actual page interaction as MP4 video (the master proof),
extracts screenshots at key interaction points (before/after states),
and composes GIF check frames from those screenshots + metadata.

Workflow:
  1. RECORD: Playwright records video while interacting with the page
  2. INTERACT: Navigate, click, wait — actual demonstration
  3. EXTRACT: Screenshots captured at key moments during interaction
  4. MP4: The recording IS the proof of completion
  5. GIF: Composed from extracted screenshots + test metadata

Usage:
    # Run a test interaction and produce proof artifacts
    python3 scripts/interaction_test_driver.py \\
        --test-plan test-plans/expand-collapse.json \\
        --output-dir docs/publications/test-live-mindmap-expand/assets/

    # Or with inline test definition
    python3 scripts/interaction_test_driver.py \\
        --page interfaces/live-mindmap/index.md \\
        --title "Live Mindmap — Expand/Collapse Bug Fix" \\
        --steps '[{"action":"click","target":"architecture","capture":"before"},...]' \\
        --output-dir /tmp/test-output/

Knowledge asset — part of the interaction-driven test methodology.
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time

from playwright.async_api import async_playwright

# Add K_TOOLS scripts to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from render_web_page import find_chrome

# ─── Constants ────────────────────────────────────────────────────────────────

NPM_DIR = '/tmp/mermaid-local-test'
VIEWPORT = {"width": 1500, "height": 820}

CDN_FILES = {
    'MindElixir.css': ('mind-elixir/dist/MindElixir.css', 'text/css'),
    'MindElixir.iife': ('mind-elixir/dist/MindElixir.iife.js', 'application/javascript'),
    'marked': ('marked/lib/marked.umd.js', 'application/javascript'),
    'mermaid': ('mermaid/dist/mermaid.min.js', 'application/javascript'),
}

# ─── Route Handlers ───────────────────────────────────────────────────────────


def _build_cdn_handler():
    """Build CDN route handler that serves from local npm packages."""
    async def handle_cdn(route):
        url = route.request.url
        for key, (rel_path, ct) in CDN_FILES.items():
            if key in url:
                local = os.path.join(NPM_DIR, 'node_modules', rel_path)
                if os.path.isfile(local):
                    with open(local, 'r') as f:
                        body = f.read()
                    await route.fulfill(body=body, content_type=ct)
                    return
        await route.abort()
    return handle_cdn


def _build_raw_handler(docs_root):
    """Build GitHub raw handler that serves from local filesystem."""
    k_mind = os.path.join(docs_root, '..', 'Knowledge', 'K_MIND')
    file_map = {
        'mind_memory.md': os.path.join(k_mind, 'mind', 'mind_memory.md'),
        'depth_config.json': os.path.join(k_mind, 'conventions', 'depth_config.json'),
        'architecture.json': os.path.join(k_mind, 'architecture', 'architecture.json'),
    }

    async def handle_raw(route):
        url = route.request.url
        for key, local in file_map.items():
            if key in url and os.path.isfile(local):
                with open(local, 'r') as f:
                    body = f.read()
                ct = 'application/json' if local.endswith('.json') else 'text/plain'
                await route.fulfill(body=body, content_type=ct)
                return
        await route.abort()
    return handle_raw


# ─── Mindmap Frame Helpers ────────────────────────────────────────────────────


async def find_mind_frame(page):
    """Find the iframe frame containing window.mindInstance."""
    for f in page.frames:
        try:
            if await f.evaluate('() => !!window.mindInstance'):
                return f
        except:
            pass
    return None


async def find_expand_button(mind_frame, node_name):
    """Find the expand button index for a named node."""
    return await mind_frame.evaluate(f'''() => {{
        var epds = document.querySelectorAll('me-epd');
        for (var i = 0; i < epds.length; i++) {{
            var prev = epds[i].previousSibling;
            if (prev && prev.textContent.trim() === '{node_name}') return i;
        }}
        return -1;
    }}''')


async def click_expand(mind_frame, node_name):
    """Click the expand button for a named node."""
    idx = await find_expand_button(mind_frame, node_name)
    if idx >= 0:
        await mind_frame.evaluate(
            f'() => document.querySelectorAll("me-epd")[{idx}].click()')
        return True
    return False


async def expand_all(mind_frame, node_name):
    """Simulate the old broken behavior: expandNodeAll."""
    idx = await find_expand_button(mind_frame, node_name)
    if idx >= 0:
        await mind_frame.evaluate(f'''() => {{
            var epd = document.querySelectorAll('me-epd')[{idx}];
            var tpc = epd.previousSibling;
            if (tpc && tpc.nodeObj) window.mindInstance.expandNodeAll(tpc);
        }}''')
        return True
    return False


async def fit_and_center(mind_frame, page):
    """Refresh layout, fit to view, center."""
    await mind_frame.evaluate('() => window.mindInstance.refresh()')
    await page.wait_for_timeout(300)
    await mind_frame.evaluate('() => window.mindInstance.scaleFit()')
    await page.wait_for_timeout(300)
    await mind_frame.evaluate('() => window.mindInstance.toCenter()')
    await page.wait_for_timeout(500)


# ─── Main Driver ──────────────────────────────────────────────────────────────


async def run_interaction_test(docs_root, page_path, title, steps, output_dir,
                               direct_page=None, **kwargs):
    """
    Run an interaction test with MP4 recording and screenshot extraction.

    Args:
        docs_root: Path to docs/ directory
        page_path: Doc path relative to docs/ (e.g. interfaces/live-mindmap/index.md)
        title: Test title
        steps: List of interaction steps, each with:
            - action: 'wait', 'click_expand', 'expand_all', 'fit', 'capture',
                      'click_selector', 'evaluate_js', 'assert_js'
            - target: node name (for click/expand) or CSS selector (for click_selector)
            - selector: CSS selector (for click_selector, overrides target)
            - js: JavaScript expression (for evaluate_js, assert_js)
            - capture_as: screenshot label (for capture action)
            - wait_ms: milliseconds to wait
            - description: human-readable step description
        output_dir: Directory for output artifacts
        direct_page: If set, load this file directly instead of through the viewer.
                     Path relative to docs_root (e.g. publications/test-slug/index.md).

    Returns:
        dict with paths to artifacts and test results
    """
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found")
        return None

    os.makedirs(output_dir, exist_ok=True)

    from urllib.parse import quote
    if direct_page:
        abs_direct = os.path.abspath(os.path.join(docs_root, direct_page))
        viewer_url = f"file://{abs_direct}"
    else:
        abs_index = os.path.abspath(os.path.join(docs_root, 'index.html'))
        viewer_url = f"file://{abs_index}?doc={quote(page_path)}"

    # Video recording directory
    video_dir = tempfile.mkdtemp(prefix='interaction_video_')

    screenshots = {}  # capture_as -> path
    results = {
        'title': title,
        'page': page_path,
        'steps': [],
        'artifacts': {},
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chrome,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                  '--allow-file-access-from-files']
        )

        # Create context WITH video recording — MP4 is the master
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=video_dir,
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()

        # Route handlers
        await page.route('**cdn.jsdelivr.net**', _build_cdn_handler())
        await page.route('**raw.githubusercontent.com**', _build_raw_handler(docs_root))

        # Navigate
        print(f"  navigating: {page_path}")
        await page.goto(viewer_url, wait_until='load', timeout=30000)
        await page.evaluate(
            '() => { var o = document.querySelector(".fs-prompt-overlay"); if (o) o.remove(); }')

        # Wait for page to fully render
        if direct_page:
            await page.wait_for_timeout(2000)
            mind_frame = None
        else:
            await page.wait_for_timeout(10000)
            mind_frame = await find_mind_frame(page)
            if mind_frame:
                print("  mindmap frame found")

        # ═══ Pre-check validation ═══
        # Validates page infrastructure before running steps.
        # If any pre-check fails, all checks are marked FAIL and test aborts.
        pre_checks = kwargs.get('pre_checks', [])
        pre_check_results = []
        pre_check_passed = True

        if pre_checks:
            print("  ── pre-checks ──")
            for pc in pre_checks:
                pc_type = pc.get('type', 'selector_exists')
                pc_desc = pc.get('description', pc_type)
                pc_result = {'type': pc_type, 'description': pc_desc, 'status': 'ok'}

                try:
                    if pc_type == 'selector_exists':
                        sel = pc['selector']
                        count = await page.locator(sel).count()
                        expected = pc.get('min_count', 1)
                        pc_result['found'] = count
                        pc_result['expected'] = expected
                        if count < expected:
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'Expected >= {expected} elements for "{sel}", found {count}'

                    elif pc_type == 'selector_count':
                        sel = pc['selector']
                        count = await page.locator(sel).count()
                        expected = pc['count']
                        pc_result['found'] = count
                        pc_result['expected'] = expected
                        if count != expected:
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'Expected {expected} elements for "{sel}", found {count}'

                    elif pc_type == 'assert_js':
                        js = pc['js']
                        val = await page.evaluate(js)
                        pc_result['js_result'] = val
                        if not val:
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'JS assertion returned falsy'

                    elif pc_type == 'listener_bound':
                        sel = pc['selector']
                        event_type = pc.get('event', 'click')
                        val = await page.evaluate(f'''() => {{
                            var el = document.querySelector('{sel}');
                            if (!el) return {{ found: false }};
                            var bound = false;
                            var handler = function(e) {{ bound = true; e.stopPropagation(); }};
                            el.addEventListener('{event_type}', handler, true);
                            el.dispatchEvent(new Event('{event_type}', {{bubbles: true}}));
                            el.removeEventListener('{event_type}', handler, true);
                            return {{ found: true, listeners_active: bound }};
                        }}''')
                        pc_result['detail'] = val
                        # Can't reliably detect other listeners this way,
                        # use assert_js with specific logic instead
                        if not val or not val.get('found'):
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'Element "{sel}" not found'

                    elif pc_type == 'visual_match':
                        sel = pc['selector']
                        prop = pc.get('css_property', 'display')
                        expected_val = pc.get('expected_value', '')
                        val = await page.evaluate(f'''() => {{
                            var el = document.querySelector('{sel}');
                            if (!el) return null;
                            return getComputedStyle(el)['{prop}'];
                        }}''')
                        pc_result['computed'] = val
                        pc_result['expected'] = expected_val
                        if val is None:
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'Element "{sel}" not found'
                        elif expected_val and val != expected_val:
                            pc_result['status'] = 'fail'
                            pc_result['error'] = f'CSS {prop}: expected "{expected_val}", got "{val}"'

                except Exception as e:
                    pc_result['status'] = 'error'
                    pc_result['error'] = str(e)

                mark = '✓' if pc_result['status'] == 'ok' else '✗'
                print(f"    {mark} {pc_desc}")
                if pc_result['status'] != 'ok':
                    print(f"      {pc_result.get('error', '')}")
                    pre_check_passed = False

                pre_check_results.append(pc_result)

            if not pre_check_passed:
                print("  ── pre-checks FAILED — aborting test ──")
                # Capture failure screenshot
                fail_path = os.path.join(output_dir, 'pre-check-fail.png')
                await page.screenshot(path=fail_path)
                screenshots['pre-check-fail'] = fail_path

                # Mark all captures (checks) as FAIL
                for step in steps:
                    if step.get('action') == 'capture':
                        step_result = {
                            'step': len(results['steps']) + 1,
                            'action': 'capture',
                            'description': step.get('description', ''),
                            'status': 'fail',
                            'error': 'Pre-check validation failed — page infrastructure missing',
                            'video_ts': 0,
                        }
                        results['steps'].append(step_result)

                results['pre_checks'] = pre_check_results
                results['artifacts']['screenshots'] = screenshots

                video_tmp = await page.video.path()
                await context.close()
                mp4_path = os.path.join(output_dir, 'proof.mp4')
                if os.path.isfile(video_tmp):
                    import shutil
                    shutil.move(video_tmp, mp4_path)
                results['artifacts']['mp4'] = mp4_path
                results_path = os.path.join(output_dir, 'interaction_results.json')
                with open(results_path, 'w') as f:
                    json.dump(results, f, indent=2)
                results['artifacts']['results'] = results_path
                await browser.close()
                return results

            print("  ── pre-checks OK ──")
            results['pre_checks'] = pre_check_results

        # Video recording starts when context is created — track elapsed time
        recording_start = time.monotonic()

        # Execute interaction steps
        for i, step in enumerate(steps):
            action = step.get('action', 'wait')
            target = step.get('target', '')
            capture_as = step.get('capture_as', '')
            wait_ms = step.get('wait_ms', 500)
            desc = step.get('description', f'Step {i+1}: {action}')

            # Record video timestamp at step start
            video_ts = round(time.monotonic() - recording_start, 2)

            print(f"  [{i+1}/{len(steps)}] {desc}  @{video_ts}s")

            step_result = {'step': i + 1, 'action': action, 'description': desc,
                          'status': 'ok', 'video_ts': video_ts}

            try:
                if action == 'wait':
                    await page.wait_for_timeout(wait_ms)

                elif action == 'click_selector':
                    sel = step.get('selector', target)
                    await page.click(sel, timeout=5000)
                    await page.wait_for_timeout(wait_ms)
                    step_result['target'] = sel

                elif action == 'evaluate_js':
                    js = step.get('js', '')
                    result_val = await page.evaluate(js)
                    step_result['js_result'] = result_val
                    await page.wait_for_timeout(wait_ms)

                elif action == 'assert_js':
                    js = step.get('js', '')
                    result_val = await page.evaluate(js)
                    step_result['js_result'] = result_val
                    if not result_val:
                        step_result['status'] = 'fail'
                        step_result['error'] = f'Assertion failed: {js}'

                elif action == 'click_expand' and mind_frame:
                    ok = await click_expand(mind_frame, target)
                    await page.wait_for_timeout(wait_ms)
                    step_result['target'] = target
                    step_result['status'] = 'ok' if ok else 'target_not_found'

                elif action == 'expand_all' and mind_frame:
                    ok = await expand_all(mind_frame, target)
                    await page.wait_for_timeout(wait_ms)
                    step_result['target'] = target
                    step_result['status'] = 'ok' if ok else 'target_not_found'

                elif action == 'fit' and mind_frame:
                    await fit_and_center(mind_frame, page)

                elif action == 'capture':
                    screenshot_path = os.path.join(output_dir, f'{capture_as}.png')
                    await page.screenshot(path=screenshot_path)
                    screenshots[capture_as] = screenshot_path
                    step_result['screenshot'] = screenshot_path

                elif action == 'collapse' and mind_frame:
                    ok = await click_expand(mind_frame, target)
                    await page.wait_for_timeout(wait_ms)
                    step_result['target'] = target

                elif action == 'reload':
                    await mind_frame.evaluate('() => window.loadMindmap()')
                    await page.wait_for_timeout(wait_ms)

            except Exception as e:
                step_result['status'] = 'error'
                step_result['error'] = str(e)
                print(f"    ERROR: {e}")

            results['steps'].append(step_result)

        # Close context to finalize video recording
        video_path_tmp = await page.video.path()
        await context.close()
        await browser.close()

    # Move video to output directory
    mp4_path = os.path.join(output_dir, 'proof.mp4')
    if os.path.isfile(video_path_tmp):
        import shutil
        shutil.move(video_path_tmp, mp4_path)
        results['artifacts']['mp4'] = mp4_path
        print(f"  MP4 proof: {mp4_path}")

    # Clean up temp video dir
    try:
        os.rmdir(video_dir)
    except:
        pass

    results['artifacts']['screenshots'] = screenshots

    # Save results
    results_path = os.path.join(output_dir, 'interaction_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    results['artifacts']['results'] = results_path

    return results


# ─── Multi-Part Recording ─────────────────────────────────────────────────────


async def run_multipart_test(docs_root, page_path, title, parts, output_dir):
    """
    Run a multi-part interaction test. Each part gets its own browser session
    and video recording. Parts are stitched into one proof.mp4 via ffmpeg.

    Args:
        docs_root: Path to docs/ directory
        page_path: Doc path relative to docs/
        title: Test title
        parts: List of part dicts, each with:
            - label: Part label (e.g. "BEFORE — Bug", "AFTER — Fix")
            - steps: List of interaction steps (same format as single-part)
        output_dir: Directory for output artifacts

    Returns:
        dict with paths to artifacts and combined test results
    """
    os.makedirs(output_dir, exist_ok=True)

    part_videos = []
    all_screenshots = {}
    all_steps = []

    for pi, part in enumerate(parts):
        part_label = part.get('label', f'Part {pi + 1}')
        part_steps = part.get('steps', [])
        part_dir = os.path.join(output_dir, f'part-{pi + 1}')

        print(f"\n  ══ {part_label} ══")

        result = await run_interaction_test(
            docs_root, page_path, f"{title} — {part_label}",
            part_steps, part_dir)

        if not result:
            print(f"  ERROR: Part {pi + 1} failed")
            continue

        # Collect artifacts
        mp4 = result['artifacts'].get('mp4')
        if mp4 and os.path.isfile(mp4):
            part_videos.append(mp4)

        for k, v in result['artifacts'].get('screenshots', {}).items():
            all_screenshots[k] = v

        for step in result.get('steps', []):
            step['part'] = pi + 1
            step['part_label'] = part_label
            all_steps.append(step)

    # Stitch videos with ffmpeg
    combined_mp4 = os.path.join(output_dir, 'proof.mp4')
    if len(part_videos) > 1:
        import subprocess
        concat_file = os.path.join(output_dir, '_concat.txt')
        with open(concat_file, 'w') as f:
            for v in part_videos:
                f.write(f"file '{os.path.abspath(v)}'\n")

        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
               '-i', concat_file, '-c', 'copy', combined_mp4]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"\n  Stitched {len(part_videos)} parts → {combined_mp4}")
        else:
            # Fallback: re-encode if codec mismatch
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                   '-i', concat_file,
                   '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                   combined_mp4]
            subprocess.run(cmd, capture_output=True, text=True)
            print(f"\n  Stitched (re-encoded) {len(part_videos)} parts → {combined_mp4}")
        os.unlink(concat_file)
    elif len(part_videos) == 1:
        import shutil
        shutil.copy2(part_videos[0], combined_mp4)

    # Build combined results
    results = {
        'title': title,
        'page': page_path,
        'parts': len(parts),
        'steps': all_steps,
        'artifacts': {
            'mp4': combined_mp4 if os.path.isfile(combined_mp4) else None,
            'part_videos': part_videos,
            'screenshots': all_screenshots,
        },
    }

    results_path = os.path.join(output_dir, 'interaction_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    results['artifacts']['results'] = results_path

    return results


# ─── Side-by-Side Recording ───────────────────────────────────────────────────


async def _run_single_session(browser, docs_root, page_path, label, steps, output_dir,
                               page_override=None):
    """Run one interaction session (one side of side-by-side). Returns (mp4_path, screenshots, step_results).

    page_override: if set, swap this file in place of the real page source before
    loading, then restore after. Used for bug/fix tests where each side needs different code.
    """
    from urllib.parse import quote
    os.makedirs(output_dir, exist_ok=True)
    abs_index = os.path.abspath(os.path.join(docs_root, 'index.html'))
    viewer_url = f"file://{abs_index}?doc={quote(page_path)}"

    video_dir = tempfile.mkdtemp(prefix=f'sbs_video_{label}_')
    screenshots = {}
    step_results = []

    # If page_override, temporarily swap the file on disk
    real_page = os.path.join(docs_root, page_path)
    backup_page = None
    if page_override and os.path.isfile(page_override):
        import shutil
        backup_page = real_page + '.sbs-backup'
        shutil.copy2(real_page, backup_page)
        shutil.copy2(page_override, real_page)

    context = await browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=video_dir,
        record_video_size=VIEWPORT,
    )
    page = await context.new_page()
    await page.route('**cdn.jsdelivr.net**', _build_cdn_handler())
    await page.route('**raw.githubusercontent.com**', _build_raw_handler(docs_root))

    await page.goto(viewer_url, wait_until='load', timeout=30000)
    await page.evaluate(
        '() => { var o = document.querySelector(".fs-prompt-overlay"); if (o) o.remove(); }')
    await page.wait_for_timeout(8000)

    mind_frame = await find_mind_frame(page)
    recording_start = time.monotonic()

    for i, step in enumerate(steps):
        action = step.get('action', 'wait')
        target = step.get('target', '')
        capture_as = step.get('capture_as', '')
        wait_ms = step.get('wait_ms', 500)
        desc = step.get('description', f'Step {i+1}: {action}')

        video_ts = round(time.monotonic() - recording_start, 2)
        sr = {'step': i + 1, 'action': action, 'description': desc, 'status': 'ok',
              'part_label': label, 'video_ts': video_ts}
        try:
            if action == 'wait':
                await page.wait_for_timeout(wait_ms)
            elif action == 'click_selector':
                sel = step.get('selector', target)
                await page.click(sel, timeout=5000)
                await page.wait_for_timeout(wait_ms)
                sr['target'] = sel
            elif action == 'evaluate_js':
                js = step.get('js', '')
                result_val = await page.evaluate(js)
                sr['js_result'] = result_val
                await page.wait_for_timeout(wait_ms)
            elif action == 'assert_js':
                js = step.get('js', '')
                result_val = await page.evaluate(js)
                sr['js_result'] = result_val
                if not result_val:
                    sr['status'] = 'fail'
                    sr['error'] = f'Assertion failed: {js}'
            elif action == 'click_expand' and mind_frame:
                ok = await click_expand(mind_frame, target)
                await page.wait_for_timeout(wait_ms)
                sr['target'] = target
                sr['status'] = 'ok' if ok else 'target_not_found'
            elif action == 'expand_all' and mind_frame:
                ok = await expand_all(mind_frame, target)
                await page.wait_for_timeout(wait_ms)
                sr['target'] = target
                sr['status'] = 'ok' if ok else 'target_not_found'
            elif action == 'fit' and mind_frame:
                await fit_and_center(mind_frame, page)
            elif action == 'capture':
                spath = os.path.join(output_dir, f'{capture_as}.png')
                await page.screenshot(path=spath)
                screenshots[capture_as] = spath
                sr['screenshot'] = spath
            elif action == 'collapse' and mind_frame:
                await click_expand(mind_frame, target)
                await page.wait_for_timeout(wait_ms)
            elif action == 'reload' and mind_frame:
                await mind_frame.evaluate('() => window.loadMindmap()')
                await page.wait_for_timeout(wait_ms)
        except Exception as e:
            sr['status'] = 'error'
            sr['error'] = str(e)
        step_results.append(sr)

    video_tmp = await page.video.path()
    await context.close()

    # Restore original file if we swapped it
    if backup_page and os.path.isfile(backup_page):
        import shutil as _shutil
        _shutil.move(backup_page, real_page)

    mp4_path = os.path.join(output_dir, 'proof.mp4')
    if os.path.isfile(video_tmp):
        import shutil
        shutil.move(video_tmp, mp4_path)
    try:
        os.rmdir(video_dir)
    except:
        pass

    return mp4_path, screenshots, step_results


async def run_sidebyside_test(docs_root, page_path, title, parts, output_dir):
    """
    Run two interaction parts sequentially, then stitch videos side-by-side
    (hstack) via ffmpeg. Each part can optionally override the page source
    via 'page_override' — enabling bug/fix tests with different code versions.

    parts[0] = left side (e.g. BEFORE/Bug), parts[1] = right side (e.g. AFTER/Fix)
    Both should have matching steps for synchronized visual comparison.
    """
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found")
        return None

    os.makedirs(output_dir, exist_ok=True)

    if len(parts) != 2:
        print("ERROR: Side-by-side requires exactly 2 parts")
        return None

    left = parts[0]
    right = parts[1]
    left_label = left.get('label', 'LEFT')
    right_label = right.get('label', 'RIGHT')
    left_dir = os.path.join(output_dir, 'part-1')
    right_dir = os.path.join(output_dir, 'part-2')

    print(f"\n  ══ Side-by-Side Recording ══")
    print(f"  LEFT:  {left_label}")
    print(f"  RIGHT: {right_label}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chrome,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                  '--allow-file-access-from-files']
        )

        # Run sequentially (page_override swaps file on disk)
        print(f"\n  Recording LEFT: {left_label}")
        left_mp4, left_ss, left_steps = await _run_single_session(
            browser, docs_root, page_path, left_label,
            left.get('steps', []), left_dir,
            page_override=left.get('page_override'))

        print(f"\n  Recording RIGHT: {right_label}")
        right_mp4, right_ss, right_steps = await _run_single_session(
            browser, docs_root, page_path, right_label,
            right.get('steps', []), right_dir,
            page_override=right.get('page_override'))

        await browser.close()

    # Combine screenshots
    all_screenshots = {}
    for k, v in left_ss.items():
        all_screenshots[k] = v
    for k, v in right_ss.items():
        all_screenshots[k] = v

    import subprocess

    # 1. Concatenate part videos → proof.mp4 (full sequential interaction demo)
    proof_mp4 = os.path.join(output_dir, 'proof.mp4')
    if os.path.isfile(left_mp4) and os.path.isfile(right_mp4):
        concat_file = os.path.join(output_dir, '_concat.txt')
        with open(concat_file, 'w') as f:
            f.write(f"file '{os.path.abspath(left_mp4)}'\n")
            f.write(f"file '{os.path.abspath(right_mp4)}'\n")
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
               '-i', concat_file, '-c:v', 'libx264', '-preset', 'fast',
               '-crf', '23', proof_mp4]
        subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(concat_file)
        print(f"\n  proof.mp4 (sequential): {proof_mp4}")

    # 2. Side-by-side hstack → proof-sidebyside.mp4
    sbs_mp4 = os.path.join(output_dir, 'proof-sidebyside.mp4')
    if os.path.isfile(left_mp4) and os.path.isfile(right_mp4):
        cmd = [
            'ffmpeg', '-y',
            '-i', left_mp4,
            '-i', right_mp4,
            '-filter_complex',
            '[0:v]pad=iw+10:ih:0:0:color=white[left];[left][1:v]hstack=inputs=2',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            sbs_mp4
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"  proof-sidebyside.mp4: {sbs_mp4}")
        else:
            print(f"  hstack error: {proc.stderr[:200]}")

    # 3. Animated GIF from side-by-side MP4 (skip page load, keep interaction)
    proof_gif = os.path.join(output_dir, 'proof.gif')
    if os.path.isfile(sbs_mp4):
        cmd = [
            'ffmpeg', '-y',
            '-ss', '9',  # skip page load (8s wait + 1s settle)
            '-i', sbs_mp4,
            '-vf', 'fps=5,scale=960:-1:flags=lanczos',
            '-loop', '0',
            proof_gif
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            gif_size = os.path.getsize(proof_gif) // 1024
            print(f"  proof.gif (animated): {proof_gif} ({gif_size}K)")
        else:
            print(f"  GIF error: {proc.stderr[:200]}")

    # Clean up intermediate side-by-side MP4 (only needed for GIF generation)
    if os.path.isfile(sbs_mp4) and os.path.isfile(proof_gif):
        os.unlink(sbs_mp4)

    # Offset Part 2 timestamps by Part 1 duration for sequential video seeking
    left_duration = 0
    if os.path.isfile(left_mp4):
        try:
            probe = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', left_mp4],
                capture_output=True, text=True)
            left_duration = float(probe.stdout.strip())
        except (ValueError, AttributeError):
            pass

    all_steps = []
    for s in left_steps:
        s['part'] = 1
        all_steps.append(s)
    for s in right_steps:
        s['part'] = 2
        if 'video_ts' in s:
            s['video_ts'] = round(s['video_ts'] + left_duration, 2)
        all_steps.append(s)

    results = {
        'title': title,
        'page': page_path,
        'parts': 2,
        'mode': 'sidebyside',
        'steps': all_steps,
        'artifacts': {
            'mp4': proof_mp4 if os.path.isfile(proof_mp4) else None,
            'gif': proof_gif if os.path.isfile(proof_gif) else None,
            'part_videos': [left_mp4, right_mp4],
            'screenshots': all_screenshots,
        },
    }

    results_path = os.path.join(output_dir, 'interaction_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    results['artifacts']['results'] = results_path

    return results


# ─── GIF Composition ──────────────────────────────────────────────────────────


def compose_proof_gif(screenshots, title, subtitle, description, conclusion,
                      output_path, before_key='before', after_key='after'):
    """
    Compose a proof-of-completion GIF from extracted screenshots + metadata.

    Uses generate_check_snapshot.compose_proof_of_completion for the one-page format:
    Header → Before/After screenshots → Footer

    Args:
        screenshots: dict of capture_as -> path
        title, subtitle, description, conclusion: metadata
        output_path: GIF output path
        before_key, after_key: keys in screenshots dict
    """
    from generate_check_snapshot import compose_proof_of_completion
    from PIL import Image

    before_path = screenshots.get(before_key)
    after_path = screenshots.get(after_key)

    if not before_path or not after_path:
        print(f"  ERROR: Missing screenshots for GIF (need '{before_key}' and '{after_key}')")
        return None

    # Generate the one-page check image
    check_img = compose_proof_of_completion(
        before_path, after_path,
        test_title=title,
        check_subtitle=subtitle,
        description=description,
        conclusion=conclusion,
    )

    # Save as GIF (single frame — the check is the proof)
    check_img.save(output_path, format='GIF')
    print(f"  GIF proof: {output_path} ({check_img.size[0]}x{check_img.size[1]})")
    return output_path


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='Interaction Test Driver — MP4-first proof of completion')
    parser.add_argument('--page', help='Doc path relative to docs/ (e.g. interfaces/live-mindmap/index.md)')
    parser.add_argument('--title', help='Test title')
    parser.add_argument('--subtitle', default='', help='Check subtitle')
    parser.add_argument('--description', default='', help='Check description')
    parser.add_argument('--conclusion', default='', help='Check conclusion')
    parser.add_argument('--steps', help='JSON array of interaction steps')
    parser.add_argument('--test-plan', help='Path to JSON test plan file')
    parser.add_argument('--output-dir', '-o', help='Output directory')
    parser.add_argument('--docs-root', help='Path to docs/ directory')
    parser.add_argument('--direct-page', help='Load this file directly (path relative to docs/) instead of through the viewer')
    parser.add_argument('--module', help='Run a rerunnable test module by name (e.g. live_mindmap_expand)')
    parser.add_argument('--list-modules', action='store_true', help='List available test modules')
    args = parser.parse_args()

    # List modules mode
    if args.list_modules:
        from interactions.tests import list_modules
        modules = list_modules()
        if not modules:
            print("No test modules found.")
        else:
            print(f"{'Name':<30} {'Test ID':<30} {'Title'}")
            print(f"{'─'*30} {'─'*30} {'─'*40}")
            for m in modules:
                print(f"{m['name']:<30} {m['test_id']:<30} {m['title']}")
        sys.exit(0)

    # Module mode — load test plan from module
    if args.module:
        from interactions.tests import get_module
        mod = get_module(args.module)
        if not mod:
            print(f"ERROR: Test module '{args.module}' not found. Use --list-modules to see available.")
            sys.exit(1)
        plan = mod['get_test_plan']()
        if not args.output_dir:
            # Auto-resolve output dir from module
            k_tools = os.path.dirname(SCRIPT_DIR)
            knowledge = os.path.dirname(k_tools)
            repo_root = os.path.dirname(knowledge)
            args.output_dir = os.path.join(repo_root, mod['output_dir'], 'assets')
        args.test_plan = '__module__'  # Signal that plan is loaded
        print(f"  Module: {mod['name']} → {mod['slug']}")
        print(f"  Output: {args.output_dir}")

    if not args.output_dir:
        print("ERROR: --output-dir is required (unless using --module)")
        sys.exit(1)

    # Resolve docs root
    docs_root = args.docs_root
    if not docs_root:
        # Auto-detect from script location
        k_tools = os.path.dirname(SCRIPT_DIR)
        knowledge = os.path.dirname(k_tools)
        repo_root = os.path.dirname(knowledge)
        docs_root = os.path.join(repo_root, 'docs')

    # Load steps or parts
    if args.test_plan == '__module__':
        # Plan already loaded from --module
        title = plan.get('title', args.title or 'Test')
        subtitle = plan.get('subtitle', args.subtitle or '')
        description = plan.get('description', args.description or '')
        conclusion = plan.get('conclusion', args.conclusion or '')
        if not args.page:
            args.page = plan.get('page')
        parts = plan.get('parts')
        steps = plan.get('steps', [])
    elif args.test_plan:
        with open(args.test_plan) as f:
            plan = json.load(f)
        title = plan.get('title', args.title or 'Test')
        subtitle = plan.get('subtitle', args.subtitle)
        description = plan.get('description', args.description)
        conclusion = plan.get('conclusion', args.conclusion)
        if not args.page:
            args.page = plan.get('page')
        parts = plan.get('parts')
        steps = plan.get('steps', [])
    elif args.steps:
        steps = json.loads(args.steps)
        parts = None
        title = args.title
        subtitle = args.subtitle
        description = args.description
        conclusion = args.conclusion
    else:
        print("ERROR: Provide --steps or --test-plan")
        sys.exit(1)

    # Resolve direct_page from plan or CLI
    direct_page = getattr(args, 'direct_page', None)
    if args.test_plan and not direct_page:
        direct_page = plan.get('direct_page')

    # Run test — sidebyside, multi-part, or single
    mode = plan.get('mode', '') if args.test_plan else ''
    if mode == 'sidebyside' and parts:
        results = asyncio.run(run_sidebyside_test(
            docs_root, args.page, title, parts, args.output_dir))
    elif parts:
        results = asyncio.run(run_multipart_test(
            docs_root, args.page, title, parts, args.output_dir))
    else:
        pre_checks = plan.get('pre_checks', []) if args.test_plan else []
        results = asyncio.run(run_interaction_test(
            docs_root, args.page, title, steps, args.output_dir,
            direct_page=direct_page, pre_checks=pre_checks))

    if not results:
        sys.exit(1)

    # Narrate master recording — burn chat panel into proof.mp4
    import subprocess as _sp
    mp4_path = results['artifacts'].get('mp4')
    results_path = results['artifacts'].get('results')
    if mp4_path and results_path and os.path.isfile(mp4_path):
        narrate_script = os.path.join(SCRIPT_DIR, 'narrate_video.py')
        if os.path.isfile(narrate_script):
            narrated_tmp = os.path.join(tempfile.gettempdir(), 'proof-narrated.mp4')
            cmd = [sys.executable, narrate_script,
                   '--results', results_path, '--video', mp4_path,
                   '-o', narrated_tmp]
            proc = _sp.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                os.replace(narrated_tmp, mp4_path)
                size_kb = os.path.getsize(mp4_path) // 1024
                print(f"  proof.mp4 (narrated): {size_kb}K")
            else:
                print(f"  narration error: {(proc.stderr or proc.stdout or 'unknown')[:300]}")
                if os.path.isfile(narrated_tmp):
                    os.unlink(narrated_tmp)

    # Compose proof GIF — standard before/after (skip if sidebyside already produced one)
    if not results['artifacts'].get('gif'):
        screenshots = results['artifacts'].get('screenshots', {})
        if 'before' in screenshots and 'after' in screenshots:
            gif_path = os.path.join(args.output_dir, 'proof.gif')
            compose_proof_gif(
                screenshots, title, subtitle, description, conclusion, gif_path)

    print(f"\n  Results: {results['artifacts'].get('results', 'N/A')}")
    print(f"  MP4: {results['artifacts'].get('mp4', 'N/A')}")


if __name__ == '__main__':
    main()
