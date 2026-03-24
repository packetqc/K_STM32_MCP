#!/usr/bin/env python3
"""
Test Report Generator — Rich Publication from Test Results
==========================================================

Generates a standalone web publication document from web_test_engine results.

Document structure:
  1. Run History Tab Bar (if multiple runs exist)
  2. Introduction — test request description
  3. Summary — pass/fail/skip totals
  4. Animated GIF — inline proof (also used as webcard)
  5. Video — MP4 proof embed
  6. Results Grid — pages + detailed tables
  7. Conclusion — assessment

Runs are split by file: assets/runs.json holds a summary index with filesystem
references, while full run data lives in assets/runs/run-N.json. Historical
runs are rendered as additional tab panels so the user can browse past results.

Usage:
    python3 scripts/generate_test_report.py \\
        --title "Main Navigator Full Test" \\
        --request "Full detailed test on main navigator interface" \\
        --gif test-reports/test-report.gif \\
        --video test-reports/test-report.mp4 \\
        --results test-reports/results.json \\
        --output docs/publications/test-main-navigator/

Knowledge asset — part of the Test Report methodology.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from urllib.parse import quote as _q

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

MAX_RUNS = 10  # Keep at most 10 runs in runs.json


# ═══════════════════════════════════════════════════════════════════════
# Runs Management
# ═══════════════════════════════════════════════════════════════════════

def load_runs(assets_dir):
    """Load runs from split format (index + per-run files) or legacy flat list.

    Split format: runs.json is an index with 'file' keys pointing to runs/run-N.json.
    Legacy format: runs.json is a flat list of full run objects (auto-migrated on save).
    """
    runs_path = os.path.join(assets_dir, 'runs.json')
    if not os.path.isfile(runs_path):
        return []
    try:
        with open(runs_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []
    if not data:
        return []

    # Detect format: index entries have 'file' key, full runs have 'default'/'detailed'
    if isinstance(data[0], dict) and 'file' in data[0] and 'default' not in data[0]:
        # Split format — load each run from its file
        runs = []
        for entry in data:
            run_file = os.path.join(assets_dir, entry['file'])
            if os.path.isfile(run_file):
                with open(run_file) as f:
                    runs.append(json.load(f))
            else:
                # Fallback: use index entry as-is (missing detail)
                runs.append(entry)
        return runs
    else:
        # Legacy flat format
        return data


def save_runs(assets_dir, runs):
    """Save runs in split format: index in runs.json, full data in runs/run-N.json."""
    runs = runs[-MAX_RUNS:]
    runs_dir = os.path.join(assets_dir, 'runs')
    os.makedirs(runs_dir, exist_ok=True)

    index = []
    for i, run in enumerate(runs):
        run_num = i + 1
        filename = f'run-{run_num}.json'
        filepath = os.path.join(runs_dir, filename)

        # Write individual run file
        with open(filepath, 'w') as f:
            json.dump(run, f, indent=2, ensure_ascii=False)

        # Build index entry with filesystem reference
        index.append({
            'run': run_num,
            'timestamp': run.get('timestamp', ''),
            'mode': run.get('mode', ''),
            'request_text': run.get('request_text', ''),
            'total': run.get('total', 0),
            'passed': run.get('passed', 0),
            'failed': run.get('failed', 0),
            'widgets_total': run.get('widgets_total', 0),
            'widgets_passed': run.get('widgets_passed', 0),
            'widgets_failed': run.get('widgets_failed', 0),
            'widgets_skipped': run.get('widgets_skipped', 0),
            'file': f'runs/{filename}',
        })

    runs_path = os.path.join(assets_dir, 'runs.json')
    with open(runs_path, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    return runs


# ═══════════════════════════════════════════════════════════════════════
# HTML Generation Helpers
# ═══════════════════════════════════════════════════════════════════════

def _esc(text):
    """Escape HTML entities."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _find_check_snapshots(assets_dir):
    """Find check snapshot PNGs in assets directory."""
    checks_dir = os.path.join(assets_dir, 'checks')
    if not os.path.isdir(checks_dir):
        return []
    snaps = sorted(f for f in os.listdir(checks_dir) if f.endswith('_snapshot.png'))
    return [f'checks/{s}' for s in snaps]


def render_summary_table(run):
    """Render a summary stats table from run data."""
    h = []
    h.append('<table class="tg-summary">')
    h.append('<thead><tr><th>Metric</th><th>Count</th></tr></thead>')
    h.append('<tbody>')
    h.append(f'<tr><td>Pages tested</td><td>{run["total"]}</td></tr>')
    h.append(f'<tr><td>Pages passed</td><td>{run["passed"]}</td></tr>')
    h.append(f'<tr><td>Pages failed</td><td>{run["failed"]}</td></tr>')
    wt = run.get('widgets_total', 0)
    if wt > 0:
        h.append(f'<tr><td>Widgets scanned</td><td>{wt}</td></tr>')
        h.append(f'<tr><td>Widgets passed</td><td>{run.get("widgets_passed", 0)}</td></tr>')
        h.append(f'<tr><td>Widgets failed</td><td>{run.get("widgets_failed", 0)}</td></tr>')
        h.append(f'<tr><td>Widgets skipped</td><td>{run.get("widgets_skipped", 0)}</td></tr>')
    h.append('</tbody></table>')
    return '\n'.join(h)


def render_test_grid(default_results, passed, total, grid_id='test-grid'):
    """Render the sortable test grid table."""
    h = []
    h.append(f'<table class="tg" id="{grid_id}">')
    h.append('<thead><tr>')
    h.append('<th data-col="0">#</th>')
    h.append('<th data-col="1">Section</th>')
    h.append('<th data-col="2">Target</th>')
    h.append('<th data-col="3">Panel</th>')
    h.append(f'<th data-col="4">Result ({passed}/{total})</th>')
    h.append('</tr></thead>')
    h.append('<tbody>')

    for r in default_results:
        result_class = 'pass' if r.get('result') == 'PASS' else 'fail'
        mark = '<span class="led-p"></span> ✓' if r.get('result') == 'PASS' else '<span class="led-f"></span> ✗'
        doc = r.get('doc', '')
        if doc:
            page_url = f"/index.html?doc={_q(doc)}"
            target_cell = f'<a href="{page_url}" target="content-frame">{_esc(r["target"])}</a>'
        else:
            target_cell = _esc(r['target'])
        error = r.get('error', '')
        error_attr = f' title="{_esc(error)}"' if error else ''
        h.append('<tr>')
        h.append(f'  <td>{r["num"]}</td>')
        h.append(f'  <td>{_esc(r["phase"])}</td>')
        h.append(f'  <td>{target_cell}</td>')
        h.append(f'  <td>{_esc(r["panel"])}</td>')
        h.append(f'  <td class="{result_class}"{error_attr}>{mark} {r["result"]}</td>')
        h.append('</tr>')

    h.append('</tbody></table>')
    return '\n'.join(h)


def render_detailed_widgets(detailed_results):
    """Render detailed widget test tables as HTML."""
    if not detailed_results:
        return ''
    h = []
    h.append('<h2>Detailed Widget Tests</h2>')

    # Summary table
    h.append('<table class="tg-summary">')
    h.append('<thead><tr><th>Page</th><th>Pass</th><th>Fail</th><th>Skip</th><th>Total</th></tr></thead>')
    h.append('<tbody>')
    for page in detailed_results:
        widgets = page.get('widgets', [])
        p = sum(1 for w in widgets if w.get('result') == 'PASS')
        f = sum(1 for w in widgets if w.get('result') == 'FAIL')
        s = sum(1 for w in widgets if w.get('result') == 'SKIP')
        h.append(f'<tr><td>{_esc(page["page"])}</td><td>{p}</td><td>{f}</td><td>{s}</td><td>{len(widgets)}</td></tr>')
    h.append('</tbody></table>')

    # Per-page tables
    for page in detailed_results:
        widgets = page.get('widgets', [])
        if not widgets:
            continue
        h.append(f'<h3>{_esc(page["page"])}</h3>')
        h.append('<table class="tg-summary">')
        h.append('<thead><tr><th>#</th><th>Type</th><th>Widget</th><th>Result</th><th>Detail</th></tr></thead>')
        h.append('<tbody>')
        for i, w in enumerate(widgets):
            mark = '✓' if w.get('result') == 'PASS' else ('○' if w.get('result') == 'SKIP' else '✗')
            detail = _esc(w.get('detail', ''))
            label = _esc(w['label'])
            if w['type'] == 'link' and w.get('detail', '').startswith('href='):
                href = w['detail'][5:]
                label = f'<a href="{_esc(href)}">{_esc(w["label"])}</a>'
                detail = ''
            h.append(f'<tr><td>{i+1}</td><td>{_esc(w["type"])}</td><td>{label}</td><td>{mark} {w["result"]}</td><td>{detail}</td></tr>')
        h.append('</tbody></table>')

    return '\n'.join(h)


# ═══════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════

REPORT_CSS = """
/* ═══ Run Tab Bar ═══ */
.run-tab-bar {
  display: flex; align-items: center; gap: 0;
  background: var(--code-bg, #f6f8fa);
  border-bottom: 2px solid var(--border, #d0d7de);
  padding: 0 0.25rem; min-height: 36px;
  overflow-x: auto; overflow-y: hidden;
  scrollbar-width: thin; margin-bottom: 1rem;
}
.run-tab-bar::-webkit-scrollbar { height: 3px; }
.run-tab-bar::-webkit-scrollbar-thumb { background: var(--border, #d0d7de); border-radius: 3px; }
.run-tab {
  display: flex; flex-direction: column; align-items: center;
  padding: 0.4rem 0.7rem; font-size: 0.72rem; font-weight: 500;
  color: var(--muted, #656d76); background: transparent;
  border: 1px solid transparent; border-bottom: none;
  border-radius: 6px 6px 0 0; cursor: pointer;
  white-space: nowrap; position: relative;
  transition: background 0.15s, color 0.15s;
  margin-bottom: -2px;
}
.run-tab:hover { background: var(--bg, #fff); color: var(--fg, #24292f); }
.run-tab.active {
  background: var(--bg, #fff); color: var(--fg, #24292f);
  border-color: var(--border, #d0d7de);
  font-weight: 600; z-index: 1;
}
.run-tab-label { font-weight: inherit; }
.run-tab-date { font-size: 0.6rem; color: var(--muted, #656d76); }
.run-tab .run-led {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; margin-right: 4px; vertical-align: middle;
}
.run-led-green { background: #16a34a; box-shadow: 0 0 3px rgba(22,163,74,0.4); }
.run-led-red { background: #dc2626; box-shadow: 0 0 3px rgba(220,38,38,0.4); }
.run-led-yellow { background: #d97706; box-shadow: 0 0 3px rgba(217,119,6,0.3); }

/* ═══ Run Panels ═══ */
.run-panel { display: none; }
.run-panel.active { display: block; }

/* ═══ Grid ═══ */
.tg { width:100%; border-collapse:collapse; font-size:0.85rem; }
.tg th { cursor:pointer; user-select:none; padding:0.5rem 0.6rem; text-align:left; font-weight:600;
  background:var(--code-bg,#f6f8fa); border-bottom:2px solid var(--border,#d0d7de);
  font-size:0.75rem; text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap; }
.tg th:hover { color:var(--accent,#1d4ed8); }
.tg th::after { content:" ⇅"; font-size:0.6rem; color:var(--muted,#656d76); }
.tg th.asc::after { content:" ▲"; color:var(--accent,#1d4ed8); }
.tg th.desc::after { content:" ▼"; color:var(--accent,#1d4ed8); }
.tg td { padding:0.4rem 0.6rem; border-bottom:1px solid var(--border,#d0d7de); }
.tg tr:hover td { background:var(--col-alt,#f0f4f8); }
.tg .pass { color:#16a34a; font-weight:600; }
.tg .fail { color:#dc2626; font-weight:600; }
.tg a { color:var(--accent,#1d4ed8); text-decoration:none; }
.tg a:hover { text-decoration:underline; }
.led-p,.led-f { display:inline-block; width:10px; height:10px; border-radius:50%; vertical-align:middle; margin-right:3px; }
.led-p { background:#16a34a; box-shadow:0 0 4px rgba(22,163,74,0.4); }
.led-f { background:#dc2626; box-shadow:0 0 4px rgba(220,38,38,0.4); }

/* ═══ Summary Table ═══ */
.tg-summary { width:100%; border-collapse:collapse; font-size:0.85rem; margin-bottom:1rem; }
.tg-summary th { padding:0.5rem 0.6rem; text-align:left; font-weight:600;
  background:var(--code-bg,#f6f8fa); border-bottom:2px solid var(--border,#d0d7de);
  font-size:0.75rem; text-transform:uppercase; }
.tg-summary td { padding:0.4rem 0.6rem; border-bottom:1px solid var(--border,#d0d7de); }
.tg-summary tr:hover td { background:var(--col-alt,#f0f4f8); }

/* ═══ Original Request Collapsible ═══ */
.original-request { margin: 0.5rem 0 1rem 0; }
.original-request summary {
  cursor: pointer; font-size: 0.8rem; font-weight: 500;
  color: var(--muted, #656d76); padding: 0.3rem 0;
  user-select: none;
}
.original-request summary:hover { color: var(--accent, #1d4ed8); }
.original-request blockquote {
  margin: 0.5rem 0; padding: 0.5rem 1rem;
  border-left: 3px solid var(--border, #d0d7de);
  background: var(--code-bg, #f6f8fa);
  font-size: 0.85rem; color: var(--fg, #24292f);
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Tab Switching JS
# ═══════════════════════════════════════════════════════════════════════

SORT_JS = """
(function(){
  document.querySelectorAll('.tg').forEach(function(tbl){
    var headers=tbl.querySelectorAll('th[data-col]');
    var sortState={};
    headers.forEach(function(th){
      th.addEventListener('click',function(){
        var col=parseInt(th.dataset.col);
        var dir=sortState[col]==='asc'?'desc':'asc';
        sortState={};sortState[col]=dir;
        headers.forEach(function(h){h.classList.remove('asc','desc');});
        th.classList.add(dir);
        var tbody=tbl.querySelector('tbody');
        var rows=[].slice.call(tbody.querySelectorAll('tr'));
        rows.sort(function(a,b){
          var av=a.children[col].textContent.trim();
          var bv=b.children[col].textContent.trim();
          if(col===0){av=parseInt(av);bv=parseInt(bv);}
          if(av<bv)return dir==='asc'?-1:1;
          if(av>bv)return dir==='asc'?1:-1;
          return 0;
        });
        rows.forEach(function(r){tbody.appendChild(r);});
      });
    });
  });
})();
"""

TAB_JS = """
(function(){
  var bar=document.querySelector('.run-tab-bar');
  if(!bar)return;
  bar.addEventListener('click',function(e){
    var tab=e.target.closest('.run-tab');
    if(!tab)return;
    var runId=tab.getAttribute('data-run');
    bar.querySelectorAll('.run-tab').forEach(function(t){t.classList.remove('active');});
    document.querySelectorAll('.run-panel').forEach(function(p){p.classList.remove('active');});
    tab.classList.add('active');
    var panel=document.querySelector('.run-panel[data-run="'+runId+'"]');
    if(panel)panel.classList.add('active');
  });
})();
"""


# ═══════════════════════════════════════════════════════════════════════
# Main Generator
# ═══════════════════════════════════════════════════════════════════════

def generate_report(title, request_text, gif_path, video_path,
                    default_results, detailed_results, output_dir,
                    slug=None, pub_number=None, conclusion=None,
                    mode=None, timestamp=None, original_request=None):
    """Generate the full test report publication with run history tabs.

    original_request: verbatim user request that initiated the test.
    Rendered as a collapsible block under the synthesized test description.
    """

    os.makedirs(output_dir, exist_ok=True)

    # Copy proof artifacts
    assets_dir = os.path.join(output_dir, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    gif_name = 'proof.gif'
    video_name = 'proof.mp4'

    has_gif = gif_path and os.path.isfile(gif_path)
    has_video = video_path and os.path.isfile(video_path)

    if has_gif:
        shutil.copy2(gif_path, os.path.join(assets_dir, gif_name))
    if has_video:
        shutil.copy2(video_path, os.path.join(assets_dir, video_name))

    # Calculate totals
    total_pages = len(default_results)
    pages_passed = sum(1 for r in default_results if r.get('result') == 'PASS')
    pages_failed = total_pages - pages_passed

    total_widgets = 0
    widgets_passed = 0
    widgets_failed = 0
    widgets_skipped = 0
    for page_detail in detailed_results:
        for w in page_detail.get('widgets', []):
            total_widgets += 1
            if w.get('result') == 'PASS':
                widgets_passed += 1
            elif w.get('result') == 'FAIL':
                widgets_failed += 1
            else:
                widgets_skipped += 1

    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    if not timestamp:
        timestamp = now.isoformat()
    if not mode:
        mode = 'TARGETED'

    if not slug:
        slug = title.lower().replace(' ', '-').replace('/', '-')

    # Auto-conclusion
    if not conclusion:
        if pages_failed == 0 and widgets_failed == 0:
            conclusion = (f"All {total_pages} pages loaded successfully. "
                         f"{widgets_passed} interactive widgets tested with 0 failures "
                         f"across {total_widgets} total widgets scanned. "
                         f"The interface is fully functional.")
        else:
            conclusion = (f"{pages_failed} page(s) failed to load. "
                         f"{widgets_failed} widget(s) failed interaction tests. "
                         f"Review the detailed grid below for specific failures requiring attention.")

    # ═══ Manage runs.json ═══
    runs = load_runs(assets_dir)
    new_run = {
        'timestamp': timestamp,
        'mode': mode,
        'request_text': request_text,
        'original_request': original_request,
        'total': total_pages,
        'passed': pages_passed,
        'failed': pages_failed,
        'widgets_total': total_widgets,
        'widgets_passed': widgets_passed,
        'widgets_failed': widgets_failed,
        'widgets_skipped': widgets_skipped,
        'default': default_results,
        'detailed': detailed_results,
    }
    runs.append(new_run)
    runs = save_runs(assets_dir, runs)

    asset_base = f'/publications/{slug}/assets'

    # ═══ Generate Full HTML Report ═══
    md = []

    # Frontmatter (YAML — processed by Jekyll)
    md.append('---')
    md.append('layout: publication')
    md.append(f'title: "{title}"')
    md.append(f'description: "Test report: {total_pages} pages, {total_widgets} widgets — {pages_passed}/{total_pages} pages pass, {widgets_passed}/{total_widgets} widgets pass"')
    if pub_number:
        md.append(f'pub_id: "#{pub_number} {title}"')
    md.append(f'date: "{date_str}"')
    md.append(f'permalink: /publications/{slug}/')
    md.append(f'og_image: /publications/{slug}/assets/{gif_name}')
    md.append(f'keywords: "test, report, qa, validation, web, interface"')
    md.append('---')
    md.append('')

    # Title (markdown — rendered by Jekyll)
    md.append(f'# {title}')
    md.append('')

    # Everything below is HTML in a single {::nomarkdown} block
    md.append('{::nomarkdown}')
    md.append(f'<style>{REPORT_CSS}</style>')

    # ─── Tab Bar (always shown — fixed set of run iteration tabs) ───
    md.append('<div class="run-tab-bar">')
    # Reverse order: latest first
    for i, run in enumerate(reversed(runs)):
        run_idx = len(runs) - 1 - i
        is_latest = (run_idx == len(runs) - 1)
        active = ' active' if is_latest else ''
        p = run.get('passed', 0)
        t = run.get('total', 0)
        f = run.get('failed', 0)
        pct = round(100 * p / t) if t > 0 else 0
        led_class = 'run-led-green' if f == 0 else ('run-led-yellow' if pct >= 80 else 'run-led-red')
        ts = run.get('timestamp', '')[:16].replace('T', ' ')
        label = 'Latest' if is_latest else f'Run {run_idx + 1}'
        md.append(f'<div class="run-tab{active}" data-run="{run_idx}">')
        md.append(f'  <span class="run-tab-label"><span class="run-led {led_class}"></span>{label} — {p}/{t}</span>')
        md.append(f'  <span class="run-tab-date">{ts}</span>')
        md.append('</div>')
    md.append('</div>')

    # ─── Latest Run Panel ───
    latest_idx = len(runs) - 1
    md.append(f'<div class="run-panel active" data-run="{latest_idx}">')

    # Test Request — synthesized description + collapsible original request
    md.append('<h2>Test Request</h2>')
    md.append(f'<blockquote><p>{_esc(request_text)}</p></blockquote>')
    if original_request:
        md.append('<details class="original-request">')
        md.append('<summary>Original Test Request</summary>')
        md.append(f'<blockquote><p>{_esc(original_request)}</p></blockquote>')
        md.append('</details>')
    md.append(f'<p><strong>Date:</strong> {date_str} at {time_str}</p>')

    # Summary
    md.append('<h2>Summary</h2>')
    md.append(render_summary_table(new_run))

    # Proof of Completion — animated GIF + video (built from check snapshots)
    if has_gif or has_video:
        md.append('<h2>Proof of Completion</h2>')
        md.append('<p><em>Each frame shows the full check evidence: test title &amp; description → annotated screenshot → pass/fail result with conclusion.</em></p>')

    if has_gif:
        md.append('<h3>Animated Test Sequence</h3>')
        md.append(f'<p><img src="{asset_base}/{gif_name}" alt="Test execution proof — animated check snapshots" style="max-width:100%;"></p>')

    if has_video:
        md.append('<h3>Video Recording</h3>')
        md.append(f'<video controls width="100%">')
        md.append(f'  <source src="{asset_base}/{video_name}" type="video/mp4">')
        md.append(f'  Your browser does not support the video tag.')
        md.append(f'</video>')

    if not has_gif and not has_video:
        md.append('<h2>Proof of Completion</h2>')
        md.append('<p><em>No proof artifacts available for this run. Re-run the test to generate animated GIF and video proof.</em></p>')

    # Pages Test Grid
    md.append('<h2>Pages Test Grid</h2>')
    md.append(render_test_grid(default_results, pages_passed, total_pages,
                               grid_id=f'test-grid-{latest_idx}'))

    # Check Validation Snapshots
    check_snapshots = _find_check_snapshots(assets_dir)
    if check_snapshots:
        md.append('<h2>Check Validation Snapshots</h2>')
        md.append('<p><em>Each check shows: header (test + check info) → evidence (annotated screenshot) → result (status + conclusion).</em></p>')
        for snap_name in check_snapshots:
            snap_url = f'{asset_base}/{snap_name}'
            md.append(f'<details><summary>{_esc(snap_name.replace("_snapshot.png", "").replace("_", " ").title())}</summary>')
            md.append(f'<p><img src="{snap_url}" alt="{_esc(snap_name)}" style="max-width:100%;"></p>')
            md.append('</details>')

    # Detailed Widget Tests
    md.append(render_detailed_widgets(detailed_results))

    # Conclusion
    md.append('<h2>Conclusion</h2>')
    md.append(f'<p>{_esc(conclusion)}</p>')

    md.append('</div>')  # end latest run panel

    # ─── Historical Run Panels ───
    for run_idx in range(len(runs) - 2, -1, -1):
        run = runs[run_idx]
        ts = run.get('timestamp', '')[:16].replace('T', ' ')
        run_mode = run.get('mode', 'TARGETED')
        rp = run.get('passed', 0)
        rt = run.get('total', 0)

        md.append(f'<div class="run-panel" data-run="{run_idx}">')
        md.append(f'<h2>Run {run_idx + 1} — {run_mode}</h2>')
        md.append(f'<p><strong>Date:</strong> {ts} &nbsp; | &nbsp; <strong>Mode:</strong> {_esc(run_mode)}</p>')

        # Historical run request (if stored)
        hist_request = run.get('request_text', '')
        hist_original = run.get('original_request', '')
        if hist_request:
            md.append(f'<blockquote><p>{_esc(hist_request)}</p></blockquote>')
            if hist_original:
                md.append('<details class="original-request">')
                md.append('<summary>Original Test Request</summary>')
                md.append(f'<blockquote><p>{_esc(hist_original)}</p></blockquote>')
                md.append('</details>')

        # Summary
        md.append('<h3>Summary</h3>')
        md.append(render_summary_table(run))

        # Grid (from stored results)
        run_default = run.get('default', [])
        if run_default:
            md.append('<h3>Test Grid</h3>')
            md.append(render_test_grid(run_default, rp, rt,
                                       grid_id=f'test-grid-{run_idx}'))

        # Detailed widgets (from stored results)
        run_detailed = run.get('detailed', [])
        if run_detailed:
            md.append(render_detailed_widgets(run_detailed))

        md.append('</div>')  # end historical panel

    # ─── Scripts ───
    md.append(f'<script>{SORT_JS}</script>')
    if len(runs) > 1:
        md.append(f'<script>{TAB_JS}</script>')

    md.append('{:/nomarkdown}')
    md.append('')

    # Write markdown
    md_path = os.path.join(output_dir, 'index.md')
    with open(md_path, 'w') as f:
        f.write('\n'.join(md))

    print(f"Test report generated: {md_path}")
    print(f"  Pages: {pages_passed}/{total_pages} | Widgets: {widgets_passed}/{total_widgets}")
    print(f"  Runs: {len(runs)} stored in assets/runs.json")
    if has_gif:
        print(f"  Webcard: assets/{gif_name}")
    if has_video:
        print(f"  Video: assets/{video_name}")

    return md_path


def _load_test_module(module_name):
    """Load a rerunnable test module from interactions/tests/."""
    import importlib.util
    mod_path = os.path.join(SCRIPT_DIR, 'interactions', 'tests', f'{module_name}.py')
    if not os.path.isfile(mod_path):
        print(f"ERROR: module '{module_name}' not found in interactions/tests/")
        return None
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, 'get_test_config'):
        return mod.get_test_config()
    return {
        'test_id': getattr(mod, 'TEST_ID', module_name),
        'title': getattr(mod, 'TITLE', module_name),
        'slug': getattr(mod, 'SLUG', module_name),
        'output_dir': getattr(mod, 'OUTPUT_DIR', ''),
        'request': getattr(mod, 'REQUEST', ''),
        'original_request': getattr(mod, 'ORIGINAL_REQUEST', ''),
    }


def main():
    parser = argparse.ArgumentParser(description='Generate test report publication')
    parser.add_argument('--title', help='Report title')
    parser.add_argument('--request', help='Test request description (falls back to results.json request_text)')
    parser.add_argument('--gif', help='Path to animated GIF proof')
    parser.add_argument('--video', help='Path to MP4 video proof')
    parser.add_argument('--results', help='Path to results JSON (from web_test_engine)')
    parser.add_argument('--output', '-o', help='Output directory for publication')
    parser.add_argument('--slug', help='URL slug (auto-generated from title if omitted)')
    parser.add_argument('--pub-number', help='Publication number (e.g. 28)')
    parser.add_argument('--conclusion', help='Custom conclusion text')
    parser.add_argument('--original-request', help='Verbatim user request that initiated the test')
    parser.add_argument('--module', help='Load config from rerunnable test module in interactions/tests/')
    args = parser.parse_args()

    # Module mode — load all config from module
    if args.module:
        cfg = _load_test_module(args.module)
        if not cfg:
            return
        if not args.title:
            args.title = cfg.get('title', args.module)
        if not args.slug:
            args.slug = cfg.get('slug')
        if not args.output:
            args.output = cfg.get('output_dir')
        if not args.request:
            args.request = cfg.get('request', '')
        if not args.original_request:
            args.original_request = cfg.get('original_request', '')

    if not args.title or not args.output:
        parser.print_help()
        print("\nERROR: --title and --output are required (or use --module)")
        return

    default_results = []
    detailed_results = []
    mode = None
    timestamp = None
    original_request = args.original_request

    if args.results and os.path.isfile(args.results):
        data = json.load(open(args.results))
        default_results = data.get('default', [])
        detailed_results = data.get('detailed', [])
        mode = data.get('mode')
        timestamp = data.get('timestamp')
        # Read original_request from results.json if not provided via CLI
        if not original_request:
            original_request = data.get('original_request')
        # Read request_text from results.json as fallback
        if not args.request:
            args.request = data.get('request_text', 'Test execution')

    generate_report(
        title=args.title,
        request_text=args.request,
        gif_path=args.gif,
        video_path=args.video,
        default_results=default_results,
        detailed_results=detailed_results,
        output_dir=args.output,
        slug=args.slug,
        pub_number=args.pub_number,
        conclusion=args.conclusion,
        mode=mode,
        timestamp=timestamp,
        original_request=original_request,
    )


if __name__ == '__main__':
    main()
