# Test Proof-of-Completion Methodology

## Purpose

When a **change request** is made — a fix, a new feature, an addition, a modification — the deliverable is a **proof-of-completion**: a visual CHECK/PROOF comparison that proves the change was applied as requested. This is published as a test report page.

The test is NOT about whether the program ran successfully. The test is about **proving the requested change exists in the result**. A human reviews the PROOF screenshot and confirms: "Yes, the requested change is visible."

## Scope — Universal Dual Format

The CHECK/PROOF dual-screenshot format described here is now the **mandatory default for ALL test execution** — not just proof-of-completion workflows. The test engine (`web_test_engine.py`) captures CHECK (before navigation) and PROOF (after validation) frames for every check. Single-screenshot format is reserved exclusively for discovery mode (test plan documents for external usage).

## Prerequisites (Mandatory Gate — behav-020)

Before executing this methodology, Claude MUST verify all tools are available. Do NOT proceed if any check fails — install first.

| Tool | Check | Install if missing |
|------|-------|--------------------|
| **Chromium** | `python3 -c "from scripts.render_web_page import find_chrome; assert find_chrome(), 'Chromium not found'"` | `python3 -m playwright install chromium` |
| **Playwright** | `python3 -c "import playwright"` | `pip install playwright && python3 -m playwright install chromium` |
| **npm mermaid** | `test -f /tmp/mermaid-local-test/node_modules/mermaid/dist/mermaid.min.js` | `mkdir -p /tmp/mermaid-local-test && cd /tmp/mermaid-local-test && npm init -y --silent && npm install mermaid` |
| **generate_check_snapshot.py** | `test -f Knowledge/K_TOOLS/scripts/generate_check_snapshot.py` | Script is part of K_TOOLS module — verify module is imported |
| **render_web_page.py** | `test -f Knowledge/K_TOOLS/scripts/render_web_page.py` | Script is part of K_TOOLS module — verify module is imported |

**Rule**: If any prerequisite is missing, install it. If installation fails, STOP and report to the user. Never silently skip proof generation.

## Core Concept — Visual Proof of Completion

This format applies to **any task that changes visible state**:

| Scenario | CHECK (BEFORE) | Work | PROOF (AFTER) |
|----------|---------------|------|---------------|
| **Bug fix** | Screenshot showing the bug | Fix the bug, iterate until solved | Screenshot proving the bug is gone |
| **Change request** | Screenshot of current state | Apply the requested change | Screenshot proving the change is present |
| **New feature** | Screenshot of page without the feature | Build the feature | Screenshot proving the feature exists |
| **Modification** | Screenshot of current appearance | Modify as requested | Screenshot proving the modification was applied |

The proof answers one question: **Does the AFTER state show that the requested work was completed?**

- **CHECK** = BEFORE state — what existed before (the baseline, or the bug)
- **PROOF** = AFTER state — screenshot proving the work is done (bug fixed, change applied, feature present)
- **Conclusion** = human-readable statement confirming what the proof shows

### Bug Fix Loop

For bug fixes, the workflow is iterative:
1. **CHECK** — capture the bug (it's visible in the screenshot)
2. **Work** — apply a fix
3. **Verify** — take a new screenshot, check if the bug is gone
4. **If bug persists** → iterate (back to step 2)
5. **If bug is resolved** → that screenshot becomes the **PROOF**

The GIF alternates CHECK (bug visible) ↔ PROOF (bug gone). The reviewer confirms: "Yes, the bug is no longer there."

## Workflow

### Phase 1: Capture BEFORE Evidence (CHECK)

1. **Capture the current state** — render the page/area before the work begins
2. **Navigate to the target area** — scroll to where the change/fix will be visible
3. **Screenshot** — capture the baseline state as `*-proof-before.png`

For bug fixes: capture the broken state (the bug must be visible). For new features: capture the page without the feature. For modifications: capture the current appearance before modification.

### Phase 2: Do the Work + Capture AFTER Evidence (PROOF)

1. **Apply the change** (fix the bug, add the feature, make the modification)
2. **For bug fixes: iterate until solved** — keep working until the PROOF screenshot shows the bug is gone
3. **Capture AFTER** — render the changed state, same viewport and scroll position, screenshot as `*-proof-after.png`
4. **The PROOF screenshot must show the work is complete** — this is the evidence

### Phase 3: Compose Proof Image

Use `generate_check_snapshot.py` with the proof-of-completion mode:

```bash
python3 scripts/generate_check_snapshot.py \
  --before test-reports/proof-before.png \
  --after test-reports/proof-after.png \
  --title "Test Title" \
  --subtitle "Check area" \
  --description "What was broken and how it was fixed" \
  --conclusion "Fix verified — description of proof" \
  --output test-reports/proof-of-completion.png
```

The proof image has three vertical parts:
- **Header**: Test title, subtitle, description
- **Evidence**: BEFORE (red border) | AFTER (green border) side by side
- **Result bar**: PASS LED + conclusion

### Route Display — Visible Between Work Steps

**MANDATORY**: During proof-of-completion work, Claude MUST display the routing stack at each phase transition so the user can track where Claude is in the multi-path flow.

```
Phase 1 (CHECK):
  [test-proof-of-completion]  "automatic test for change request"
       |
       v
  [web-page-visualization]  "capture CHECK screenshot"    <<< ACTIVE

Phase 2 (WORK):
  [test-proof-of-completion]  "automatic test for change request"    <<< ACTIVE

Phase 3 (PROOF):
  [test-proof-of-completion]  "automatic test for change request"
       |
       v
  [web-page-visualization]  "capture PROOF screenshot"    <<< ACTIVE

Phase 4 (REPORT):
  [test-proof-of-completion]  "automatic test for change request"
       |
       v
  [test-report-generation]  "publish test report"    <<< ACTIVE
```

Use `routing_stack.py` to push/pop routes as you enter/exit each phase. The stack display is output as Claude's own text (not hidden in tool output).

### Phase 4: Publish Test Report

1. Generate the test report page using `generate_test_report.py`
2. Register in `docs/data/tests.json`
3. Persist run to dashboard history via `persist_test_run.py`

### Phase 5: Register

1. Add to `docs/index.html` JS documents array
2. Commit and push

## JSON Structure — Proof-of-Completion

```json
{
  "test_title": "Mermaid Mindmap Syntax — Pub #25",
  "checks": [
    {
      "before": "test-reports/mermaid-proof-before.png",
      "after": "test-reports/mermaid-proof-after.png",
      "label": "Mermaid Mindmap Rendering",
      "description": "Special chars in bare nodes cause parse error",
      "conclusion": "SVG rendered correctly after bracket wrapping",
      "output": "test-reports/proof-of-completion.png"
    }
  ]
}
```

## Proof-of-Completion JSON for Batch Processing

For multiple checks in a single test:

```json
{
  "test_title": "Test Suite Title",
  "checks": [
    {
      "before": "path/to/before_1.png",
      "after": "path/to/after_1.png",
      "label": "Check 1 — Area name",
      "description": "What was broken",
      "conclusion": "What was fixed and how it was verified",
      "output": "path/to/proof_1.png"
    },
    {
      "before": "path/to/before_2.png",
      "after": "path/to/after_2.png",
      "label": "Check 2 — Area name",
      "description": "What was broken",
      "conclusion": "What was fixed",
      "output": "path/to/proof_2.png"
    }
  ]
}
```

## Animated Audit GIF — Batch Check+Proof Format

For test reports with multiple checks, the proof is an **animated GIF** where each frame is one complete test step composite, pausing 2 seconds between frames. The viewer sees the full audit play step by step.

### Frame Layout (each step)

```
┌──────────────────────────────────┐
│  HEADER — Step title + description│
├────────────────┬─────────────────┤
│     CHECK      │      PROOF      │
│  (screenshot)  │   (screenshot)  │
├────────────────┴─────────────────┤
│  ● PASS/FAIL — conclusion text   │
└──────────────────────────────────┘
```

- **CHECK** = the BEFORE state — what existed before the change request was applied
- **PROOF** = the AFTER state — evidence that the requested change is now present
- Both panels share the same result-colored border (green/amber/red)
- Labels "CHECK" and "PROOF" are color-coded to the result

### JSON Structure — Batch GIF Steps

```json
{
  "test_title": "Main Navigator — Complete Test",
  "steps": [
    {
      "check": "test-reports/frames/frame_0001.png",
      "proof": "test-reports/frames/proof_0001.png",
      "label": "Step 1 — Page Load",
      "description": "Verify page loads in content panel",
      "result": "PASS",
      "conclusion": "Page loaded (2,451 chars)",
      "annotations_check": [],
      "annotations_proof": []
    }
  ]
}
```

### CLI Usage

```bash
python3 scripts/generate_check_snapshot.py \
    --batch-gif test-reports/proof-steps.json \
    --duration 2000 \
    --output test-reports/proof-audit.gif
```

### Integration with Test Engine

The test engine produces `results.json` with check screenshots. The post-processing step:
1. Pairs each check frame with its proof frame
2. Builds the steps JSON
3. Calls `batch_proof_gif()` to produce the animated audit GIF
4. The GIF is embedded in the test report publication

## Automatic Test Rule — Opt-Out, Not Opt-In

**This test is AUTOMATIC** for change requests and bug fixes. Claude MUST create and run the proof-of-completion test unless the user explicitly says "do not create a test" or similar opt-out.

### Trigger Conditions (automatic)

- User requests a **change**: "add X", "move Y", "change A to B", "update Z"
- User reports a **bug fix**: "fix X", "this is broken", "there's a bug in Y"
- Any task that **modifies visible state** in a page or interface

### Test Lifecycle

| Event | Action |
|-------|--------|
| **First time** working on a task | **Create** the test — capture CHECK, do work, capture PROOF, generate GIF |
| **Subsequent iterations** on same task | **Run** the existing test again — new run added to history (run N+1) |
| **Task completed** by user | Test persists with full run history showing the progression |

Each run accumulates in the test's history via `persist_test_run.py`. The user can see how many iterations it took to complete the work.

### Opt-Out

If the user says any of:
- "do not create a test"
- "skip the test"
- "no test needed"

→ Skip the proof-of-completion workflow entirely.

## Key Principles

- **Automatic on change requests and bug fixes** — opt-out, not opt-in
- **CHECK = BEFORE, PROOF = AFTER** — always capture baseline first
- **The test proves the change, not the program** — success = the requested change is visible in the PROOF screenshot
- **First time = create, next times = run** — test accumulates runs across iterations
- **Same viewport, same scroll position** — before and after must show the same area
- **Real browser rendering** — use Playwright + Chromium, not static analysis
- **Proof image is the deliverable** — the user sees the composite at first glance
- **Animated audit = step-by-step review** — 2s pause per frame, viewer sees full test flow
- **Human conclusion** — the reviewer confirms the PROOF shows the requested change
