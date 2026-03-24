#!/usr/bin/env python3
"""
Web Page Visualization — Production Rendering Script

Renders web pages and individual Mermaid diagrams as images using
Playwright + Chromium + local npm mermaid. Zero external services.

Knowledge asset — synced to satellites via wakeup step 5.

Usage:
    # Full page screenshot (with Mermaid rendering)
    python3 scripts/render_web_page.py --url https://packetqc.github.io/knowledge/publications/architecture-diagrams/full/

    # Single Mermaid diagram to PNG
    python3 scripts/render_web_page.py --mermaid diagram.mmd --output diagram.png

    # Single Mermaid diagram to SVG
    python3 scripts/render_web_page.py --mermaid diagram.mmd --output diagram.svg

    # Full page with custom output directory
    python3 scripts/render_web_page.py --url <URL> --output-dir /tmp/screenshots

    # Batch: render all .mmd files in a directory
    python3 scripts/render_web_page.py --mermaid-dir diagrams/ --output-dir rendered/

Prerequisites:
    - Playwright + Chromium pre-installed (Claude Code environment)
    - npm mermaid: mkdir -p /tmp/mermaid-local-test && cd /tmp/mermaid-local-test && npm init -y --silent && npm install mermaid

Related:
    - methodology/methodology-system-web-visualization.md — full specification
    - Publication #16 — Web Page Visualization
    - Publication #17 — Web Production Pipeline
"""

import argparse
import asyncio
import glob
import os
import re
import sys
import tempfile
import urllib.request

from playwright.async_api import async_playwright

# --- Configuration -----------------------------------------------------------

# Mermaid.js — local npm package (installed per session)
MERMAID_JS_PATHS = [
    "/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js",
    "/tmp/node_modules/mermaid/dist/mermaid.min.js",
]

# Chromium — pre-installed in Claude Code environment
CHROME_PATHS = [
    "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
    "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
]

VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# --- Proof Output Helpers ----------------------------------------------------

def frames_to_gif(frame_paths, output_path, duration_ms=500):
    """Assemble PNG frames into an animated GIF."""
    from PIL import Image
    frames = [Image.open(f) for f in frame_paths]
    if not frames:
        return False
    frames[0].save(
        output_path, save_all=True, append_images=frames[1:],
        duration=duration_ms, loop=0, optimize=True
    )
    print(f"GIF proof: {len(frames)} frames → {output_path}")
    return True


def frames_to_mp4(frame_paths, output_path, fps=2):
    """Assemble PNG frames into a browser-compatible H.264 MP4 video."""
    from video_utils import encode_mp4_from_paths
    if not frame_paths:
        return False
    result = encode_mp4_from_paths(frame_paths, output_path, fps=fps, scale=1.0)
    if result:
        print(f"MP4 proof: {len(frame_paths)} frames → {output_path}")
    return result


def assemble_proof(frame_paths, output_path, fps=2):
    """Route to GIF or MP4 assembly based on output extension."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext == '.gif':
        return frames_to_gif(frame_paths, output_path, duration_ms=int(1000 / fps))
    elif ext == '.mp4':
        return frames_to_mp4(frame_paths, output_path, fps=fps)
    elif ext == '.png':
        # Static: just use the last frame
        if frame_paths:
            import shutil
            shutil.copy2(frame_paths[-1], output_path)
            print(f"PNG proof: {output_path}")
            return True
    return False


def find_mermaid_js():
    """Find local mermaid.js installation."""
    for path in MERMAID_JS_PATHS:
        if os.path.isfile(path):
            return path
    return None


def find_chrome():
    """Find Chromium binary."""
    for pattern in CHROME_PATHS:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def ensure_mermaid():
    """Install mermaid npm package if not found."""
    if find_mermaid_js():
        return find_mermaid_js()
    print("Installing mermaid npm package...")
    os.makedirs("/tmp/mermaid-local-test", exist_ok=True)
    os.system("cd /tmp/mermaid-local-test && npm init -y --silent 2>/dev/null && npm install mermaid marked mind-elixir --silent 2>/dev/null")
    path = find_mermaid_js()
    if not path:
        print("ERROR: Failed to install mermaid. Run manually:")
        print("  mkdir -p /tmp/mermaid-local-test && cd /tmp/mermaid-local-test && npm init -y --silent && npm install mermaid")
        sys.exit(1)
    return path


# --- Pipeline 1: Full Page Visualization ------------------------------------

GITHUB_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
       max-width: 980px; margin: 0 auto; padding: 20px; line-height: 1.5; color: #24292f; }
h1, h2 { border-bottom: 1px solid #d0d7de; padding-bottom: .3em; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; }
th, td { border: 1px solid #d0d7de; padding: 6px 13px; }
th { background: #f6f8fa; font-weight: 600; }
code { background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-size: 85%; }
pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }
.mermaid { text-align: center; margin: 16px 0; }
blockquote { border-left: 4px solid #d0d7de; padding: 0 16px; color: #57606a; }
"""


async def render_page(url, output_dir="/tmp", mermaid_js=None, chrome=None):
    """Render a web page with Mermaid diagrams as screenshots.

    Returns dict with keys: total, ok, fail, pages, output_dir
    """
    mermaid_js = mermaid_js or find_mermaid_js()
    chrome = chrome or find_chrome()

    if not chrome:
        print("ERROR: Chromium not found.")
        return None

    # 1. Fetch HTML via urllib (bypasses container proxy)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    # 2. Extract body content
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL)
    body = body_match.group(1) if body_match else html

    # 3. Build self-contained HTML
    self_contained = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{GITHUB_CSS}</style>
</head><body>{body}</body></html>"""

    os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=chrome,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
        )
        page = await browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        # 4-5. Load page and inject mermaid.js
        await page.goto("about:blank")
        if mermaid_js:
            await page.add_script_tag(path=mermaid_js)
        await page.evaluate("""(html) => {
            document.open(); document.write(html); document.close();
        }""", self_contained)
        await page.wait_for_timeout(2000)

        # 6. Render Mermaid blocks (skip .mermaid-source containers)
        mermaid_result = {"total": 0, "ok": 0, "fail": 0}
        if mermaid_js:
            mermaid_result = await page.evaluate("""async () => {
                mermaid.initialize({startOnLoad: false, theme: 'default', securityLevel: 'loose'});
                const blocks = document.querySelectorAll('code.language-mermaid');
                let ok = 0, fail = 0;
                for (let i = 0; i < blocks.length; i++) {
                    if (blocks[i].closest('.mermaid-source')) continue;
                    try {
                        const { svg } = await mermaid.render('mmd-' + i, blocks[i].textContent);
                        const div = document.createElement('div');
                        div.className = 'mermaid';
                        div.innerHTML = svg;
                        blocks[i].parentElement.replaceWith(div);
                        ok++;
                    } catch(e) { fail++; }
                }
                return {total: blocks.length, ok, fail};
            }""")

        # 7. Full page screenshot
        full_path = os.path.join(output_dir, "page-full.png")
        await page.screenshot(path=full_path, full_page=True)

        # Viewport-by-viewport screenshots
        height = await page.evaluate("document.body.scrollHeight")
        num_pages = (height + VIEWPORT_HEIGHT - 1) // VIEWPORT_HEIGHT
        for i in range(num_pages):
            await page.evaluate(f"window.scrollTo(0, {i * VIEWPORT_HEIGHT})")
            await page.wait_for_timeout(200)
            await page.screenshot(path=os.path.join(output_dir, f"page-{i+1}.png"))

        await browser.close()

    result = {**mermaid_result, "pages": num_pages, "output_dir": output_dir}
    print(f"Page rendered: {mermaid_result['ok']}/{mermaid_result['total']} Mermaid diagrams, "
          f"{num_pages} viewport pages → {output_dir}/")
    return result


# --- Pipeline 2: Mermaid Diagram to Image ------------------------------------

async def render_mermaid(diagram_code, output_path, fmt="png", chrome=None, mermaid_js=None):
    """Render a single Mermaid diagram to SVG or PNG.

    Returns True on success, False on failure.
    """
    mermaid_js = mermaid_js or ensure_mermaid()
    chrome = chrome or find_chrome()

    if not chrome:
        print("ERROR: Chromium not found.")
        return False

    with open(mermaid_js, "r") as f:
        mermaid_js_content = f.read()

    html = f"""<!DOCTYPE html>
<html><head><script>{mermaid_js_content}</script>
<style>body {{ background: transparent; margin: 0; }}</style>
</head><body>
<div id="target"></div>
<div id="result" style="display:none"></div>
<script>
mermaid.initialize({{startOnLoad: false, theme: 'default', securityLevel: 'loose'}});
async function render() {{
    try {{
        const {{ svg }} = await mermaid.render('diagram', `{diagram_code}`);
        document.getElementById('target').innerHTML = svg;
        document.getElementById('result').textContent = 'OK';
    }} catch(e) {{
        document.getElementById('result').textContent = 'ERROR: ' + e.message;
    }}
}}
render();
</script>
</body></html>"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chrome,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
        )
        page = await browser.new_page()
        await page.set_content(html)
        await page.wait_for_timeout(3000)

        result_text = await page.evaluate("document.getElementById('result').textContent")
        success = result_text == 'OK'

        if success:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            if fmt == "svg":
                svg = await page.evaluate("document.querySelector('#target svg').outerHTML")
                with open(output_path, "w") as f:
                    f.write(svg)
            else:  # png
                target = page.locator('#target svg')
                await target.screenshot(path=output_path, type="png")
            print(f"Rendered: {output_path} ({fmt.upper()})")
        else:
            print(f"FAILED: {result_text}")

        await browser.close()
        return success


# --- Pipeline 4: Viewer Rendering (file:// with local CDN replacement) -----


async def render_viewer(doc_path, docs_root, output_path, chrome=None, wait_ms=3000, theme=None, scroll_to=None):
    """Render a doc through the local viewer via file:// URL.

    Navigates to docs/index.html?doc=<path> via file://, replaces CDN scripts
    with local npm packages via add_script_tag, waits for rendering, screenshots.

    Returns True on success.
    """
    chrome = chrome or find_chrome()
    if not chrome:
        print("ERROR: Chromium not found.")
        return False

    index_path = os.path.join(docs_root, "index.html")
    if not os.path.isfile(index_path):
        print(f"ERROR: Viewer not found at {index_path}")
        return False

    # Build file:// URL with query params
    from urllib.parse import quote
    abs_index = os.path.abspath(index_path)
    viewer_url = f"file://{abs_index}?doc={quote(doc_path)}"
    if theme:
        viewer_url += f"&theme={quote(theme)}"

    # Local CDN replacements
    cdn_scripts = {
        'marked': '/tmp/mermaid-local-test/node_modules/marked/lib/marked.umd.js',
        'mermaid': '/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js',
        'MindElixir': '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.iife.js',
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chrome,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                  '--allow-file-access-from-files']
        )
        page = await browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})

        # Intercept CDN requests and fulfill with local npm packages
        async def handle_cdn(route):
            url = route.request.url
            for name, path in cdn_scripts.items():
                if name.lower() in url.lower() and os.path.isfile(path):
                    with open(path, 'r') as f:
                        body = f.read()
                    await route.fulfill(body=body, content_type='application/javascript')
                    return
            # CSS file
            if 'MindElixir.css' in url:
                css_path = '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.css'
                if os.path.isfile(css_path):
                    with open(css_path, 'r') as f:
                        body = f.read()
                    await route.fulfill(body=body, content_type='text/css')
                    return
            await route.abort()

        # Intercept GitHub raw requests (e.g. sections.json) and serve from local
        async def handle_github_raw(route):
            url = route.request.url
            # Map raw GitHub paths to local filesystem
            if 'sections.json' in url:
                local = os.path.join(docs_root, '..', 'Knowledge', 'sections.json')
                if os.path.isfile(local):
                    with open(local, 'r') as f:
                        body = f.read()
                    await route.fulfill(body=body, content_type='application/json')
                    return
            await route.abort()

        # Intercept data/*.json fetches from iframe (Blob URL context)
        # These come as relative fetches resolved against the viewer origin
        async def handle_data_json(route):
            url = route.request.url
            # Extract the data/xxx.json part from the URL
            import re as _re
            m = _re.search(r'(data/\w+\.json)', url)
            if m:
                local = os.path.join(docs_root, m.group(1))
                if os.path.isfile(local):
                    with open(local, 'r') as f:
                        body = f.read()
                    await route.fulfill(body=body, content_type='application/json')
                    return
            # Also handle mind_memory.md and depth_config.json for live mindmap
            if 'mind_memory.md' in url or 'mind/mind_memory.md' in url:
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

        await page.route('**cdn.jsdelivr.net**', handle_cdn)
        await page.route('**raw.githubusercontent.com**', handle_github_raw)
        await page.route('**/data/*.json', handle_data_json)
        await page.route('**mind_memory.md', handle_data_json)
        await page.route('**depth_config.json', handle_data_json)

        # Navigate to viewer — CDN requests fulfilled locally
        await page.goto(viewer_url, wait_until="load", timeout=30000)

        # Dismiss fullscreen prompt overlay if present
        await page.evaluate("() => { var o = document.querySelector('.fs-prompt-overlay'); if (o) o.remove(); }")

        # Wait for MindElixir to finish rendering (any page that contains it).
        # MindElixir v5.x renders as DOM elements (me-tpc, me-main), not SVG.
        # Polls across all frames including srcdoc iframes used by the navigator.
        async def wait_for_mind_elixir(max_wait=12000, poll=500):
            elapsed = 0
            while elapsed < max_wait:
                for frame in page.frames:
                    try:
                        ready = await frame.evaluate("""() => {
                            var tpc = document.querySelector('me-tpc, me-main me-wrapper');
                            return !!tpc;
                        }""")
                        if ready:
                            await page.wait_for_timeout(1500)
                            return True
                    except:
                        pass
                await page.wait_for_timeout(poll)
                elapsed += poll
            return False

        await wait_for_mind_elixir()

        # Scroll to element if requested
        if scroll_to:
            await page.evaluate(f"""() => {{
                var el = document.querySelector('{scroll_to}');
                if (el) el.scrollIntoView({{ block: 'center', behavior: 'instant' }});
            }}""")
            await page.wait_for_timeout(500)

        # Determine output format from extension
        ext = os.path.splitext(output_path)[1].lower()
        is_animated = ext in ('.gif', '.mp4')

        if is_animated:
            # Capture frame sequence during render for animated proof
            frame_dir = tempfile.mkdtemp(prefix='render_frames_')
            frame_paths = []
            frame_interval = 500  # ms between frames
            elapsed = 0

            # Initial frame (page just loaded)
            fp = os.path.join(frame_dir, f'frame_{len(frame_paths):04d}.png')
            await page.screenshot(path=fp, full_page=False)
            frame_paths.append(fp)

            # Capture frames during rendering
            while elapsed < wait_ms:
                await page.wait_for_timeout(frame_interval)
                elapsed += frame_interval
                fp = os.path.join(frame_dir, f'frame_{len(frame_paths):04d}.png')
                await page.screenshot(path=fp, full_page=False)
                frame_paths.append(fp)

            # Assemble proof artifact
            assemble_proof(frame_paths, output_path, fps=2)

            # Cleanup temp frames
            for fp in frame_paths:
                os.unlink(fp)
            os.rmdir(frame_dir)
        else:
            # Static screenshot (PNG)
            await page.wait_for_timeout(wait_ms)
            await page.screenshot(path=output_path, full_page=False)
            print(f"Viewer rendered: {doc_path} → {output_path}")

        await browser.close()
        return True


# --- CLI Entry Point ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Web Page Visualization — render pages and Mermaid diagrams as images"
    )
    parser.add_argument("--url", help="URL of web page to render (full page screenshot)")
    parser.add_argument("--viewer", help="Render doc through local viewer: path relative to docs/ (e.g. interfaces/claude-interface/index.md)")
    parser.add_argument("--docs-root", default=None, help="Path to docs/ directory (auto-detected from script location)")
    parser.add_argument("--mermaid", help="Path to .mmd file (single Mermaid diagram)")
    parser.add_argument("--mermaid-dir", help="Directory of .mmd files (batch rendering)")
    parser.add_argument("--output", "-o", help="Output file path (for --mermaid or --viewer)")
    parser.add_argument("--output-dir", "-d", default="/tmp/render", help="Output directory (default: /tmp/render)")
    parser.add_argument("--format", "-f", choices=["png", "svg", "gif", "mp4"], default="png", help="Output format: png, svg, gif, mp4 (default: png)")
    parser.add_argument("--wait", type=int, default=3000, help="Wait time in ms after page load (default: 3000)")
    parser.add_argument("--theme", help="Theme for viewer rendering (e.g. daltonism-dark, midnight, cayman)")
    parser.add_argument("--scroll-to", help="CSS selector to scroll to before capture (e.g. '.me-rendered', '#section-3')")

    args = parser.parse_args()

    if not any([args.url, args.viewer, args.mermaid, args.mermaid_dir]):
        parser.print_help()
        sys.exit(1)

    # Ensure dependencies
    mermaid_js = ensure_mermaid()
    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found. This script requires the Claude Code environment.")
        sys.exit(1)

    if args.viewer:
        # Pipeline 4: Viewer rendering
        docs_root = args.docs_root
        if not docs_root:
            # Auto-detect: script is in Knowledge/K_TOOLS/scripts/, docs is at ../../docs/
            script_dir = os.path.dirname(os.path.abspath(__file__))
            docs_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", "docs"))
        output = args.output or os.path.join(args.output_dir, "viewer.png")
        asyncio.run(render_viewer(args.viewer, docs_root, output, chrome, args.wait, args.theme, getattr(args, 'scroll_to', None)))

    elif args.url:
        # Pipeline 1: Full page
        asyncio.run(render_page(args.url, args.output_dir, mermaid_js, chrome))

    elif args.mermaid:
        # Pipeline 2: Single diagram
        output = args.output or os.path.join(
            args.output_dir,
            os.path.splitext(os.path.basename(args.mermaid))[0] + f".{args.format}"
        )
        with open(args.mermaid, "r") as f:
            code = f.read()
        asyncio.run(render_mermaid(code, output, args.format, chrome, mermaid_js))

    elif args.mermaid_dir:
        # Pipeline 2: Batch
        mmd_files = sorted(glob.glob(os.path.join(args.mermaid_dir, "*.mmd")))
        if not mmd_files:
            print(f"No .mmd files found in {args.mermaid_dir}")
            sys.exit(1)
        os.makedirs(args.output_dir, exist_ok=True)
        ok = fail = 0
        for mmd_file in mmd_files:
            name = os.path.splitext(os.path.basename(mmd_file))[0]
            output = os.path.join(args.output_dir, f"{name}.{args.format}")
            with open(mmd_file, "r") as f:
                code = f.read()
            if asyncio.run(render_mermaid(code, output, args.format, chrome, mermaid_js)):
                ok += 1
            else:
                fail += 1
        print(f"\nBatch: {ok} OK, {fail} failed out of {len(mmd_files)} diagrams")


if __name__ == "__main__":
    main()
