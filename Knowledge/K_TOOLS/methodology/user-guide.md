---
layout: publication
title: "Commands — Full Reference"
description: "Complete command reference for the Knowledge platform — all commands, syntax, examples, and implementation details."
pub_id: "User Guide — Commands"
version: "v1"
date: "2026-03-17"
permalink: /publications/guide-commands/full/
keywords: "commands, reference, session, harvest, publications, projects, live, visual, network, normalize"
---

# Commands — Full Reference
{: #pub-title}

> **Module**: K_TOOLS — Command Framework & Utilities

**Contents**

| | |
|---|---|
| [Usage Patterns](#usage-patterns) | Three ways to invoke commands |
| [Session Management](#session-management) | Session lifecycle commands |
| [Normalize](#normalize) | Structure concordance |
| [Harvest](#harvest) | Distributed knowledge |
| [Publications](#publications) | Content management |
| [Project Management](#project-management) | Project tracking |
| [Live Session](#live-session) | Live analysis |
| [Visuals](#visuals) | Video documentation |
| [Live Network](#live-network) | Network beacon |
| [Multipart Help](#multipart-help) | How help is assembled |
| [Command Registry](#command-registry) | Internal routing |

---

## Usage Patterns

The Knowledge system accepts requests through **three entry patterns**. Every command works with all three.

### 1. Direct Command

Type a command as your session entry prompt. The system detects the command, executes it, and reports the result.

```
project create mon projet
harvest --healthcheck
pub check --all
```

**Best for**: Known commands with clear syntax. Fast, one-shot execution.

### 2. Natural Language

Describe what you want in plain language. The system interprets your intent and maps it to the appropriate command.

```
peux-tu me créer un projet ayant comme titre "go for it"
vérifie la fraîcheur de toutes mes publications
j'aimerais voir l'état du réseau de satellites
```

**Best for**: When you know what you want but not the exact syntax.

### 3. Interactive Session

Enter interactive mode with a command or request. The system displays `help` automatically, executes your initial request, then stays in free-form mode for follow-up work.

```
interactif
project create mon nouveau projet
```

**Best for**: Multi-step work sessions, exploratory tasks, chaining several operations. Type `terminé` or `done` to end.

### Pattern Comparison

| Pattern | Entry | Execution | Session | Follow-up |
|---------|-------|-----------|---------|-----------|
| **Direct** | Command syntax | Immediate | Single command | New prompt needed |
| **Natural language** | Plain text | Interpreted → executed | Single request | New prompt needed |
| **Interactive** | `interactif` + description | Help displayed → request executed | Persistent free-form | Type next command or `terminé` |

---

## Session Management

Session management commands bridge K_TOOLS (command framework) and K_MIND (memory system). Commands that delegate to K_MIND scripts are marked with *(K_MIND)*. Commands with standalone scripts in `K_TOOLS/scripts/session/` are marked with *(script)*.

| Command | What It Does | Backend |
|---------|-------------|---------|
| <a id="cmd-refresh"></a>`refresh` | Lightweight context restore — re-run `/mind-context`, re-read CLAUDE.md, git status | *(K_MIND)* `session_init.py --preserve-active` + `/mind-context` |
| <a id="cmd-help-aide"></a>`help` / `aide` / `?` | **Multipart help** — print knowledge commands + project commands | *(script)* `help_command.py` |
| <a id="cmd-status"></a>`status` | Summarize current state — K_MIND stats + git status + work items | *(K_MIND)* `memory_stats.py` + near_memory |
| <a id="cmd-save"></a>`save` | Pre-save summary → commit, push, create PR to default branch | *(script)* `session/save_session.py` |
| <a id="cmd-remember"></a>`remember ...` | Append text to K_MIND memory | *(K_MIND)* `memory_append.py` |
| <a id="cmd-elevate"></a>`elevate` | Elevate session to full autonomous — detect `GH_TOKEN` env var | *(inline)* checks env |
| <a id="cmd-resume"></a>`resume` | Resume interrupted session from checkpoint | *(K_MIND)* `session_init.py --preserve-active` + *(script)* `session/checkpoint.py` |
| <a id="cmd-recover"></a>`recover` | Search `claude/*` branches for stranded work, cherry-pick/apply | *(script)* `session/recover.py` |
| <a id="cmd-recall"></a>`recall` | Deep memory search — K_MIND memory → git → GitHub → deep files | *(script)* `session/recall.py` |
| <a id="cmd-checkpoint"></a>`checkpoint` | Show current checkpoint state | *(script)* `session/checkpoint.py` |
| `<cmd> ?` | Contextual help for any command | *(script)* `help_contextual.py` |

### `recall` — Deep Memory Search

Four-layer progressive search, each layer searched only if previous layers didn't find enough:

| Layer | Sources | Speed |
|-------|---------|-------|
| **K_MIND** | near_memory, far_memory, archives | ~5s |
| **Git** | commit messages across all branches | ~10s |
| **GitHub** | issue titles, PR descriptions (requires GH_TOKEN) | ~15s |
| **Deep** | domain JSONs, methodology, publications | ~30s |

```bash
python3 Knowledge/K_TOOLS/scripts/session/recall.py --query "architecture" --layers near git
```

### `recover` — Branch Recovery

Scans all `claude/*` and `backup-*` branches for unmerged commits. Shows file diffs, PR status. Offers cherry-pick or diff-apply recovery.

```bash
python3 Knowledge/K_TOOLS/scripts/session/recover.py
python3 Knowledge/K_TOOLS/scripts/session/recover.py --cherry-pick abc1234
```

### `save` — Session Save Protocol

1. Compile pre-save summary from K_MIND near/far memory + git stats
2. Commit all pending changes
3. Push to branch
4. Create PR to default branch
5. Optionally merge (if elevated)

```bash
python3 Knowledge/K_TOOLS/scripts/session/save_session.py --summary   # preview
python3 Knowledge/K_TOOLS/scripts/session/save_session.py --save      # full protocol
python3 Knowledge/K_TOOLS/scripts/session/save_session.py --save --merge  # save + merge
```

### `checkpoint` — Crash Recovery State

Persists execution phase to `.claude/checkpoint.json` so Claude knows exactly where work was interrupted on resume.

Phases: `idle` → `pre_execution` → `executing` → `completed` / `failed` → `saving`

```bash
python3 Knowledge/K_TOOLS/scripts/session/checkpoint.py --status
python3 Knowledge/K_TOOLS/scripts/session/checkpoint.py --write executing -d "importing scripts"
python3 Knowledge/K_TOOLS/scripts/session/checkpoint.py --clear
```

---

## Normalize

Structure concordance audit — validates mindmap vs domain JSONs, module registration, documentation references.

| Command | What It Does |
|---------|-------------|
| <a id="cmd-normalize"></a>`normalize` | Audit knowledge structure concordance (default: report mode) |
| <a id="cmd-normalize-fix"></a>`normalize --fix` | Report issues, Claude applies appropriate fixes |
| <a id="cmd-normalize-check"></a>`normalize --check` | Report only, no changes |

Checks performed:
1. Mindmap work items vs work.json entries (all modules)
2. Module registration in modules.json vs actual K_* directories
3. Documentation references vs actual files
4. Mindmap node integrity (expected groups present)

```bash
python3 Knowledge/K_TOOLS/scripts/session/normalize.py --check
python3 Knowledge/K_TOOLS/scripts/session/normalize.py --json
```

---

## Harvest

Distributed knowledge management — pull, review, stage, and promote insights from satellite projects.

| Command | What It Does |
|---------|-------------|
| <a id="cmd-harvest"></a>`harvest <project>` | Pull distributed knowledge from a satellite project into `minds/` |
| <a id="cmd-harvest-list"></a>`harvest --list` | List all harvested projects with version + drift status |
| <a id="cmd-harvest-procedure"></a>`harvest --procedure` | Guided promotion walkthrough — steps, state, next actions |
| <a id="cmd-harvest-healthcheck"></a>`harvest --healthcheck` | Full network sweep — all satellites, update dashboard, process auto-promotes |
| <a id="cmd-harvest-review"></a>`harvest --review <N>` | Mark insight #N as reviewed (human validated) |
| <a id="cmd-harvest-stage"></a>`harvest --stage <N> <type>` | Stage for integration (type: lesson, pattern, methodology, evolution, docs, project) |
| <a id="cmd-harvest-promote"></a>`harvest --promote <N>` | Promote to core knowledge now (writes to patterns/ or lessons/) |
| <a id="cmd-harvest-auto"></a>`harvest --auto <N>` | Enable auto-promote on next healthcheck run |
| <a id="cmd-harvest-fix"></a>`harvest --fix <project>` | Update satellite's CLAUDE.md to latest knowledge version |
| `harvest <cmd> ?` | Contextual help for any harvest subcommand |

---

## Publications

Content management — create, validate, sync, review, export, and generate webcards.

| Command | What It Does |
|---------|-------------|
| <a id="cmd-pub-list"></a>`pub list` | List all publications with source/docs/webcard status |
| <a id="cmd-pub-check"></a>`pub check <#>` | Validate one publication (source, docs EN/FR, webcard, links, front matter) |
| <a id="cmd-pub-check-all"></a>`pub check --all` | Validate all publications |
| <a id="cmd-pub-new"></a>`pub new <slug>` | Scaffold new publication (source + docs EN/FR + front matter + webcard placeholder) |
| <a id="cmd-pub-sync"></a>`pub sync <#>` | Sync source publication changes to docs web pages |
| <a id="cmd-doc-review"></a>`doc review --list` | Quick freshness inventory — version + severity per publication |
| <a id="cmd-doc-review-all"></a>`doc review <#>` | Review publication against current knowledge state |
| `doc review --all` | Review all publications for freshness |
| <a id="cmd-docs-check"></a>`docs check <path>` | Validate one doc page (front matter, links, language mirror, OG image) |
| <a id="cmd-docs-check-all"></a>`docs check --all` | Validate all doc pages |
| <a id="cmd-webcard"></a>`webcard <target>` | Generate animated OG GIFs — by card, group, or publication number |
| <a id="cmd-weblinks"></a>`weblinks` | Print all GitHub Pages URLs in block code |
| <a id="cmd-weblinks-admin"></a>`weblinks --admin` | Same with conformity status indicators per link |
| <a id="cmd-pub-export-pdf"></a>`pub export <#> --pdf` | Export publication to PDF |
| <a id="cmd-pub-export-docx"></a>`pub export <#> --docx` | Export publication to DOCX |
| <a id="cmd-profile-update"></a>`profile update` | Refresh all 8 profile files with current stats |
| `<cmd> ?` | Contextual help for any pub/doc/webcard/weblinks/profile command |

---

## Project Management

| Command | What It Does |
|---------|-------------|
| <a id="cmd-project-list"></a>`project list` | List all projects with P# index, type, status, satellite count |
| <a id="cmd-project-info"></a>`project info <P#>` | Show project details — identity, publications, satellites, evolution, stories |
| <a id="cmd-project-create"></a>`project create <name>` | Full creation: register P# + GitHub Project board + web presence |
| <a id="cmd-project-register"></a>`project register <name>` | Register a new project with P# ID — creates `projects/<slug>.md` |
| <a id="cmd-project-review"></a>`project review <P#>` | Review project state — documentation, publications, required assets, freshness |
| <a id="cmd-project-review-all"></a>`project review --all` | Review all projects |
| <a id="cmd-n-note"></a>`#N: <content>` | Scoped note — `#` call alias routes to project N |
| <a id="cmd-n-methodology"></a>`#N:methodology:<topic>` | Methodology insight — flagged for doc harvesting |
| <a id="cmd-n-principle"></a>`#N:principle:<topic>` | Design principle — flagged for doc harvesting |
| <a id="cmd-n-info"></a>`#N:info` | Show accumulated knowledge for #N |
| <a id="cmd-n-done"></a>`#N:done` | End documentation focus, compile summary |
| <a id="cmd-g-board-item"></a>`g:<board>:<item>` | Reference a GitHub board item by position |
| <a id="cmd-g-board-item-done"></a>`g:<board>:<item>:done` | Mark board item as Done (compilation trigger) |
| <a id="cmd-g-board-item-progress"></a>`g:<board>:<item>:progress` | Move board item to In Progress |
| `g:<board>:<item>:info` | Detailed board item view |
| `<cmd> ?` | Contextual help for any project command |

---

## Live Session

Real-time stream monitoring and analysis.

| Command | What It Does |
|---------|-------------|
| <a id="cmd-i-m-live"></a>`I'm live` | Pull latest clips, extract last frame from newest clip, report UI state |
| <a id="cmd-multi-live"></a>`multi-live` | Monitor multiple streams simultaneously, report comparative state |
| <a id="cmd-recipe"></a>`recipe` | Print the live capture quick recipe (OBS + stream_capture.py params) |
| `<cmd> ?` | Contextual help for any live session command |

### `I'm live` Flow
1. `git pull origin <branch> --rebase`
2. Extract last frame from newest clip (highest number = newest)
3. Report: active tab, entry range, page number, log count, button states, anomalies
4. On follow-up, pull and extract again

### `recipe` Output
```
Live Capture — Quick Recipe

1. Windows: Start OBS → Tools → RTSP Server → Start (port 8554, path /live)
2. WSL:
   cd /path/to/project
   python3 live/stream_capture.py --dynamic --rtsp rtsp://localhost:8554/live --scale 0.75 --crf 22 --push-interval 5
3. Claude: "I'm live" — starts monitoring clips
4. Stop: Ctrl+C in WSL (clips persist for montage, cleaned at next start)

Presets:
  QA session (recommended):  --scale 0.75 --crf 22 --push-interval 5
  UART text (sharp):         --scale 1.0  --crf 22 --clip-secs 3
  High quality debug:        --scale 1.0  --crf 18 --fps 30
  Save bandwidth:            --fps 10     --clip-secs 5 --crf 32
```

---

## Visuals

Automated documentation from video recordings using OpenCV + Pillow + NumPy.

| Command | What It Does |
|---------|-------------|
| <a id="cmd-visual"></a>`visual <path>` | Extract evidence frames from video (default: detection mode) |
| <a id="cmd-visual-timestamps"></a>`visual <path> --timestamps 10 30 60` | Extract frames at specific seconds |
| `visual <path> --times HH:MM:SS ...` | Extract frames at clock times |
| `visual <path> --dates "YYYY-MM-DD HH:MM:SS" ...` | Extract frames at date-times |
| <a id="cmd-visual-detect"></a>`visual <path> --detect` | Scan video for significant frames automatically |
| `visual <path> --detect --subjects kw1 kw2` | Content-aware detection with keyword hints |
| `visual --repo owner/repo --file path/video.mp4` | Fetch and process video from GitHub |
| <a id="cmd-visual-report"></a>`visual <path> --report` | Generate markdown evidence report |
| <a id="cmd-visual-sheet"></a>`visual <path> --sheet` | Generate contact sheet (thumbnail grid) |
| <a id="cmd-visual-dedup"></a>`visual <path> --dedup` | Deduplicate near-identical frames |
| <a id="cmd-visual-info"></a>`visual <path> --info` | Show video metadata only (no extraction) |
| <a id="cmd-deep"></a>`deep <description>` | Frame-by-frame deep analysis of a spotted anomaly |
| <a id="cmd-analyze"></a>`analyze <path>` | Static video file analysis with state progression timeline |
| `<cmd> ?` | Contextual help for any visual command |

### Detection Heuristics

| Detector | What It Finds | Method |
|----------|--------------|--------|
| Scene change | Visual transitions | Histogram correlation |
| Text density | Text-heavy frames | Adaptive threshold + morphology |
| Edge density | Diagrams, tables, code | Canny edge detection |
| Structured content | Grids, forms | Horizontal + vertical line detection |

### Full Pipeline
```
visual recording.mp4 --detect --dedup --report --sheet --title "Sprint Demo Evidence"
```

---

## Live Network

| Command | What It Does |
|---------|-------------|
| <a id="cmd-beacon"></a>`beacon` | Knowledge beacon status and peer discovery |
| `<cmd> ?` | Contextual help for any live network command |

---

## Multipart Help

The `help` command assembles output from two sources:

```
┌───────────────────────────────────┐
│  Part 1: Knowledge Commands       │  ← from K_TOOLS (this module)
│  (session + live analysis)        │     Always present in every project
├───────────────────────────────────┤
│  Part 2: Project Commands         │  ← from <project>/CLAUDE.md
│  (project-specific)               │     Varies per project
└───────────────────────────────────┘
```

**Rule**: Any project that reads the Knowledge system inherits Part 1 automatically. Part 2 is defined by each project independently. Commands are never duplicated — they are concatenated.

---

## Behavioral Routing Table

Every user request is dispatched through the **behavioral routing table** (`routing.json` v2.0). The system matches your subject + action to a specific methodology, skill, and script chain. Routes with `[PROOF]` **must** deliver visual artifacts (GIF, MP4, or PNG).

### Full Dispatch Table — 31 Routes

| Route | Depth | Proof | Chain Dependencies |
|-------|:-----:|:-----:|-------------------|
| **web-page-visualization** | 0 | yes | — |
| **web-production-pipeline** | 1 | yes | web-page-visualization |
| **web-pagination-export** | 1 | yes | web-page-visualization |
| **webcard-generation** | 1 | yes | visual-documentation |
| **documentation-generation** | 2 | yes | webcard + pipeline + export |
| **interactive-documentation** | 1 | yes | web-page-visualization |
| **interface-creation** | 2 | yes | web-viz + interactive-doc |
| **visual-documentation** | 0 | yes | — |
| **project-management** | 1 | — | github-operations |
| **documentation-validation** | 1 | — | web-page-visualization |
| **memory-management** | 0 | — | — |
| **session-lifecycle** | 0 | — | — |
| **module-creation** | 1 | — | reference-concordance |
| **test-report-generation** | 3 | yes | web-viz + visual + doc-gen |
| **security-audit** | 1 | yes | web-viz + visual-doc |
| **behavior-creation** | 1 | — | reference-concordance |
| **reference-concordance** | 0 | — | — |
| **github-operations** | 0 | — | — |
| **profile-management** | 0 | — | — |
| **network-operations** | 0 | — | — |
| **knowledge-compilation** | 0 | — | — |
| **structure-normalization** | 0 | — | — |
| **work-cycle-management** | 0 | — | — |
| **documentation-audience** | 0 | — | — |
| **code-engineering** | 4 | — | test-report-generation |
| **task-intake** | 0 | — | — |
| **help-and-reference** | 0 | — | — |
| **github-sync** | 1 | — | github-operations |
| **crash-recovery** | 0 | — | — |
| **ephemeral-capture** | 0 | — | — |
| **publication-lifecycle** | 0 | — | — |

**Stats**: 184 unique subjects, 201 action entries, 42 skills, 48 scripts, 10 proof routes. Max chain depth: 4.

### Subject → Route Quick Reference

| Subject Keywords | Route | Methodology |
|-----------------|-------|-------------|
| web, css, layout, html, page, render, screenshot | web-page-visualization | web-page-visualization.md |
| viewer, docs, deploy, github-pages | web-production-pipeline | web-production-pipeline.md |
| pdf, docx, export, print, pagination | web-pagination-export | web-pagination-export.md |
| webcard, og-image, social, preview-card | webcard-generation | webcard-generation.md |
| publication, documentation, article, story | documentation-generation | documentation-generation.md |
| interface, panel, navigator, widget | interactive-documentation | interactive-documentation.md |
| dashboard, ui, component | interface-creation | interface-creation.md |
| video, frame, stream, recording, evidence | visual-documentation | user-guide.md |
| project, task, board, workflow, roadmap | project-management | project-management.md |
| validation, integrity, quality | documentation-validation | *(direct)* |
| memory, recall, archive, far-memory, near-memory | memory-management | methodology-import-system.md |
| session, startup, resume, checkpoint | session-lifecycle | session-protocol.md |
| module, knowledge-module, K_ | module-creation | module-creation.md |
| test, report, qa, assessment | test-report-generation | test-report-generation.md |
| security, owasp, token, vulnerability | security-audit | *(direct)* |
| behavior, directive, convention, rule | behavior-creation | methodology-behavior-creation.md |
| concordance, references, cross-references, sync | reference-concordance | reference-concordance.md |
| github, pr, pull-request, issue, branch, merge | github-operations | *(direct)* |
| profile, portfolio, bio, recommendation | profile-management | *(direct)* |
| network, satellite, beacon, harvest | network-operations | *(direct)* |
| compile, data, sessions, tasks, configurations | knowledge-compilation | metrics-compilation.md |
| normalize, structure, frontmatter, en-fr | structure-normalization | *(direct)* |
| work, cycle, delivery, progress, staged | work-cycle-management | task-workflow.md |
| audience, tone, voice, style, persona | documentation-audience | documentation-audience.md |
| code, script, function, feature, bug, refactor | code-engineering | *(direct)* |
| request, instruction, ask, question | task-intake | *(direct)* |
| help, command, reference, guide | help-and-reference | commands.md |
| github-sync, enrichment, github-data | github-sync | github-project-integration.md |
| crash, recovery, stranded, backup | crash-recovery | checkpoint-resume.md |
| plan, todo, ephemeral, draft | ephemeral-capture | *(direct)* |
| pub, publication-list, publication-check | publication-lifecycle | *(direct)* |

### Chain Dependency Map

Routes may trigger **collateral routes** (max depth 5, max same-route reentry 2). The routing stack prevents infinite loops.

```
test-report-generation (depth 3)
  ├→ web-page-visualization
  ├→ visual-documentation
  └→ documentation-generation (depth 2)
       ├→ webcard-generation
       │    └→ visual-documentation
       ├→ web-production-pipeline
       │    └→ web-page-visualization
       └→ web-pagination-export
            └→ web-page-visualization

code-engineering (depth 4)
  └→ test-report-generation (depth 3)
       └→ ... (see above)

interface-creation (depth 2)
  ├→ web-page-visualization
  └→ interactive-documentation
       └→ web-page-visualization
```

### Routing Lookup

```bash
# Forward: what do I use for this task?
python3 scripts/routing_lookup.py --subject web --action fix

# Display: show the routing trace
python3 scripts/routing_display.py --callout --subject test --action generate

# Compact: one-liner for minor decisions
python3 scripts/routing_display.py --compact --subject code --action create

# Full summary: all routes
python3 scripts/routing_display.py --summary

# Chain map: dependency visualization
python3 scripts/routing_display.py --chain-map
```

---

## Command Registry

Every command is backed by a skill and registered in the command registry. When matching user input, the registry uses **longest-match-first** sorting — `harvest --healthcheck` matches before `harvest`, `normalize --fix` matches before `normalize`.

| Group | Skill Files | Methodology |
|-------|------------|-------------|
| **Session** | recall.py, recover.py, save_session.py, checkpoint.py, normalize.py, session_notes.py | K_MIND scripts (memory_append, session_init, memory_stats) |
| **Harvest** | harvest.md, healthcheck.md | production-development-minds.md |
| **Publications** | pub.md, pub-export.md, webcard.md, profile-update.md | documentation-generation.md, web-pagination-export.md |
| **Project** | project-create.md, project-manage.md | project-management.md, project-create.md |
| **Normalize** | normalize.md | Publication #6 |
| **Live** | live-session.md | interactive-diagnostic.md |
| **Visual** | visual.md | visual-documentation.md |

---

*This guide evolves as legacy commands are imported into the K_TOOLS module.*

## Completion

When a user guide publication is ready, follow the **Publication Completion Checklist** in `Knowledge/K_DOCS/methodology/documentation-generation.md#publication-completion-checklist` — page creation, HTML redirects, viewer index registration, navigator data, parent index updates, and link registry. Guide publications need entries in `docs/data/documentation.json` (navigator) and the viewer JS documents array.

---

*See also: [Main Navigator Guide]({{ '/publications/guide-main-navigator/' | relative_url }}) — [Knowledge 2.0]({{ '/publications/knowledge-2-0/' | relative_url }})*
