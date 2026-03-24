# Check Validation — Methodology

## Purpose

Define the structure, rendering, and lifecycle of a **check validation** — the atomic unit of proof within a test. A test is composed of multiple checks; each check produces a visual artifact that proves a specific verification passed or failed.

## Terminology

| Term | Definition |
|------|-----------|
| **Test** | A complete test execution covering multiple pages/widgets. Produces a report. |
| **Check** | A single verification step within a test. Produces a check snapshot. |
| **Check Snapshot** | The visual artifact for one check — a 3-part annotated image with dual evidence. |
| **CHECK Frame** | Screenshot captured BEFORE navigation/action (baseline state). |
| **PROOF Frame** | Screenshot captured AFTER navigation/action (verification state). |

## Check Snapshot Structure — 3-Part Composition

Each check snapshot is a single image composed of three vertical sections. The **mandatory default** uses dual CHECK/PROOF evidence (side-by-side screenshots showing baseline vs verified state):

```
┌─────────────────────────────────────────────────┐
│  PART 1 — HEADER                                │
│                                                 │
│  Test Title                                     │
│  Check Subtitle (vérification)                  │
│  Short description of what is being verified    │
│                                                 │
├────────────────────┬────────────────────────────┤
│  PART 2 — EVIDENCE                              │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐             │
│  │    CHECK     │  │    PROOF     │             │
│  │  (baseline)  │  │  (verified)  │             │
│  │              │  │              │             │
│  │  screenshot  │  │  screenshot  │             │
│  │   before     │  │   after      │             │
│  │  navigation  │  │  validation  │             │
│  │              │  │              │             │
│  └──────────────┘  └──────────────┘             │
│  Both bordered by result color (green/red)      │
│                                                 │
├─────────────────────────────────────────────────┤
│  PART 3 — RESULT                                │
│                                                 │
│  ● PASS  — Short conclusion text                │
│  (green/yellow/red LED + status + explanation)  │
│                                                 │
└─────────────────────────────────────────────────┘
```

> **Discovery Mode**: A single-screenshot variant exists for test plan documents
> (external usage only). It uses one screenshot instead of the CHECK/PROOF pair.
> This mode is NOT used during test execution — dual is always mandatory.

### Part 1 — Header

| Field | Source | Example |
|-------|--------|---------|
| **Test Title** | Test metadata `title` | "Main Navigator — Complete Test" |
| **Check Subtitle** | Check metadata `label` | "Interface Claude — Content Panel Load" |
| **Description** | Check metadata `description` | "Verify the page loads in the content panel without errors" |

The header uses a dark background with white text for clear visual separation.

### Part 2 — Evidence (CHECK | PROOF)

Two screenshots side by side: **CHECK** (baseline state before navigation) and **PROOF** (state after navigation + validation). Both panels share the same result-colored border (green for PASS, red for FAIL). When possible, visual annotations highlight the proof area:

| Annotation | When Used | Visual |
|------------|-----------|--------|
| **Circle** | Point to a specific element (button state, text) | Red circle outline around the proof area |
| **Arrow** | Draw attention to an area of the screenshot | Red arrow pointing to the proof |
| **Border** | Highlight the full frame result | Green (pass) or red (fail) border around the screenshot |

Annotations are **optional** — they enrich the evidence but the screenshot alone is valid proof. The annotation layer is drawn on top of the screenshot using PIL (Pillow).

### Part 3 — Result

| Field | Values | Visual |
|-------|--------|--------|
| **Status** | PASS / WARN / FAIL | Green ● / Yellow ● / Red ● LED |
| **Conclusion** | 1-line explanation | "Page loaded successfully (1,234 chars)" or "404 Not Found" |

Status mapping:
- **PASS** (green) — Check succeeded, no issues detected
- **WARN** (yellow) — Check passed with caveats (e.g., cross-origin assumed ok)
- **FAIL** (red) — Check failed, error detected

## Test Request Persistence

Every test execution must persist two levels of request description:

| Field | Content | Source |
|-------|---------|--------|
| **request_text** | Synthesized short description | Claude synthesizes from user request |
| **original_request** | Verbatim user prompt | Exact user message that initiated the test |

Both are stored in `results.json` and propagated to:
- Report generator → `runs.json` per run
- Report HTML → blockquote (synthesized) + collapsible details (original)
- Check snapshots → description field (synthesized)

The report renders the synthesized description as the visible blockquote. Below it, a **collapsible "Original Test Request"** section expands to show the verbatim user prompt. This is mandatory for professional-grade test evidence — it proves what was actually requested.

## Check Metadata Schema

Each check carries metadata used to render the snapshot and for traceability:

```json
{
  "check_id": 1,
  "test_title": "Main Navigator — Complete Test",
  "label": "Interface Claude — Content Panel Load",
  "description": "Verify the page loads in the content panel without errors",
  "phase": "Interface",
  "target": "Interface Claude",
  "panel": "Center",
  "doc": "interfaces/claude-interface/index.md",
  "result": "PASS",
  "status_color": "green",
  "conclusion": "Page loaded successfully (2,451 chars)",
  "error": null,
  "check_path": "check_0000.png",
  "proof_path": "proof_0000.png",
  "frame_path": "proof_0000.png",
  "snapshot_path": "check_0001_snapshot.png",
  "annotations": [
    {"type": "border", "color": "green"}
  ],
  "timestamp": "2026-03-20T14:30:00"
}
```

## Progressive Description Resolution

Check descriptions are resolved through a 4-level fallback chain:

```
1. Explicit description on check  →  (from original_request synthesis)
2. Exact doc path match           →  check_descriptions.json → by_doc
3. Phase-based template           →  check_descriptions.json → by_phase
4. Generic template               →  "Verify {target} loads in {panel} panel"
```

The description registry (`scripts/check_descriptions.json`) stores:
- **by_doc**: Exact doc path → rich description (highest priority)
- **by_phase**: Phase name → template with `{target}` and `{panel}` interpolation

This allows progressive enrichment: start with generic descriptions, add specific ones per doc/phase as tests mature. The registry grows organically — no need to backfill all tests at once.

## Integration with Test Pipeline

The check validation sits inside the existing Two-Loop Verification Pipeline:

```
Test Engine (web_test_engine.py)
  │
  ├── Per-page loop
  │     ├── CHECK screenshot → capture baseline BEFORE navigation
  │     ├── Navigate to target page (set iframe src)
  │     ├── Content validation → PASS/FAIL
  │     ├── PROOF screenshot → capture state AFTER validation
  │     ├── Build check metadata with check_path + proof_path
  │     └── Store check in results.json → checks[]
  │
  └── Output: results.json (format: 'check_proof') with checks[] + frames/

Check Renderer (generate_check_snapshot.py → batch_generate)
  │
  ├── Input: results.json checks[] + CHECK + PROOF frames
  ├── Per-check loop
  │     ├── Render Part 1 (header) from check metadata
  │     ├── Render Part 2 (evidence) as CHECK|PROOF side-by-side
  │     ├── Render Part 3 (result) from check status + conclusion
  │     └── Compose 3 parts into dual snapshot image
  │
  ├── Fallback: single-screenshot (discovery mode only, no check_path)
  └── Output: check_NNNN_snapshot.png per check

Report Generator (generate_test_report.py)
  │
  ├── Includes check snapshots in the report
  ├── Each check is a row in the test grid + expandable snapshot
  └── Snapshots also available as standalone proof artifacts
```

## Rendering Specification

### Dimensions

| Element | Size |
|---------|------|
| Snapshot width | ~2x screenshot width (CHECK + PROOF side-by-side + gap) |
| Header height | 120px |
| Evidence | CHECK screenshot + 6px gap + PROOF screenshot, label height 28px |
| Result height | 60px |
| Total height | Header + Label + Evidence + Result |

### Colors

| Element | Color |
|---------|-------|
| Header background | `#1e293b` (dark slate) |
| Header title text | `#ffffff` |
| Header subtitle text | `#94a3b8` (muted) |
| Header description text | `#cbd5e1` (light muted) |
| Result background (PASS) | `#052e16` (dark green) |
| Result background (WARN) | `#422006` (dark amber) |
| Result background (FAIL) | `#450a0a` (dark red) |
| Result text | `#ffffff` |
| Result LED (PASS) | `#16a34a` (green) |
| Result LED (WARN) | `#d97706` (amber) |
| Result LED (FAIL) | `#dc2626` (red) |
| Annotation circle/arrow | `#dc2626` (red) |
| Evidence border (PASS) | `#16a34a` 3px |
| Evidence border (FAIL) | `#dc2626` 3px |

### Fonts

Use system fonts via PIL with fallback chain:
1. DejaVu Sans (Linux default)
2. Arial
3. PIL default

## Script Interface

### generate_check_snapshot.py

```bash
# Generate all check snapshots from results
python3 K_TOOLS/scripts/generate_check_snapshot.py \
    --results K_TOOLS/test-reports/results.json \
    --frames-dir K_TOOLS/test-reports/frames/ \
    --output K_TOOLS/test-reports/checks/ \
    --test-title "Main Navigator — Complete Test"

# Generate a single check snapshot
python3 K_TOOLS/scripts/generate_check_snapshot.py \
    --frame frame_0001.png \
    --title "Main Navigator — Complete Test" \
    --subtitle "Interface Claude" \
    --description "Verify page loads in content panel" \
    --result PASS \
    --conclusion "Page loaded (2,451 chars)" \
    --output check_0001_snapshot.png
```

### Annotation helpers (optional enrichment)

```bash
# Add circle annotation to a frame before compositing
python3 K_TOOLS/scripts/generate_check_snapshot.py \
    --frame frame_0001.png \
    --annotate circle --ax 500 --ay 300 --ar 80 \
    ...
```

## Lifecycle

1. **Test engine** captures CHECK frame (before navigation) + PROOF frame (after validation) per check
2. **Check metadata** is built with `check_path` + `proof_path` in `results.json` → `checks[]`
3. **Check renderer** composes 3-part dual snapshots (CHECK|PROOF side-by-side) from metadata + frame pairs
4. **Report generator** embeds check snapshots in the test report
5. **Run persistence** stores check-level results alongside page-level results

## Related

- Methodology: `methodology/test-report-generation.md` — parent test methodology
- Scripts: `web_test_engine.py`, `generate_test_report.py`, `generate_check_snapshot.py`
- Visual engine: `visual_engine.py` — PIL annotation patterns (reusable)
