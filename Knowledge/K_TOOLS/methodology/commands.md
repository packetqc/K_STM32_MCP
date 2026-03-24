# Quick Commands Reference

The user types short phrases to trigger specific Claude actions.

---

## Multipart Help Architecture

The `help` command outputs a **concatenated** command table from two sources:

```
┌───────────────────────────────────┐
│  Part 1: Knowledge Commands       │  ← from K_TOOLS/methodology/commands.md
│  (session + live analysis)        │     Always present in every project
├───────────────────────────────────┤
│  Part 2: Project Commands         │  ← from active project CLAUDE.md
│  (project-specific)               │     Varies per project
└───────────────────────────────────┘
```

**Rule**: Any project with K_TOOLS installed inherits Part 1 automatically. Part 2 is defined by each project independently. Commands are never duplicated — they are concatenated.

---

## Usage Patterns — Three Ways to Work

The Knowledge system accepts requests through **three entry patterns**. Every command listed below works with all three — choose the pattern that fits your workflow.

### 1. Direct Command

Type a command as your session entry prompt. The system detects the command, executes it, and reports the result.

```
project create mon projet
```
```
harvest --healthcheck
```
```
pub check --all
```

**Best for**: Known commands with clear syntax. Fast, one-shot execution.

### 2. Natural Language

Describe what you want in plain language. The system interprets your intent and maps it to the appropriate command or workflow.

```
peux-tu me créer un projet ayant comme titre "go for it"
```
```
vérifie la fraîcheur de toutes mes publications
```
```
j'aimerais voir l'état du réseau de satellites
```

**Best for**: When you know what you want but not the exact command syntax. The system understands intent and acts accordingly.

### 3. Interactive Session

Enter interactive mode with a command or request in the description. The system starts an interactive session, displays `help` automatically, executes your initial request, then stays in free-form mode for follow-up work.

```
interactif
project create mon nouveau projet
```
```
interactif
je veux créer un projet, ajouter des publications et générer les webcards
```
```
interactif
diagnostic sur le pipeline de build
```

**Best for**: Multi-step work sessions, exploratory tasks, or when you want to chain several operations. The session persists until you type `terminé` or `done`.

### Pattern Comparison

| Pattern | Entry | Execution | Session | Follow-up |
|---------|-------|-----------|---------|-----------|
| **Direct** | Command syntax | Immediate | Single command | New prompt needed |
| **Natural language** | Plain text | Interpreted → executed | Single request | New prompt needed |
| **Interactive** | `interactif` + description | Help displayed → request executed | Persistent free-form | Type next command or `terminé` |

**Key insight**: The interactive pattern combines the best of both worlds — your initial description (command or natural language) starts the first task, and the persistent session lets you continue with any combination of commands, natural language, or free-form instructions until you're done.

---

## Part 1 — Knowledge Commands (Always Available)

### Session Management

| Command | What Claude Does |
|---------|-----------------|
| `wakeup` | **Auto-runs on session start** — never type as entry prompt. Mid-session: deep re-sync after PRs merged |
| `refresh` | Lightweight mid-session context restore — re-read CLAUDE.md, git status, reprint help |
| `/know` / `aide` / `?` | **Multipart help** — print knowledge commands + project-specific commands (concatenated) |
| `status` | Read `notes/` and summarize current state |
| `save` | Pre-save summary (v50) → save context, commit, push, create PR to default branch |
| `remember ...` | Append text to current session notes |
| `elevate` | Elevate session to full autonomous — detects `GH_TOKEN` env var or `/tmp/.gh_token` temp file |
| `resume` | Resume interrupted session from checkpoint (crash recovery) |
| `recover` | Search `claude/*` branches for stranded work, cherry-pick/apply to current branch (resiliency) |
| `recall` | Deep memory search across all knowledge channels — near memory first, deeper with confirmation |
| `checkpoint` | Show current checkpoint state (or "no active checkpoint" if none) |
| `normalize` | Audit and fix knowledge structure concordance |
| `normalize --fix` | Apply concordance fixes automatically |
| `normalize --check` | Report only, no changes |
| `concord` | Audit reference concordance — cross-references between scripts, skills, docs, routing |
| `concord --fix` | Audit with fix suggestions for Claude to apply |
| `concord --check` | Report only, exit code for CI |
| `<cmd> ?` | Contextual help for any command — usage, examples, publication link |

### Harvest — Distributed Knowledge

| Command | What Claude Does |
|---------|-----------------|
| `harvest <project>` | Pull distributed knowledge from a satellite project into `minds/` |
| `harvest --list` | List all harvested projects with version + drift status |
| `harvest --procedure` | Guided promotion walkthrough — steps, state, next actions |
| `harvest --healthcheck` | Full network sweep — all satellites, update dashboard, process auto-promotes |
| `harvest --review <N>` | Mark insight #N as reviewed (human validated) |
| `harvest --stage <N> <type>` | Stage for integration (type: lesson, pattern, methodology, evolution, docs, project) |
| `harvest --promote <N>` | Promote to core knowledge now (writes to patterns/ or lessons/) |
| `harvest --auto <N>` | Enable auto-promote on next healthcheck run |
| `harvest --fix <project>` | Update satellite's CLAUDE.md to latest knowledge version |
| `harvest <cmd> ?` | Contextual help for any harvest subcommand |

### Content Management

| Command | What Claude Does |
|---------|-----------------|
| `pub list` | List all publications with source/docs/webcard status |
| `pub check <#>` | Validate one publication (source, docs EN/FR, webcard, links, front matter) |
| `pub check --all` | Validate all publications |
| `pub new <slug>` | Scaffold new publication (source + docs EN/FR + front matter + webcard placeholder) |
| `pub sync <#>` | Sync source publication changes to docs web pages |
| `doc review --list` | Quick freshness inventory — version + severity per publication |
| `doc review <#>` | Review publication against current knowledge state |
| `doc review --all` | Review all publications for freshness |
| `docs check <path>` | Validate one doc page (front matter, links, language mirror, OG image) |
| `docs check --all` | Validate all doc pages |
| `webcard <target>` | Generate animated OG GIFs — by card, group, or publication number |
| `weblinks` | Print all GitHub Pages URLs in block code |
| `weblinks --admin` | Same with conformity status indicators per link |
| `pub export <#> --pdf` | Export publication to PDF |
| `pub export <#> --docx` | Export publication to DOCX |
| `profile update` | Refresh all 8 profile files with current stats (versions, publications, issues, stories) |
| `<cmd> ?` | Contextual help for any pub/doc/webcard/weblinks/profile command |

### Project Management

| Command | What Claude Does |
|---------|-----------------|
| `project list` | List all projects with P# index, type, status, satellite count |
| `project info <P#>` | Show project details — identity, publications, satellites, evolution, stories |
| `project create <name>` | Full creation: register P# + GitHub Project board (elevated, linked to repo) + web presence |
| `project register <name>` | Register a new project with P# ID — creates `projects/<slug>.md` in core |
| `project review <P#>` | Review project state — documentation, publications, required assets, freshness |
| `project review --all` | Review all projects |
| `#N: <content>` | Scoped note — `#` call alias routes to project N |
| `#N:methodology:<topic>` | Methodology insight — flagged for doc harvesting |
| `#N:principle:<topic>` | Design principle — flagged for doc harvesting |
| `#N:info` | Show accumulated knowledge for #N |
| `#N:done` | End documentation focus, compile summary |
| `g:<board>:<item>` | Reference a GitHub board item by position |
| `g:<board>:<item>:done` | Mark board item as Done (compilation trigger) |
| `g:<board>:<item>:progress` | Move board item to In Progress |
| `g:<board>:<item>:info` | Detailed board item view |
| `<cmd> ?` | Contextual help for any project command |

### Live Session Analysis

| Command | What Claude Does |
|---------|-----------------|
| `I'm live` | Pull latest clips, extract last frame from newest clip, report UI state |
| `multi-live` | Monitor multiple streams simultaneously, report comparative state |
| `recipe` | Print the live capture quick recipe (OBS + stream_capture.py params) |
| `<cmd> ?` | Contextual help for any live session command |

### Visuals — Automated Documentation from Recordings

| Command | What Claude Does |
|---------|-----------------|
| `visual <path>` | Extract evidence frames from video (default: detection mode) |
| `visual <path> --timestamps 10 30 60` | Extract frames at specific seconds from video start |
| `visual <path> --times HH:MM:SS ...` | Extract frames at clock times (with optional `--video-start`) |
| `visual <path> --dates "YYYY-MM-DD HH:MM:SS" ...` | Extract frames at date-times (with optional `--video-start-datetime`) |
| `visual <path> --detect` | Scan video for significant frames automatically (scene change, text, edges) |
| `visual <path> --detect --subjects kw1 kw2` | Content-aware detection with keyword hints |
| `visual --repo owner/repo --file path/video.mp4` | Fetch and process video from GitHub repository |
| `visual <path> --report` | Generate markdown evidence report |
| `visual <path> --sheet` | Generate contact sheet (thumbnail grid) |
| `visual <path> --dedup` | Deduplicate near-identical frames (perceptual hashing) |
| `visual <path> --info` | Show video metadata only (no extraction) |
| `deep <description>` | Frame-by-frame deep analysis of a spotted anomaly |
| `analyze <path>` | Static video file analysis with state progression timeline |
| `<cmd> ?` | Contextual help for any visual command |

### Live Network

| Command | What Claude Does |
|---------|-----------------|
| `beacon` | Knowledge beacon status and peer discovery |
| `<cmd> ?` | Contextual help for any live network command |

---

## Live Session — Full Details

### `I'm live` flow
1. `git pull origin <branch> --rebase`
2. Extract last frame from `clip_2` (highest number = newest): `ffmpeg -i clip_2.mp4 -vf "select=eq(n\,59)" -vsync vfr -update 1 /tmp/latest_frame.png -y`
3. Report: active tab, entry range, page number, log count, button states, anomalies
4. On follow-up, pull and extract again

### `deep` flow
1. Pull latest clips
2. Extract ALL frames from newest clip: `ffmpeg -i clip_2.mp4 /tmp/deep_frame_%04d.png -y`
3. Frame-by-frame analysis focused on the described anomaly
4. Report: before state → anomaly frames → after state → root cause hypothesis → suggested investigation

### `analyze` flow
1. Extract key frames at regular intervals: `ffmpeg -i <path> -vf "fps=1" /tmp/static_frame_%04d.png -y`
2. For short videos (< 30s), extract every second. For longer videos, sample every 5–10s.
3. Build state progression timeline with anomaly detection
4. Report: timeline summary, state transitions, anomalies, test verdict (pass/fail)

### `multi-live` flow
1. Scan `live/dynamic/` for all clip families
2. Extract last frame from each family's highest-numbered file
3. Report comparative state in a single table
4. Flag cross-source inconsistencies immediately

### `recipe` output
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

### Clip naming convention
```
live/dynamic/
  clip_0.mp4, clip_1.mp4, clip_2.mp4       # Primary: UI
  uart_0.mp4, uart_1.mp4, uart_2.mp4       # Secondary: Serial terminal
  cam_0.mp4,  cam_1.mp4,  cam_2.mp4        # Tertiary: Physical board camera
```

### Live Session Directives
1. No image prints — extract data silently via ffmpeg probes or single-frame reads
2. Start from latest clip (clip_2 → clip_1 → clip_0)
3. Fast 1-frame pulls — last frame of latest clip only
4. Focus on live troubleshooting — no queued tasks during live sessions
5. Proceed with live code modifications based on UART feedback
6. No waiting — report what's visible, propose fixes immediately

### Escalation from live to deep
During a standard `I'm live` session, Claude may **proactively suggest** hybrid analysis when it detects:
- State inconsistency between consecutive pulls
- UI elements in unexpected positions or states
- Data values that don't match expected progression
- Artifacts or rendering glitches in extracted frames

Claude will say: *"Spotted [anomaly] — want me to go deep on this?"*

---

## Visuals — Full Details

### `visual` command

The Visual Documentation Engine processes video files using OpenCV + Pillow + NumPy (no external tools, no cloud APIs).

### Two operating modes

**Timestamp mode** — extract frames at known points:
```bash
# By seconds offset
visual recording.mp4 --timestamps 10.5 30.0 60.0

# By clock time (with optional video start for offset calc)
visual recording.mp4 --times 00:01:30 00:05:00 --video-start 00:00:00

# By date-time
visual recording.mp4 --dates "2026-03-01 14:30:00" --video-start-datetime "2026-03-01 14:00:00"
```

**Detection mode** — automatic frame extraction using computer vision:
```bash
# Default detection (scene change + text + edges + structure)
visual recording.mp4 --detect

# With subject hints and tuned sensitivity
visual recording.mp4 --detect --subjects "UART" "error" --sensitivity 0.25 --max-frames 30

# From GitHub repo
visual --repo packetqc/stm32-poc --file live/dynamic/clip_0.mp4 --detect
```

### Detection heuristics

| Detector | What it finds | Method |
|----------|--------------|--------|
| Scene change | Visual transitions | Histogram correlation |
| Text density | Text-heavy frames | Adaptive threshold + morphology |
| Edge density | Diagrams, tables, code | Canny edge detection |
| Structured content | Grids, forms | Horizontal + vertical line detection |

### Output pipeline

```bash
# Full pipeline: detect + dedup + markdown report + contact sheet
visual recording.mp4 --detect --dedup --report --sheet --title "Sprint Demo Evidence"

# Info only (no extraction)
visual recording.mp4 --info

# JSON output (for programmatic use)
visual recording.mp4 --detect --json
```

### Frame annotation

Extracted frames include optional annotation overlay:
- Timestamp bar (bottom, semi-transparent)
- Source info (filename, resolution)
- Detection badge (green, detection reason)
- Corner marks (green evidence indicators)

Disable with `--no-annotate`.

### `deep` and `analyze` (recording analysis)

These commands originated in Live Session and are now part of the Visuals category:

- `deep <description>`: Frame-by-frame analysis focused on a described anomaly. Extracts ALL frames from the newest clip and builds a before→anomaly→after timeline.
- `analyze <path>`: Static video file analysis. Extracts key frames at regular intervals, builds state progression timeline with anomaly detection.

### Full specification

- `K_DOCS/methodology/visual-documentation.md` — Architecture, modes, output pipeline
- Legacy `scripts/visual_engine.py` — Core processing engine
- Legacy `scripts/visual_cli.py` — CLI entry point
- Publication: Visual Documentation

---

## Part 2 — Project Commands (Examples)

These are defined in each project's own CLAUDE.md. They form the second part of multipart help.

### MPLIB Projects

| Command | What Claude Does |
|---------|-----------------|
| `vanilla <NAME> <LED>` | Generate singleton module from VANILLA template |

**Example**: `vanilla GPS YELLOW`

Creates `MPLIB_GPS.h` and `MPLIB_GPS.cpp` from the template with:
- All naming replacements (class, guards, scope operators, static guard, pointer)
- LED color assignment
- Unique ThreadX entry point (`Services_GPS()`)

**Available LED colors**: `GREEN` | `BLUE` | `YELLOW` | `ORANGE` | `RED` | `CYAN` | `PURPLE`

---

## Knowledge Asset Sync

On `wakeup`, Claude syncs portable assets from Knowledge modules to the active project. Each asset belongs to the K_* module that owns it:

| Asset | Source Module | Source Path | Sync condition |
|-------|:------------:|-------------|----------------|
| GitHub helper | K_MIND | `K_MIND/scripts/gh_helper.py` | If missing |
| Help command | K_TOOLS | `K_TOOLS/scripts/help_command.py` | If missing |
| Help contextual | K_TOOLS | `K_TOOLS/scripts/help_contextual.py` | If missing |

**Rule**: Only sync if the project doesn't already have the asset. Never overwrite existing project files (they may be customized). Only tooling is synced.

---

## Command Registry & Skill Backing (v100)

Every command listed in Part 1 is backed by a **Claude Code skill** (`.claude/skills/<name>.md`) and mapped to the owning K_* module via the command-to-module mapping convention.

### COMMAND_REGISTRY Structure

The registry maps 42 command patterns to their skill, methodology, label, and group:

```python
COMMAND_REGISTRY = {
    "project create": {
        "skill": "project-create",
        "label": "FEATURE",
        "methodology": "project-create.md",
        "description": "Create new project with P# registration",
        "group": "project"
    },
    "harvest --healthcheck": {
        "skill": "healthcheck",
        "label": "CHORE",
        "methodology": "production-development-minds.md",
        "description": "Full network sweep",
        "group": "harvest"
    },
    # ... 40 more entries
}
```

**Longest-match-first**: When matching user input, the registry is sorted by key length descending. This ensures `harvest --healthcheck` matches before `harvest`, and `normalize --fix` matches before `normalize`.

### Skill-to-Command Mapping

| Group | Commands | Skill File | Methodology |
|-------|----------|------------|-------------|
| **Session** | wakeup, refresh, resume, recover, recall, checkpoint, elevate | wakeup.md, resume.md, recall.md | session-protocol.md, checkpoint-resume.md |
| **Harvest** | harvest, harvest --list/--fix/--healthcheck/--review/--stage/--promote/--auto/--procedure | harvest.md, healthcheck.md | production-development-minds.md |
| **Content** | pub list/check/new/sync, pub export, doc review, docs check, webcard, weblinks, profile update | pub.md, pub-export.md, webcard.md, profile-update.md | methodology-documentation-generation.md, web-pagination-export.md |
| **Project** | project list/info/create/register/review | project-create.md, project-manage.md | project-management.md, project-create.md |
| **Normalize** | normalize, normalize --fix/--check | normalize.md | Publication #6 |
| **Tagged Input** | #N:, #N:info, #N:done, g:board:item | tagged-input.md | tagged-input.md, github-board-item-alias.md |
| **Live** | I'm live, multi-live, recipe | live-session.md | interactive-diagnostic.md |
| **Visual** | visual, deep, analyze | visual.md | visual-documentation.md |

### Sub-Task Execution

When a command is detected during the task workflow, it executes as a **tracked sub-task** within the parent task. The sub-task records its own status, commits, and files_modified in `session_data.sub_tasks[]`. See `methodology/task-workflow.md` § "Command Detection & Sub-Task Lifecycle (v100)".

---

## Implementation Notes for New Projects

When setting up a new project:
1. Always implement all Part 1 commands (`wakeup`, `help`, `status`, `save`, `<remember>`, all live commands)
2. `help` always outputs multipart: K_TOOLS commands first, then project commands
3. `wakeup` syncs tooling from Knowledge modules if missing
4. Add Part 2 project-specific commands in the project's own CLAUDE.md
5. K_TOOLS is the single source of truth for Part 1 — project CLAUDE.md never redefines them
