# Methodology — K_MIND Import System

## Purpose
Create a new project with K_MIND memory system capabilities. K_MIND is the core Knowledge module — other modules (like K_DOCS) are built on top of it by cloning K_MIND as their foundation.

## Prerequisites
- Python 3 available
- GitHub access
- GH_TOKEN configured in VS Code settings (`claudeCode.environmentVariables`)
- Use WSL terminal / Claude Code CLI for initialization

## New Project from K_MIND (Recommended)

Since K_MIND is structured with `Knowledge/K_MIND/` at its root, a clone is a ready-to-use project. No install script needed.

### 1. Clone K_MIND as the new project
```bash
git clone https://github.com/packetqc/K_MIND.git /path/to/NEW_PROJECT
cd /path/to/NEW_PROJECT
```

### 2. Create the new repo on GitHub
Create the repo manually on GitHub, or ask Claude in a session with GH_TOKEN configured:
> "Create a GitHub repo called NEW_PROJECT using gh_helper"

Claude will use the `/github` skill and `gh_helper.py` with the token from the environment — never exposing it.

### 3. Change the remote and push
```bash
git remote set-url origin https://github.com/packetqc/NEW_PROJECT.git
git push -u origin main
```

### 4. Create the Knowledge module
```bash
bash Knowledge/K_MIND/scripts/install.sh K_DOCS
```
This creates `Knowledge/K_DOCS/` alongside K_MIND. The install script validates that K_MIND is present and creates the module directory.

### 5. Launch Claude Code
```bash
claude
```

That's it. The hook detects `Knowledge/K_MIND/scripts`, initializes the session, and Claude auto-invokes `/mind-context`. Everything is inherited from K_MIND: CLAUDE.md, .claude/ (hooks, skills, settings), and the full Knowledge/K_MIND/ system.

## What You Get Out of the Box
- `CLAUDE.md` — complete K_MIND instructions (lifecycle, GitHub operations, memory maintenance)
- `.claude/hooks/session-start.sh` — auto-detects K_MIND, initializes sessions
- `.claude/settings.json` — SessionStart hook configuration
- `.claude/skills/` — mind-context, mind-depth, mind-stats, github
- `Knowledge/K_MIND/` — full memory system (mind, scripts, sessions, conventions, etc.)

## How It Works

### Path Detection
The `session-start.sh` hook checks:
```bash
if [ -d "Knowledge/K_MIND/scripts" ]; then
    K_MIND_ROOT="Knowledge/K_MIND"
else
    K_MIND_ROOT="."
fi
```
Skills also auto-detect via `os.path.isdir('Knowledge/K_MIND/scripts')`.

### No Separate CLAUDE.md Needed
The root CLAUDE.md contains all K_MIND instructions directly. No reference indirection, no generated templates. What works in K_MIND works identically in the new project.

## Updating K_MIND in a Project
When K_MIND evolves upstream:
```bash
# Add K_MIND as a remote (one-time)
git remote add k_mind https://github.com/packetqc/K_MIND.git

# Pull updates
git fetch k_mind main
git merge k_mind/main --allow-unrelated-histories
```

Or selectively update just the Knowledge/K_MIND/ directory:
```bash
cd Knowledge/K_MIND
# (if it's a subtree or you manually sync files)
```

## Adding New Knowledge Modules
To add a new module (e.g., K_DOCS) alongside K_MIND:
```bash
bash Knowledge/K_MIND/scripts/install.sh K_DOCS
```
This creates `Knowledge/K_DOCS/` with a basic module structure. The script validates K_MIND presence, prevents duplicates, and reports the created directory.

## Known Issues and Lessons Learned

### GH_TOKEN setup
`gh_helper.py` reads `GH_TOKEN` from environment. Configure in VS Code:
```json
"claudeCode.environmentVariables": [
    {"name": "GH_TOKEN", "value": "ghp_..."}
]
```
Token is never passed as argument or exposed in session output. Requires session restart to take effect.

### GitHub skill must be explicit
Claude does not automatically use `/github` skill after import. The root CLAUDE.md includes a `## GitHub Operations — MANDATORY` section that instructs Claude to use gh_helper.py for all GitHub operations.

### Session restart after config changes
VS Code environment variables (`GH_TOKEN`, etc.) are only loaded when a new Claude Code session starts. After changing settings.json, restart the session.

## Key Files
| File | Location | Role |
|------|----------|------|
| `CLAUDE.md` | root | Complete K_MIND instructions (inherited by all projects) |
| `.claude/hooks/session-start.sh` | root | Auto-detect K_MIND, init session |
| `.claude/settings.json` | root | SessionStart hook config |
| `.claude/skills/` | root | All skills (mind-context, mind-depth, mind-stats, github) |
| `Knowledge/K_MIND/scripts/` | K_MIND | All Python scripts (memory, mindmap, gh_helper) |
| `Knowledge/K_MIND/mind/` | K_MIND | Mindmap (mind_memory.md) |
| `Knowledge/K_MIND/sessions/` | K_MIND | Far memory, near memory, archives |
| `Knowledge/K_MIND/scripts/install.sh` | K_MIND | Bootstrap for adding new modules |

## Architecture Context
K_MIND repo is self-hosting: it uses `Knowledge/K_MIND/` internally (dogfooding its own imported mode). A clone of K_MIND IS a functional project. New Knowledge modules are added under `Knowledge/` alongside K_MIND.
