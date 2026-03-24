# K_MIND — Memory System Instructions

## Core Principle: Mind-First — The Mindmap Is Your Memory Grid

Always read `mind/mind_memory.md` FIRST as your primary context. This is the hive view — one glance to see everything. Only dig into domain JSON files and session memory files when you need full details.

**The mindmap is not decoration — it is your operating memory.** Every node is a directive that governs how you behave. On every load (start, resume, compaction recovery), walk the full tree and internalize each node as a rule you commit to follow:

- **architecture** nodes → HOW you work. System design rules. Follow as implementation constraints.
- **behaviors** nodes → WHAT you do and WHY. Structured into 4 subcategories:
  - **rules** → Hard mandatory behaviors. NEVER skip. Violations break system integrity.
  - **routes** → Routing system mechanics. How routes are resolved, displayed, discovered, chained.
  - **guides** → Operational patterns. How Claude works day-to-day. Soft but consistent.
  - **cycles** → Repeatable work patterns. What to produce and in what sequence.
- **constraints** nodes → BOUNDARIES. Hard limits. Never violate.
- **conventions** nodes → HOW you execute. Patterns and standards. Apply consistently.
- **work** nodes → STATE. What's accomplished/staged. Your continuity anchor.
- **session** nodes → CONTEXT. Current brainstorming record. References work for concordance.
- **documentation** nodes → STRUCTURE. Documentation references.

If a node says "scripts handle all mechanical operations" — you use scripts. If a node says "split by summarized subjects not size" — you split by subject. The mindmap is your contract with the system.

## Core Principle: Mind-First Search — Mindmap Before Filesystem

**Whenever Claude needs to find, locate, or understand ANYTHING — search the mindmap FIRST.** This is not optional. This applies to ALL searches, not just routed requests. The mindmap is a structured index of everything in the system.

### Node Classification

Mindmap top-level nodes are classified into two categories:

- **FRAMEWORK nodes** (architecture, behaviors, constraints, conventions) — System rules. HOW things work. These govern behavior, they are not searchable content. When you need to know HOW to do something, read framework nodes.
- **CONTENT nodes** (session, documentation, work) — Searchable data. WHAT exists. When you need to find WHERE something is, search content nodes.

### Search Order (mandatory for ALL lookups)

1. **Mindmap leaf nodes** — Walk the content nodes (work, documentation, session). Leaf text contains human-readable descriptions of what exists and where. Match your search subject against leaf descriptions.
2. **JSON domain files** — Once a matching leaf is found, follow its top-level group path to the corresponding JSON file (e.g., `work/work.json`, `documentation/documentation.json`, `conventions/conventions.json`). These contain filesystem paths, IDs, structured details, and far_memory references.
3. **Filesystem grep** — LAST RESORT ONLY. Use only when: (a) no mindmap node matches, AND (b) no route exists, AND (c) the subject is genuinely unknown to the system. This is the "no route detected" fallback.

### Why This Matters

The mindmap already indexes everything. A single leaf node like "webcards theme aware" tells Claude exactly where to look (conventions::documentation::web docs::webcards) without scanning 500 files. Following that path to `conventions/conventions.json` gives the exact details. Filesystem grep wastes tokens scanning files the mindmap already points to.

## Core Principle: Dual Context Adaptation (200K / 1M)

The system behaves identically to the user regardless of context window size. The difference is internal — how much is kept warm vs loaded on-demand.

**Context detection:** `memory_stats.py` detects the model ID suffix (`[1m]` = 1M context). Override via `depth_config.json` → `context_mode`.

| Aspect | 200K Mode | 1M Mode |
|--------|-----------|---------|
| Pinned entries | Always loaded | Always loaded |
| Near memory window | 35 summaries | 35 summaries |
| Architecture/diagrams | Pinned reference, read on-demand | Pinned reference, read on-demand |
| WIP persistence layer | Minimal (pointers only) | Warm — full decision log and work items |
| Routing, scripts, lifecycle | Identical | Identical |

**WIP persistence layer** (`wip_context` in near_memory): Holds essential working state for the current activity — active branch, work items, decision log, activity chain. In 1M mode, this stays warm in context for long sessions with less interruption.

**Activity detection:** On every `--phase before`, the system classifies the user's message as `addon` (continuation of current activity) or `new` (new work item). Classification uses word overlap with `wip_context.active_branch` and recent near_memory summaries. Override with `--activity-mode new|addon`.

**Route interrupt stacking:** When a new user prompt arrives mid-processing, the current route is suspended (not popped). New prompt gets routed on top. On completion, suspended route resumes. Use `--suspend` / `--resume` on `routing_stack.py`.

## Core Principle: Programs Over Improvisation

Claude-as-engine is ONLY the bootstrap (new session, resume, compaction recovery). All mechanical operations use scripts. Claude provides intelligence (summaries, topic names) as arguments to deterministic programs.

## File Structure

- `mind/mind_memory.md` — Core mermaid mindmap. The subconscious mind. Primary reference.
- `sessions/far_memory.json` — Full verbatim conversation history.
- `sessions/near_memory.json` — Real-time summaries with pointers to far_memory and mind_memory.
- `sessions/archives/` — Topic-based far_memory archive files.
- `architecture/architecture.json` — System design references (static).
- `behaviors/behaviors.json` — Behavioral directives: routing, proof delivery, operational patterns (growing).
- `constraints/constraints.json` — Known limitations references (semi-dynamic).
- `work/work.json` — Accomplished/staged work results. The stable reference point for continuity.
- `conventions/conventions.json` — Reusable patterns discovered during work (growing).
- `documentation/documentation.json` — Documentation structure references (TBD).

## Scripts (deterministic programs)

- `scripts/memory_append.py` — Append messages to far_memory + summary to near_memory. Called every turn. Supports `--stdin` for large content. Also manages pinned entries (`--pin`, `--unpin`, `--list-pinned`), WIP context (`--wip set|append|clear|remove|show`), and activity detection (`--activity-mode detect|new|addon`).
- `scripts/far_memory_split.py` — Archive completed topics from far_memory by subject.
- `scripts/memory_recall.py` — Search and load archived memory by subject keyword.
- `scripts/session_init.py` — Initialize fresh session files (preserves archives).
- `scripts/memory_stats.py` — Output memory stats table with context availability. Detects context mode (200K/1M) from model ID. Flags: `--available`, `--context-mode`.
- `scripts/set_depth.py` — Manage mindmap depth config (depth_config.json).
- `scripts/mindmap_filter.py` — Render filtered mindmap from depth config.
- `scripts/routing_display.py` — Generate behavioral routing trace displays. Shows which mindmap nodes govern Claude's decisions.
- `scripts/routing_lookup.py` — Route subject+action to methodology, skills, and scripts.
- `scripts/routing_approve.py` — Persist approved proposed routes to routing.json. Validates, checks conflicts, tracks proposals.
- `scripts/routing_stack.py` — Track reentrant route chains with loop protection and **methodology step enforcement**. Push/pop/check/trace/step. Auto-loads steps from methodology files on push. Blocks pop if steps incomplete.

## Lifecycle Events

### MANDATORY: Mindmap Output Rule

**Every time `/mind-context` is invoked — whether at session start, resume, compaction recovery, or on demand — Claude MUST output the mermaid mindmap code block and the recent near_memory summaries as visible text in the conversation.** This is not optional. The mindmap is the user's primary interface to the knowledge system. Failing to output it defeats the purpose of the skill. The output must include:
1. The mermaid code block (reduced or full per mode)
2. Last session context (if fresh start — shows where work was left off)
3. The last 5 near_memory summaries from current session
4. Session confirmation

### On New Session Start
1. Run: `python3 scripts/session_init.py --session-id "<id>"`
   - Previous session is auto-archived but its summaries are carried forward in `near_memory.json` under `last_session`
2. Run `/mind-context` and **output the mindmap and context visually**
   - The last session's summaries will be displayed as "Last Session Context" so Claude and user can see where work was left off
   - Use this context to orient: check work nodes in the mindmap for accomplished tasks, and last session summaries for recent activity
3. Begin real-time maintenance using scripts

### On Resume
1. Run: `python3 scripts/session_init.py --session-id "<id>" --preserve-active`
2. Run `/mind-context` and **output the mindmap and context visually**
3. Dig into memory files as needed for continuity
4. Continue real-time maintenance using scripts

### On Compaction Recovery
1. Run `/mind-context` and **output the mindmap and context visually**
2. Use `python3 scripts/memory_recall.py --subject "<topic>"` if needed for specific details
3. Continue real-time maintenance using scripts

### Full Context
Run `/mind-context full` when you need the complete mindmap including architecture and constraints trees.

## Every Turn — BEFORE Processing (Mandatory)

**Run BEFORE doing any work on the user's request.** Two objectives: (1) make the behavioral route visible so the user can track decisions, and (2) capture the user's message early to prevent memory loss on compaction.

### Step 1: Capture User Message (memory safety)

Save the user's **VERBATIM** message to far_memory immediately. This ensures the input is persisted even if compaction occurs mid-processing.

**CRITICAL — VERBATIM MEANS VERBATIM:**
- Copy the user's COMPLETE message exactly as written — every word, every detail, every nuance
- NEVER paraphrase, summarize, shorten, rephrase, or "clean up" the user's words
- NEVER drop qualifiers, context, or instructions the user included
- NEVER replace the user's phrasing with your own interpretation
- The user's exact words carry intent that paraphrasing DESTROYS (e.g., "I want you to test and proof it is fixed" is an instruction — dropping it loses the action request)
- When in doubt about length: USE STDIN MODE — there is no size limit
- **Violation = lost intent = broken trust.** This is a hard rule, not a guideline.

```bash
# Short messages (args mode) — use ONLY if the message fits in a single shell arg
python3 scripts/memory_append.py --phase before \
    --role user --content "COPY-PASTE the user's exact message here, every word"
```

```bash
# Long messages (stdin mode — NO SIZE LIMIT) — PREFER THIS for any non-trivial message
python3 scripts/memory_append.py --stdin << 'ENDJSON'
{"phase":"before","role":"user","content":"COPY-PASTE the user's exact message here, every word, every sentence"}
ENDJSON
```

### Step 2: Detect and Display Behavioral Route

**MANDATORY: The user must see which route governs the response BEFORE work begins.**

**NO EXCEPTIONS: This applies to ALL user prompts — including structural tasks, meta-discussions, mindmap changes, and system evolution work. Claude must NEVER skip routing with justifications like "no route needed" or "structural task". Every prompt gets routed. If no route exists, the NO ROUTE protocol applies and a route is proposed.**

1. Analyze the user's prompt to identify the subject and action
2. Run the routing display script:
   ```bash
   python3 scripts/routing_display.py --callout --subject "<subject>" --action "<action>"
   ```
   Or for minor/continuation turns:
   ```bash
   python3 scripts/routing_display.py --compact --subject "<subject>" --action "<action>"
   ```
3. **Output the route trace as your own text** (not hidden in tool output)
4. **Always output the result as your own text** — even when no route matches

**When to use which format:**
- **Full callout**: ALWAYS use on the first user prompt of a session — no exceptions, no judgment calls, regardless of how casual or simple the prompt appears. Also use for new tasks, subject changes, or first turn on a topic.
- **Compact**: Continuation of current route, minor follow-up. NEVER use compact on the first user prompt.
- **Stack**: When entering a collateral route (show parent→child)
- **No route → Propose**: When no route matches, the script outputs a `[NO ROUTE]` block with nearby routes, related mindmap nodes, and a proposed route template. Claude MUST use this context to **propose a complete route** to the user before proceeding. See "Route Discovery Protocol" below.

### Step 3: Route Discovery Protocol — Self-Evolution (when no route matches)

The routing script now handles three cases automatically when no exact match exists:

#### Case A: Equivalent Route Found (`[EQUIVALENT ROUTE FOUND]`)

The script detects a strong partial match (score >= 4, meaning both subject AND action overlap). This is a **shortcut** — use the equivalent route directly. The miss is still tracked in metrics so the system knows this subject pattern should eventually be added to the equivalent route's subjects list.

#### Case B: No Route, No Equivalent (`[NO ROUTE]` with metrics)

This is the **self-evolution** path. The script:
1. **Tracks the miss** in `conventions/route_metrics.json` — every NO ROUTE is recorded
2. **Shows frequency** — "this request seen: N time(s)". At N >= 2, flags `>>> RECURRING PATTERN <<<`
3. **Shows nearby routes** and mindmap nodes for context
4. **Outputs the self-evolution flow**:

Claude then follows this protocol:

1. **Read the proposal context** — metrics, nearby routes, mindmap nodes
2. **Propose a generic route** — fill in the template with specifics from context
3. **Display the proposed route** to the user as a code block, clearly labeled `PROPOSED ROUTE`
4. **User approves** → Claude proceeds with work
5. **Work completes** → Claude asks: "Was that what you expected?"
6. **User confirms** → persist as official route:
   ```bash
   echo '{"name":"route-slug","subjects":[...],"actions":[...],...}' | \
   python3 scripts/routing_approve.py --stdin --scaffold
   ```
   The approval script automatically resolves matching metric entries — the miss becomes a learned route.
7. **Fill scaffolded templates** — the script creates skeleton methodology and skill files. Claude fills them with specifics from the verbatim far_memory record of what actually worked.

#### Route Metrics — The Learning Signal

Every NO ROUTE miss is recorded in `conventions/route_metrics.json`:
- `unrouted_hits[]` — timestamped records with subject, action, nearby routes
- `resolved[]` — hits that were resolved when a route was approved
- `stats` — total misses, total resolved, last updated

When `routing_approve.py` persists a new route, it automatically scans unrouted_hits and moves matching entries to resolved. This closes the feedback loop: miss → track → propose → approve → resolve.

This means every gap in the routing table is a **learning opportunity**. The system discovers new routes from actual usage, the user controls what gets persisted, and metrics show which gaps recur most.

### Route Scaffolding — Full Capability Creation

When `--scaffold` is used, the approval script creates **everything the route needs** that doesn't already exist:

| Artifact | Created When | Location |
|----------|-------------|----------|
| **Route** | Always | `conventions/routing.json` |
| **Methodology** | Route declares a methodology path that doesn't exist | `K_*/methodology/<name>.md` |
| **Skill** | Route declares skills that don't have SKILL.md | `.claude/skills/<name>/SKILL.md` |
| **Mindmap node** | Route name not in mindmap | `mind/mind_memory.md` |

Scaffolded files are **templates** — Claude fills them with specifics from the verbatim far_memory record of what actually worked. The system self-evolves from usage.

**Route approval scripts:**
- `scripts/routing_approve.py --stdin --scaffold` — persist route + scaffold all missing artifacts
- `scripts/routing_approve.py --stdin --scaffold --dry` — preview what would be created
- `scripts/routing_approve.py --stdin` — persist route only (no scaffolding)
- `scripts/routing_approve.py --list` — show all proposals from this session

### Step 3.5: Push Route onto Stack with Methodology Enforcement

**MANDATORY: Every matched route MUST be pushed onto the routing stack before work begins.** The stack now auto-loads methodology steps from the route's methodology file and **BLOCKS pop unless all steps are completed**.

```bash
# Push the route — auto-loads methodology steps
python3 scripts/routing_stack.py --push "<route-name>" --reason "why this route"
```

The push output shows the step checklist. Claude MUST mark each step as completed during execution:

```bash
# Mark steps as you complete them
python3 scripts/routing_stack.py --step "route-lookup" --note "confirmed methodology"
python3 scripts/routing_stack.py --step "test-engine" --note "11/11 pass"
python3 scripts/routing_stack.py --step "report-generator"
python3 scripts/routing_stack.py --step "run-persistence" --note "persisted to history.json"
python3 scripts/routing_stack.py --step "publication-gate"
# ... continue for all steps in the methodology
```

**Pop enforcement:**
- `--pop` with status `completed` → **BLOCKED** if any methodology step is missing
- `--pop --force` → override enforcement (escape hatch, logged in history)
- `--pop --status skipped` → exit without completing (not blocked, used for reroutes)

```bash
# Check progress at any time
python3 scripts/routing_stack.py --steps

# Pop when all steps are done
python3 scripts/routing_stack.py --pop
```

**This closes the gap where Claude detected the right route but skipped steps.** The stack is the contract enforcer — methodology steps are not suggestions, they are hard requirements.

### Step 4: Proceed with Work

Only after steps 1-3.5 are complete, begin processing the user's request.

---

## Every Turn — AFTER Processing

**Run AFTER completing your response.** Captures the assistant's output and creates the near_memory summary linking both messages.

### Step 1: Save Assistant Response + Summary

**CRITICAL: far_memory stores FULL VERBATIM content, NEVER summaries.**
- `--content2` = your COMPLETE visible output (all text, tables, code blocks, mermaid diagrams — everything the user sees)
- `--summary` = one-line summary (this goes to near_memory only)
- `--tools` = JSON array of tool calls made: `[{"tool":"Edit","file":"path","action":"desc"},...]`

For short turns (args mode):
```bash
python3 scripts/memory_append.py --phase after \
    --role2 assistant --content2 "full assistant output text" \
    --summary "one-line summary" \
    --mind-refs "knowledge::node1,knowledge::node2" \
    --tools '[{"tool":"Edit","file":"path","action":"desc"}]'
```

For long turns with tables/code (stdin mode — no size limit):
```bash
python3 scripts/memory_append.py --stdin << 'ENDJSON'
{"phase":"after","role2":"assistant","content2":"full output with tables, code blocks, etc","summary":"one-line summary","mind_refs":"node1,node2","tools":[{"tool":"Edit","file":"path","action":"desc"}]}
ENDJSON
```

### Step 2: Update Knowledge (as needed)

2. Update `mind/mind_memory.md` mindmap nodes as needed
3. Update domain JSON files when relevant knowledge is produced
4. Stage completed work: conventions → self-contained templates (no memory refs); content → work.json linked to far_memory ranges

### Step 3: Push and Merge (mandatory default)

**Every completed unit of work MUST be committed, pushed, and merged to main** using the `/elevate` skill (GitHubHelper PR workflow). This is the default behavior — work is not considered complete until it is on main.

- **Default**: commit → push → elevate (PR + merge to main)
- **Opt-out**: Only skip if the user explicitly says "don't merge", "WIP", "draft", or similar in their prompt
- **Partial work**: If the task is part of a larger multi-step session, batch the merge at logical checkpoints rather than after every micro-change
- **Session files**: Memory/session file updates can be batched with the next substantive commit

This ensures no work is stranded on feature branches.

### GitHub Failure Detection — Automatic Reroute to `/github` Skill

**MANDATORY: Before ANY GitHubHelper usage, invoke `/github` skill first.** The skill loads the constructor convention (pitfall #23) and ensures correct token setup.

**Failure detection triggers:** If a GitHubHelper call produces any of these signals, Claude MUST reroute to the `/github` skill and retry:

| Signal | Meaning | Action |
|--------|---------|--------|
| Empty result / `None` / `{}` | Silent auth failure | Load `/github` skill → retry |
| `401 Bad Credentials` | Repo passed as token (pitfall #23) | Load `/github` skill → fix constructor → retry |
| `403 Forbidden` | Token scope missing | Load `/github` skill → check token setup |
| `404 Not Found` | Bad repo/PR number | Load `/github` skill → verify args |
| Exception / traceback | Any unhandled error | Load `/github` skill → diagnose → retry |
| No output from python3 -c | Script crashed silently | Load `/github` skill → retry with error capture |

**Reroute protocol:**
1. Detect failure signal from GitHubHelper call
2. Invoke `/github` skill (loads the full convention with correct patterns)
3. Re-read the convention output — verify constructor is `GitHubHelper()` with NO args
4. Retry the failed operation using the correct pattern
5. If retry fails again, report the error to the user — do not loop

**Prevention (preferred over detection):** Always invoke `/github` skill BEFORE the first GitHubHelper usage in a session. This front-loads the convention and prevents failures entirely.

### Legacy Single-Call Mode

The single-call mode (no `--phase` flag) is still supported for backward compatibility but the two-phase protocol is preferred.

## Ephemeral Artifact Capture (Plans & Todos)

Claude Code plans (.claude/plans/*.md) and todos are ephemeral — lost on compaction/session end. K_MIND captures them automatically.

- **Auto-capture on session start**: The session hook runs `capture_ephemeral.py --plans` on every start/resume/compact
- **Manual todo capture**: Before compaction or when todos are valuable, capture them:
  ```bash
  echo '{"todos": [...]}' | python3 scripts/capture_ephemeral.py --todos --stdin
  ```
- **Recall**: Captured plans/todos appear in `memory_recall.py --subject` searches and in:
  ```bash
  python3 scripts/capture_ephemeral.py --recall "keyword"
  python3 scripts/capture_ephemeral.py --list
  ```
- **Memory tagging**: Plans get `type: "plan"`, todos get `type: "todo"` in far_memory — searchable across all recall workflows

## Pinned Near Memory — Persistent Behavioral Context

Pinned entries are near_memory items that **survive across sessions** — never archived, never rolled off. They carry essential behavioral directives that every session inherits automatically.

### Structure

```json
{
  "pinned": [
    {"id": "pin-001", "category": "behaviors", "content": "directive text", "mind_ref": "behaviors::node"},
    {"id": "pin-011", "category": "reference", "content": "architecture analysis → path (read on-demand)", "mind_ref": "architecture::node"}
  ],
  "wip_context": {
    "active_branch": "feature-name",
    "work_items": ["item summary"],
    "decision_log": ["chose X because Y"],
    "activity_chain": ["activity-id"]
  },
  "summaries": [ ... ]
}
```

### Management

```bash
# Add or update a pinned entry
python3 scripts/memory_append.py --pin "pin-008" "behaviors" "directive text" "behaviors::node"

# Remove a pinned entry
python3 scripts/memory_append.py --unpin "pin-008"

# List all pinned entries
python3 scripts/memory_append.py --list-pinned
```

### Lifecycle

- **Session init** (fresh or resume): `pinned` array is preserved — `session_init.py` carries it forward
- **Far memory split**: Only removes from `summaries` — `pinned` is untouched
- **Compaction recovery**: Pinned entries are always available — they're the first thing loaded from near_memory
- **Categories**: `behaviors`, `conventions`, `architecture`, `reference` — match top-level mindmap groups plus reference pointers

### Reference Pins

Reference pins (category `"reference"`) carry **pointers** to architecture analysis and diagram publications. They are always present so Claude knows where to look, but the referenced content is only loaded on-demand when work requires it. In 200K mode, content stays on disk. In 1M mode, the system may preload referenced content into the WIP layer.

### WIP Context

The `wip_context` section in near_memory holds essential working state:
- **active_branch**: Current work branch name
- **work_items**: Summaries of active work items
- **decision_log**: Key decisions made during the session
- **activity_chain**: Ordered list of activity IDs in current work

Managed via `memory_append.py --wip set|append|clear|remove|show`. Initialized empty on fresh sessions, preserved on resume.

### When to Pin

Pin directives that are **essential for correct operation** regardless of session context:
- Mandatory behavioral patterns (routing display, proof delivery)
- Core architectural rules (programs over improvisation, two-phase protocol)
- Critical conventions (lean startup, local-first validation)

Do NOT pin work items, session-specific notes, or temporary instructions.

## Far Memory Topic Splitting

When `sessions/far_memory.json` grows large, run:
```bash
python3 scripts/far_memory_split.py \
    --topic "Topic Name" \
    --start-msg 1 --end-msg 24 \
    --start-near 1 --end-near 7
```

Claude identifies topic boundaries from near_memory summary clusters, then calls the script.

## Memory Recall

To recall a past topic:
```bash
python3 scripts/memory_recall.py --subject "architecture"
python3 scripts/memory_recall.py --list
python3 scripts/memory_recall.py --subject "theme" --full
```

## Mindmap Node Groups — Behavioral Mapping

Each group maps to a behavioral category. When you read a node, you adopt its directive:

- **architecture** — Static. System design. HOW you work. Changes only when the system evolves.
- **behaviors** — Growing. Behavioral directives. WHAT you do and WHY. Structured tree:
  - **rules** — Hard mandatory. Never skip. (mind-first search, proof delivery, push-and-merge, local validation, github reroute)
  - **routes** — Routing mechanics. (routing table, display, discovery protocol, reentrant chains)
  - **guides** — Operational patterns. (token startup, methodology selection, skills/scripts, visual confirmation, ask user)
  - **cycles** — Repeatable work patterns. (build-test-plugin cycle)
- **constraints** — Semi-dynamic. Known limitations. BOUNDARIES you never violate.
- **conventions** — Growing. Reusable patterns. HOW you execute every operation.
- **work** — Dynamic. Accomplished/staged results. STATE you check before starting new tasks.
- **session** — Dynamic. Brainstorming record. CONTEXT that references work for concordance.
- **documentation** — TBD. Documentation structure. REFERENCES to be defined later.

## Behavioral Routing Display — Transparency Protocol (Option C)

**The mindmap's governance must be VISIBLE to the user.** Routing traces use the **vertical flow format (Option C)** — top-to-bottom nodes with arrows, reasons at each step, and a `<<< ACTIVE` marker.

### CRITICAL: Output as Claude's Own Text

**Tool output is collapsed in the Claude desktop app.** The user cannot see script results without clicking to expand. Therefore:

1. Run the routing script to generate the trace
2. **Copy the output and paste it as your own text response** — either inline or in a code block
3. NEVER leave the routing trace hidden inside a tool result

### Display Format — Vertical Flow

**Full trace** (for major routing decisions — output as a code block):
```
  [route-name]  "why this route"
     nodes: mindmap node, other node
     method: methodology-file.md
     proof: gif, mp4, png  <<<
```

**Stack** (when entering collateral routes — output as a code block):
```
  [primary-route]  "original task"
       |
       v
  [collateral-route]  "why needed"    <<< ACTIVE (2/5)
```

**Compact** (for minor decisions — output as inline text):

`[route-name]  method: file.md  proof: gif, png`

**Reroute** (when user says reroute — output as a code block):
```
  REROUTED

  [original-route]  "original task"    <<< BACK HERE
       |
       x
  x--x [derailed-route]  (unwound)
```

### When to Display

- **Session start**: Groups table after mindmap in `/mind-context`
- **Activity routing**: Full trace BEFORE beginning work
- **Collateral route**: Stack display showing parent→child flow
- **Minor decisions**: Compact one-liner
- **No route found**: State handling directly without methodology

### Scripts (generate the format, Claude echoes as text)

```bash
python3 scripts/routing_display.py --callout --subject "<subject>" --action "<action>"
python3 scripts/routing_display.py --compact --subject "<subject>" --action "<action>"
python3 scripts/routing_display.py --startup
python3 scripts/routing_display.py --summary
```

## Reentrant Routing — Chain Tracking & Loop Protection

Complex tasks trigger collateral routes. For example, `test-report-generation` may need `web-page-visualization` for screenshots, which may need `visual-documentation` for proof artifacts. This creates a **route chain** that must be tracked to prevent infinite loops and provide audit transparency.

### Route Chain Dependencies

Each route in `routing.json` declares `chain_deps` — the collateral routes it may trigger during execution. These are not automatic — Claude decides when to enter a collateral route based on the task context.

### Routing Stack Protocol

Claude MUST use `routing_stack.py` to track route chains:

1. **Before entering a route**: Push it onto the stack
   ```bash
   python3 scripts/routing_stack.py --push "<route-name>" --reason "why this route is needed"
   ```
   The script displays the current stack state to the user. If the push is BLOCKED (loop detected or max depth exceeded), Claude must NOT enter that route.

2. **On route completion**: Pop it from the stack
   ```bash
   python3 scripts/routing_stack.py --pop --status completed
   ```
   Or with `--status skipped` / `--status failed` if the route was not completed.

3. **Before entering a collateral route**: Check first
   ```bash
   python3 scripts/routing_stack.py --check "<route-name>"
   ```

4. **Show current chain state** (for audit):
   ```bash
   python3 scripts/routing_stack.py --trace
   ```

5. **Suspend current route** (when new user prompt interrupts mid-processing):
   ```bash
   python3 scripts/routing_stack.py --suspend --reason "new user prompt arrived"
   ```
   The suspended route stays on the stack but is marked `⏸ SUSPENDED`. A new route can be pushed on top.

6. **Resume suspended route** (after interrupt is handled):
   ```bash
   python3 scripts/routing_stack.py --resume
   ```
   Resumes the most recently suspended route. If the interrupt was an addon to the same activity, it merges into the suspended route's context.

### Safety Limits

- **Max stack depth**: 5 nested routes
- **Max same-route reentry**: 2 (prevents oscillation)
- **Direct recursion**: Blocked (same route cannot call itself immediately)
- **Stack reset**: Automatic on session init

### Reroute — Get Back on Track

When Claude derails into collateral routes and the user says **"reroute"** (or any variant like "get back on track", "back to the original task"), Claude MUST immediately run:

```bash
python3 scripts/routing_stack.py --reroute
```

This unwinds all collateral routes back to the original task, shows the user what was derailed, and resumes the primary route from where it was interrupted. One word to get back on track.

### Reroute Full — Nuclear Reset

When the user says **"reroute full"** (or any variant like "full reset", "reinit on mindmap"), Claude MUST immediately run:

```bash
python3 scripts/routing_stack.py --reroute --full
```

This is the nuclear option: clears the **entire** routing stack (not just collateral routes), then forces Claude to run `/mind-context full` — re-reading CLAUDE.md and reinternalizing the complete mindmap behavior graph including architecture and constraints. Use when Claude is fundamentally off-track, not just on a wrong collateral route.

**Escalation ladder:**
| Command | Effect |
|---------|--------|
| **"reroute"** | Unwind collateral routes → back to primary route |
| **"reroute full"** | Clear entire stack + `/mind-context full` reinit |

### Chain Dependency Visualization

To see which routes may chain into others:
```bash
# Single route chain tree
python3 scripts/routing_display.py --chain test-report-generation

# Full dependency map (all routes)
python3 scripts/routing_display.py --chain-map
```

## Session Files Role

Session files (far_memory, near_memory) are the dynamic brainstorming record. They reference accomplished work in `work/` for concordance and continuity of working and building activities.

---

# K_STM32_MCP — STM32 Live Debug Module Instructions

## Overview

This module provides MCP server tools for live STM32 debugging. Claude uses these tools to read/write hardware registers, execute GDB commands, and run BAT build/flash scripts — all through the Model Context Protocol.

## MCP Server

The server runs as a stdio MCP transport, launched by Claude Code via `.mcp.json`:

```json
{
  "mcpServers": {
    "stm32": {
      "command": "python3",
      "args": ["Knowledge/K_STM32_MCP/mcp/server.py"],
      "cwd": "."
    }
  }
}
```

## Tool Layers

### Layer 1: Raw GDB
- `gdb_command(cmd)` — Execute any GDB/MI command directly
- Returns raw GDB/MI response

### Layer 2: High-Level (SVD-Aware)
- `read_register(peripheral, register)` — Read a named peripheral register
- `write_register(peripheral, register, value)` — Write to a named register
- `read_memory(address, length)` — Read raw memory region
- `flash_verify(address, expected)` — Verify flash content

### Layer 3: BAT Scripts
- `list_bat()` — List available .bat scripts with descriptions
- `run_bat(script, args)` — Execute a .bat script via cmd.exe /c

## GDB Connection

- Transport: GDB/MI via pygdbmi
- Default port: 3333 (OpenOCD)
- Connection config in `mcp/config.json`

## SVD Files

Place SVD files for your target MCU in `svd/`. The server auto-discovers them and uses them for named register access.

## Conventions

- Always verify GDB connection before operations
- SVD register names are case-insensitive
- BAT scripts execute via WSL-to-Windows interop (cmd.exe /c)
- All tool responses include raw values and human-readable descriptions
