---
name: elevate
description: "Merge current feature branch to main via GitHub API. Creates PR and merges automatically."
user_invocable: true
---

# /elevate — Merge Feature Branch to Main

Merges the current working branch into `main` via GitHubHelper `pr_create_and_merge()`.

**Prerequisite**: `/github` skill convention — `GitHubHelper()` with zero args, repo on methods.

## Usage

```
/elevate              — merge current branch to main
/elevate <message>    — merge with custom PR title
```

## Mandatory Procedure

### Step 1 — Pre-flight checks

```bash
git status
git rev-parse --abbrev-ref HEAD
```

- If on `main` → abort: "Already on main — nothing to elevate."
- If uncommitted changes → commit and push first
- If unpushed commits → push to origin first

### Step 2 — Push if needed

```bash
git push -u origin <branch-name>
```

### Step 3 — Create PR and merge via GitHubHelper

**CRITICAL**: `git push origin main` is always 403 from the local proxy. Never attempt it. Always use the API route.

```bash
export GH_TOKEN="$GH_TOKEN" && python3 -c "
import sys, os, subprocess
sys.path.insert(0, os.path.join(os.getcwd(), 'Knowledge', 'K_MIND'))
from scripts.gh_helper import GitHubHelper

branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
gh = GitHubHelper()  # No args — token from GH_TOKEN env (pitfall #23)
result = gh.pr_create_and_merge(
    'packetqc/knowledge',   # repo on method, not constructor
    branch,                  # head
    'main',                  # base
    'TITLE_HERE',            # PR title
    body='BODY_HERE'         # PR description
)
print(result)
"
```

Replace `TITLE_HERE` and `BODY_HERE` with:
- Default title: descriptive summary of branch changes
- User-provided `<message>` overrides title if given

### Step 4 — Report result

Output to user:
- PR number and URL
- Merge status (True/False)
- SHA if merged

### Step 5 — Sync local main (optional, if staying on main)

```bash
git fetch origin main && git checkout main && git pull origin main
```

## Key Facts

| Fact | Detail |
|------|--------|
| `git push origin main` | Always 403 — never attempt |
| `pr_create_and_merge` | Idempotent — safe to retry |
| Constructor | `GitHubHelper()` — zero args always |
| Repo | First arg on every method call |
| Returns | `{number, html_url, merged, sha, message}` |
| Token | Auto from `GH_TOKEN` env var |

## Error Recovery

- **401 Bad credentials** → repo string passed to constructor (pitfall #23)
- **403 on API** → token lacks `repo` scope
- **409 Merge conflict** → resolve conflicts locally, push, retry
- **Already merged** → `pr_create_and_merge` detects and reports gracefully
