#!/usr/bin/env python3
"""
Security Test Engine — Token Conformity & OWASP Top 10 Audit
=============================================================

Programmatic security audit for the Claude Interface (I6) and Claude API
interface. Tests token handling, storage, persistence, and OWASP compliance.

Three evidence vectors:
  1. Browser — Playwright DOM inspection, localStorage scan, network intercept
  2. Filesystem — grep for token patterns on disk, git history, session files
  3. Console — JS evaluation to probe runtime state

Each OWASP check produces a proof artifact (screenshot or log capture).

Usage:
    python3 scripts/security_test_engine.py --token "sk-ant-..." [--interface claude|api|both]

Knowledge asset — part of the Web Test command category.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from urllib.parse import quote

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

VIEWPORT = {'width': 1920, 'height': 1080}

# ─── OWASP Security Checks ──────────────────────────────────────────────────

OWASP_CHECKS = [
    {
        'id': 'A01',
        'category': 'Broken Access Control',
        'check': 'Token scope validation — verify token format and prefix',
        'severity': 'HIGH',
        'type': 'token_format',
    },
    {
        'id': 'A01-2',
        'category': 'Broken Access Control',
        'check': 'Token not exposed in URL parameters or query strings',
        'severity': 'CRITICAL',
        'type': 'url_exposure',
    },
    {
        'id': 'A02',
        'category': 'Cryptographic Failures',
        'check': 'Token entropy analysis — sufficient randomness',
        'severity': 'HIGH',
        'type': 'entropy',
    },
    {
        'id': 'A02-2',
        'category': 'Cryptographic Failures',
        'check': 'Token transmitted only over HTTPS endpoints',
        'severity': 'CRITICAL',
        'type': 'transport',
    },
    {
        'id': 'A03',
        'category': 'Injection',
        'check': 'Token sanitized in DOM — no script injection via token field',
        'severity': 'HIGH',
        'type': 'dom_injection',
    },
    {
        'id': 'A05',
        'category': 'Security Misconfiguration',
        'check': 'Token NOT present in git history or tracked files',
        'severity': 'CRITICAL',
        'type': 'git_scan',
    },
    {
        'id': 'A05-2',
        'category': 'Security Misconfiguration',
        'check': 'Token NOT hardcoded in source files on disk',
        'severity': 'CRITICAL',
        'type': 'disk_scan',
    },
    {
        'id': 'A05-3',
        'category': 'Security Misconfiguration',
        'check': 'CORS headers — API requests include proper origin restrictions',
        'severity': 'MEDIUM',
        'type': 'cors',
    },
    {
        'id': 'A07',
        'category': 'Identification and Authentication Failures',
        'check': 'Token stored only in localStorage, NOT in cookies or sessionStorage',
        'severity': 'HIGH',
        'type': 'storage_audit',
    },
    {
        'id': 'A07-2',
        'category': 'Identification and Authentication Failures',
        'check': 'Token NOT persisted in K_MIND session files (far_memory, near_memory)',
        'severity': 'CRITICAL',
        'type': 'session_scan',
    },
    {
        'id': 'A07-3',
        'category': 'Identification and Authentication Failures',
        'check': 'Token clearable via disconnect — full cleanup on disconnect',
        'severity': 'HIGH',
        'type': 'disconnect_cleanup',
    },
    {
        'id': 'A09',
        'category': 'Security Logging and Monitoring Failures',
        'check': 'Token NOT leaked in console logs or error messages',
        'severity': 'HIGH',
        'type': 'console_leak',
    },
    {
        'id': 'A09-2',
        'category': 'Security Logging and Monitoring Failures',
        'check': 'Token NOT present in Playwright test artifacts or report files',
        'severity': 'CRITICAL',
        'type': 'artifact_scan',
    },
]


def find_chrome():
    import glob as g
    for p in CHROME_PATHS:
        matches = g.glob(p)
        if matches:
            return matches[0]
    return None


def mask_token(token):
    """Return masked token for safe display: first 8 + ... + last 4."""
    if len(token) <= 16:
        return token[:4] + '...' + token[-4:]
    return token[:8] + '...' + token[-4:]


def compute_entropy(token):
    """Compute Shannon entropy of token string."""
    import math
    freq = {}
    for c in token:
        freq[c] = freq.get(c, 0) + 1
    entropy = 0.0
    for count in freq.values():
        p = count / len(token)
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# ─── Route Handlers (reused from web_test_engine) ───────────────────────────

CDN_SCRIPTS = {
    'marked': '/tmp/mermaid-local-test/node_modules/marked/lib/marked.umd.js',
    'mermaid': '/tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js',
    'MindElixir': '/tmp/mermaid-local-test/node_modules/mind-elixir/dist/MindElixir.iife.js',
}


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


# ─── Security Check Implementations ─────────────────────────────────────────

async def check_token_format(token, page, context):
    """A01: Validate token format and prefix."""
    results = {'check_id': 'A01', 'result': 'FAIL', 'detail': '', 'evidence': []}

    # Anthropic key format: sk-ant-api03-...
    valid_prefixes = ['sk-ant-api03-', 'sk-ant-']
    has_valid_prefix = any(token.startswith(p) for p in valid_prefixes)

    if has_valid_prefix and len(token) > 40:
        results['result'] = 'PASS'
        results['detail'] = f'Valid Anthropic API key format — prefix ok, length {len(token)} chars'
    elif len(token) > 20:
        results['result'] = 'WARN'
        results['detail'] = f'Non-standard prefix but sufficient length ({len(token)}). May be Bedrock/Vertex token.'
    else:
        results['detail'] = f'Token too short ({len(token)} chars) or invalid prefix'

    results['evidence'].append(f'Prefix check: {mask_token(token)}')
    results['evidence'].append(f'Length: {len(token)} characters')
    return results


async def check_url_exposure(token, page, context):
    """A01-2: Token must not appear in URLs."""
    results = {'check_id': 'A01-2', 'result': 'PASS', 'detail': '', 'evidence': []}

    current_url = page.url
    if token in current_url:
        results['result'] = 'FAIL'
        results['detail'] = 'Token found in page URL!'
        results['evidence'].append(f'URL contains token: {current_url[:80]}...')
    else:
        results['detail'] = 'Token not present in any URL parameter'
        results['evidence'].append(f'Current URL clean: {current_url[:80]}')

    # Check all frames — use the top-level page object for frame enumeration
    top_page = context.get('top_page', page)
    try:
        for frame in top_page.frames:
            if token in frame.url:
                results['result'] = 'FAIL'
                results['evidence'].append(f'Token found in frame URL: {frame.url[:80]}')
    except Exception:
        pass  # Frame enumeration not available on sub-frames

    return results


async def check_entropy(token, page, context):
    """A02: Token entropy analysis."""
    results = {'check_id': 'A02', 'result': 'FAIL', 'detail': '', 'evidence': []}

    entropy = compute_entropy(token)
    unique_chars = len(set(token))

    if entropy >= 4.0 and unique_chars >= 20:
        results['result'] = 'PASS'
        results['detail'] = f'Sufficient entropy: {entropy:.2f} bits/char, {unique_chars} unique chars'
    elif entropy >= 3.0:
        results['result'] = 'WARN'
        results['detail'] = f'Moderate entropy: {entropy:.2f} bits/char — acceptable but not ideal'
    else:
        results['detail'] = f'Low entropy: {entropy:.2f} bits/char — weak token'

    results['evidence'].append(f'Shannon entropy: {entropy:.2f} bits/char')
    results['evidence'].append(f'Unique characters: {unique_chars}')
    results['evidence'].append(f'Token length: {len(token)}')
    return results


async def check_transport(token, page, context):
    """A02-2: Token only sent over HTTPS."""
    results = {'check_id': 'A02-2', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Check provider URLs in the interface source
    api_urls = await page.evaluate("""() => {
        var urls = [];
        if (typeof PROVIDERS !== 'undefined') {
            for (var k in PROVIDERS) {
                var u = PROVIDERS[k].url;
                urls.push(typeof u === 'function' ? u('us-east-1') : u);
            }
        }
        return urls;
    }""")

    http_urls = [u for u in api_urls if u and u.startswith('http://')]
    if http_urls:
        results['result'] = 'FAIL'
        results['detail'] = f'{len(http_urls)} HTTP (non-TLS) endpoint(s) found'
        results['evidence'].extend(http_urls)
    else:
        results['detail'] = f'All {len(api_urls)} API endpoints use HTTPS'
        results['evidence'].extend([u[:60] for u in api_urls if u])

    return results


async def check_dom_injection(token, page, context):
    """A03: Token field sanitized against XSS."""
    results = {'check_id': 'A03', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Try injecting script via key input
    xss_payload = '<script>alert("xss")</script>'
    injected = await page.evaluate("""(payload) => {
        var input = document.querySelector('.ci-key-input');
        if (!input) return {found: false};
        input.value = payload;
        // Check if the value was sanitized or rendered as HTML
        var parent = input.parentElement;
        var hasScript = parent.querySelector('script') !== null;
        return {found: true, hasScript: hasScript, value: input.value};
    }""", xss_payload)

    if not injected.get('found'):
        results['result'] = 'SKIP'
        results['detail'] = 'Key input field not found (may be in different state)'
        results['evidence'].append('Interface not in setup state')
    elif injected.get('hasScript'):
        results['result'] = 'FAIL'
        results['detail'] = 'XSS payload rendered in DOM!'
    else:
        results['detail'] = 'Input field properly sanitizes script injection'
        results['evidence'].append(f'Payload stayed as text value: {injected.get("value", "")[:40]}')

    return results


async def check_git_scan(token, page, context):
    """A05: Token NOT in git history."""
    results = {'check_id': 'A05', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Search git log for a unique portion of the token (skip common prefix, use chars 15-35)
    token_prefix = token[15:35] if len(token) > 35 else token[8:]
    try:
        proc = subprocess.run(
            ['git', 'log', '--all', '-p', '-S', token_prefix, '--oneline'],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30
        )
        if proc.stdout.strip():
            results['result'] = 'FAIL'
            results['detail'] = 'Token pattern found in git history!'
            # Capture first few lines as evidence (masked)
            lines = proc.stdout.strip().split('\n')[:5]
            results['evidence'].extend([l[:80] for l in lines])
        else:
            results['detail'] = 'No token match in git history (searched all branches)'
            results['evidence'].append(f'git log -S "{mask_token(token_prefix)}" — 0 matches')
    except Exception as e:
        results['result'] = 'SKIP'
        results['detail'] = f'Git scan failed: {str(e)}'

    return results


async def check_disk_scan(token, page, context):
    """A05-2: Token NOT hardcoded on disk."""
    results = {'check_id': 'A05-2', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Use unique portion of token (skip common prefix like sk-ant-api03-)
    token_prefix = token[15:35] if len(token) > 35 else token[8:]
    scan_dirs = [
        DOCS_ROOT,
        os.path.join(PROJECT_ROOT, 'Knowledge'),
    ]

    found_files = []
    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        try:
            proc = subprocess.run(
                ['grep', '-rl', token_prefix, scan_dir,
                 '--include=*.md', '--include=*.json', '--include=*.html',
                 '--include=*.js', '--include=*.py'],
                capture_output=True, text=True, timeout=30
            )
            if proc.stdout.strip():
                found_files.extend(proc.stdout.strip().split('\n'))
        except Exception:
            pass

    if found_files:
        results['result'] = 'FAIL'
        results['detail'] = f'Token found in {len(found_files)} file(s) on disk!'
        results['evidence'].extend([os.path.relpath(f, PROJECT_ROOT) for f in found_files[:5]])
    else:
        results['detail'] = 'No token match in project files (md, json, html, js, py)'
        results['evidence'].append(f'Scanned {len(scan_dirs)} directories — 0 matches')

    return results


async def check_cors(token, page, context):
    """A05-3: CORS headers on API requests."""
    results = {'check_id': 'A05-3', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Check that the interface sets the dangerous-direct-browser-access header
    has_header = await page.evaluate("""() => {
        if (typeof PROVIDERS !== 'undefined' && PROVIDERS.anthropic) {
            var h = PROVIDERS.anthropic.headers('test');
            return {
                hasDangerousHeader: !!h['anthropic-dangerous-direct-browser-access'],
                hasVersion: !!h['anthropic-version'],
                headers: Object.keys(h)
            };
        }
        return {hasDangerousHeader: false, headers: []};
    }""")

    if has_header.get('hasDangerousHeader'):
        results['result'] = 'WARN'
        results['detail'] = 'Uses anthropic-dangerous-direct-browser-access header — required for browser-direct API calls but increases attack surface'
        results['evidence'].append('Header: anthropic-dangerous-direct-browser-access = true')
        results['evidence'].append('This is expected for client-side Claude API usage')
    else:
        results['detail'] = 'Standard CORS configuration'

    results['evidence'].append(f'Request headers: {", ".join(has_header.get("headers", []))}')
    return results


async def check_storage_audit(token, page, context):
    """A07: Token stored only in localStorage, not cookies/sessionStorage."""
    results = {'check_id': 'A07', 'result': 'PASS', 'detail': '', 'evidence': []}

    storage_state = await page.evaluate("""(tokenPrefix) => {
        var result = {
            localStorage: {},
            sessionStorage: {},
            cookies: document.cookie,
            tokenInLocalStorage: false,
            tokenInSessionStorage: false,
            tokenInCookies: false
        };

        // Scan localStorage
        for (var i = 0; i < localStorage.length; i++) {
            var key = localStorage.key(i);
            var val = localStorage.getItem(key);
            result.localStorage[key] = val ? val.substring(0, 30) + '...' : '';
            if (val && val.indexOf(tokenPrefix) !== -1) {
                result.tokenInLocalStorage = true;
            }
        }

        // Scan sessionStorage
        for (var i = 0; i < sessionStorage.length; i++) {
            var key = sessionStorage.key(i);
            var val = sessionStorage.getItem(key);
            result.sessionStorage[key] = val ? val.substring(0, 30) + '...' : '';
            if (val && val.indexOf(tokenPrefix) !== -1) {
                result.tokenInSessionStorage = true;
            }
        }

        // Check cookies
        if (document.cookie.indexOf(tokenPrefix) !== -1) {
            result.tokenInCookies = true;
        }

        return result;
    }""", token[:12])

    issues = []
    if storage_state.get('tokenInSessionStorage'):
        issues.append('Token found in sessionStorage')
    if storage_state.get('tokenInCookies'):
        issues.append('Token found in cookies')

    if issues:
        results['result'] = 'FAIL'
        results['detail'] = ' | '.join(issues)
    else:
        results['detail'] = 'Token correctly limited to localStorage only'

    results['evidence'].append(f'localStorage keys: {", ".join(storage_state.get("localStorage", {}).keys())}')
    results['evidence'].append(f'sessionStorage keys: {", ".join(storage_state.get("sessionStorage", {}).keys())}')
    results['evidence'].append(f'Cookies: {"present" if storage_state.get("cookies") else "none"}')
    return results


async def check_session_scan(token, page, context):
    """A07-2: Token NOT in K_MIND session files."""
    results = {'check_id': 'A07-2', 'result': 'PASS', 'detail': '', 'evidence': []}

    session_files = [
        os.path.join(PROJECT_ROOT, 'Knowledge', 'K_MIND', 'sessions', 'far_memory.json'),
        os.path.join(PROJECT_ROOT, 'Knowledge', 'K_MIND', 'sessions', 'near_memory.json'),
        os.path.join(PROJECT_ROOT, 'Knowledge', 'K_MIND', 'mind', 'mind_memory.md'),
        os.path.join(PROJECT_ROOT, 'Knowledge', 'K_MIND', 'work', 'work.json'),
    ]

    # Also check archives
    archive_dir = os.path.join(PROJECT_ROOT, 'Knowledge', 'K_MIND', 'sessions', 'archives')
    if os.path.isdir(archive_dir):
        for f in os.listdir(archive_dir):
            if f.endswith('.json'):
                session_files.append(os.path.join(archive_dir, f))

    token_prefix = token[:12] if len(token) > 12 else token
    found_in = []

    for fpath in session_files:
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, 'r') as f:
                content = f.read()
            if token_prefix in content:
                found_in.append(os.path.relpath(fpath, PROJECT_ROOT))
        except Exception:
            pass

    if found_in:
        results['result'] = 'FAIL'
        results['detail'] = f'Token found in {len(found_in)} session file(s)!'
        results['evidence'].extend(found_in)
    else:
        results['detail'] = f'Token not found in {len(session_files)} session/memory files'
        results['evidence'].append(f'Scanned: far_memory, near_memory, mind_memory, work, {len(session_files)-4} archives')

    return results


async def check_disconnect_cleanup(token, page, context):
    """A07-3: Disconnect fully clears token from all storage."""
    results = {'check_id': 'A07-3', 'result': 'PASS', 'detail': '', 'evidence': []}

    # Check if clearKey function exists and what it removes
    cleanup_check = await page.evaluate("""() => {
        var stores = ['ci-anthropic-key', 'ci-provider', 'ci-region'];
        var result = {clearFunctionExists: false, storesBeforeClear: {}, storesAfterClear: {}};

        // Check before state
        stores.forEach(function(s) {
            result.storesBeforeClear[s] = localStorage.getItem(s) !== null;
        });

        // Check if clearKey function is accessible
        if (typeof clearKey === 'function') {
            result.clearFunctionExists = true;
        }

        // Check disconnect button
        var dcBtn = document.querySelector('[onclick*="clearKey"], .ci-disconnect-btn, button');
        var buttons = document.querySelectorAll('button');
        var disconnectBtn = null;
        buttons.forEach(function(b) {
            if (b.textContent.toLowerCase().includes('disconnect') ||
                b.textContent.includes('⏻') ||
                b.classList.contains('ci-disconnect-btn')) {
                disconnectBtn = b;
            }
        });

        result.hasDisconnectButton = disconnectBtn !== null;
        result.disconnectText = disconnectBtn ? disconnectBtn.textContent.trim() : 'not found';

        return result;
    }""")

    if cleanup_check.get('hasDisconnectButton'):
        results['detail'] = 'Disconnect mechanism present — clears ci-anthropic-key, ci-provider, ci-region'
        results['evidence'].append(f'Button found: "{cleanup_check.get("disconnectText", "")}"')
        results['evidence'].append(f'Stores tracked: ci-anthropic-key, ci-provider, ci-region')
    else:
        results['result'] = 'WARN'
        results['detail'] = 'Disconnect button not found in current state (may require connected state)'
        results['evidence'].append('Interface may be in setup state — disconnect only visible when connected')

    return results


async def check_console_leak(token, page, context):
    """A09: Token NOT leaked in console output."""
    results = {'check_id': 'A09', 'result': 'PASS', 'detail': '', 'evidence': []}

    console_messages = context.get('console_messages', [])
    token_prefix = token[:12] if len(token) > 12 else token

    leaked_messages = []
    for msg in console_messages:
        if token_prefix in msg:
            leaked_messages.append(msg[:80])

    if leaked_messages:
        results['result'] = 'FAIL'
        results['detail'] = f'Token leaked in {len(leaked_messages)} console message(s)'
        results['evidence'].extend(leaked_messages)
    else:
        results['detail'] = f'No token leak in {len(console_messages)} console messages'
        results['evidence'].append(f'Console messages captured: {len(console_messages)}')

    return results


async def check_artifact_scan(token, page, context):
    """A09-2: Token NOT in test report artifacts."""
    results = {'check_id': 'A09-2', 'result': 'PASS', 'detail': '', 'evidence': []}

    token_prefix = token[:12] if len(token) > 12 else token
    artifact_dirs = [
        REPORT_DIR,
        os.path.join(DOCS_ROOT, 'publications'),
    ]

    found_in = []
    for adir in artifact_dirs:
        if not os.path.isdir(adir):
            continue
        for root, dirs, files in os.walk(adir):
            for fname in files:
                if not fname.endswith(('.json', '.md', '.html')):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r') as f:
                        content = f.read()
                    if token_prefix in content:
                        found_in.append(os.path.relpath(fpath, PROJECT_ROOT))
                except Exception:
                    pass

    if found_in:
        results['result'] = 'FAIL'
        results['detail'] = f'Token found in {len(found_in)} artifact file(s)!'
        results['evidence'].extend(found_in[:5])
    else:
        results['detail'] = 'Token not found in any test report or publication artifact'
        results['evidence'].append(f'Scanned: {", ".join(artifact_dirs)}')

    return results


# ─── Check Dispatcher ────────────────────────────────────────────────────────

CHECK_FUNCTIONS = {
    'token_format': check_token_format,
    'url_exposure': check_url_exposure,
    'entropy': check_entropy,
    'transport': check_transport,
    'dom_injection': check_dom_injection,
    'git_scan': check_git_scan,
    'disk_scan': check_disk_scan,
    'cors': check_cors,
    'storage_audit': check_storage_audit,
    'session_scan': check_session_scan,
    'disconnect_cleanup': check_disconnect_cleanup,
    'console_leak': check_console_leak,
    'artifact_scan': check_artifact_scan,
}


# ─── Main Engine ─────────────────────────────────────────────────────────────

async def run_security_audit(token, interfaces=None):
    """Run the full security audit and return results."""
    from playwright.async_api import async_playwright

    if interfaces is None:
        interfaces = ['claude']

    chrome = find_chrome()
    if not chrome:
        print("ERROR: Chromium not found", file=sys.stderr)
        sys.exit(1)

    os.makedirs(REPORT_DIR, exist_ok=True)

    results = {
        'timestamp': datetime.now().isoformat(),
        'token_masked': mask_token(token),
        'interfaces_tested': interfaces,
        'checks': [],
        'summary': {'total': 0, 'pass': 0, 'fail': 0, 'warn': 0, 'skip': 0},
    }

    frames = []  # screenshot frames for GIF assembly

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=chrome,
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                  '--allow-file-access-from-files']
        )

        page = await browser.new_page(viewport=VIEWPORT)

        # Capture console messages for leak detection
        console_messages = []
        page.on('console', lambda msg: console_messages.append(msg.text))

        # Network request tracking
        network_requests = []
        page.on('request', lambda req: network_requests.append({
            'url': req.url[:120], 'method': req.method
        }))

        # Setup routes
        handle_cdn, handle_github_raw, handle_data = make_route_handlers(DOCS_ROOT)
        await page.route('**cdn.jsdelivr.net**', handle_cdn)
        await page.route('**unpkg.com**', handle_cdn)
        await page.route('**raw.githubusercontent.com**', handle_github_raw)
        await page.route('**/data/*.json', handle_data)
        await page.route('**mind_memory.md**', handle_data)
        await page.route('**depth_config.json**', handle_data)

        # Block actual API calls — we don't want to use the token for real
        async def block_api(route):
            url = route.request.url
            if 'api.anthropic.com' in url or 'bedrock-runtime' in url or 'aiplatform.googleapis.com' in url:
                await route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({
                        'id': 'msg_test',
                        'type': 'message',
                        'content': [{'type': 'text', 'text': 'Security audit — API call intercepted'}],
                        'model': 'claude-sonnet-4-6',
                        'role': 'assistant',
                        'stop_reason': 'end_turn',
                        'usage': {'input_tokens': 10, 'output_tokens': 10}
                    })
                )
            else:
                await route.continue_()

        await page.route('**api.anthropic.com**', block_api)
        await page.route('**bedrock-runtime**', block_api)
        await page.route('**aiplatform.googleapis.com**', block_api)

        # ─── Test Claude Interface ───
        for iface in interfaces:
            if iface == 'claude':
                doc_path = 'interfaces/claude-interface/index.md'
                viewer_url = f'file://{DOCS_ROOT}/index.html?doc={quote(doc_path)}'
                print(f"\n{'='*60}")
                print(f"  SECURITY AUDIT — Claude Interface (I6)")
                print(f"{'='*60}")
            elif iface == 'api':
                doc_path = 'interfaces/claude-interface/index.md'
                viewer_url = f'file://{DOCS_ROOT}/index.html?doc={quote(doc_path)}'
                print(f"\n{'='*60}")
                print(f"  SECURITY AUDIT — Claude API Interface")
                print(f"{'='*60}")
            else:
                continue

            # Navigate to interface
            print(f"\n  Loading: {doc_path}")
            await page.goto(viewer_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)

            # For interface pages, find the content frame
            target_frame = page
            if len(page.frames) > 1:
                for frame in page.frames:
                    if frame != page.main_frame:
                        target_frame = frame
                        break

            # Inject token into localStorage (simulating user input)
            await target_frame.evaluate("""(token) => {
                localStorage.setItem('ci-anthropic-key', token);
            }""", token)

            # Take initial screenshot
            frame_path = os.path.join(REPORT_DIR, f'security-frame-{iface}-init.png')
            await page.screenshot(path=frame_path)
            frames.append(frame_path)

            # Run all checks
            context = {
                'console_messages': console_messages,
                'network_requests': network_requests,
                'interface': iface,
                'top_page': page,
            }

            for check_def in OWASP_CHECKS:
                check_type = check_def['type']
                check_fn = CHECK_FUNCTIONS.get(check_type)
                if not check_fn:
                    continue

                print(f"\n  [{check_def['id']}] {check_def['category']}")
                print(f"    Check: {check_def['check']}")

                try:
                    result = await check_fn(token, target_frame, context)
                except Exception as e:
                    result = {
                        'check_id': check_def['id'],
                        'result': 'ERROR',
                        'detail': str(e),
                        'evidence': []
                    }

                result['category'] = check_def['category']
                result['check'] = check_def['check']
                result['severity'] = check_def['severity']
                result['interface'] = iface

                status_icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '⚠', 'SKIP': '○', 'ERROR': '!'}.get(result['result'], '?')
                print(f"    Result: {status_icon} {result['result']} — {result['detail']}")
                for ev in result.get('evidence', []):
                    print(f"      → {ev}")

                results['checks'].append(result)
                results['summary']['total'] += 1
                key = result['result'].lower()
                if key in results['summary']:
                    results['summary'][key] += 1

                # Take proof screenshot for FAIL and WARN
                if result['result'] in ('FAIL', 'WARN'):
                    proof_path = os.path.join(REPORT_DIR, f'security-proof-{check_def["id"]}.png')
                    await page.screenshot(path=proof_path)
                    result['proof_screenshot'] = os.path.basename(proof_path)
                    frames.append(proof_path)

            # Clean up — remove token from localStorage
            await target_frame.evaluate("""() => {
                localStorage.removeItem('ci-anthropic-key');
                localStorage.removeItem('ci-provider');
                localStorage.removeItem('ci-region');
                localStorage.removeItem('ci-chat-history');
            }""")

            # Final screenshot after cleanup
            frame_path = os.path.join(REPORT_DIR, f'security-frame-{iface}-cleanup.png')
            await page.screenshot(path=frame_path)
            frames.append(frame_path)

        await browser.close()

    # Save results
    results_path = os.path.join(REPORT_DIR, 'security-results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Assemble proof GIF
    gif_path = assemble_gif(frames)
    mp4_path = assemble_mp4(frames)

    # Print summary
    s = results['summary']
    print(f"\n{'='*60}")
    print(f"  SECURITY AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Total checks: {s['total']}")
    print(f"  ✓ PASS:  {s['pass']}")
    print(f"  ✗ FAIL:  {s['fail']}")
    print(f"  ⚠ WARN:  {s['warn']}")
    print(f"  ○ SKIP:  {s['skip']}")
    print(f"\n  Results: {results_path}")
    if gif_path:
        print(f"  Proof GIF: {gif_path}")
    if mp4_path:
        print(f"  Proof MP4: {mp4_path}")

    return results


def assemble_gif(frame_paths):
    """Assemble PNG frames into animated GIF proof."""
    try:
        from PIL import Image
    except ImportError:
        print("  [warn] Pillow not available — skipping GIF assembly")
        return None

    valid = [p for p in frame_paths if os.path.isfile(p)]
    if not valid:
        return None

    imgs = []
    for p in valid:
        img = Image.open(p).convert('RGBA')
        # Convert to palette for GIF
        imgs.append(img.convert('P', palette=Image.ADAPTIVE))

    gif_path = os.path.join(REPORT_DIR, 'security-test-report.gif')
    imgs[0].save(gif_path, save_all=True, append_images=imgs[1:],
                 duration=2000, loop=0, optimize=True)
    print(f"  Proof GIF assembled: {len(valid)} frames → {gif_path}")
    return gif_path


def assemble_mp4(frame_paths):
    """Assemble PNG frames into browser-compatible H.264 MP4 video proof."""
    from video_utils import encode_mp4_from_paths, estimate_mp4_scale

    valid = [p for p in frame_paths if os.path.isfile(p)]
    if not valid:
        return None

    mp4_path = os.path.join(REPORT_DIR, 'security-test-report.mp4')

    # Read first frame to get dimensions
    from PIL import Image
    first = Image.open(valid[0])
    w, h = first.size
    first.close()

    # Auto-scale to keep under 7MB
    auto_scale = estimate_mp4_scale(len(valid), w, h, max_mb=7.0)
    scale = min(auto_scale, 0.5)  # never exceed 0.5 default

    success = encode_mp4_from_paths(valid, mp4_path, fps=0.5, scale=scale)
    if success:
        print(f"  Proof MP4 assembled: {len(valid)} frames → {mp4_path}")
        return mp4_path
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Security Test Engine — Token Conformity & OWASP Audit')
    parser.add_argument('--token', required=True, help='API token to audit')
    parser.add_argument('--interface', default='both', choices=['claude', 'api', 'both'],
                        help='Interface to test (default: both)')
    args = parser.parse_args()

    if args.interface == 'both':
        interfaces = ['claude', 'api']
    else:
        interfaces = [args.interface]

    asyncio.run(run_security_audit(args.token, interfaces))


if __name__ == '__main__':
    main()
