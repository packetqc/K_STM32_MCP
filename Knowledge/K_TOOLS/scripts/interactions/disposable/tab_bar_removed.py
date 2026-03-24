"""
Tab Bar Removed — Disposable Verification
============================================

Confirms the tab bar has been removed from the Tests Interface.
Created for the tab bar removal task. Kept here for reruns if needed.

Once this check is no longer relevant, delete this file.
"""

MATCH_PATTERNS = [
    r'interfaces/tests/',
    r'interfaces/tests/index\.md',
]
DESCRIPTION = 'Verify tab bar is removed from Tests Interface'


async def _find_dashboard_frame(frame, page):
    """Find the frame containing the Tests Interface content."""
    try:
        count = await frame.evaluate("() => document.querySelectorAll('#tv-content, #test-viewer').length")
        if count and count > 0:
            return frame
    except Exception:
        pass

    for f in page.frames:
        if f == page.main_frame:
            continue
        try:
            has_tv = await f.evaluate("() => !!document.getElementById('test-viewer')")
            if has_tv:
                return f
        except Exception:
            pass

    return frame


async def run(frame, page, context):
    """Check that the tab bar is not present."""
    frame = await _find_dashboard_frame(frame, page)
    results = []

    try:
        tab_bar = await frame.evaluate("""() => {
            var bar = document.querySelector('#tv-tab-bar, .tv-tab-bar');
            return { found: !!bar, visible: bar ? bar.offsetHeight > 0 : false };
        }""")

        if not tab_bar.get('found') or not tab_bar.get('visible'):
            results.append({'type': 'interaction', 'label': 'Tab bar removed',
                            'result': 'PASS', 'detail': 'no tab bar found (as expected)'})
        else:
            results.append({'type': 'interaction', 'label': 'Tab bar removed',
                            'result': 'FAIL', 'detail': 'tab bar still visible'})
    except Exception as e:
        results.append({'type': 'interaction', 'label': 'Tab bar removed',
                        'result': 'FAIL', 'detail': str(e)[:80]})

    return results
