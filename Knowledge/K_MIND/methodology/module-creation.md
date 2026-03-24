# Methodology — Create a New Knowledge Module

## Purpose
Create a new K_* module in the Knowledge 2.0 multi-module architecture. This covers the full lifecycle: GitHub repository, local structure, system registration, documentation integration, and subtree synchronization.

## Prerequisites
- Active K_MIND session in the host project (e.g., K_DOCS)
- GitHub access with GH_TOKEN configured
- Understanding of the module's purpose and domain

## Step-by-Step

### 1. Create the GitHub Repository

Create an empty `packetqc/K_<NAME>` repository on GitHub:

```python
from knowledge.engine.scripts.gh_helper import GitHubHelper
gh = GitHubHelper()
gh.repo_create('packetqc/K_TOOLS', description='Knowledge Tools — command framework and utilities', private=False)
```

Or manually via GitHub UI. The repo starts empty — all content is developed in the host project first.

### 2. Create the Local Module Structure

Use the install script or create manually:

```bash
# Option A: Install script (basic scaffold)
bash Knowledge/K_MIND/scripts/install.sh K_TOOLS

# Option B: Manual (full control)
mkdir -p Knowledge/K_TOOLS/{conventions,documentation,methodology,scripts,work}
```

### 3. Create Required Files

Every module needs these 4 files + README:

**README.md** — Module purpose, structure, integration:
```markdown
# K_TOOLS — Command Framework & Utilities Module

Description of what the module manages.

## Structure
(list directories and key files)

## Integration
- Sessions and mindmap stay centralized in K_MIND
- Domain-specific conventions, documentation, and work tracked here
- Scripts in K_MIND auto-detect this module via `K_*` sibling scanning

---
*Part of the Knowledge 2.0 multi-module architecture*
```

**conventions/conventions.json**:
```json
{
  "module": "K_TOOLS",
  "conventions": []
}
```

**documentation/documentation.json**:
```json
{
  "domain": "documentation",
  "module": "K_TOOLS",
  "references": [],
  "external_files": []
}
```

**work/work.json**:
```json
{
  "module": "K_TOOLS",
  "work": []
}
```

### 4. Register in modules.json

Add the module entry to `Knowledge/modules.json`:

```json
{
  "id": "K_TOOLS",
  "name": "Knowledge Tools",
  "description": "Command framework and utilities module",
  "status": "active",
  "imported": false,
  "upstream": null,
  "path": "Knowledge/K_TOOLS",
  "has": ["conventions", "documentation", "methodology", "scripts", "work"]
}
```

**Fields:**
- `status`: "active" (ready), "imported" (imported but not fully adapted)
- `imported`: false for new modules, true for modules imported from another repo
- `upstream`: null for new modules, or "packetqc/knowledge" for imported ones
- `has`: list of subdirectories present in the module

### 5. Update the Mindmap

Add the module under two nodes in `mind/mind_memory.md`:

**Under `work::en cours`** (active work):
```
K_TOOLS module creation
  command framework and help system module
  import legacy commands into Knowledge 2.0
```

**Under `work::validation::multi module architecture`** (module registry):
```
K_TOOLS command framework and utilities module
```

### 6. Verify Auto-Discovery

Run memory stats to confirm the module is detected:
```bash
python3 Knowledge/K_MIND/scripts/memory_stats.py
```

The domain JSONs count should increase (3 new files: conventions.json, documentation.json, work.json). The mindmap node count should also increase.

### 7. Add Methodology Content

Place domain-specific methodology documents in `Knowledge/K_TOOLS/methodology/`:
- These are the operational reference docs for the module
- Import from legacy if available, or create fresh
- Register in `documentation/documentation.json` references

### 8. Create Documentation Integration

**User guide** — Create as methodology doc in the module:
```
Knowledge/K_TOOLS/methodology/user-guide.md
```

**Web presence** — Create guide pages for the main interface:
```
docs/publications/guide-<name>/index.md      # Summary
docs/publications/guide-<name>/full/index.md  # Full reference
```

**Register in data files:**
- `docs/data/documentation.json` → Add guide entry under "Guides" group
- `docs/data/methodologies.json` → Add methodology entries for K_TOOLS

### 9. Commit and Push to Host

Commit all changes to the host project (K_DOCS). Push to **staging branch only** — not production.

### 10. Create Module Repository (Subtree Push)

Once content is ready, push the module to its own repository:

```bash
# Add remote (one-time)
git remote add k_tools https://github.com/packetqc/K_TOOLS.git

# Push subtree
git subtree push --prefix Knowledge/K_TOOLS k_tools main
```

This creates the `main` branch in the K_TOOLS repo with all the module content.

### 11. Future Sync

**Push changes from host to module repo:**
```bash
git subtree push --prefix Knowledge/K_TOOLS k_tools main
```

**Pull changes from module repo to host:**
```bash
git subtree pull --prefix Knowledge/K_TOOLS k_tools main --squash
```

## Checklist

| Step | Action | Verified |
|------|--------|----------|
| 1 | GitHub repo `packetqc/K_<NAME>` created | |
| 2 | Local directory `Knowledge/K_<NAME>/` created | |
| 3 | README.md + 3 JSON files created | |
| 4 | Registered in `Knowledge/modules.json` | |
| 5 | Mindmap updated (en cours + multi module architecture) | |
| 6 | Auto-discovery confirmed via `memory_stats.py` | |
| 7 | Methodology content placed | |
| 8 | Documentation integration (guide + data files) | |
| 9 | Committed and pushed to host staging | |
| 10 | Subtree push to module repo | |

## Architecture Notes

- **No module registry code** — modules are discovered by glob pattern (`Knowledge/K_*`)
- **Sessions are shared** — all modules use K_MIND's `sessions/` folder
- **Mindmap is shared** — single `mind/mind_memory.md` in K_MIND
- **Scripts scan automatically** — `memory_stats.py` walks all `K_*` siblings
- **Content lives in the module** — methodology, conventions, work all belong to the module, not to K_DOCS or K_MIND
- **Web presence lives in docs/** — guide pages and data file entries for the main interface

## Completion

Module creation produces guide publications and data file entries. After the module is scaffolded, follow the **Publication Completion Checklist** in `Knowledge/K_DOCS/methodology/documentation-generation.md#publication-completion-checklist` for the guide publication — page creation, HTML redirects, viewer index registration, navigator data, and link registry.

## Related
- [Import System](methodology-import-system.md) — Creating new projects from K_MIND
- [install.sh](../scripts/install.sh) — Bootstrap script for basic module scaffold
- `Knowledge/K_DOCS/methodology/documentation-generation.md` — Publication completion checklist
