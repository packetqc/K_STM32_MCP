# Reference Concordance Methodology

## Purpose

**Update-first**: When work is completed (scripts added, commands renamed, features delivered), `/concord` updates all system documentation, user documentation, and mindmap assets to stay in sync. The script audits drift; Claude applies the updates.

**Distinct from `/normalize`**: Normalize checks **structure** (EN/FR mirrors, front matter, webcards, links, assets). Concord updates **references** (script listings, command names, routing entries, architecture diagrams, mindmap nodes).

---

## Primary Behavior: Update Documentation After Changes

`/concord` is the **post-delivery sweep**. When triggered, it:

1. **Audits** all cross-references (script runs `concord.py`)
2. **Updates system docs** — CLAUDE.md, SKILL.md, routing.json, conventions.json, documentation.json, architecture-mindmap.md
3. **Updates user docs** — commands.md, user-guide.md, command tables, publication references
4. **Updates mindmap** — mind_memory.md work/convention nodes reflecting the change

This is not passive reporting — Claude reads the audit, then applies all necessary updates across every documentation layer.

---

## Trigger Conditions

Run `/concord` after any of these events:

| Event | What Drifts |
|-------|-------------|
| New script added | CLAUDE.md, SKILL.md, architecture-mindmap.md, routing.json, documentation.json |
| Command/skill renamed | conventions.json, commands.md, routing.json, SKILL.md, user-guide.md |
| Feature completed | mind_memory.md work nodes, work.json, routing.json |
| Module imported | modules.json, routing.json, documentation.json |
| Behavior created | routing.json, conventions.json, mindmap nodes |

---

## Three Documentation Layers

| Layer | Files | What Gets Updated |
|-------|-------|-------------------|
| **System** (Claude reads) | CLAUDE.md, SKILL.md, routing.json, conventions.json, documentation.json | Script references, routing entries, convention definitions |
| **User** (Human reads) | commands.md, user-guide.md, publications | Command tables, usage examples, feature descriptions |
| **Mindmap** (Both) | mind_memory.md, architecture-mindmap.md | Work nodes, architecture nodes, convention nodes |

---

## Concordance Categories (6 Checks)

| # | Category | Source of Truth | Cross-References Checked |
|---|----------|----------------|--------------------------|
| C1 | Script Registry | Actual files in `scripts/` dirs | CLAUDE.md, SKILL.md (mind-context), architecture-mindmap.md, routing.json, documentation.json |
| C2 | Command Names | `.claude/skills/*/SKILL.md` | conventions.json (help_wiring), commands.md, routing.json |
| C3 | Routing Completeness | routing.json routes | scripts listed vs actual scripts, skills listed vs actual skills |
| C4 | Architecture Diagram | architecture-mindmap.md | programs_over_improvisation node vs actual K_MIND scripts |
| C5 | Module Registration | `Knowledge/K_*/` dirs | modules.json (delegated to normalize) |
| C6 | Mindmap Work Nodes | mind_memory.md | work.json entries across modules |

---

## Execution Flow

```
/concord           → Audit + Claude updates all three layers
/concord --fix     → Same as default (update mode)
/concord --check   → Report only, exit code for CI (no updates)
/concord --json    → JSON output for programmatic use
```

### Update Algorithm (default)

1. **Audit** — `concord.py` scans all cross-references, reports drift
2. **System layer** — Claude updates routing.json, conventions.json, documentation.json, SKILL.md, CLAUDE.md
3. **User layer** — Claude updates commands.md, user-guide.md, any affected command tables
4. **Mindmap layer** — Claude updates mind_memory.md nodes and architecture-mindmap.md
5. **Verify** — Re-run `concord.py --check` to confirm zero drift

---

## Files Scanned

### K_MIND Scripts (source: `Knowledge/K_MIND/scripts/*.py`)
- `CLAUDE.md` § Scripts section
- `.claude/skills/mind-context/SKILL.md` § Available scripts
- `Knowledge/K_MIND/files/mind/architecture-mindmap.md` § programs_over_improvisation
- `Knowledge/K_MIND/conventions/routing.json` § memory-management route

### K_TOOLS Scripts (source: `Knowledge/K_TOOLS/scripts/**/*.py`)
- `Knowledge/K_TOOLS/documentation/documentation.json` § scripts array
- `Knowledge/K_MIND/conventions/routing.json` § all routes

### Skills (source: `.claude/skills/*/SKILL.md`)
- `Knowledge/K_TOOLS/conventions/conventions.json` § help_wiring
- `Knowledge/K_TOOLS/methodology/commands.md` § command tables
- `Knowledge/K_MIND/conventions/routing.json` § skills arrays

---

## Integration

- **Route**: `reference-concordance` in routing.json
- **Skill**: `/concord`
- **Script**: `K_TOOLS/scripts/session/concord.py`
- **Complements**: `/normalize` (structure) + `/integrity-check` (modules)
