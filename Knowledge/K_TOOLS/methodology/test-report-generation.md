# Test Report Generation — Methodology

## Purpose

Generate rich test report publications from automated web page assessments. Each report is a standalone document with embedded proof artifacts (animated GIF, MP4 video) and detailed results grids.

## Prerequisites (Mandatory Gate — behav-020)

Before executing this methodology, Claude MUST verify all tools are available. Do NOT proceed if any check fails — install first.

| Tool | Check | Install if missing |
|------|-------|--------------------|
| **Chromium** | `python3 -c "from scripts.render_web_page import find_chrome; assert find_chrome(), 'Chromium not found'"` | `python3 -m playwright install chromium` |
| **Playwright** | `python3 -c "import playwright"` | `pip install playwright && python3 -m playwright install chromium` |
| **npm mermaid** | `test -f /tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js` | `mkdir -p /tmp/mermaid-local-test && cd /tmp/mermaid-local-test && npm init -y --silent && npm install mermaid` |
| **web_test_engine.py** | `test -f Knowledge/K_TOOLS/scripts/web_test_engine.py` | Script is part of K_TOOLS module — verify module is imported |
| **generate_test_report.py** | `test -f Knowledge/K_TOOLS/scripts/generate_test_report.py` | Script is part of K_TOOLS module — verify module is imported |
| **generate_check_snapshot.py** | `test -f Knowledge/K_TOOLS/scripts/generate_check_snapshot.py` | Script is part of K_TOOLS module — verify module is imported |
| **persist_test_run.py** | `test -f Knowledge/K_TOOLS/scripts/persist_test_run.py` | Script is part of K_TOOLS module — verify module is imported |

**Rule**: If any prerequisite is missing, install it. If installation fails, STOP and report to the user. Never silently skip test execution or proof generation.

## Test Execution

Tests are **request-driven** — no predefined modes. Claude determines which pages to test based on the user's request, then passes specific targets to the engine.

| Flag | Purpose |
|------|---------|
| `--targets <docs>` | Test specific pages identified from the request |
| `--detailed <docs>` | Add widget interaction tests on specific pages |
| `--request` | Synthesized test description |
| `--original-request` | Verbatim user prompt |

## Execution Pipeline — Two-Loop Verification

The pipeline has two verification loops separated by a publication gate. A standalone page can behave differently when embedded in the main interface (CSS conflicts, JS scope, iframe restrictions, routing failures). Both contexts must be verified.

```
┌─────────────────────────────────────────────────────────────┐
│  LOOP 1 — STANDALONE VERIFICATION                           │
│                                                             │
│  Route Lookup → Test Engine → Proof Capture → Report Gen    │
│       ↑                                          │          │
│       └──── fix & re-test if FAIL ◄──────────────┘          │
│                                                             │
│  Exit: standalone page passes all checks                    │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  PUBLICATION GATE                                           │
│                                                             │
│  Register across all system surfaces so the main            │
│  interface can discover and embed the page.                 │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LOOP 2 — MAIN INTERFACE INTEGRATION VERIFICATION           │
│                                                             │
│  Load main interface → navigate to page → verify            │
│       ↑                                          │          │
│       └──── fix & re-test if FAIL ◄──────────────┘          │
│                                                             │
│  Exit: page works correctly inside main interface           │
└─────────────────────────────────────────────────────────────┘
```

This two-loop pattern applies to **any new standalone page** — test report, publication, guide, interface — not just test reports.

---

### LOOP 1 — Standalone Verification

Build and verify the standalone page in isolation.

#### Step 1.1: Route Lookup

```bash
python3 K_MIND/scripts/routing_lookup.py --subject test --action report
```

Confirms: methodology, skills, scripts, proof_output requirements.

#### Step 1.2: Test Engine

```bash
# Targeted test — specific pages
python3 K_TOOLS/scripts/web_test_engine.py --targets doc1.md doc2.md \
    --request "test description" --original-request "user prompt"

# With widget interaction tests
python3 K_TOOLS/scripts/web_test_engine.py --targets doc1.md doc2.md \
    --detailed doc1.md doc2.md \
    --request "test description" --original-request "user prompt"
```

Outputs:
- `test-reports/default-test-report.gif` — animated proof (Full HD 1920x1080)
- `test-reports/default-test-report.mp4` — video proof (auto-scaled to stay under MP4_MAX_MB)
- `test-reports/results.json` — machine-readable results

#### Step 1.3: Report Generator

```bash
python3 K_TOOLS/scripts/generate_test_report.py \
    --title "Main Navigator — Complete Test" \
    --request "Complete test of all links from the main navigator" \
    --gif K_TOOLS/test-reports/default-test-report.gif \
    --video K_TOOLS/test-reports/default-test-report.mp4 \
    --results K_TOOLS/test-reports/results.json \
    --slug test-main-navigator \
    -o docs/publications/test-main-navigator/
```

#### Step 1.4: Run Persistence

After each test execution, persist the run to the dashboard history so the Tests Interface shows the full run timeline:

```bash
# From results JSON (web_test_engine output)
python3 K_TOOLS/scripts/persist_test_run.py \
    --test-id tests-interface-no-tab-bar \
    --title "Tests Interface — Tab Bar Removal" \
    --title-fr "Interface Tests — Suppression de la barre d'onglets" \
    --slug test-tests-interface-no-tab-bar \
    --results K_TOOLS/test-reports/results.json

# From explicit values (custom tests, Loop 2 results)
python3 K_TOOLS/scripts/persist_test_run.py \
    --test-id tests-interface-no-tab-bar \
    --title "Tests Interface — Tab Bar Removal" \
    --slug test-tests-interface-no-tab-bar \
    --mode VERIFICATION --total 12 --passed 12 --failed 0

# Sync local runs.json → dashboard (after generate_test_report.py)
python3 K_TOOLS/scripts/persist_test_run.py \
    --test-id tests-interface-no-tab-bar \
    --sync-from-runs docs/publications/test-tests-interface-no-tab-bar/assets/runs.json

# List all tests and their run counts
python3 K_TOOLS/scripts/persist_test_run.py --list
```

This writes to **both** dashboard history files:
- **PRIMARY**: `docs/publications/test-main-navigator/assets/history.json` — loaded first by the Tests Interface
- **FALLBACK**: `docs/data/test-history.json` — used when PRIMARY fails

Each re-run appends to the `runs[]` array. Duplicate timestamps are detected and updated in place (no double-counting). The dashboard shows up to 10 columns per test, with LED indicators per run.

#### Step 1.5: Standalone Result

Loop 1 exits when the standalone page passes all checks. If any check fails, fix the issue and re-run from Step 1.2. Each re-run automatically appends to the run history via Step 1.4.

---

### PUBLICATION GATE

Register the verified standalone page across all system surfaces so the main interface can discover and embed it. This step is **MANDATORY** before Loop 2 — the main interface can only load pages that exist in the system.

**HARD RULE: Distribution is NOT optional. Every surface must be registered. Partial distribution = broken system.**

| Surface | File | Purpose |
|---------|------|---------|
| Navigator section data | `docs/data/tests.json` | Left panel TESTS section entry |
| Test history (primary) | `publications/test-main-navigator/assets/history.json` | Dashboard primary source |
| Test history (fallback) | `docs/data/test-history.json` | Dashboard fallback |
| Viewer index | `docs/index.html` | Route registration for content panel |
| HTML redirect + OG tags | `docs/publications/<slug>/index.html` | Standalone access + social preview |
| Link registry | `LINKS.md` | Central link reference |
| Mindmap | `mind/mind_memory.md` | System inventory (documentation node) |

### RERUNNABLE TEST MODULES

Every test MUST have a rerunnable Python module in `interactions/tests/`. This ensures tests can be rerun and reports regenerated deterministically.

```bash
# List available test modules
python3 interaction_test_driver.py --list-modules

# Run a specific test module
python3 interaction_test_driver.py --module <name>
```

**Module contract** — each file in `interactions/tests/` exports:
- `TEST_ID` — unique slug
- `TITLE` / `TITLE_FR` — display titles
- `SLUG` — publication directory name
- `OUTPUT_DIR` — relative path to publication
- `get_test_plan()` — returns the test plan dict for interaction_test_driver

---

### LOOP 2 — Main Interface Integration Verification

Verify the published page works correctly when embedded in the main interface content panel.

#### Step 2.1: Layout & Visual QA

Load the page inside the main interface content panel and verify:

- Page loads in the content panel iframe without errors
- **Fit** — content fills the panel properly, no overflow or undersized rendering
- **Spacing** — adequate breathing room, margins, padding around content
- **Borders** — no visual gaps between the page and the panel frame
- **Widgets** — interactive elements (buttons, accordions, tabs) work within the iframe context
- **No console errors** — check browser console for JS/CSS conflicts from embedding

#### Step 2.2: Section Navigation Check

Verify the page appears in its correct left panel section:

1. Open the main interface
2. Navigate to the appropriate section (e.g., TESTS for test reports)
3. Locate the new page entry in the section list
4. **Click** the entry → confirm it opens in the content panel (right panel)
5. If the entry is missing → publication failed, fix and re-publish

#### Step 2.3: LINKS.md Registry Check

Verify the page is listed in the central link registry:

1. Open `LINKS.md` in the main interface (it renders in the content panel)
2. Find the new page entry in the appropriate category
3. **Click** the link → confirm it opens in the content panel
4. If missing → the publication routine missed LINKS.md, fix and re-publish

#### Step 2.4: Test Interface Check (test pages only)

For test report pages, verify presence in the test interface:

1. Open the test interface in the main interface
2. Locate the test entry in the test history list
3. Confirm the run count reflects the actual number of executions
4. If the test was run multiple times, verify the interface handles history correctly

#### Step 2.5: Integration Result

Loop 2 exits when all integration checks pass. If any check fails, fix the issue (may require re-publishing or fixing the standalone page) and re-verify from Step 2.1.

#### Generic Integration Checklist (any new standalone page)

This checklist applies to any page type — test report, publication, guide:

| # | Check | Action | Pass Criteria |
|---|-------|--------|---------------|
| 1 | Content panel load | Navigate to page via section | Page renders in content panel |
| 2 | Layout QA | Visual inspection | No gaps, overflow, or spacing issues |
| 3 | Section presence | Find in left panel section | Entry exists and is clickable |
| 4 | Section link works | Click section entry | Opens in content panel |
| 5 | LINKS.md presence | Open LINKS.md, find entry | Entry exists in correct category |
| 6 | LINKS.md link works | Click entry in LINKS.md | Opens in content panel |
| 7 | Request compliance | Compare to original request | Matches the change request (feature/fix/bug) |

## Check Validation

Each row in the test grid corresponds to a **check** — a single verification step. Checks produce **check snapshots**: annotated 3-part images that serve as standalone proof artifacts.

See: `methodology/check-validation.md` for the complete check validation methodology.

| Concept | Definition |
|---------|-----------|
| **Check** | Atomic verification unit (1 page load, 1 widget interaction) |
| **Check Snapshot** | 3-part image: Header (title + description) → CHECK\|PROOF evidence (dual side-by-side) → Result (status + conclusion) |
| **CHECK Frame** | Screenshot captured BEFORE navigation (baseline state) |
| **PROOF Frame** | Screenshot captured AFTER navigation + validation (verified state) |

The test engine captures CHECK + PROOF frame pairs per check and outputs `checks[]` with `check_path` + `proof_path` in `results.json` (`format: 'check_proof'`). The check renderer (`generate_check_snapshot.py`) composes dual CHECK|PROOF snapshot images. The report generator embeds these in the report alongside the existing grid.

## Test Request Persistence

Every test execution persists two request descriptions:

- **request_text**: Synthesized short description (displayed as blockquote in report)
- **original_request**: Verbatim user prompt (collapsible "Original Test Request" below the blockquote)

Both are stored in `results.json`, propagated to `runs.json`, and rendered in the HTML report. The original request is mandatory for professional-grade test evidence — it proves what was actually requested and provides audit traceability.

Pass these via CLI:
```bash
python3 K_TOOLS/scripts/web_test_engine.py --default \
    --request "Complete test of main navigator interface" \
    --original-request "Run a full test on the main navigator, check all links work"
```

The report generator reads both from `results.json` automatically.

## Document Structure

| Section | Content | Proof |
|---------|---------|-------|
| Introduction | Test request (blockquote) + date | — |
| Summary | Pass/fail/skip totals table | — |
| Proof of Execution | Animated GIF inline | GIF (also webcard) |
| Video Recording | MP4 embed with controls | MP4 |
| Default Test Grid | Per-page pass/fail rows | — |
| Check Snapshots | Per-check 3-part CHECK\|PROOF dual images | PNG per check |
| Detailed Widget Tests | Per-widget pass/fail (if detailed) | — |
| Conclusion | Auto-generated assessment | — |

## Proof Artifacts — Interaction-Driven Workflow

The proof workflow is **MP4-first**: video recording is the master driver, screenshots are extracted from the interaction, and GIF is composed from screenshots + metadata.

```
  ┌─────────────────────────────────────────────────────────┐
  │  MP4 RECORDING (master)                                  │
  │  Playwright records video while interacting with page    │
  │                                                          │
  │  Navigate → Wait → Interact → Capture → Interact → ...  │
  │               ↓                  ↓                       │
  │          screenshot          screenshot                  │
  │          (before)            (after)                      │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  ARTIFACTS                                               │
  │                                                          │
  │  proof.mp4  ← the actual interaction recording           │
  │  before.png ← screenshot at "before" interaction point   │
  │  after.png  ← screenshot at "after" interaction point    │
  │  proof.gif  ← composed: header + before/after + footer   │
  └─────────────────────────────────────────────────────────┘
```

| Artifact | Source | Format | Purpose |
|----------|--------|--------|---------|
| **MP4** | Playwright video recording | H.264 video | Master proof — shows actual interaction |
| **Screenshots** | Extracted at key interaction points | PNG | Evidence frames — before/after states |
| **GIF** | Composed from screenshots + metadata | One-pager: header, 2 screenshots, footer | Static check — embeddable in report |

### Interaction Test Driver

```bash
# From test plan file
python3 K_TOOLS/scripts/interaction_test_driver.py \
    --test-plan K_TOOLS/test-plans/expand-collapse-bugfix.json \
    -o docs/publications/test-live-mindmap-expand/assets/

# With inline steps
python3 K_TOOLS/scripts/interaction_test_driver.py \
    --page interfaces/live-mindmap/index.md \
    --title "Live Mindmap — Expand Bug Fix" \
    --steps '[{"action":"expand_all","target":"architecture"},{"action":"capture","capture_as":"before"},...]' \
    -o /tmp/test-output/
```

### Test Plan Format

```json
{
  "title": "Test Title",
  "subtitle": "Check subtitle",
  "description": "What is being tested",
  "conclusion": "Expected result",
  "page": "interfaces/live-mindmap/index.md",
  "steps": [
    {"action": "wait", "wait_ms": 2000},
    {"action": "expand_all", "target": "architecture"},
    {"action": "fit"},
    {"action": "capture", "capture_as": "before"},
    {"action": "click_expand", "target": "architecture"},
    {"action": "capture", "capture_as": "after"}
  ]
}
```

### Step Actions

| Action | Description | Requires mindmap |
|--------|-------------|:---:|
| `wait` | Wait for specified ms | No |
| `capture` | Take screenshot with `capture_as` label | No |
| `click_expand` | Click + button on named node (1-level) | Yes |
| `expand_all` | Simulate broken full-subtree expand | Yes |
| `collapse` | Click expanded node to collapse | Yes |
| `fit` | Refresh + scaleFit + toCenter | Yes |
| `reload` | Reload mindmap from source | Yes |

### Key Principle: No Falsification

The MP4 recording captures the actual page behavior — no CSS injection, no DOM manipulation, no post-processing. If the page doesn't render correctly, the proof shows it. The Heisenberg effect (observation changing the result) is avoided by fixing the page itself, not the test harness.

## DOM Scanner

The test engine scans each page iframe for interactive widgets:

| Widget Type | Discovery | Trigger Action |
|-------------|-----------|----------------|
| Button | `<button>` | click |
| Link | `<a href>` | verify href exists |
| Select | `<select>` | change to option[1] |
| Accordion | `<details>` | toggle open/close |
| Tab | `[role="tab"]` | click to activate |
| Checkbox | `input[type=checkbox]` | toggle checked |
| Radio | `input[type=radio]` | toggle checked |
| Input | `<input>`, `<textarea>` | verify exists |

## Three Discovery Vectors

1. **Code** — read source HTML/JS/CSS to know what widgets should exist
2. **Console** — execute JS in page context to query DOM and inspect state
3. **Visual** — screenshot to confirm what's actually rendered and visible

## Completion

A test is complete only when **both loops pass**:

1. **Loop 1 passed** — standalone page works in isolation (all test checks green)
2. **Publication Gate done** — page registered across all system surfaces (see Publication Gate table above)
3. **Loop 2 passed** — page works inside the main interface (all integration checks green)

If only Loop 1 passes, the test is **halfway complete** — standalone proof exists but integration is unverified. The Publication Gate and Loop 2 must still be executed.

## Related

- Skill: `/test` — user-invocable command
- Scripts: `web_test_engine.py`, `generate_test_report.py`, `generate_check_snapshot.py`, `persist_test_run.py`, `render_web_page.py`, `interaction_test_driver.py`
- Test Plans: `K_TOOLS/test-plans/*.json` — interaction test definitions
- Methodology: `methodology/check-validation.md` — check validation specification
- Routing: `routing.json` → `test-report-generation` route
- Section: `docs/data/tests.json` → TESTS in navigator
