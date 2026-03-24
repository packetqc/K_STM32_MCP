#!/usr/bin/env python3
"""
Interaction Test Report Generator — Publication from Interaction Test Results
=============================================================================

Generates a standalone web publication from interaction_test_driver results.
For standalone page tests (bug/fix demos, expand/collapse, UI interactions).

Document structure:
  1. Run History Tab Bar (if multiple runs exist)
  2. Introduction — test request description
  3. Summary — parts, steps, pass/fail
  4. Before/After Screenshots — side-by-side comparison
  5. Proof Video — MP4 embed (multi-part stitched)
  6. Interaction Steps — per-part step tables
  7. Conclusion — assessment

Runs stored in split format: assets/runs.json (index) + assets/runs/run-N.json.

Usage:
    python3 scripts/generate_interaction_report.py \\
        --title "Live Mindmap — Expand/Collapse Bug Fix Test" \\
        --request "Test bug/fix with actual code rollback" \\
        --interaction-results path/to/interaction_results.json \\
        --slug test-live-mindmap-expand \\
        -o docs/publications/test-live-mindmap-expand/
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from urllib.parse import quote as _q

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_RUNS = 10


# ═══════════════════════════════════════════════════════════════════════
# Runs Management (same split format as generate_test_report.py)
# ═══════════════════════════════════════════════════════════════════════

def load_runs(assets_dir):
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
    if isinstance(data[0], dict) and 'file' in data[0] and 'steps' not in data[0]:
        runs = []
        for entry in data:
            run_file = os.path.join(assets_dir, entry['file'])
            if os.path.isfile(run_file):
                with open(run_file) as f:
                    runs.append(json.load(f))
            else:
                runs.append(entry)
        return runs
    return data


def save_runs(assets_dir, runs):
    runs = runs[-MAX_RUNS:]
    runs_dir = os.path.join(assets_dir, 'runs')
    os.makedirs(runs_dir, exist_ok=True)

    index = []
    for i, run in enumerate(runs):
        run_num = i + 1
        filename = f'run-{run_num}.json'
        filepath = os.path.join(runs_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(run, f, indent=2, ensure_ascii=False)

        total_steps = len(run.get('steps', []))
        passed_steps = sum(1 for s in run.get('steps', []) if s.get('status') == 'ok')

        index.append({
            'run': run_num,
            'timestamp': run.get('timestamp', ''),
            'type': 'interaction',
            'request_text': run.get('request_text', ''),
            'parts': run.get('parts', 1),
            'total_steps': total_steps,
            'passed_steps': passed_steps,
            'file': f'runs/{filename}',
        })

    runs_path = os.path.join(assets_dir, 'runs.json')
    with open(runs_path, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    return runs


# ═══════════════════════════════════════════════════════════════════════
# HTML Helpers
# ═══════════════════════════════════════════════════════════════════════

def _esc(text):
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def render_interaction_summary(run, lang='en'):
    """Render summary table for an interaction test run."""
    t = I18N.get(lang, I18N['en'])
    steps = run.get('steps', [])
    total = len(steps)
    passed = sum(1 for s in steps if s.get('status') == 'ok')
    failed = sum(1 for s in steps if s.get('status') not in ('ok',))
    parts = run.get('parts', 1)

    h = []
    h.append('<table class="tg-summary">')
    h.append(f'<thead><tr><th>{t["metric"]}</th><th>{t["count"]}</th></tr></thead>')
    h.append('<tbody>')
    h.append(f'<tr><td>{t["parts_label"]}</td><td>{parts}</td></tr>')
    h.append(f'<tr><td>{t["total_steps"]}</td><td>{total}</td></tr>')
    h.append(f'<tr><td>{t["steps_passed"]}</td><td>{passed}</td></tr>')
    if failed > 0:
        h.append(f'<tr><td>{t["steps_failed"]}</td><td>{failed}</td></tr>')
    h.append('</tbody></table>')
    return '\n'.join(h)


def render_steps_table(steps, grid_id='interaction-grid', video_id='proof-video'):
    """Render interactive steps table with video seek on click.

    Steps are grouped by checkpoints (capture actions). Each checkpoint is a
    collapsible section header showing the capture description. Sub-steps
    leading to each checkpoint are revealed on expand. Clicking any row
    seeks the video to that step's recorded timestamp.
    """
    h = []
    has_parts = any(s.get('part_label') for s in steps)
    has_timestamps = any(s.get('video_ts') is not None for s in steps)

    h.append(f'<table class="tg tg-interactive" id="{grid_id}" data-video="{video_id}">')
    h.append('<thead><tr>')
    h.append('<th>#</th>')
    if has_parts:
        h.append('<th>Part</th>')
    h.append('<th>Action</th>')
    h.append('<th>Description</th>')
    if has_timestamps:
        h.append('<th>Time</th>')
    h.append('<th>Status</th>')
    h.append('</tr></thead>')
    h.append('<tbody>')

    # Group steps into checkpoint sections
    # A checkpoint is a 'capture' action; preceding steps are its context
    groups = []
    current_group = []
    for s in steps:
        current_group.append(s)
        if s.get('action') == 'capture':
            groups.append(current_group)
            current_group = []
    if current_group:
        groups.append(current_group)

    step_num = 0
    for gi, group in enumerate(groups):
        checkpoint = group[-1] if group[-1].get('action') == 'capture' else None
        context_steps = group[:-1] if checkpoint else group

        # Checkpoint header row (always visible)
        if checkpoint:
            step_num += 1
            status = checkpoint.get('status', 'ok')
            rc = 'pass' if status == 'ok' else 'fail'
            mark = '<span class="led-p"></span> ✓' if status == 'ok' else '<span class="led-f"></span> ✗'
            ts = checkpoint.get('video_ts')
            ts_str = f'{ts:.1f}s' if ts is not None else ''
            desc = _esc(checkpoint.get('description', ''))
            capture_as = checkpoint.get('capture_as', '')
            if capture_as:
                desc = f'<strong>{_esc(capture_as)}</strong> — {desc}'

            ts_attr = f' data-ts="{ts}"' if ts is not None else ''
            toggle = f' data-toggle="grp-{grid_id}-{gi}"' if context_steps else ''
            arrow = '<span class="step-arrow">▶</span> ' if context_steps else ''

            h.append(f'<tr class="step-checkpoint"{ts_attr}{toggle}>')
            h.append(f'  <td>{step_num}</td>')
            if has_parts:
                h.append(f'  <td>{_esc(checkpoint.get("part_label", ""))}</td>')
            h.append(f'  <td>capture</td>')
            h.append(f'  <td>{arrow}{desc}</td>')
            if has_timestamps:
                h.append(f'  <td class="step-ts">{ts_str}</td>')
            h.append(f'  <td class="{rc}">{mark}</td>')
            h.append('</tr>')

        # Context steps (collapsed by default)
        for s in context_steps:
            step_num += 1
            status = s.get('status', 'ok')
            rc = 'pass' if status == 'ok' else 'fail'
            mark = '<span class="led-p"></span> ✓' if status == 'ok' else '<span class="led-f"></span> ✗'
            ts = s.get('video_ts')
            ts_str = f'{ts:.1f}s' if ts is not None else ''
            target = s.get('target', '')
            desc = _esc(s.get('description', ''))
            if target:
                desc += f' <code>{_esc(target)}</code>'

            ts_attr = f' data-ts="{ts}"' if ts is not None else ''
            grp_class = f' step-context grp-{grid_id}-{gi}' if checkpoint else ''

            h.append(f'<tr class="step-row{grp_class}"{ts_attr}>')
            h.append(f'  <td>{step_num}</td>')
            if has_parts:
                h.append(f'  <td>{_esc(s.get("part_label", ""))}</td>')
            h.append(f'  <td>{_esc(s.get("action", ""))}</td>')
            h.append(f'  <td>{desc}</td>')
            if has_timestamps:
                h.append(f'  <td class="step-ts">{ts_str}</td>')
            h.append(f'  <td class="{rc}">{mark}</td>')
            h.append('</tr>')

    h.append('</tbody></table>')
    return '\n'.join(h)


# ═══════════════════════════════════════════════════════════════════════
# CSS (shared base + interaction-specific)
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

/* ═══ Before/After ═══ */
.ba-row { display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; }
.ba-col { flex: 1; min-width: 300px; }
.ba-col img { width: 100%; border: 2px solid var(--border, #d0d7de); border-radius: 6px; }
.ba-label {
  text-align: center; font-weight: 600; font-size: 0.85rem;
  padding: 0.3rem 0; text-transform: uppercase; letter-spacing: 0.05em;
}
.ba-label-before { color: #dc2626; }
.ba-label-after { color: #16a34a; }

/* ═══ Interactive Steps ═══ */
.tg-interactive tr[data-ts] { cursor: pointer; }
.tg-interactive tr[data-ts]:hover td { background: var(--accent-bg, #e8f0fe); }
.tg-interactive tr.step-active td { background: var(--accent-bg, #dbeafe); border-left: 3px solid var(--accent, #1d4ed8); }
.step-context { display: none; }
.step-context td { font-size: 0.8rem; color: var(--muted, #656d76); padding-left: 1.5rem; }
.step-context.visible { display: table-row; }
.step-checkpoint { font-weight: 600; }
.step-checkpoint td { background: var(--code-bg, #f6f8fa); }
.step-arrow { display: inline-block; transition: transform 0.2s; font-size: 0.7rem; margin-right: 0.3rem; padding: 0.2rem 0.4rem; cursor: pointer; border-radius: 3px; }
.step-arrow:hover { background: var(--accent-bg, #dbeafe); }
.step-arrow.open { transform: rotate(90deg); }
.step-ts { font-family: monospace; font-size: 0.75rem; color: var(--accent, #1d4ed8); white-space: nowrap; }

/* ═══ Original Request ═══ */
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

INTERACTIVE_JS = """
(function(){
  document.querySelectorAll('.tg-interactive').forEach(function(tbl){
    var videoId = tbl.getAttribute('data-video');
    var video = document.getElementById(videoId);

    function toggleGroup(row) {
      var toggleGrp = row.getAttribute('data-toggle');
      if (!toggleGrp) return;
      var arrow = row.querySelector('.step-arrow');
      var contextRows = tbl.querySelectorAll('.' + toggleGrp);
      var isOpen = contextRows.length > 0 && contextRows[0].classList.contains('visible');
      contextRows.forEach(function(r){ r.classList.toggle('visible', !isOpen); });
      if (arrow) arrow.classList.toggle('open', !isOpen);
    }

    function seekVideo(row) {
      var ts = parseFloat(row.getAttribute('data-ts'));
      if (isNaN(ts)) return;
      tbl.querySelectorAll('tr.step-active').forEach(function(r){ r.classList.remove('step-active'); });
      row.classList.add('step-active');
      if (!video) return;

      function doSeek() {
        video.currentTime = ts;
        if (video.paused) {
          var p = video.play();
          if (p && p.catch) p.catch(function(){});
        }
      }

      if (video.readyState >= 1) {
        doSeek();
      } else {
        video.addEventListener('loadedmetadata', function onMeta() {
          video.removeEventListener('loadedmetadata', onMeta);
          doSeek();
        });
        video.load();
      }
    }

    tbl.addEventListener('click', function(e){
      var arrow = e.target.closest('.step-arrow');
      var row = e.target.closest('tr[data-ts]');
      if (!row) return;

      if (arrow) {
        // Arrow click: only toggle expand/collapse, no video seek
        toggleGroup(row);
      } else if (row.classList.contains('step-checkpoint') && row.hasAttribute('data-toggle')) {
        // Checkpoint row body click: seek video AND toggle expand
        seekVideo(row);
        toggleGroup(row);
      } else {
        // Regular step row click: just seek video
        seekVideo(row);
      }
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
# Bilingual Translations
# ═══════════════════════════════════════════════════════════════════════

I18N = {
    'en': {
        'interaction_test': 'Interaction test',
        'parts': 'parts',
        'steps': 'steps',
        'pass': 'pass',
        'keywords': 'test, interaction, qa, validation, bug fix',
        'original_request': 'Original request',
        'date': 'Date',
        'summary': 'Summary',
        'metric': 'Metric',
        'count': 'Count',
        'parts_label': 'Parts',
        'total_steps': 'Total steps',
        'steps_passed': 'Steps passed',
        'steps_failed': 'Steps failed',
        'before_after': 'Before / After',
        'before_bug': 'BEFORE — Bug',
        'after_fix': 'AFTER — Fix',
        'proof': 'Proof',
        'video': 'Video',
        'video_seek_hint': 'Click any step below to seek the video to that moment.',
        'interaction_steps': 'Interaction Steps',
        'conclusion': 'Conclusion',
        'auto_conclusion_pass': 'All {total} interaction steps completed successfully '
                                'across {parts} part(s). The bug/fix behavior is validated.',
        'auto_conclusion_fail': '{failed} step(s) failed out of {total}. '
                                'Review the steps table for details.',
    },
    'fr': {
        'interaction_test': 'Test d\'interaction',
        'parts': 'parties',
        'steps': 'étapes',
        'pass': 'réussi',
        'keywords': 'test, interaction, qa, validation, correction de bogue',
        'original_request': 'Demande originale',
        'date': 'Date',
        'summary': 'Résumé',
        'metric': 'Métrique',
        'count': 'Nombre',
        'parts_label': 'Parties',
        'total_steps': 'Étapes totales',
        'steps_passed': 'Étapes réussies',
        'steps_failed': 'Étapes échouées',
        'before_after': 'Avant / Après',
        'before_bug': 'AVANT — Bogue',
        'after_fix': 'APRÈS — Correctif',
        'proof': 'Preuve',
        'video': 'Vidéo',
        'video_seek_hint': 'Cliquez sur une étape ci-dessous pour positionner la vidéo à ce moment.',
        'interaction_steps': 'Étapes d\'interaction',
        'conclusion': 'Conclusion',
        'auto_conclusion_pass': 'Les {total} étapes d\'interaction ont été complétées avec succès '
                                'sur {parts} partie(s). Le comportement bogue/correctif est validé.',
        'auto_conclusion_fail': '{failed} étape(s) échouée(s) sur {total}. '
                                'Consultez le tableau des étapes pour les détails.',
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Main Generator
# ═══════════════════════════════════════════════════════════════════════

def generate_interaction_report(title, request_text, interaction_results,
                                output_dir, slug=None, conclusion=None,
                                timestamp=None, original_request=None,
                                subtitle=None, description=None,
                                lang='en'):
    """Generate interaction test report publication with run history tabs.

    lang: 'en' or 'fr'. Controls UI labels, permalink prefix, and auto-conclusion.
    Assets are shared (same assets/ dir) — only the index.md content differs.
    """
    t = I18N.get(lang, I18N['en'])

    os.makedirs(output_dir, exist_ok=True)
    # FR doesn't manage its own assets — references EN assets via web paths
    if lang == 'en':
        assets_dir = os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
    else:
        assets_dir = None

    if not timestamp:
        timestamp = datetime.now().isoformat()
    date_str = timestamp[:10]

    if not slug:
        slug = title.lower().replace(' ', '-').replace('/', '-')

    steps = interaction_results.get('steps', [])
    total_steps = len(steps)
    passed_steps = sum(1 for s in steps if s.get('status') == 'ok')
    failed_steps = total_steps - passed_steps
    num_parts = interaction_results.get('parts', 1)

    if not conclusion:
        if failed_steps == 0:
            conclusion = t['auto_conclusion_pass'].format(total=total_steps, parts=num_parts)
        else:
            conclusion = t['auto_conclusion_fail'].format(failed=failed_steps, total=total_steps)

    # ═══ Manage runs.json (EN only — FR reuses EN runs) ═══
    new_run = {
        'timestamp': timestamp,
        'type': 'interaction',
        'request_text': request_text or '',
        'original_request': original_request or '',
        'parts': num_parts,
        'steps': steps,
        'title': title,
    }
    if assets_dir:
        runs = load_runs(assets_dir)
        runs.append(new_run)
        runs = save_runs(assets_dir, runs)
    else:
        runs = [new_run]

    asset_base = f'/publications/{slug}/assets'

    # ═══ Build HTML ═══
    md = []

    # Frontmatter
    permalink_prefix = '/fr' if lang == 'fr' else ''
    md.append('---')
    md.append('layout: publication')
    md.append(f'title: "{title}"')
    md.append(f'description: "{t["interaction_test"]}: {num_parts} {t["parts"]}, {total_steps} {t["steps"]} — {passed_steps}/{total_steps} {t["pass"]}"')
    md.append(f'date: "{date_str}"')
    md.append(f'permalink: {permalink_prefix}/publications/{slug}/')
    md.append(f'og_image: /publications/{slug}/assets/proof.gif')
    md.append(f'keywords: "{t["keywords"]}"')
    md.append('---')
    md.append('')
    md.append(f'# {title}')
    md.append('')
    md.append('{::nomarkdown}')
    md.append(f'<style>{REPORT_CSS}</style>')

    # ═══ Tab Bar ═══
    if len(runs) > 1:
        md.append('<div class="run-tab-bar">')
        for ri, run in enumerate(reversed(runs)):
            run_idx = len(runs) - ri
            active = ' active' if ri == 0 else ''
            ts = run.get('timestamp', '')[:16].replace('T', ' ')
            parts = run.get('parts', 1)
            run_steps = run.get('steps', [])
            ok = all(s.get('status') == 'ok' for s in run_steps) if run_steps else True
            led_class = 'run-led-green' if ok else 'run-led-red'
            md.append(f'<div class="run-tab{active}" data-run="{run_idx}">')
            md.append(f'  <span class="run-tab-label"><span class="run-led {led_class}"></span>Run {run_idx}</span>')
            md.append(f'  <span class="run-tab-date">{ts}</span>')
            md.append('</div>')
        md.append('</div>')

    # ═══ Run Panels ═══
    for ri, run in enumerate(reversed(runs)):
        run_idx = len(runs) - ri
        active = ' active' if ri == 0 else ''
        is_latest = (ri == 0)

        md.append(f'<div class="run-panel{active}" data-run="{run_idx}">')

        run_steps = run.get('steps', [])
        run_req = run.get('request_text', '')
        run_orig = run.get('original_request', '')
        run_ts = run.get('timestamp', '')

        # Introduction
        if run_req:
            md.append(f'<blockquote>{_esc(run_req)}</blockquote>')
        if run_orig:
            md.append('<details class="original-request">')
            md.append(f'<summary>{t["original_request"]}</summary>')
            md.append(f'<blockquote>{_esc(run_orig)}</blockquote>')
            md.append('</details>')

        md.append(f'<p><strong>{t["date"]}:</strong> {run_ts[:10] if run_ts else date_str} &nbsp; '
                  f'<strong>{t["parts_label"]}:</strong> {run.get("parts", 1)} &nbsp; '
                  f'<strong>{t["steps"].capitalize()}:</strong> {len(run_steps)}</p>')

        # Summary
        md.append(f'<h2>{t["summary"]}</h2>')
        md.append(render_interaction_summary(run, lang=lang))

        # Before/After (only for latest run — screenshots are current)
        if is_latest:
            run_parts = run.get('parts') or num_parts
            if run_parts and run_parts > 1:
                before_src = f'{asset_base}/part-1/before.png'
                after_src = f'{asset_base}/part-2/after.png'
            else:
                before_src = f'{asset_base}/before.png'
                after_src = f'{asset_base}/after.png'
            md.append(f'<h2>{t["before_after"]}</h2>')
            md.append('<div class="ba-row">')
            md.append('<div class="ba-col">')
            md.append(f'<div class="ba-label ba-label-before">{t["before_bug"]}</div>')
            md.append(f'<img src="{before_src}" alt="{t["before_bug"]}">')
            md.append('</div>')
            md.append('<div class="ba-col">')
            md.append(f'<div class="ba-label ba-label-after">{t["after_fix"]}</div>')
            md.append(f'<img src="{after_src}" alt="{t["after_fix"]}">')
            md.append('</div>')
            md.append('</div>')

            # Animated GIF proof
            md.append(f'<h2>{t["proof"]}</h2>')
            md.append(f'<p><img src="{asset_base}/proof.gif" alt="{t["proof"]}" style="max-width:100%;"></p>')

            # Full interaction video — with ID for step seeking
            md.append(f'<h2>{t["video"]}</h2>')
            video_id = f'proof-video-{run_idx}'
            md.append(f'<video id="{video_id}" controls width="100%">')
            md.append(f'  <source src="{asset_base}/proof.mp4" type="video/mp4">')
            md.append('</video>')
            md.append(f'<p style="font-size:0.75rem;color:var(--muted,#656d76);">{t["video_seek_hint"]}</p>')

        # Steps Grid
        md.append(f'<h2>{t["interaction_steps"]}</h2>')
        md.append(render_steps_table(run_steps, grid_id=f'grid-{run_idx}',
                                     video_id=f'proof-video-{run_idx}'))

        # Conclusion
        if is_latest:
            md.append(f'<h2>{t["conclusion"]}</h2>')
            md.append(f'<p>{_esc(conclusion)}</p>')

        md.append('</div>')  # close run-panel

    # JS
    md.append(f'<script>{SORT_JS}</script>')
    md.append(f'<script>{INTERACTIVE_JS}</script>')
    if len(runs) > 1:
        md.append(f'<script>{TAB_JS}</script>')

    md.append('{:/nomarkdown}')

    # Write
    index_path = os.path.join(output_dir, 'index.md')
    with open(index_path, 'w') as f:
        f.write('\n'.join(md))

    lang_label = 'FR' if lang == 'fr' else 'EN'
    print(f"[{lang_label}] Interaction report: {index_path}")
    print(f"  Parts: {num_parts} | Steps: {passed_steps}/{total_steps}")
    if lang == 'en':
        print(f"  Runs: {len(runs)} stored in assets/runs.json")
        print(f"  Webcard: assets/proof.gif")
        print(f"  Video: assets/proof.mp4")

    return index_path


def generate_bilingual_reports(title_en, title_fr, request_en, request_fr,
                               interaction_results, output_dir, slug=None,
                               conclusion_en=None, conclusion_fr=None,
                               timestamp=None, original_request=None,
                               subtitle_en=None, subtitle_fr=None,
                               description_en=None, description_fr=None):
    """Generate both EN and FR versions of an interaction test report.

    EN goes to output_dir, FR goes to the parallel fr/ tree.
    Assets are shared — FR references the same assets/ as EN.
    Runs.json is managed only by the EN generation (single source of truth).
    """
    # EN version
    en_path = generate_interaction_report(
        title=title_en, request_text=request_en,
        interaction_results=interaction_results,
        output_dir=output_dir, slug=slug,
        conclusion=conclusion_en, timestamp=timestamp,
        original_request=original_request,
        subtitle=subtitle_en, description=description_en,
        lang='en')

    # FR version — parallel tree: docs/publications/X → docs/fr/publications/X
    # output_dir is like docs/publications/test-slug/
    # fr_dir is like docs/fr/publications/test-slug/
    parts = output_dir.rstrip('/').split('/')
    try:
        pub_idx = parts.index('publications')
        fr_parts = parts[:pub_idx - 1] + [parts[pub_idx - 1]] + ['fr'] + parts[pub_idx:]
        fr_dir = '/'.join(fr_parts)
    except ValueError:
        fr_dir = output_dir.rstrip('/') + '-fr'

    os.makedirs(fr_dir, exist_ok=True)

    # FR references EN assets via absolute web paths (/publications/{slug}/assets/)
    # No symlink needed — GitHub Pages doesn't follow symlinks

    fr_path = generate_interaction_report(
        title=title_fr, request_text=request_fr,
        interaction_results=interaction_results,
        output_dir=fr_dir, slug=slug,
        conclusion=conclusion_fr, timestamp=timestamp,
        original_request=original_request,
        subtitle=subtitle_fr, description=description_fr,
        lang='fr')

    return en_path, fr_path


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Interaction Test Report Generator — Bilingual (EN + FR)')
    parser.add_argument('--title', required=True, help='Report title (EN)')
    parser.add_argument('--title-fr', help='Report title (FR)')
    parser.add_argument('--subtitle', default='', help='Subtitle (EN)')
    parser.add_argument('--subtitle-fr', default='', help='Subtitle (FR)')
    parser.add_argument('--description', default='', help='Description (EN)')
    parser.add_argument('--description-fr', default='', help='Description (FR)')
    parser.add_argument('--request', help='Test description (EN)')
    parser.add_argument('--request-fr', help='Test description (FR)')
    parser.add_argument('--original-request', help='Verbatim user request')
    parser.add_argument('--conclusion', help='Conclusion (EN)')
    parser.add_argument('--conclusion-fr', help='Conclusion (FR)')
    parser.add_argument('--interaction-results', required=True,
                        help='Path to interaction_results.json')
    parser.add_argument('--slug', help='Publication slug')
    parser.add_argument('-o', '--output-dir', required=True,
                        help='Output publication directory (EN)')
    args = parser.parse_args()

    with open(args.interaction_results) as f:
        results = json.load(f)

    generate_bilingual_reports(
        title_en=args.title,
        title_fr=args.title_fr or args.title,
        request_en=args.request or '',
        request_fr=args.request_fr or args.request or '',
        interaction_results=results,
        output_dir=args.output_dir,
        slug=args.slug,
        conclusion_en=args.conclusion,
        conclusion_fr=args.conclusion_fr,
        original_request=args.original_request,
        subtitle_en=args.subtitle,
        subtitle_fr=args.subtitle_fr or args.subtitle,
        description_en=args.description,
        description_fr=args.description_fr or args.description,
    )


if __name__ == '__main__':
    main()
