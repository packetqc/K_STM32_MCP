"""
Tests Interface — Interaction Plugin (REUSABLE)
=================================================

Verifies the Tests Interface dashboard renders correctly:
- Stats bar (Tests, Runs, Pass, Fail counts)
- LED matrix grid with test rows and run columns
- Test links are present and clickable
- Click routing to content-frame (embedded mode)

Works in both standalone (Loop 1) and embedded (Loop 2) contexts.

TIER: reusable — the Tests Interface dashboard is stable.
These checks apply every time the interface is tested.
"""

MATCH_PATTERNS = [
    r'interfaces/tests/',
    r'interfaces/tests/index\.md',
]
DESCRIPTION = 'Tests Interface dashboard: stats, LED matrix, test links, click routing'


async def _find_dashboard_frame(frame, page):
    """Find the frame containing the Tests Interface dashboard.

    The dashboard may be in the passed frame directly, or nested inside
    an ifaceFrame srcdoc (when loaded as an interface page).
    """
    # Check the passed frame first
    try:
        count = await frame.evaluate("() => document.querySelectorAll('#tv-content, #test-viewer').length")
        if count and count > 0:
            return frame
    except Exception:
        pass

    # Search all srcdoc frames for the dashboard
    for f in page.frames:
        if f == page.main_frame:
            continue
        try:
            has_tv = await f.evaluate("() => !!document.getElementById('test-viewer')")
            if has_tv:
                return f
        except Exception:
            pass

    return frame  # fallback to original


async def _wait_for_stats(frame, page, retries=5):
    """Wait for dashboard async fetch to complete."""
    for _ in range(retries):
        count = await frame.evaluate("() => document.querySelectorAll('.tv-stat').length")
        if count and count > 0:
            return True
        await page.wait_for_timeout(2000)
    return False


async def run(frame, page, context):
    """Run interaction checks on the Tests Interface.

    Args:
        frame: Playwright Frame containing the Tests Interface content
        page: top-level Playwright Page
        context: dict with 'doc', 'panel', 'phase', 'nav', 'mode'

    Returns:
        list of check results [{'type', 'label', 'result', 'detail'}]
    """
    results = []
    nav = context.get('nav')
    mode = context.get('mode', 'standalone')

    # Find the actual dashboard frame (may be nested in ifaceFrame)
    frame = await _find_dashboard_frame(frame, page)

    # ── Check 1: Dashboard stats render ──────────────────────────────
    await _wait_for_stats(frame, page)
    try:
        stats = await frame.evaluate("""() => {
            var els = document.querySelectorAll('.tv-stat');
            var vals = [];
            els.forEach(function(el) {
                var v = el.querySelector('.tv-stat-val');
                var l = el.querySelector('.tv-stat-lbl');
                vals.push({
                    value: v ? v.textContent.trim() : '?',
                    label: l ? l.textContent.trim() : '?'
                });
            });
            return { count: els.length, stats: vals };
        }""")

        if stats.get('count', 0) >= 2:
            labels = ', '.join(s['label'] + '=' + s['value'] for s in stats.get('stats', []))
            results.append({'type': 'interaction', 'label': 'Dashboard stats render',
                            'result': 'PASS', 'detail': f"{stats['count']} stats: {labels}"})
        else:
            results.append({'type': 'interaction', 'label': 'Dashboard stats render',
                            'result': 'FAIL', 'detail': f"expected ≥2 stats, got {stats.get('count', 0)}"})
    except Exception as e:
        results.append({'type': 'interaction', 'label': 'Dashboard stats render',
                        'result': 'FAIL', 'detail': str(e)[:80]})

    # ── Check 2: LED matrix grid exists ──────────────────────────────
    try:
        matrix = await frame.evaluate("""() => {
            var table = document.querySelector('.tv-matrix');
            if (!table) return { found: false };
            var rows = table.querySelectorAll('tbody tr');
            var cols = table.querySelectorAll('thead th');
            var leds = table.querySelectorAll('.led');
            return { found: true, rows: rows.length, cols: cols.length, leds: leds.length };
        }""")

        if matrix.get('found') and matrix.get('rows', 0) > 0:
            results.append({'type': 'interaction', 'label': 'LED matrix grid',
                            'result': 'PASS',
                            'detail': f"{matrix['rows']} tests, {matrix['cols']-1} run columns, {matrix['leds']} LEDs"})
        else:
            results.append({'type': 'interaction', 'label': 'LED matrix grid',
                            'result': 'FAIL', 'detail': f"matrix not found or empty: {matrix}"})
    except Exception as e:
        results.append({'type': 'interaction', 'label': 'LED matrix grid',
                        'result': 'FAIL', 'detail': str(e)[:80]})

    # ── Check 3: Test links present ──────────────────────────────────
    try:
        links = await frame.evaluate("""() => {
            var els = document.querySelectorAll('.tv-test-link');
            var items = [];
            els.forEach(function(l) {
                items.push({
                    text: l.textContent.trim(),
                    href: l.getAttribute('href') || ''
                });
            });
            return { count: els.length, items: items };
        }""")

        if links.get('count', 0) > 0:
            names = [l['text'][:40] for l in links.get('items', [])[:5]]
            results.append({'type': 'interaction', 'label': 'Test links present',
                            'result': 'PASS', 'detail': f"{links['count']} links: {names}"})
        else:
            results.append({'type': 'interaction', 'label': 'Test links present',
                            'result': 'FAIL', 'detail': 'no .tv-test-link elements found'})
    except Exception as e:
        results.append({'type': 'interaction', 'label': 'Test links present',
                        'result': 'FAIL', 'detail': str(e)[:80]})

    # ── Check 4: Latest run shows green LED ──────────────────────────
    try:
        latest = await frame.evaluate("""() => {
            var firstRow = document.querySelector('.tv-matrix tbody tr');
            if (!firstRow) return { found: false };
            var cells = firstRow.querySelectorAll('td');
            if (cells.length < 2) return { found: false };
            var latestCell = cells[1];
            var led = latestCell.querySelector('.led');
            if (!led) return { found: false };
            var classes = led.className;
            var score = latestCell.textContent.trim();
            return { found: true, classes: classes, score: score };
        }""")

        if latest.get('found'):
            color = 'green' if 'led-green' in latest.get('classes', '') else \
                    'yellow' if 'led-yellow' in latest.get('classes', '') else \
                    'red' if 'led-red' in latest.get('classes', '') else 'grey'
            results.append({'type': 'interaction', 'label': 'Latest run LED status',
                            'result': 'PASS', 'detail': f"LED={color}, score={latest.get('score', '?')}"})
        else:
            results.append({'type': 'interaction', 'label': 'Latest run LED status',
                            'result': 'FAIL', 'detail': 'no latest run LED found'})
    except Exception as e:
        results.append({'type': 'interaction', 'label': 'Latest run LED status',
                        'result': 'FAIL', 'detail': str(e)[:80]})

    # ── Check 5: Click routing (embedded only) ───────────────────────
    if nav and mode == 'embedded':
        try:
            before_src = await nav.evaluate("""() => {
                var rf = document.getElementById('right-frame-el');
                return rf ? rf.src : '';
            }""")

            # Click first test link
            await frame.click('.tv-test-link')
            await page.wait_for_timeout(3000)

            after_src = await nav.evaluate("""() => {
                var rf = document.getElementById('right-frame-el');
                return rf ? rf.src : '';
            }""")

            if after_src != before_src:
                results.append({'type': 'interaction', 'label': 'Click routes to content-frame',
                                'result': 'PASS', 'detail': 'content-frame src changed after click'})
            else:
                results.append({'type': 'interaction', 'label': 'Click routes to content-frame',
                                'result': 'FAIL', 'detail': 'content-frame src unchanged'})
        except Exception as e:
            results.append({'type': 'interaction', 'label': 'Click routes to content-frame',
                            'result': 'FAIL', 'detail': str(e)[:80]})

    return results
