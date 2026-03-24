# Mindmap Behavior Creation — Methodology

## Purpose

Define how to create, update, and maintain behavioral directives in the mindmap (`mind/mind_memory.md`). The mindmap is not decoration — it is the operating memory. Every node is a directive that governs how Claude behaves across sessions, compactions, and context reloads.

## The Mindmap as Guide Index

The mindmap serves as a **guided index** — each node points to its implementation:

```
behavior node → methodology file → skill → script
```

This is the routing chain. A behavior in the mindmap is not just a note — it links to the methodology that explains HOW, the skill that invokes it, and the script that executes it.

## Behavioral Node Groups

| Group | Purpose | Changes |
|-------|---------|---------|
| **architecture** | System design rules — HOW you work | Rare (system evolution) |
| **constraints** | Hard limits — BOUNDARIES | Semi-dynamic |
| **conventions** | Patterns and standards — HOW you execute | Growing |
| **behaviors** | Active directives — WHAT you do in response | Growing |
| **work** | Accomplished/staged — STATE | Dynamic |
| **session** | Current context — CONTEXT | Dynamic |
| **documentation** | Structure references — REFERENCES | TBD |

## Creating a New Behavior

### Step 1: Identify the Gap

A behavior is needed when:
- A pattern is repeated manually across sessions
- A compaction loses a critical directive
- A new capability requires consistent execution rules

### Step 2: Define the Behavior Node

Add to the `behaviors` subtree in `mind/mind_memory.md`:

```
behaviors
  <behavior name>
    <sub-rule 1>
    <sub-rule 2>
    <sub-rule 3>
```

Rules for naming:
- Use imperative lowercase phrases
- Be specific enough to be actionable
- Each sub-rule is one directive

### Step 3: Link to Implementation

Every behavior should reference its implementation chain:

| Component | File | Purpose |
|-----------|------|---------|
| **Methodology** | `K_*/methodology/<name>.md` | Full specification |
| **Routing** | `K_MIND/conventions/routing.json` | Subject+action dispatch |
| **Skill** | `.claude/skills/<name>/SKILL.md` | User-invocable command |
| **Script** | `K_*/scripts/<name>.py` | Deterministic execution |

### Step 4: Register in Routing Table

Add a route in `conventions/routing.json`:

```json
{
  "route-name": {
    "subjects": ["keyword1", "keyword2"],
    "actions": ["action1", "action2"],
    "methodology": "K_*/methodology/<name>.md",
    "skills": ["skill-name"],
    "scripts": ["K_*/scripts/<script>.py"],
    "proof_output": ["gif", "mp4", "png"]
  }
}
```

### Step 5: Set Depth Override

If the behavior must be visible at startup/compaction recovery, add a depth override:

```bash
python3 scripts/set_depth.py behaviors::<name> 3
```

### Step 6: Verify Survival

The behavior must survive:
1. **New session** — visible via `/mind-context`
2. **Compaction** — visible after context compression
3. **Resume** — visible on session resume

## Updating an Existing Behavior

1. Edit the node text in `mind/mind_memory.md`
2. Update any referenced methodology files
3. Update routing table if subjects/actions changed
4. Verify depth config if visibility changed

## Routing System

The routing table (`conventions/routing.json` v2.0) provides bidirectional dispatch across **31 routes** covering all system capabilities:

**Forward**: subject + action → methodology → skill → script
**Reverse**: skill → methodology → subjects/actions

**184 unique subjects, 201 action entries, 10 proof routes, max chain depth 4.**

For the complete dispatch table with all routes, subjects, chain dependencies, and lookup examples, see the **Behavioral Routing Table** section in `K_TOOLS/methodology/user-guide.md`.

Quick lookup:
```bash
# Forward: what do I use for this task?
python3 scripts/routing_lookup.py --subject web --action troubleshoot

# Reverse: what methodology does this skill follow?
python3 scripts/routing_lookup.py --skill render-web-page

# Full routing summary (31 routes)
python3 scripts/routing_display.py --summary

# Chain dependency map
python3 scripts/routing_display.py --chain-map
```

## Proof Output Rule

Routes with `proof_output` defined MUST produce the specified artifact type. This is enforced by the routing table — not optional. The behavior node `mandatory proof delivery on web and video` governs this.

## Example: Creating the "test report" Behavior

1. **Gap identified**: No automated test reporting with proof artifacts
2. **Behavior node added**:
   ```
   behaviors
     rules
       upon change or bug fix request
         mandatory proof delivery on web and video
           every interaction produces gif mp4 or png
           2s pause between captures on web
           variable pause on video analysis
           proof artifact always returned to user
   ```
3. **Methodology**: `K_TOOLS/methodology/test-report-generation.md`
4. **Routing**: `test-report-generation` route with `proof_output: ["gif", "mp4"]`
5. **Skill**: `/test` — user-invocable command
6. **Scripts**: `web_test_engine.py`, `generate_test_report.py`

## Web Code Fix Procedure

When fixing viewer/web code (`docs/index.html`, interfaces, publications), follow this mandatory sequence:

1. **Read** the relevant code section before editing
2. **Edit** with the fix
3. **Test** using Playwright before committing — load the affected page, check for JS errors, verify content renders
4. **Capture proof** — screenshot or GIF of the fix working
5. **Show proof** to the user (mandatory proof delivery)
6. **Commit** only after test passes
7. **Push** to branch

**Never push web code changes without local Playwright verification.** The scope bug (`directDoc` declared in IIFE, referenced at module scope) was caught by this procedure after it broke the viewer.

## Related

- `mind/mind_memory.md` — the mindmap itself
- `conventions/routing.json` — routing table
- `scripts/routing_lookup.py` — lookup tool
- `scripts/set_depth.py` — depth config management
- `scripts/mindmap_filter.py` — filtered rendering
