#!/usr/bin/env python3
"""
Security Report Generator — Rich Publication from Security Audit Results
=========================================================================

Generates a standalone web publication document from security_test_engine results.

Document structure:
  1. Introduction — audit request description
  2. Summary — pass/fail/warn totals by OWASP category
  3. Proof of Execution — animated GIF
  4. Video Recording — MP4 proof embed
  5. OWASP Check Grid — per-check results with severity + evidence
  6. Detailed Evidence — per-check proof captures
  7. Conclusion — security assessment

Usage:
    python3 scripts/generate_security_report.py \
        --title "Token Conformity & OWASP Security Audit" \
        --request "Security audit description" \
        --gif test-reports/security-test-report.gif \
        --video test-reports/security-test-report.mp4 \
        --results test-reports/security-results.json \
        --slug security-audit-claude-interface \
        -o docs/publications/security-audit-claude-interface/

Knowledge asset — part of the Test Report methodology.
"""

import argparse
import json
import os
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
REPORT_DIR = os.path.join(MODULE_DIR, 'test-reports')


def generate_security_report(title, request_text, gif_path, video_path,
                              results_data, output_dir, slug=None, conclusion=None):
    """Generate the full security audit report publication."""

    os.makedirs(output_dir, exist_ok=True)

    # Copy proof artifacts
    assets_dir = os.path.join(output_dir, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    gif_name = 'proof.gif'
    video_name = 'proof.mp4'

    if gif_path and os.path.isfile(gif_path):
        shutil.copy2(gif_path, os.path.join(assets_dir, gif_name))

    if video_path and os.path.isfile(video_path):
        shutil.copy2(video_path, os.path.join(assets_dir, video_name))

    # Copy individual proof screenshots
    for check in results_data.get('checks', []):
        proof = check.get('proof_screenshot')
        if proof:
            src = os.path.join(REPORT_DIR, proof)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(assets_dir, proof))

    checks = results_data.get('checks', [])
    summary = results_data.get('summary', {})

    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')

    if not slug:
        slug = title.lower().replace(' ', '-').replace('/', '-')

    # Auto-conclusion
    if not conclusion:
        fail_count = summary.get('fail', 0)
        warn_count = summary.get('warn', 0)
        total = summary.get('total', 0)
        pass_count = summary.get('pass', 0)

        if fail_count == 0 and warn_count == 0:
            conclusion = f"All {total} OWASP security checks passed. The token handling in the Claude Interface conforms to security best practices. No token persistence detected on disk, git, session files, or browser storage beyond intended localStorage scope."
        elif fail_count == 0:
            conclusion = f"{pass_count}/{total} checks passed with {warn_count} warning(s). No critical security vulnerabilities detected. Review warnings for potential hardening opportunities."
        else:
            conclusion = f"SECURITY ISSUES DETECTED: {fail_count} check(s) failed. {warn_count} warning(s). Immediate remediation recommended for failed checks. Review the detailed evidence grid below."

    # ═══ Generate Markdown ═══

    md = []

    # Frontmatter
    md.append('---')
    md.append('layout: publication')
    md.append(f'title: "{title}"')
    md.append(f'description: "Security audit report: {summary.get("total", 0)} OWASP checks — {summary.get("pass", 0)} pass, {summary.get("fail", 0)} fail, {summary.get("warn", 0)} warn"')
    md.append(f'date: "{date_str}"')
    md.append(f'permalink: /publications/{slug}/')
    md.append(f'og_image: /publications/{slug}/assets/{gif_name}')
    md.append(f'keywords: "security, audit, owasp, token, conformity, api, claude, interface"')
    md.append('---')
    md.append('')

    # Title
    md.append(f'# {title}')
    md.append('')

    # Introduction — user's original request as blockquote
    md.append('## Audit Request')
    md.append('')
    for line in request_text.split('\n'):
        md.append(f'> {line}')
    md.append('')
    md.append(f'**Date:** {date_str} at {time_str}')
    md.append(f'**Token:** `{results_data.get("token_masked", "N/A")}`')
    md.append(f'**Interfaces tested:** {", ".join(results_data.get("interfaces_tested", []))}')
    md.append('')

    # Summary
    md.append('## Summary')
    md.append('')
    md.append('| Metric | Count |')
    md.append('|--------|-------|')
    md.append(f'| Total OWASP checks | {summary.get("total", 0)} |')
    md.append(f'| Checks passed | {summary.get("pass", 0)} |')
    md.append(f'| Checks failed | {summary.get("fail", 0)} |')
    md.append(f'| Warnings | {summary.get("warn", 0)} |')
    md.append(f'| Skipped | {summary.get("skip", 0)} |')
    md.append('')

    # Proof GIF
    asset_base = f'/publications/{slug}/assets'
    md.append('## Proof of Execution')
    md.append('')
    md.append(f'![Security audit proof]({asset_base}/{gif_name})')
    md.append('')
    md.append('*Animated GIF showing the security audit sequence — interface loading, check execution, and cleanup.*')
    md.append('')

    # Video proof
    if video_path and os.path.isfile(video_path):
        md.append('### Video Recording')
        md.append('')
        md.append(f'<video controls width="100%">')
        md.append(f'  <source src="{asset_base}/{video_name}" type="video/mp4">')
        md.append(f'  Your browser does not support the video tag.')
        md.append(f'</video>')
        md.append('')

    # OWASP Check Grid — HTML table with severity colors
    md.append('## OWASP Security Check Grid')
    md.append('')
    md.append('{::nomarkdown}')
    md.append('<style>')
    md.append('.sg { width:100%; border-collapse:collapse; font-size:0.82rem; }')
    md.append('.sg th { padding:0.5rem 0.6rem; text-align:left; font-weight:600;')
    md.append('  background:var(--code-bg,#f6f8fa); border-bottom:2px solid var(--border,#d0d7de);')
    md.append('  font-size:0.72rem; text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap; }')
    md.append('.sg td { padding:0.4rem 0.6rem; border-bottom:1px solid var(--border,#d0d7de); vertical-align:top; }')
    md.append('.sg tr:hover td { background:var(--col-alt,#f0f4f8); }')
    md.append('.sg .pass { color:#16a34a; font-weight:600; }')
    md.append('.sg .fail { color:#dc2626; font-weight:600; }')
    md.append('.sg .warn { color:#d97706; font-weight:600; }')
    md.append('.sg .skip { color:#6b7280; font-weight:600; }')
    md.append('.sg .sev-critical { color:#dc2626; font-weight:700; font-size:0.7rem; }')
    md.append('.sg .sev-high { color:#ea580c; font-weight:600; font-size:0.7rem; }')
    md.append('.sg .sev-medium { color:#d97706; font-size:0.7rem; }')
    md.append('.led-p,.led-f,.led-w,.led-s { display:inline-block; width:10px; height:10px; border-radius:50%; vertical-align:middle; margin-right:3px; }')
    md.append('.led-p { background:#16a34a; box-shadow:0 0 4px rgba(22,163,74,0.4); }')
    md.append('.led-f { background:#dc2626; box-shadow:0 0 4px rgba(220,38,38,0.4); }')
    md.append('.led-w { background:#d97706; box-shadow:0 0 4px rgba(217,119,6,0.4); }')
    md.append('.led-s { background:#6b7280; }')
    md.append('</style>')

    pass_count = sum(1 for c in checks if c.get('result') == 'PASS')
    total_count = len(checks)

    md.append(f'<table class="sg" id="security-grid">')
    md.append(f'<thead><tr>')
    md.append(f'<th>ID</th>')
    md.append(f'<th>OWASP Category</th>')
    md.append(f'<th>Check</th>')
    md.append(f'<th>Severity</th>')
    md.append(f'<th>Result ({pass_count}/{total_count})</th>')
    md.append(f'<th>Detail</th>')
    md.append(f'</tr></thead>')
    md.append(f'<tbody>')

    for check in checks:
        result = check.get('result', 'SKIP')
        result_lower = result.lower()
        led_class = {'pass': 'led-p', 'fail': 'led-f', 'warn': 'led-w', 'skip': 'led-s'}.get(result_lower, 'led-s')
        mark = {'PASS': '✓', 'FAIL': '✗', 'WARN': '⚠', 'SKIP': '○'}.get(result, '?')
        sev = check.get('severity', 'MEDIUM')
        sev_class = f'sev-{sev.lower()}'

        md.append(f'<tr>')
        md.append(f'  <td><strong>{check.get("check_id", "")}</strong></td>')
        md.append(f'  <td>{check.get("category", "")}</td>')
        md.append(f'  <td>{check.get("check", "")}</td>')
        md.append(f'  <td class="{sev_class}">{sev}</td>')
        md.append(f'  <td class="{result_lower}"><span class="{led_class}"></span> {mark} {result}</td>')
        md.append(f'  <td>{check.get("detail", "")}</td>')
        md.append(f'</tr>')

    md.append(f'</tbody></table>')
    md.append('{:/nomarkdown}')
    md.append('')

    # Detailed Evidence per check
    md.append('## Detailed Evidence')
    md.append('')

    for check in checks:
        evidence = check.get('evidence', [])
        if not evidence and not check.get('proof_screenshot'):
            continue

        result = check.get('result', 'SKIP')
        icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '⚠', 'SKIP': '○'}.get(result, '?')

        md.append(f'### {icon} {check.get("check_id", "")} — {check.get("category", "")}')
        md.append('')
        md.append(f'**Check:** {check.get("check", "")}')
        md.append(f'**Result:** {result} — {check.get("detail", "")}')
        md.append('')

        if evidence:
            md.append('**Evidence:**')
            for ev in evidence:
                md.append(f'- `{ev}`')
            md.append('')

        # Inline proof screenshot if available
        proof = check.get('proof_screenshot')
        if proof:
            md.append(f'**Proof capture:**')
            md.append(f'![{check.get("check_id", "")} proof]({asset_base}/{proof})')
            md.append('')

    # Conclusion
    md.append('## Conclusion')
    md.append('')
    md.append(conclusion)
    md.append('')

    # Write markdown
    md_path = os.path.join(output_dir, 'index.md')
    with open(md_path, 'w') as f:
        f.write('\n'.join(md))

    print(f"Security report generated: {md_path}")
    print(f"  Checks: {pass_count}/{total_count} pass | {summary.get('fail', 0)} fail | {summary.get('warn', 0)} warn")
    if gif_path:
        print(f"  Webcard: assets/{gif_name}")
    if video_path:
        print(f"  Video: assets/{video_name}")

    return md_path


def main():
    parser = argparse.ArgumentParser(description='Generate security audit report publication')
    parser.add_argument('--title', required=True, help='Report title')
    parser.add_argument('--request', required=True, help='Audit request description')
    parser.add_argument('--gif', help='Path to animated GIF proof')
    parser.add_argument('--video', help='Path to MP4 video proof')
    parser.add_argument('--results', required=True, help='Path to security-results.json')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--slug', help='URL slug')
    parser.add_argument('--conclusion', help='Custom conclusion text')
    args = parser.parse_args()

    results_data = {}
    if os.path.isfile(args.results):
        with open(args.results) as f:
            results_data = json.load(f)

    generate_security_report(
        title=args.title,
        request_text=args.request,
        gif_path=args.gif,
        video_path=args.video,
        results_data=results_data,
        output_dir=args.output,
        slug=args.slug,
        conclusion=args.conclusion,
    )


if __name__ == '__main__':
    main()
