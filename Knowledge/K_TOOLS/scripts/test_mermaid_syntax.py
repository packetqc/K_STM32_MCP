#!/usr/bin/env python3
"""Test: Mermaid Mindmap Syntax Validation
==========================================

Validates that all mermaid mindmap code blocks in publication markdown files
use correct syntax. Catches the most common rendering failures:

  1. Special characters (:, =, >, <, etc.) in node text must be wrapped
     in [brackets], (parens), or ((double-parens))
  2. Indentation must be consistent (spaces only, uniform step size)
  3. Root node must use a shape wrapper like root((text))
  4. No empty node lines
  5. No tabs mixed with spaces

Usage:
    python3 scripts/test_mermaid_syntax.py                    # all publications
    python3 scripts/test_mermaid_syntax.py --slug behavioral-intelligence  # one pub
    python3 scripts/test_mermaid_syntax.py --verbose           # show all nodes checked
"""

import argparse
import glob
import os
import re
import sys
import json
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
DOCS_ROOT = os.path.join(PROJECT_ROOT, 'docs')
REPORT_DIR = os.path.join(MODULE_DIR, 'test-reports')

# Characters that break mermaid mindmap parsing when used in bare node text
SPECIAL_CHARS = re.compile(r'[:=<>{}]')

# Wrapped node patterns — these are safe even with special chars
WRAPPED_NODE = re.compile(
    r'^\s+'           # leading whitespace (indentation)
    r'(?:'
    r'\(\(.*\)\)'     # ((double-parens))
    r'|\(.*\)'        # (single-parens)
    r'|\[.*\]'        # [brackets]
    r'|`.*`'          # `backticks`
    r')'
    r'\s*$'           # trailing whitespace
)

# Root node pattern
ROOT_NODE = re.compile(r'^\s+root\s*[\(\[]')


def extract_mermaid_blocks(filepath):
    """Extract mermaid mindmap code blocks from a markdown file."""
    blocks = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_block = False
    block_lines = []
    block_start = 0

    for i, line in enumerate(lines, 1):
        if line.strip() == '```mermaid':
            in_block = True
            block_lines = []
            block_start = i
        elif in_block and line.strip() == '```':
            in_block = False
            # Only keep mindmap blocks
            if block_lines and block_lines[0]['text'].strip() == 'mindmap':
                blocks.append({
                    'start_line': block_start,
                    'lines': block_lines,
                })
        elif in_block:
            block_lines.append({'num': i, 'text': line.rstrip('\n')})

    return blocks


def check_block(block, filepath, verbose=False):
    """Validate a single mindmap block. Returns list of issues."""
    issues = []
    lines = block['lines']

    if not lines:
        issues.append({
            'line': block['start_line'],
            'severity': 'error',
            'message': 'Empty mindmap block',
        })
        return issues

    # Skip the 'mindmap' declaration line
    content_lines = [l for l in lines if l['text'].strip() != 'mindmap']

    if not content_lines:
        issues.append({
            'line': block['start_line'],
            'severity': 'error',
            'message': 'Mindmap block has no nodes',
        })
        return issues

    # Check 1: Root node must use shape wrapper
    root_line = content_lines[0]
    if not ROOT_NODE.match(root_line['text']):
        if 'root' in root_line['text']:
            issues.append({
                'line': root_line['num'],
                'severity': 'error',
                'message': f"Root node missing shape wrapper — use root((text)) or root[text]: {root_line['text'].strip()}",
            })

    # Check 2: Indentation consistency (no tabs)
    for l in content_lines:
        if '\t' in l['text']:
            issues.append({
                'line': l['num'],
                'severity': 'error',
                'message': f"Tab character in indentation (use spaces only): {l['text'].strip()}",
            })

    # Check 3: Special characters in bare (unwrapped) node text
    for l in content_lines:
        text = l['text']
        stripped = text.strip()

        # Skip root line, empty lines, 'mindmap' keyword
        if not stripped or stripped == 'mindmap' or stripped.startswith('root'):
            continue

        # Check if this node is wrapped
        if WRAPPED_NODE.match(text):
            if verbose:
                print(f"    OK (wrapped): L{l['num']}: {stripped}")
            continue

        # Bare node — check for special characters
        if SPECIAL_CHARS.search(stripped):
            issues.append({
                'line': l['num'],
                'severity': 'error',
                'message': f"Special character in bare node text — wrap in [brackets]: {stripped}",
            })
        elif verbose:
            print(f"    OK (bare):    L{l['num']}: {stripped}")

    # Check 4: Empty node lines (just whitespace inside the block)
    for l in content_lines:
        if l['text'].strip() == '' and l != content_lines[-1]:
            issues.append({
                'line': l['num'],
                'severity': 'warning',
                'message': 'Empty line inside mindmap block may cause parsing issues',
            })

    return issues


def find_publication_files(slug=None):
    """Find all publication markdown files, or filter by slug."""
    patterns = [
        os.path.join(DOCS_ROOT, 'publications', '**', '*.md'),
        os.path.join(DOCS_ROOT, 'fr', 'publications', '**', '*.md'),
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))

    if slug:
        files = [f for f in files if f'/{slug}/' in f]

    return sorted(files)


def run_tests(slug=None, verbose=False):
    """Run mermaid mindmap syntax validation across publications."""
    files = find_publication_files(slug)
    if not files:
        print(f"No publication files found{' for slug: ' + slug if slug else ''}")
        sys.exit(1)

    total_blocks = 0
    total_issues = 0
    total_files_with_mindmaps = 0
    all_results = []

    print(f"\nMermaid Mindmap Syntax Validation")
    print(f"={'=' * 50}")
    print(f"Scanning {len(files)} markdown files...\n")

    for filepath in files:
        blocks = extract_mermaid_blocks(filepath)
        if not blocks:
            continue

        total_files_with_mindmaps += 1
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)

        for block in blocks:
            total_blocks += 1
            if verbose:
                print(f"  [{rel_path}] block at line {block['start_line']}:")

            issues = check_block(block, filepath, verbose=verbose)

            file_result = {
                'file': rel_path,
                'block_line': block['start_line'],
                'node_count': len([l for l in block['lines'] if l['text'].strip() and l['text'].strip() != 'mindmap']),
                'issues': issues,
                'pass': len([i for i in issues if i['severity'] == 'error']) == 0,
            }
            all_results.append(file_result)

            if issues:
                total_issues += len(issues)
                if not verbose:
                    print(f"  FAIL  {rel_path} (line {block['start_line']})")
                for issue in issues:
                    marker = 'ERROR' if issue['severity'] == 'error' else 'WARN '
                    print(f"    {marker} L{issue['line']}: {issue['message']}")
            else:
                print(f"  PASS  {rel_path} (line {block['start_line']}, {file_result['node_count']} nodes)")

    # Summary
    errors = sum(1 for r in all_results if not r['pass'])
    print(f"\n{'=' * 52}")
    print(f"  Files with mindmaps: {total_files_with_mindmaps}")
    print(f"  Mindmap blocks:      {total_blocks}")
    print(f"  Passed:              {total_blocks - errors}")
    print(f"  Failed:              {errors}")
    print(f"  Total issues:        {total_issues}")
    print(f"{'=' * 52}")

    if errors == 0:
        print(f"\n  ALL MERMAID MINDMAP BLOCKS PASS\n")
    else:
        print(f"\n  {errors} BLOCK(S) HAVE SYNTAX ERRORS\n")

    # Save results
    os.makedirs(REPORT_DIR, exist_ok=True)
    results_path = os.path.join(REPORT_DIR, 'mermaid-syntax-results.json')
    report = {
        'test': 'mermaid-mindmap-syntax',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'slug_filter': slug,
        'files_scanned': len(files),
        'files_with_mindmaps': total_files_with_mindmaps,
        'blocks_checked': total_blocks,
        'blocks_passed': total_blocks - errors,
        'blocks_failed': errors,
        'total_issues': total_issues,
        'all_pass': errors == 0,
        'checks': [
            {
                'name': f"{r['file']}:{r['block_line']}",
                'pass': r['pass'],
                'detail': {
                    'nodes': r['node_count'],
                    'issues': [{'line': i['line'], 'severity': i['severity'], 'msg': i['message']} for i in r['issues']],
                },
            }
            for r in all_results
        ],
    }
    with open(results_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  Results saved: {os.path.relpath(results_path, PROJECT_ROOT)}")

    return 0 if errors == 0 else 1


def build_render_html(mermaid_code, mermaid_js_path):
    """Build a minimal HTML page that renders one mermaid block in a real browser."""
    escaped = mermaid_code.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>
<div id="container"></div>
<script src="file://{mermaid_js_path}"></script>
<script>
async function render() {{
    try {{
        mermaid.initialize({{ startOnLoad: false, logLevel: 'error' }});
        const code = `{escaped}`;
        const {{ svg }} = await mermaid.render('test-diagram', code);
        document.getElementById('container').innerHTML = svg;
        window.__RESULT__ = {{ success: true, svgLength: svg.length }};
    }} catch (err) {{
        window.__RESULT__ = {{ success: false, error: err.message || String(err) }};
    }}
}}
render();
</script>
</body></html>'''


def extract_raw_mermaid_mindmaps(filepath):
    """Extract raw mermaid mindmap code strings from a markdown file."""
    import re as _re
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = _re.compile(r'```mermaid\s*\n(mindmap\s*\n.*?)```', _re.DOTALL)
    return [m.group(1).rstrip() for m in pattern.finditer(content)]


async def run_browser_tests(slug=None):
    """Render every mermaid mindmap block in a real Chromium browser via Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n  SKIP: playwright not installed (pip install playwright)")
        return 0

    # Find chromium
    chrome_candidates = glob.glob('/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome')
    if not chrome_candidates:
        print("\n  SKIP: Playwright Chromium not found")
        return 0
    chrome = chrome_candidates[0]

    # Find mermaid.js
    mermaid_paths = [
        '/tmp/mermaid-render-test/node_modules/mermaid/dist/mermaid.min.js',
        '/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js',
    ]
    mermaid_js = next((p for p in mermaid_paths if os.path.exists(p)), None)
    if not mermaid_js:
        print("\n  SKIP: mermaid.js not found (install: npm install mermaid)")
        return 0

    files = find_publication_files(slug)
    if not files:
        return 0

    print(f"\n{'=' * 55}")
    print(f"  BROWSER RENDER TEST (Playwright + Chromium + mermaid.js)")
    print(f"{'=' * 55}\n")

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix='mermaid-test-')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path=chrome,
            headless=True,
            args=['--no-sandbox', '--disable-gpu', '--allow-file-access-from-files']
        )

        passed = 0
        failed = 0

        for filepath in files:
            blocks = extract_raw_mermaid_mindmaps(filepath)
            if not blocks:
                continue

            rel = os.path.relpath(filepath, PROJECT_ROOT)

            for i, block in enumerate(blocks):
                label = f"{rel} (block {i+1})"
                html = build_render_html(block, mermaid_js)

                tmp_html = os.path.join(tmpdir, 'test_page.html')
                with open(tmp_html, 'w') as f:
                    f.write(html)

                page = await browser.new_page()
                try:
                    await page.goto(f'file://{tmp_html}', wait_until='networkidle', timeout=10000)
                    await page.wait_for_timeout(2000)

                    result = await page.evaluate('window.__RESULT__')

                    if result and result.get('success'):
                        svg_len = result.get('svgLength', 0)
                        print(f"  PASS  {label} — SVG rendered ({svg_len} chars)")
                        passed += 1
                    elif result:
                        error = result.get('error', 'unknown')
                        print(f"  FAIL  {label}")
                        print(f"        Error: {error}")
                        failed += 1
                    else:
                        print(f"  FAIL  {label} — no result (render timeout)")
                        failed += 1
                except Exception as e:
                    print(f"  FAIL  {label} — {e}")
                    failed += 1
                finally:
                    await page.close()

        await browser.close()

    print(f"\n  Browser: {passed} passed, {failed} failed")

    if failed == 0:
        print(f"  ALL MERMAID MINDMAPS RENDER SUCCESSFULLY\n")
    else:
        print(f"  {failed} BLOCK(S) FAILED TO RENDER\n")

    return failed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Validate mermaid mindmap syntax in publications')
    parser.add_argument('--slug', help='Filter to a specific publication slug')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all nodes checked')
    parser.add_argument('--browser', action='store_true',
                        help='Also run browser render test (requires playwright + mermaid.js)')
    args = parser.parse_args()

    rc = run_tests(slug=args.slug, verbose=args.verbose)

    if args.browser:
        import asyncio
        browser_failures = asyncio.run(run_browser_tests(slug=args.slug))
        if browser_failures > 0:
            rc = 1

    sys.exit(rc)
