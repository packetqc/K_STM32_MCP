#!/usr/bin/env python3
"""GitHub Helper — Portable PR and Project management without gh CLI

Lightweight Python replacement for `gh` CLI using the GitHub REST + GraphQL APIs
via urllib. Covers PR operations (create, list, view, merge) and GitHub Projects v2
(create board, link to repo).

Deployed as a knowledge asset to all satellites. Eliminates the dependency on
the `gh` CLI being installed — works anywhere Python 3 is available.

Requires a classic GitHub PAT with repo + project scopes.
Token is read from GH_TOKEN environment variable (set in cloud environment config).
Token is NEVER written to files, logs, command history, or command-line arguments.

Usage:
  # Detect default branch (supports main, master, or any custom name)
  DEFAULT=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')

  # PR operations
  python3 scripts/gh_helper.py pr create --repo packetqc/knowledge \
    --head claude/task-branch --base "$DEFAULT" \
    --title "feat: description" --body "Summary of changes"
  python3 scripts/gh_helper.py pr list --repo packetqc/knowledge --head claude/task-branch
  python3 scripts/gh_helper.py pr view --repo packetqc/knowledge --number 157
  python3 scripts/gh_helper.py pr merge --repo packetqc/knowledge --number 157
  python3 scripts/gh_helper.py pr ensure --repo packetqc/knowledge \
    --head claude/task-branch --base "$DEFAULT" --title "feat: ..."

  # GitHub Projects v2 operations
  python3 scripts/gh_helper.py project create-board --title "Project Name"
  python3 scripts/gh_helper.py project link-repo \
    --project-id PVT_xxx --owner packetqc --repo knowledge
  python3 scripts/gh_helper.py project ensure \
    --title "Project Name" --owner packetqc --repo knowledge

  # Token check
  python3 scripts/gh_helper.py auth status

  # Programmatic usage (imported as module):
  from scripts.gh_helper import GitHubHelper
  gh = GitHubHelper()  # Reads GH_TOKEN from environment
  default = gh.detect_default_branch("packetqc/knowledge")
  pr = gh.pr_create("packetqc/knowledge", head="claude/task", base=default,
                     title="feat: ...", body="...")
  board = gh.project_ensure("My Project", "packetqc", "my-repo")

Authors: Martin Paquet, Claude (Anthropic)
License: MIT
Knowledge version: v46
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


API_BASE = "https://api.github.com"


class GitHubHelper:
    """Portable GitHub API client for PR operations.

    Replaces gh CLI with pure Python urllib calls.
    No external dependencies — works on any Python 3.6+ installation.
    """

    def __init__(self, token_or_repo: Optional[str] = None, token: Optional[str] = None):
        """Initialize with a GitHub PAT.

        Accepts either:
          - GitHubHelper()                      — token from environment
          - GitHubHelper('packetqc/knowledge')  — repo string (ignored), token from env
          - GitHubHelper(token='ghp_xxx')        — explicit token

        Token resolution order:
          1. Explicit token parameter
          2. GH_TOKEN environment variable
          3. GITHUB_TOKEN environment variable
          4. /tmp/.gh_token file (read and delete)

        The first positional argument is checked: if it looks like a repo
        (contains '/'), it is stored as default_repo, not used as token.
        """
        # Detect repo vs token in first positional argument
        self.default_repo = None
        resolved_token = token  # explicit keyword takes priority

        if token_or_repo and '/' in token_or_repo:
            # Looks like owner/repo — store as default, don't use as token
            self.default_repo = token_or_repo
        elif token_or_repo and not resolved_token:
            # Doesn't look like a repo — treat as token
            resolved_token = token_or_repo

        # Token resolution chain
        if not resolved_token:
            resolved_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

        # Try /tmp/.gh_token file as last resort
        if not resolved_token:
            token_file = Path("/tmp/.gh_token")
            if token_file.exists():
                try:
                    resolved_token = token_file.read_text().strip()
                    token_file.unlink()  # Read and delete
                except (OSError, PermissionError):
                    pass

        self.token = resolved_token
        if not self.token:
            raise ValueError(
                "GH_TOKEN environment variable not set.\n"
                "Set it in your Claude Code cloud environment configuration:\n"
                "  Environment variables field: GH_TOKEN=ghp_xxx\n"
                "Generate a classic PAT with 'repo' + 'project' scopes at:\n"
                "  GitHub > Settings > Developer settings > Personal access tokens (classic)"
            )

    def _request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        """Make an authenticated API request."""
        url = f"{API_BASE}{path}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_body = resp.read().decode("utf-8")
                if response_body:
                    return json.loads(response_body)
                return {"status": resp.status}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            try:
                error_data = json.loads(error_body)
            except (json.JSONDecodeError, ValueError):
                error_data = {"message": error_body}
            error_data["http_status"] = e.code
            # Flag rate-limit errors for resilience layer
            if e.code in (403, 429):
                error_data["rate_limited"] = True
                retry_after = e.headers.get("Retry-After") if e.headers else None
                if retry_after:
                    try:
                        error_data["retry_after"] = int(retry_after)
                    except (ValueError, TypeError):
                        pass
            return error_data
        except urllib.error.URLError as e:
            return {"message": f"Network error: {e.reason}", "network_error": True}
        except TimeoutError:
            return {"message": "Request timed out", "network_error": True}

    def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query against GitHub API.

        Uses the same urllib pattern as _request() but targets the GraphQL
        endpoint. Token is read from self.token (set from GH_TOKEN env var
        at init) — never passed on command line.
        """
        url = "https://api.github.com/graphql"
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"bearer {self.token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "errors" in result:
                    return {
                        "errors": result["errors"],
                        "message": result["errors"][0].get("message", "GraphQL error"),
                    }
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            try:
                error_data = json.loads(error_body)
            except (json.JSONDecodeError, ValueError):
                error_data = {"message": error_body}
            error_data["http_status"] = e.code
            return error_data
        except urllib.error.URLError as e:
            return {"message": f"Network error: {e.reason}", "network_error": True}
        except TimeoutError:
            return {"message": "Request timed out", "network_error": True}

    def auth_status(self) -> dict:
        """Check token validity and scopes."""
        url = f"{API_BASE}/user"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                scopes = resp.headers.get("X-OAuth-Scopes", "")
                user_data = json.loads(resp.read().decode("utf-8"))
                return {
                    "authenticated": True,
                    "user": user_data.get("login", "unknown"),
                    "scopes": scopes,
                    "token_type": "fine-grained" if not scopes else "classic",
                }
        except urllib.error.HTTPError as e:
            return {"authenticated": False, "http_status": e.code}

    def repo_create(
        self,
        name: str,
        description: str = "",
        private: bool = True,
        auto_init: bool = True,
    ) -> dict:
        """Create a new GitHub repository for the authenticated user.

        Args:
            name: Repository name (e.g. 'K_PROJECTS')
            description: Repository description
            private: Whether the repo is private (default True)
            auto_init: Initialize with README (default True)

        Returns:
            Dict with 'html_url', 'full_name', 'private', 'created'.
            On error, dict with 'message' and 'http_status'.
        """
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        result = self._request("POST", "/user/repos", data)
        if "html_url" in result:
            return {
                "html_url": result["html_url"],
                "full_name": result["full_name"],
                "private": result.get("private", private),
                "default_branch": result.get("default_branch", "main"),
                "created": True,
            }
        return result

    def repo_file_content(self, repo: str, path: str, ref: str = "") -> Optional[str]:
        """Fetch raw file content from a repository.

        Uses the Contents API to retrieve a file's content, decoded from base64.

        Args:
            repo: Repository in 'owner/repo' format
            path: File path within the repository (e.g. 'Knowledge/K_MIND/sessions/far_memory.json')
            ref: Branch, tag, or commit SHA (optional — defaults to repo's default branch)

        Returns:
            File content as a string, or None if not found / on error.
        """
        import base64
        query = f"?ref={urllib.parse.quote(ref, safe='')}" if ref else ""
        result = self._request("GET", f"/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}{query}")
        if "content" in result:
            return base64.b64decode(result["content"]).decode("utf-8")
        return None

    def repo_tree_list(self, repo: str, path: str, ref: str = "") -> Optional[list]:
        """List files in a repository directory.

        Uses the Contents API to list directory entries.

        Args:
            repo: Repository in 'owner/repo' format
            path: Directory path within the repository
            ref: Branch, tag, or commit SHA (optional)

        Returns:
            List of filenames in the directory, or None on error.
        """
        query = f"?ref={urllib.parse.quote(ref, safe='')}" if ref else ""
        result = self._request("GET", f"/repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}{query}")
        if isinstance(result, list):
            return [entry["name"] for entry in result if "name" in entry]
        return None

    def _find_existing_pr(self, repo: str, head: str) -> Optional[dict]:
        """Search for an existing PR from the given head branch.

        Checks open PRs first, then all states (catches merged/closed PRs
        that may have been created by a timed-out request).

        Returns:
            PR dict with number, html_url, state, merged — or None.
        """
        # Try open PRs first (most common case)
        existing = self.pr_list(repo, head=head, state="open")
        if existing:
            pr = existing[0]
            return {
                "number": pr["number"],
                "html_url": pr["html_url"],
                "state": pr["state"],
                "merged": False,
            }

        # Check all states — catches PRs that were created but already merged/closed
        existing = self.pr_list(repo, head=head, state="all")
        if existing:
            pr = existing[0]
            # Get full details to check merged status
            details = self.pr_view(repo, pr["number"])
            return {
                "number": pr["number"],
                "html_url": pr["html_url"],
                "state": details.get("state", pr["state"]),
                "merged": details.get("merged", False),
            }

        return None

    def pr_create(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str = "",
    ) -> dict:
        """Create a pull request.

        Uses verify-after-failure pattern: on ANY error (timeout, 422, 500),
        checks if the PR was actually created on GitHub before reporting failure.
        This handles the case where the API processes the request but the
        response is lost (timeout, proxy delay, network interruption).

        Args:
            repo: Owner/repo (e.g., "packetqc/knowledge")
            head: Source branch name
            base: Target branch name
            title: PR title
            body: PR body/description

        Returns:
            Dict with 'number', 'html_url', 'created' (True/False), or error info.
        """
        result = self._request("POST", f"/repos/{repo}/pulls", {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        })

        if "number" in result:
            return {
                "number": result["number"],
                "html_url": result["html_url"],
                "state": result.get("state", "open"),
                "created": True,
            }

        # Any failure — verify if PR was created despite the error
        # Covers: 422 (duplicate), timeout, network error, 500
        found = self._find_existing_pr(repo, head)
        if found:
            return {
                "number": found["number"],
                "html_url": found["html_url"],
                "state": found["state"],
                "merged": found.get("merged", False),
                "created": False,
                "message": "PR already exists",
            }

        return result

    def pr_list(
        self,
        repo: str,
        head: Optional[str] = None,
        state: str = "open",
    ) -> list:
        """List pull requests, optionally filtered by head branch.

        Args:
            repo: Owner/repo
            head: Filter by head branch (e.g., "claude/task-branch")
            state: Filter by state: open, closed, all

        Returns:
            List of PR dicts with number, title, html_url, state.
        """
        params = [f"state={state}"]
        if head:
            # GitHub API requires owner:branch format for head filter
            owner = repo.split("/")[0]
            params.append(f"head={owner}:{head}")

        query = "&".join(params)
        result = self._request("GET", f"/repos/{repo}/pulls?{query}")

        if isinstance(result, list):
            return [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "html_url": pr["html_url"],
                    "state": pr["state"],
                    "head": pr["head"]["ref"],
                    "base": pr["base"]["ref"],
                }
                for pr in result
            ]
        return []

    def pr_view(self, repo: str, number: int) -> dict:
        """View a specific pull request.

        Args:
            repo: Owner/repo
            number: PR number

        Returns:
            Dict with PR details.
        """
        result = self._request("GET", f"/repos/{repo}/pulls/{number}")
        if "number" in result:
            return {
                "number": result["number"],
                "title": result["title"],
                "html_url": result["html_url"],
                "state": result["state"],
                "head": result["head"]["ref"],
                "base": result["base"]["ref"],
                "mergeable": result.get("mergeable"),
                "merged": result.get("merged", False),
                "body": result.get("body", ""),
            }
        return result

    def pr_merge(
        self,
        repo: str,
        number: int,
        method: str = "merge",
    ) -> dict:
        """Merge a pull request.

        Uses verify-before-and-after pattern:
        - Before: checks if PR is already merged (idempotent)
        - After failure: checks again if merge went through despite error

        Args:
            repo: Owner/repo
            number: PR number
            method: Merge method: merge, squash, rebase

        Returns:
            Dict with 'merged' (True/False), 'sha', or error info.
        """
        # Pre-check: is it already merged?
        pre = self.pr_view(repo, number)
        if pre.get("merged"):
            return {"merged": True, "sha": "", "message": "Already merged", "was_merged": True}
        if pre.get("state") == "closed":
            return {"merged": False, "message": "PR is closed (not merged)"}

        # Attempt merge
        result = self._request("PUT", f"/repos/{repo}/pulls/{number}/merge", {
            "merge_method": method,
        })

        if result.get("merged"):
            return {"merged": True, "sha": result.get("sha", ""), "message": result.get("message", "")}

        # On failure (timeout, 500, network error) — verify if merge went through
        if result.get("network_error") or result.get("http_status", 0) >= 500:
            post = self.pr_view(repo, number)
            if post.get("merged"):
                return {"merged": True, "sha": "", "message": "Merged (verified after timeout)", "was_merged": True}

        return result

    def pr_create_and_merge(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str = "",
        method: str = "merge",
    ) -> dict:
        """Create a PR and merge it in two separate resilient steps.

        Each step verifies state before and after — handles the case where
        the API processes a request but the response is lost. If step 1
        (create) times out, step 2 (merge) still finds the PR via lookup.

        Args:
            repo: Owner/repo
            head: Source branch name
            base: Target branch name
            title: PR title
            body: PR body/description
            method: Merge method: merge, squash, rebase

        Returns:
            Dict with 'number', 'html_url', 'merged' status, and step details.
        """
        # Step 1: Create (or find existing)
        pr = self.pr_create(repo, head=head, base=base, title=title, body=body)

        if "number" not in pr:
            return {"merged": False, "step": "create", "error": pr.get("message", str(pr))}

        # If PR was already merged (found via _find_existing_pr)
        if pr.get("merged"):
            return {
                "number": pr["number"],
                "html_url": pr["html_url"],
                "merged": True,
                "step": "create",
                "message": "Already merged",
            }

        # Step 2: Merge (with pre-check and post-verify)
        merge = self.pr_merge(repo, pr["number"], method=method)

        return {
            "number": pr["number"],
            "html_url": pr["html_url"],
            "merged": merge.get("merged", False),
            "sha": merge.get("sha", ""),
            "step": "merge",
            "message": merge.get("message", ""),
            "created": pr.get("created", False),
        }

    def detect_default_branch(self, repo: str) -> str:
        """Detect the repository's default branch name.

        Returns:
            Branch name (e.g., "main" or "master").
        """
        result = self._request("GET", f"/repos/{repo}")
        return result.get("default_branch", "main")

    # --- GitHub Projects v2 (GraphQL) ---

    def get_viewer(self) -> dict:
        """Get authenticated user's node ID and login.

        Returns:
            Dict with 'id' (node ID) and 'login' (username).
        """
        result = self._graphql("query { viewer { id login } }")
        if "data" in result:
            return result["data"]["viewer"]
        return result

    def get_repo_id(self, owner: str, name: str) -> dict:
        """Get repository node ID for linking.

        Args:
            owner: Repository owner (e.g., "packetqc")
            name: Repository name (e.g., "knowledge")

        Returns:
            Dict with 'id' (node ID) and 'name'.
        """
        result = self._graphql(
            "query($owner: String!, $name: String!) {"
            "  repository(owner: $owner, name: $name) { id name }"
            "}",
            variables={"owner": owner, "name": name},
        )
        if "data" in result and result["data"].get("repository"):
            return result["data"]["repository"]
        return result

    def project_create_board(self, owner_id: str, title: str) -> dict:
        """Create a GitHub Projects v2 board.

        Args:
            owner_id: Owner's node ID (from get_viewer)
            title: Project board title

        Returns:
            Dict with 'id' (project node ID), 'number', 'url'.
        """
        result = self._graphql(
            "mutation($input: CreateProjectV2Input!) {"
            "  createProjectV2(input: $input) {"
            "    projectV2 { id number url }"
            "  }"
            "}",
            variables={"input": {"ownerId": owner_id, "title": title}},
        )
        if "data" in result:
            return result["data"]["createProjectV2"]["projectV2"]
        return result

    def project_link_repo(self, project_id: str, repo_id: str) -> dict:
        """Link a GitHub Projects v2 board to a repository.

        Args:
            project_id: Project node ID (from project_create_board)
            repo_id: Repository node ID (from get_repo_id)

        Returns:
            Dict with 'name' of linked repository.
        """
        result = self._graphql(
            "mutation($input: LinkProjectV2ToRepositoryInput!) {"
            "  linkProjectV2ToRepository(input: $input) {"
            "    repository { name }"
            "  }"
            "}",
            variables={"input": {"projectId": project_id, "repositoryId": repo_id}},
        )
        if "data" in result:
            return result["data"]["linkProjectV2ToRepository"]["repository"]
        return result

    def project_ensure(self, title: str, owner: str, repo_name: str) -> dict:
        """Find an existing project board by title, or create one and link it.

        First searches all open projects for a case-insensitive title match.
        If found, reuses the existing board. Otherwise creates a new one and
        links it to the repository.

        Args:
            title: Project board title
            owner: Repository owner (e.g., "packetqc")
            repo_name: Repository name (e.g., "knowledge")

        Returns:
            Dict with 'number', 'url', 'project_id', 'repo_linked', 'created'.
        """
        # Step 0: Check for existing project with same title
        existing = self.project_list(limit=100)
        title_lower = title.lower()
        for proj in existing:
            if proj.get("title", "").lower() == title_lower:
                # Found existing project — reuse it
                result = {
                    "number": proj["number"],
                    "url": f"https://github.com/users/{owner}/projects/{proj['number']}",
                    "project_id": proj["id"],
                    "created": False,
                }
                # Still ensure repo is linked
                repo = self.get_repo_id(owner, repo_name)
                if "id" in repo:
                    link = self.project_link_repo(proj["id"], repo["id"])
                    result["repo_linked"] = (
                        link.get("name", repo_name)
                        if isinstance(link, dict)
                        else repo_name
                    )
                else:
                    result["repo_linked"] = repo_name
                return result

        # Step 1: Get owner ID
        viewer = self.get_viewer()
        if "id" not in viewer:
            return {"error": "Failed to get owner ID", "details": viewer}

        # Step 2: Create board
        board = self.project_create_board(viewer["id"], title)
        if "number" not in board:
            return {"error": "Failed to create board", "details": board}

        # Step 3: Get repo ID
        repo = self.get_repo_id(owner, repo_name)
        if "id" not in repo:
            return {"error": "Failed to get repo ID", "details": repo}

        # Step 4: Link board to repo
        link = self.project_link_repo(board["id"], repo["id"])

        return {
            "number": board["number"],
            "url": board["url"],
            "project_id": board["id"],
            "repo_linked": link.get("name", repo_name)
            if isinstance(link, dict)
            else repo_name,
            "created": True,
        }


    # --- TAG: Convention — Issue + Label + Board Item Management ---

    # Label color mapping for TAG: convention
    TAG_LABELS = {
        "methodology": {"color": "0075ca", "description": "Knowledge methodology insight"},
        "pattern": {"color": "2da44e", "description": "Proven pattern — battle-tested"},
        "lesson": {"color": "e11d48", "description": "Hard-won lesson — pitfall to avoid"},
        "evolution": {"color": "7c3aed", "description": "Knowledge system architectural discovery"},
        "story": {"color": "0d9488", "description": "User story — feature narrative"},
        "task": {"color": "6b7280", "description": "Work item — implementation step"},
        "bug": {"color": "ea580c", "description": "Defect — something that doesn't work"},
        "publication": {"color": "ca8a04", "description": "Publication tracking"},
        "harvest": {"color": "06b6d4", "description": "Harvest pipeline — promotion queue"},
    }

    # Engineering cycle stage labels — applied to GitHub issues to track
    # the current engineering stage. Only one stage label is active at a time.
    #
    # Aligned with: Classical SDLC, Agile/Scrum, DevOps CI/CD, ITIL v4,
    # SAFe, GitHub Flow, ISO/IEC 12207:2017, V-Model.
    #
    # Documentation is cross-cutting (not a stage) — tracked via request
    # type label, not stage label. Color palette: indigo→blue→amber→green→red
    # progression matching the lifecycle flow.
    ENGINEERING_STAGE_LABELS = {
        "analysis":       {"color": "6366f1", "description": "Stage: analysis — requirements, investigation, stakeholder needs"},
        "planning":       {"color": "8b5cf6", "description": "Stage: planning — task breakdown, scheduling, sprint planning"},
        "design":         {"color": "a855f7", "description": "Stage: design — architecture, solution conception, prototyping"},
        "implementation": {"color": "3b82f6", "description": "Stage: implementation — coding, building, integration"},
        "testing":        {"color": "f59e0b", "description": "Stage: testing — verification, automated QA, unit/integration tests"},
        "validation":     {"color": "eab308", "description": "Stage: validation — user acceptance, stakeholder review, demo"},
        "review":         {"color": "10b981", "description": "Stage: review — code review, PR review, peer inspection, approval"},
        "deployment":     {"color": "f97316", "description": "Stage: deployment — release, staging, production push, delivery"},
        "operations":     {"color": "ef4444", "description": "Stage: operations — production runtime, monitoring, incident response"},
        "improvement":    {"color": "06b6d4", "description": "Stage: improvement — retrospective, lessons learned, rework trigger"},
    }

    def labels_setup(self, repo: str) -> list:
        """Create all TAG: labels on a repository. Idempotent — skips existing.

        Args:
            repo: owner/repo format (e.g., "packetqc/knowledge-live")

        Returns:
            List of dicts with label name and status (created/exists/error).
        """
        results = []
        for name, config in self.TAG_LABELS.items():
            result = self._request("POST", f"/repos/{repo}/labels", {
                "name": name,
                "color": config["color"],
                "description": config["description"],
            })
            if result.get("id"):
                results.append({"name": name, "status": "created"})
            elif result.get("http_status") == 422:
                # Label already exists — try to update color/description
                self._request("PATCH", f"/repos/{repo}/labels/{name}", {
                    "color": config["color"],
                    "description": config["description"],
                })
                results.append({"name": name, "status": "exists"})
            else:
                results.append({"name": name, "status": "error", "details": result})
        return results

    def issue_create(self, repo: str, title: str, body: str = "", labels: Optional[list] = None) -> dict:
        """Create a repository issue.

        Args:
            repo: owner/repo format
            title: Issue title (should include TAG: prefix)
            body: Issue body (markdown)
            labels: List of label names to apply

        Returns:
            Dict with 'number', 'html_url', 'node_id'.
        """
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        result = self._request("POST", f"/repos/{repo}/issues", data)
        if "number" in result:
            return {
                "number": result["number"],
                "html_url": result["html_url"],
                "node_id": result["node_id"],
                "created": True,
            }
        return result

    def issue_update(self, repo: str, issue_number: int, **kwargs) -> dict:
        """Update an existing issue's title, body, state, or labels.

        Args:
            repo: owner/repo format (e.g., "packetqc/knowledge")
            issue_number: Issue number
            **kwargs: Fields to update — title, body, state ("open"/"closed"),
                      labels (list of label names).

        Returns:
            Dict with 'number', 'html_url', 'title', 'updated'.
        """
        allowed = {"title", "body", "state", "labels"}
        data = {k: v for k, v in kwargs.items() if k in allowed}
        if not data:
            return {"error": "No valid fields to update"}
        result = self._request("PATCH", f"/repos/{repo}/issues/{issue_number}", data)
        if "number" in result:
            return {
                "number": result["number"],
                "html_url": result["html_url"],
                "title": result["title"],
                "updated": True,
            }
        return result

    def issue_comment_post(self, repo: str, issue_number: int, body: str) -> dict:
        """Post a comment on a repository issue.

        Args:
            repo: owner/repo format
            issue_number: Issue number
            body: Comment body (markdown)

        Returns:
            Dict with 'id', 'html_url', 'created_at'.
        """
        result = self._request(
            "POST",
            f"/repos/{repo}/issues/{issue_number}/comments",
            {"body": body},
        )
        if "id" in result:
            return {
                "id": result["id"],
                "html_url": result["html_url"],
                "created_at": result["created_at"],
                "posted": True,
            }
        return result

    def issue_comment_edit(self, repo: str, comment_id: int, body: str) -> dict:
        """Edit an existing comment on a repository issue.

        Used for the ⏳→✅ lifecycle: post a comment when a step starts,
        then edit it when the step completes.

        Args:
            repo: owner/repo format
            comment_id: Comment ID (returned by issue_comment_post)
            body: Updated comment body (markdown)

        Returns:
            Dict with 'id', 'updated_at'.
        """
        result = self._request(
            "PATCH",
            f"/repos/{repo}/issues/comments/{comment_id}",
            {"body": body},
        )
        if "id" in result:
            return {
                "id": result["id"],
                "updated_at": result["updated_at"],
                "edited": True,
            }
        return result

    def issue_comments_list(self, repo: str, issue_number: int) -> list:
        """List all comments on a repository issue.

        Used by integrity check to compare posted comments against
        expected session activity.

        Args:
            repo: owner/repo format
            issue_number: Issue number

        Returns:
            List of dicts with 'id', 'body', 'created_at', 'updated_at', 'user'.
        """
        comments = []
        page = 1
        while True:
            result = self._request(
                "GET",
                f"/repos/{repo}/issues/{issue_number}/comments?per_page=100&page={page}",
            )
            if isinstance(result, list):
                for c in result:
                    comments.append({
                        "id": c["id"],
                        "body": c.get("body", ""),
                        "created_at": c["created_at"],
                        "updated_at": c["updated_at"],
                        "user": c.get("user", {}).get("login", ""),
                    })
                if len(result) < 100:
                    break
                page += 1
            else:
                break
        return comments

    def issue_close(self, repo: str, issue_number: int) -> dict:
        """Close a repository issue.

        Args:
            repo: owner/repo format
            issue_number: Issue number

        Returns:
            Dict with 'number', 'state'.
        """
        result = self._request(
            "PATCH",
            f"/repos/{repo}/issues/{issue_number}",
            {"state": "closed"},
        )
        if "number" in result:
            return {
                "number": result["number"],
                "state": result["state"],
                "closed": True,
            }
        return result

    def issue_labels_add(self, repo: str, issue_number: int, labels: list) -> dict:
        """Add labels to an issue. Creates labels if they don't exist.

        Args:
            repo: owner/repo format
            issue_number: Issue number
            labels: List of label name strings to add

        Returns:
            Dict with 'labels' (list of applied label names) and 'added': True.
        """
        result = self._request(
            "POST",
            f"/repos/{repo}/issues/{issue_number}/labels",
            {"labels": labels},
        )
        if isinstance(result, list):
            return {
                "labels": [lbl.get("name", "") for lbl in result],
                "added": True,
            }
        return result

    def issue_label_remove(self, repo: str, issue_number: int, label: str) -> dict:
        """Remove a single label from an issue. Silent if label not present.

        Args:
            repo: owner/repo format
            issue_number: Issue number
            label: Label name to remove

        Returns:
            Dict with 'removed': True on success, or error details.
        """
        encoded_label = urllib.parse.quote(label, safe="")
        result = self._request(
            "DELETE",
            f"/repos/{repo}/issues/{issue_number}/labels/{encoded_label}",
        )
        # DELETE returns the remaining labels list on success, or 404 if label wasn't on the issue
        if isinstance(result, list):
            return {"removed": True, "remaining": [lbl.get("name", "") for lbl in result]}
        if result.get("http_status") == 404:
            return {"removed": True, "was_missing": True}
        return result

    def engineering_labels_setup(self, repo: str) -> list:
        """Create all engineering cycle stage labels on a repository. Idempotent.

        Args:
            repo: owner/repo format

        Returns:
            List of dicts with label name and status (created/exists/error).
        """
        results = []
        for name, config in self.ENGINEERING_STAGE_LABELS.items():
            result = self._request("POST", f"/repos/{repo}/labels", {
                "name": name,
                "color": config["color"],
                "description": config["description"],
            })
            if result.get("id"):
                results.append({"name": name, "status": "created"})
            elif result.get("http_status") == 422:
                # Label already exists — update color/description
                self._request("PATCH", f"/repos/{repo}/labels/{name}", {
                    "color": config["color"],
                    "description": config["description"],
                })
                results.append({"name": name, "status": "exists"})
            else:
                results.append({"name": name, "status": "error", "details": result})
        return results

    def issue_engineering_stage_sync(self, repo: str, issue_number: int,
                                     new_stage: str,
                                     old_stage: str = "") -> dict:
        """Sync engineering cycle stage label on an issue.

        Removes the old stage label (if any) and adds the new one.
        Only one engineering stage label should be active at a time.

        Args:
            repo: owner/repo format
            issue_number: Issue number
            new_stage: New stage name (must be in ENGINEERING_STAGE_LABELS)
            old_stage: Previous stage name to remove (optional)

        Returns:
            Dict with 'synced': True, 'added', 'removed' fields.
        """
        if new_stage not in self.ENGINEERING_STAGE_LABELS:
            return {"error": f"Unknown stage: {new_stage}"}

        result = {"synced": False, "added": None, "removed": None}

        # Remove old stage label
        if old_stage and old_stage != new_stage and old_stage in self.ENGINEERING_STAGE_LABELS:
            rm = self.issue_label_remove(repo, issue_number, old_stage)
            result["removed"] = old_stage if rm.get("removed") else None

        # Ensure the stage label exists on the repo, then add to issue
        if new_stage in self.ENGINEERING_STAGE_LABELS:
            config = self.ENGINEERING_STAGE_LABELS[new_stage]
            # Create label if missing (idempotent)
            self._request("POST", f"/repos/{repo}/labels", {
                "name": new_stage,
                "color": config["color"],
                "description": config["description"],
            })

        add = self.issue_labels_add(repo, issue_number, [new_stage])
        if add.get("added"):
            result["added"] = new_stage
            result["synced"] = True

        return result

    def project_item_add_draft(self, project_id: str, title: str, body: str = "") -> dict:
        """Add a draft issue directly to a Project board.

        Uses addProjectV2DraftIssue — creates board-level items without
        requiring a repo issue. Works with classic PAT project scope.

        Args:
            project_id: Project node ID (from project_ensure/get_id)
            title: Item title (should include TAG: prefix)
            body: Item body (markdown)

        Returns:
            Dict with item 'id'.
        """
        query = """
            mutation($projectId: ID!, $title: String!, $body: String) {
                addProjectV2DraftIssue(input: {
                    projectId: $projectId
                    title: $title
                    body: $body
                }) {
                    projectItem {
                        id
                    }
                }
            }
        """
        result = self._graphql(query, {
            "projectId": project_id,
            "title": title,
            "body": body or "",
        })
        if "data" in result:
            return result["data"]["addProjectV2DraftIssue"]["projectItem"]
        return result

    def project_item_add(self, project_id: str, content_id: str) -> dict:
        """Add an existing issue or PR to a Project board.

        Uses addProjectV2ItemById — links a repo issue/PR (by node_id)
        to a project board. This is the correct way to assign issues
        to projects (vs project_item_add_draft which creates new drafts).

        Args:
            project_id: Project node ID (from project_ensure/get_id)
            content_id: Issue or PR node_id (from issue_create)

        Returns:
            Dict with item 'id'.
        """
        query = """
            mutation($projectId: ID!, $contentId: ID!) {
                addProjectV2ItemById(input: {
                    projectId: $projectId
                    contentId: $contentId
                }) {
                    item {
                        id
                    }
                }
            }
        """
        result = self._graphql(query, {
            "projectId": project_id,
            "contentId": content_id,
        })
        if "data" in result:
            return result["data"]["addProjectV2ItemById"]["item"]
        return result

    def project_item_add_by_number(self, owner: str, project_number: int, repo: str, issue_number: int) -> dict:
        """Add an issue to a project board using human-readable identifiers.

        Resolves node IDs automatically from project number and issue number,
        then delegates to project_item_add.

        Args:
            owner: Project owner (e.g., "packetqc")
            project_number: Project board number (e.g., 56)
            repo: owner/repo format (e.g., "packetqc/knowledge")
            issue_number: Issue number (e.g., 42)

        Returns:
            Dict with item 'id', or error dict.
        """
        # Resolve project node ID
        project = self.project_get_id(owner, project_number)
        if "error" in project:
            return {"error": f"Project #{project_number} not found", "details": project}

        # Resolve issue node ID via REST API
        result = self._request("GET", f"/repos/{repo}/issues/{issue_number}")
        if "node_id" not in result:
            return {"error": f"Issue #{issue_number} not found in {repo}", "details": result}

        return self.project_item_add(project["id"], result["node_id"])

    def project_fields(self, project_id: str) -> dict:
        """Query a Project's fields — returns Status field ID and option IDs.

        Args:
            project_id: Project node ID (from project_ensure/get_id)

        Returns:
            Dict with 'fields' list. Each field has 'id', 'name', and
            optionally 'options' (for single-select fields like Status).
        """
        query = """
            query($projectId: ID!) {
                node(id: $projectId) {
                    ... on ProjectV2 {
                        fields(first: 20) {
                            nodes {
                                ... on ProjectV2SingleSelectField {
                                    id
                                    name
                                    options {
                                        id
                                        name
                                    }
                                }
                                ... on ProjectV2Field {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        """
        result = self._graphql(query, {"projectId": project_id})
        if "data" in result and result["data"]["node"]:
            return {"fields": result["data"]["node"]["fields"]["nodes"]}
        return {"error": "Project not found", "details": result}

    def project_item_update(self, project_id: str, item_id: str, field_id: str, option_id: str) -> dict:
        """Update a single-select field (e.g., Status) on a board item.

        Uses updateProjectV2ItemFieldValue — sets Todo/In Progress/Done.

        Args:
            project_id: Project node ID
            item_id: Board item ID (PVTI_...)
            field_id: Field node ID (PVTSSF_... for Status)
            option_id: Option ID (e.g., "98236657" for Done)

        Returns:
            Dict with updated item 'id'.
        """
        query = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
        """
        result = self._graphql(query, {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": option_id,
        })
        if "data" in result:
            return result["data"]["updateProjectV2ItemFieldValue"]["projectV2Item"]
        return {"error": "Update failed", "details": result}

    def project_items_list(self, owner: str, number: int) -> dict:
        """List all items on a Project board with status and metadata.

        Fetches every item (draft issues and linked issues/PRs) with their
        Status field value, TAG: prefix parsing, and timestamps.

        Args:
            owner: Project owner (e.g., "packetqc")
            number: Project board number (e.g., 37)

        Returns:
            Dict with 'items' list and 'meta' summary.
            Each item has: id, title, tag, display_title, status, body,
            issue_url, issue_number, created_at, updated_at.
        """
        query = """
            query($owner: String!, $number: Int!, $cursor: String) {
                user(login: $owner) {
                    projectV2(number: $number) {
                        id
                        title
                        url
                        items(first: 100, after: $cursor) {
                            pageInfo {
                                hasNextPage
                                endCursor
                            }
                            nodes {
                                id
                                createdAt
                                updatedAt
                                fieldValueByName(name: "Status") {
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        name
                                    }
                                }
                                content {
                                    ... on DraftIssue {
                                        title
                                        body
                                        createdAt
                                        updatedAt
                                    }
                                    ... on Issue {
                                        title
                                        body
                                        number
                                        url
                                        state
                                        createdAt
                                        updatedAt
                                    }
                                    ... on PullRequest {
                                        title
                                        body
                                        number
                                        url
                                        state
                                        createdAt
                                        updatedAt
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        all_items = []
        cursor = None
        project_meta = None

        while True:
            variables = {"owner": owner, "number": number}
            if cursor:
                variables["cursor"] = cursor

            result = self._graphql(query, variables)
            project = (result.get("data") or {}).get("user", {}).get("projectV2")
            if not project:
                return {"error": "Project not found", "details": result}

            if not project_meta:
                project_meta = {
                    "id": project["id"],
                    "title": project["title"],
                    "url": project["url"],
                    "board_number": number,
                }

            for node in project["items"]["nodes"]:
                content = node.get("content") or {}
                title = content.get("title", "(untitled)")
                status_field = node.get("fieldValueByName") or {}
                status = status_field.get("name", "")

                # Parse TAG: prefix
                tag = ""
                display_title = title
                if ": " in title:
                    parts = title.split(": ", 1)
                    tag = parts[0]
                    display_title = parts[1]

                all_items.append({
                    "id": node["id"],
                    "title": title,
                    "tag": tag,
                    "display_title": display_title,
                    "status": status,
                    "body": content.get("body", ""),
                    "issue_url": content.get("url"),
                    "issue_number": content.get("number"),
                    "issue_state": content.get("state"),
                    "created_at": node.get("createdAt", content.get("createdAt", "")),
                    "updated_at": node.get("updatedAt", content.get("updatedAt", "")),
                })

            page_info = project["items"]["pageInfo"]
            if page_info["hasNextPage"]:
                cursor = page_info["endCursor"]
            else:
                break

        # Summary by status
        status_counts = {}
        tag_counts = {}
        for item in all_items:
            s = item["status"] or "(none)"
            status_counts[s] = status_counts.get(s, 0) + 1
            if item["tag"]:
                tag_counts[item["tag"]] = tag_counts.get(item["tag"], 0) + 1

        return {
            "meta": {
                **project_meta,
                "total": len(all_items),
                "by_status": status_counts,
                "by_tag": tag_counts,
            },
            "items": all_items,
        }

    def project_sync(self, owner: str, number: int, local_state_path: str) -> dict:
        """Bidirectional sync between a Project board and local state file.

        Reads all board items, compares with local JSON state, and produces
        a reconciliation report with actions: new_on_board, new_locally,
        updated_on_board, updated_locally, in_sync.

        The local state file is a JSON with 'items' list, each having:
        id, title, status, updated_at. If the file doesn't exist, it's
        treated as a first sync (everything is new_on_board).

        Args:
            owner: Project owner
            number: Board number
            local_state_path: Path to local state JSON file

        Returns:
            Dict with 'actions' list and summary. Each action has:
            type (new_on_board|updated_on_board|in_sync), item, local.
        """
        # Fetch current board state
        board = self.project_items_list(owner, number)
        if "error" in board:
            return board

        # Load local state
        local_items = {}
        if os.path.exists(local_state_path):
            with open(local_state_path, "r") as f:
                local_data = json.load(f)
                for item in local_data.get("items", []):
                    local_items[item["id"]] = item

        actions = []
        board_ids = set()

        for item in board["items"]:
            board_ids.add(item["id"])
            local = local_items.get(item["id"])

            if not local:
                actions.append({
                    "type": "new_on_board",
                    "item": item,
                    "local": None,
                })
            elif item["updated_at"] > local.get("updated_at", ""):
                actions.append({
                    "type": "updated_on_board",
                    "item": item,
                    "local": local,
                    "changes": _diff_item(local, item),
                })
            else:
                actions.append({
                    "type": "in_sync",
                    "item": item,
                    "local": local,
                })

        # Items that exist locally but not on board (deleted/archived)
        for lid, local in local_items.items():
            if lid not in board_ids:
                actions.append({
                    "type": "removed_from_board",
                    "item": None,
                    "local": local,
                })

        # Write updated local state
        state = {
            "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "board_number": number,
            "owner": owner,
            "items": board["items"],
        }
        os.makedirs(os.path.dirname(local_state_path) or ".", exist_ok=True)
        with open(local_state_path, "w") as f:
            json.dump(state, f, indent=2)

        # Summary
        summary = {}
        for a in actions:
            summary[a["type"]] = summary.get(a["type"], 0) + 1

        return {
            "meta": board["meta"],
            "actions": actions,
            "summary": summary,
            "local_state_path": local_state_path,
        }

    def project_get_id(self, owner: str, number: int) -> dict:
        """Get the node ID of a Project board by number.

        Args:
            owner: Project owner (e.g., "packetqc")
            number: Project board number (e.g., 37)

        Returns:
            Dict with 'id' (node ID).
        """
        query = """
            query($owner: String!, $number: Int!) {
                user(login: $owner) {
                    projectV2(number: $number) {
                        id
                        title
                        number
                    }
                }
            }
        """
        result = self._graphql(query, {"owner": owner, "number": number})
        if "data" in result and result["data"]["user"]["projectV2"]:
            return result["data"]["user"]["projectV2"]
        return {"error": "Project not found", "details": result}

    def project_delete(self, project_id: str) -> dict:
        """Delete a GitHub Project v2 by its node ID.

        Args:
            project_id: The node ID of the project (e.g., PVT_kwHO...)

        Returns:
            Dict with 'deleted': True on success, or 'error' on failure.
        """
        query = """
            mutation($projectId: ID!) {
                deleteProjectV2(input: {projectId: $projectId}) {
                    projectV2 { id title }
                }
            }
        """
        result = self._graphql(query, {"projectId": project_id})
        if "data" in result and result["data"].get("deleteProjectV2"):
            proj = result["data"]["deleteProjectV2"]["projectV2"]
            return {"deleted": True, "title": proj.get("title"), "id": proj.get("id")}
        return {"error": "Failed to delete project", "details": result}

    def project_list(self, limit: int = 20) -> list:
        """List user's open GitHub Projects v2, sorted by most recently updated.

        Args:
            limit: Maximum number of projects to return (default 20)

        Returns:
            List of dicts with 'id', 'title', 'number', 'updatedAt'.
        """
        query = """
            query($first: Int!) {
                viewer {
                    projectsV2(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
                        nodes {
                            id
                            title
                            number
                            updatedAt
                            closed
                        }
                    }
                }
            }
        """
        result = self._graphql(query, {"first": limit})
        if "data" in result:
            nodes = result["data"]["viewer"]["projectsV2"]["nodes"]
            return [p for p in nodes if not p.get("closed")]
        return []

    def project_list_page(self, per_page: int = 3, cursor: str = None) -> dict:
        """Lazy-fetch paginated projects, sorted by most recently updated.

        Fetches only `per_page` open projects at a time using cursor-based
        pagination with per-edge cursors. Designed for A3 knowledge pagination
        (3 items + Suivant).

        Args:
            per_page: Number of open projects to return per page (default 3)
            cursor: Edge cursor from a previous call, or None for first page

        Returns:
            Dict with 'projects' (list of project dicts), 'next_cursor' (str or None),
            and 'has_next' (bool).
        """
        collected = []
        current_cursor = cursor
        api_has_more = True

        while len(collected) < per_page + 1 and api_has_more:
            batch = per_page + 2  # small over-fetch for closed filtering
            if current_cursor:
                query = """
                    query($first: Int!, $after: String!) {
                        viewer {
                            projectsV2(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
                                edges { cursor node { id title number updatedAt closed } }
                                pageInfo { hasNextPage }
                            }
                        }
                    }
                """
                variables = {"first": batch, "after": current_cursor}
            else:
                query = """
                    query($first: Int!) {
                        viewer {
                            projectsV2(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
                                edges { cursor node { id title number updatedAt closed } }
                                pageInfo { hasNextPage }
                            }
                        }
                    }
                """
                variables = {"first": batch}

            result = self._graphql(query, variables)
            if "data" not in result:
                break

            data = result["data"]["viewer"]["projectsV2"]
            edges = data["edges"]
            api_has_more = data["pageInfo"]["hasNextPage"]

            for edge in edges:
                node = edge["node"]
                if not node.get("closed"):
                    collected.append({"project": node, "cursor": edge["cursor"]})
                current_cursor = edge["cursor"]

            if not edges:
                break

        projects = [item["project"] for item in collected[:per_page]]
        has_more = len(collected) > per_page or api_has_more
        next_cursor = collected[per_page - 1]["cursor"] if projects and has_more else None

        return {
            "projects": projects,
            "next_cursor": next_cursor,
            "has_next": has_more,
        }


def _diff_item(local: dict, remote: dict) -> list:
    """Compare local and remote item, return list of changed fields."""
    changes = []
    for key in ("title", "status", "body", "tag"):
        lv = local.get(key, "")
        rv = remote.get(key, "")
        if lv != rv:
            changes.append({"field": key, "local": lv, "remote": rv})
    return changes


# --- CLI Interface ---


def _print_json(data: dict | list) -> None:
    """Pretty-print JSON output."""
    print(json.dumps(data, indent=2))


def _parse_args(args: list[str]) -> dict:
    """Parse CLI arguments into a dict."""
    parsed = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                parsed[key] = args[i + 1]
                i += 2
            else:
                parsed[key] = True
                i += 1
        else:
            parsed.setdefault("_positional", []).append(arg)
            i += 1
    return parsed


def main():
    """CLI entry point — mirrors gh pr subcommand structure."""
    if len(sys.argv) < 2:
        print("Usage: gh_helper.py <command> <subcommand> [options]")
        print("")
        print("Commands:")
        print("  pr create            Create a pull request")
        print("  pr list              List pull requests")
        print("  pr view              View a pull request")
        print("  pr merge             Merge a pull request")
        print("  pr ensure            Create + merge in two resilient steps")
        print("  project create-board Create a GitHub Projects v2 board")
        print("  project link-repo    Link a project board to a repository")
        print("  project ensure       Create board + link to repo (full pipeline)")
        print("  project items-list   List all items on a project board")
        print("  project sync         Bidirectional sync board ↔ local state")
        print("  project fields       Query project field metadata (Status, etc.)")
        print("  project item-add     Add a draft item to a board")
        print("  project item-update  Update a field value on a board item")
        print("  project get-id       Get board node ID by number")
        print("  labels setup         Setup TAG: labels on a repo")
        print("  labels setup-all     Setup TAG: labels on multiple repos")
        print("  issue create         Create a repo issue with labels")
        print("  issue comment        Post a comment on an issue")
        print("  issue comment-edit   Edit an existing issue comment")
        print("  issue comments       List all comments on an issue")
        print("  issue close          Close an issue")
        print("  repo create          Create a new repository")
        print("  auth status          Check token validity")
        print("")
        print("Token: Set GH_TOKEN in cloud environment config (never on command line)")
        print("")
        print("PR Options:")
        print("  --repo OWNER/REPO  Target repository")
        print("  --head BRANCH      Source branch (pr create/list)")
        print("  --base BRANCH      Target branch (pr create)")
        print("  --title TITLE      PR title (pr create)")
        print("  --body BODY        PR body (pr create)")
        print("  --number N         PR number (pr view/merge)")
        print("  --state STATE      Filter: open/closed/all (pr list)")
        print("  --method METHOD    Merge method: merge/squash/rebase (pr merge)")
        print("")
        print("Project Options:")
        print("  --title TITLE      Board title (project create-board/ensure)")
        print("  --owner OWNER      Repo owner (project link-repo/ensure)")
        print("  --repo REPO        Repo name (project link-repo/ensure)")
        print("  --project-id ID    Project node ID (project link-repo)")
        sys.exit(1)

    # Parse command structure
    command = sys.argv[1]
    subcommand = sys.argv[2] if len(sys.argv) > 2 else ""
    opts = _parse_args(sys.argv[3:])

    # Token from environment only — never accept via CLI (zero-display convention v46)
    if "token" in opts:
        print("Error: --token flag is not supported. Set GH_TOKEN environment variable instead.", file=sys.stderr)
        print("  This prevents token exposure in command-line output.", file=sys.stderr)
        print("  Set in cloud environment config: GH_TOKEN=ghp_xxx", file=sys.stderr)
        sys.exit(1)

    try:
        gh = GitHubHelper()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Route commands
    if command == "auth" and subcommand == "status":
        result = gh.auth_status()
        if result.get("authenticated"):
            print(f"Authenticated as: {result['user']}")
            print(f"Token type: {result['token_type']}")
            if result["scopes"]:
                print(f"Scopes: {result['scopes']}")
        else:
            print(f"Authentication failed (HTTP {result.get('http_status', '?')})")
            sys.exit(1)

    elif command == "repo" and subcommand == "create":
        name = opts.get("name")
        if not name:
            print("Error: --name required", file=sys.stderr)
            sys.exit(1)
        description = opts.get("description", "")
        private = opts.get("private", "true").lower() != "false"
        auto_init = opts.get("auto-init", "true").lower() != "false"
        result = gh.repo_create(name, description=description, private=private, auto_init=auto_init)
        if result.get("created"):
            print(f"Created: {result['full_name']} ({'private' if result['private'] else 'public'})")
            print(f"URL: {result['html_url']}")
        else:
            print(f"Error: {result.get('message', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

    elif command == "pr" and subcommand == "create":
        repo = opts.get("repo")
        head = opts.get("head")
        base = opts.get("base")
        title = opts.get("title")
        body = opts.get("body", "")

        if not all([repo, head, title]):
            print("Error: --repo, --head, and --title are required", file=sys.stderr)
            sys.exit(1)

        if not base:
            base = gh.detect_default_branch(repo)
            print(f"Auto-detected base branch: {base}")

        result = gh.pr_create(repo, head=head, base=base, title=title, body=body)

        if result.get("created"):
            print(f"PR #{result['number']} created: {result['html_url']}")
        elif result.get("created") is False:
            print(f"PR #{result['number']} already exists: {result['html_url']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "pr" and subcommand == "list":
        repo = opts.get("repo")
        if not repo:
            print("Error: --repo is required", file=sys.stderr)
            sys.exit(1)

        prs = gh.pr_list(
            repo,
            head=opts.get("head"),
            state=opts.get("state", "open"),
        )

        if not prs:
            print("No pull requests found.")
        else:
            for pr in prs:
                state_icon = "🟢" if pr["state"] == "open" else "🟣"
                print(f"  {state_icon} #{pr['number']}  {pr['title']}")
                print(f"     {pr['head']} → {pr['base']}")
                print(f"     {pr['html_url']}")

    elif command == "pr" and subcommand == "view":
        repo = opts.get("repo")
        number = opts.get("number")
        if not repo or not number:
            print("Error: --repo and --number are required", file=sys.stderr)
            sys.exit(1)

        result = gh.pr_view(repo, int(number))
        if "number" in result:
            state = "merged" if result.get("merged") else result["state"]
            print(f"PR #{result['number']}: {result['title']}")
            print(f"State: {state}")
            print(f"Branch: {result['head']} → {result['base']}")
            print(f"URL: {result['html_url']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "pr" and subcommand == "merge":
        repo = opts.get("repo")
        number = opts.get("number")
        if not repo or not number:
            print("Error: --repo and --number are required", file=sys.stderr)
            sys.exit(1)

        method = opts.get("method", "merge")
        result = gh.pr_merge(repo, int(number), method=method)

        if result.get("merged"):
            if result.get("was_merged"):
                print(f"PR #{number} was already merged")
            else:
                print(f"PR #{number} merged ({method}): {result.get('sha', '')[:8]}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "pr" and subcommand == "ensure":
        repo = opts.get("repo")
        head = opts.get("head")
        base = opts.get("base")
        title = opts.get("title")
        body = opts.get("body", "")
        method = opts.get("method", "merge")

        if not all([repo, head, title]):
            print("Error: --repo, --head, and --title are required", file=sys.stderr)
            sys.exit(1)

        if not base:
            base = gh.detect_default_branch(repo)
            print(f"Auto-detected base branch: {base}")

        result = gh.pr_create_and_merge(
            repo, head=head, base=base, title=title, body=body, method=method,
        )

        if result.get("merged"):
            if result.get("created"):
                print(f"PR #{result['number']} created and merged: {result['html_url']}")
            else:
                print(f"PR #{result['number']} merged (already existed): {result['html_url']}")
        elif "number" in result:
            print(f"PR #{result['number']} created but merge failed: {result.get('message', '')}")
            print(f"URL: {result['html_url']}")
            sys.exit(1)
        else:
            print(f"Error: {result.get('error', result.get('message', result))}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "create-board":
        title = opts.get("title")
        if not title:
            print("Error: --title is required", file=sys.stderr)
            sys.exit(1)
        viewer = gh.get_viewer()
        if "id" not in viewer:
            print(f"Error: {viewer.get('message', viewer)}", file=sys.stderr)
            sys.exit(1)
        result = gh.project_create_board(viewer["id"], title)
        if "number" in result:
            print(f"Board #{result['number']} created: {result['url']}")
            print(f"Project ID: {result['id']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "link-repo":
        project_id = opts.get("project-id")
        owner = opts.get("owner")
        repo_name = opts.get("repo")
        if not all([project_id, owner, repo_name]):
            print(
                "Error: --project-id, --owner, and --repo are required",
                file=sys.stderr,
            )
            sys.exit(1)
        repo = gh.get_repo_id(owner, repo_name)
        if "id" not in repo:
            print(f"Error: {repo.get('message', repo)}", file=sys.stderr)
            sys.exit(1)
        result = gh.project_link_repo(project_id, repo["id"])
        if isinstance(result, dict) and "name" in result:
            print(f"Linked to repository: {result['name']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "ensure":
        title = opts.get("title")
        owner = opts.get("owner")
        repo_name = opts.get("repo")
        if not all([title, owner, repo_name]):
            print(
                "Error: --title, --owner, and --repo are required", file=sys.stderr
            )
            sys.exit(1)
        result = gh.project_ensure(title, owner, repo_name)
        if "number" in result:
            print(f"Board #{result['number']} created and linked: {result['url']}")
            print(f"Linked to: {result['repo_linked']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "labels" and subcommand == "setup":
        repo = opts.get("repo")
        if not repo:
            print("Error: --repo is required (owner/repo format)", file=sys.stderr)
            sys.exit(1)
        results = gh.labels_setup(repo)
        for r in results:
            icon = "✓" if r["status"] in ("created", "exists") else "✗"
            print(f"  {icon} {r['name']}: {r['status']}")
        created = sum(1 for r in results if r["status"] == "created")
        exists = sum(1 for r in results if r["status"] == "exists")
        print(f"\n{created} created, {exists} already existed, {len(results)} total")

    elif command == "issue" and subcommand == "create":
        repo = opts.get("repo")
        title = opts.get("title")
        if not repo or not title:
            print("Error: --repo and --title are required", file=sys.stderr)
            sys.exit(1)
        body = opts.get("body", "")
        labels = opts.get("labels", "").split(",") if opts.get("labels") else None
        result = gh.issue_create(repo, title, body, labels)
        if result.get("created"):
            print(f"Issue #{result['number']} created: {result['html_url']}")
            print(f"Node ID: {result['node_id']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "issue" and subcommand == "comment":
        repo = opts.get("repo")
        number = opts.get("number")
        body = opts.get("body")
        if not repo or not number or not body:
            print("Error: --repo, --number, and --body are required", file=sys.stderr)
            sys.exit(1)
        result = gh.issue_comment_post(repo, int(number), body)
        if result.get("posted"):
            print(f"Comment posted: {result['html_url']}")
            print(f"Comment ID: {result['id']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "issue" and subcommand == "comment-edit":
        repo = opts.get("repo")
        comment_id = opts.get("comment-id")
        body = opts.get("body")
        if not repo or not comment_id or not body:
            print("Error: --repo, --comment-id, and --body are required", file=sys.stderr)
            sys.exit(1)
        result = gh.issue_comment_edit(repo, int(comment_id), body)
        if result.get("edited"):
            print(f"Comment {comment_id} edited: {result['updated_at']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "issue" and subcommand == "comments":
        repo = opts.get("repo")
        number = opts.get("number")
        if not repo or not number:
            print("Error: --repo and --number are required", file=sys.stderr)
            sys.exit(1)
        comments = gh.issue_comments_list(repo, int(number))
        print(f"Comments on issue #{number}: {len(comments)}")
        for c in comments:
            preview = c["body"][:80].replace("\n", " ")
            print(f"  [{c['id']}] @{c['user']} ({c['created_at'][:10]}): {preview}...")

    elif command == "issue" and subcommand == "close":
        repo = opts.get("repo")
        number = opts.get("number")
        if not repo or not number:
            print("Error: --repo and --number are required", file=sys.stderr)
            sys.exit(1)
        result = gh.issue_close(repo, int(number))
        if result.get("closed"):
            print(f"Issue #{number} closed")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "item-add":
        project_id = opts.get("project-id")
        title = opts.get("title")
        if not project_id or not title:
            print("Error: --project-id and --title are required", file=sys.stderr)
            sys.exit(1)
        body = opts.get("body", "")
        result = gh.project_item_add_draft(project_id, title, body)
        if "id" in result:
            print(f"Item added to board: {result['id']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "item-link":
        project_id = opts.get("project-id")
        content_id = opts.get("content-id")
        if not project_id or not content_id:
            print("Error: --project-id and --content-id are required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_item_add(project_id, content_id)
        if "id" in result:
            print(f"Issue linked to board: {result['id']}")
        else:
            print(f"Error: {result.get('message', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "get-id":
        owner = opts.get("owner")
        number = opts.get("number")
        if not owner or not number:
            print("Error: --owner and --number are required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_get_id(owner, int(number))
        if "id" in result:
            print(f"Project: {result.get('title', '?')} (#{result.get('number', '?')})")
            print(f"Node ID: {result['id']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "fields":
        project_id = opts.get("project-id")
        if not project_id:
            print("Error: --project-id is required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_fields(project_id)
        if "fields" in result:
            for f in result["fields"]:
                if "options" in f:
                    print(f"  {f['name']} (single-select): {f['id']}")
                    for opt in f["options"]:
                        print(f"    - {opt['name']}: {opt['id']}")
                else:
                    print(f"  {f['name']}: {f['id']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "item-update":
        project_id = opts.get("project-id")
        item_id = opts.get("item-id")
        field_id = opts.get("field-id")
        option_id = opts.get("option-id")
        if not all([project_id, item_id, field_id, option_id]):
            print("Error: --project-id, --item-id, --field-id, and --option-id are required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_item_update(project_id, item_id, field_id, option_id)
        if "id" in result:
            print(f"Item updated: {result['id']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "items-list":
        owner = opts.get("owner")
        number = opts.get("number")
        if not owner or not number:
            print("Error: --owner and --number are required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_items_list(owner, int(number))
        if "items" in result:
            meta = result["meta"]
            print(f"Board: {meta['title']} (#{meta['board_number']})")
            print(f"Total items: {meta['total']}")
            print(f"By status: {json.dumps(meta['by_status'])}")
            print(f"By tag: {json.dumps(meta['by_tag'])}")
            print()
            for item in result["items"]:
                status = item["status"] or "(none)"
                tag = f"[{item['tag']}] " if item["tag"] else ""
                print(f"  {tag}{item['display_title']} — {status}")
                print(f"    ID: {item['id']}")
                if item["issue_url"]:
                    print(f"    Issue: {item['issue_url']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "project" and subcommand == "sync":
        owner = opts.get("owner")
        number = opts.get("number")
        state_path = opts.get("state", "notes/board-state.json")
        if not owner or not number:
            print("Error: --owner and --number are required", file=sys.stderr)
            sys.exit(1)
        result = gh.project_sync(owner, int(number), state_path)
        if "actions" in result:
            meta = result["meta"]
            summary = result["summary"]
            print(f"Board: {meta['title']} (#{meta['board_number']})")
            print(f"Total items: {meta['total']}")
            print(f"\nSync summary:")
            for action_type, count in sorted(summary.items()):
                icon = {"new_on_board": "+", "updated_on_board": "~",
                        "removed_from_board": "-", "in_sync": "="}
                print(f"  {icon.get(action_type, '?')} {action_type}: {count}")

            # Show new items
            new_items = [a for a in result["actions"] if a["type"] == "new_on_board"]
            if new_items:
                print(f"\nNew items ({len(new_items)}):")
                for a in new_items:
                    item = a["item"]
                    tag = f"[{item['tag']}] " if item["tag"] else ""
                    print(f"  + {tag}{item['display_title']} — {item['status'] or '(none)'}")

            # Show updated items
            updated = [a for a in result["actions"] if a["type"] == "updated_on_board"]
            if updated:
                print(f"\nUpdated items ({len(updated)}):")
                for a in updated:
                    item = a["item"]
                    tag = f"[{item['tag']}] " if item["tag"] else ""
                    print(f"  ~ {tag}{item['display_title']}")
                    for ch in a.get("changes", []):
                        print(f"      {ch['field']}: {ch['local']} → {ch['remote']}")

            # Show removed items
            removed = [a for a in result["actions"] if a["type"] == "removed_from_board"]
            if removed:
                print(f"\nRemoved from board ({len(removed)}):")
                for a in removed:
                    local = a["local"]
                    print(f"  - {local.get('title', '(unknown)')}")

            print(f"\nLocal state saved to: {result['local_state_path']}")
        else:
            print(f"Error: {result.get('error', result)}", file=sys.stderr)
            sys.exit(1)

    elif command == "labels" and subcommand == "setup-all":
        # Batch setup TAG: labels on multiple repos
        repos_arg = opts.get("repos", "")
        if not repos_arg:
            print("Error: --repos is required (comma-separated owner/repo list)", file=sys.stderr)
            sys.exit(1)
        repos = [r.strip() for r in repos_arg.split(",") if r.strip()]
        total_created = 0
        total_existed = 0
        for repo in repos:
            print(f"\n--- {repo} ---")
            try:
                results = gh.labels_setup(repo)
                for r in results:
                    icon = "✓" if r["status"] in ("created", "exists") else "✗"
                    print(f"  {icon} {r['name']}: {r['status']}")
                created = sum(1 for r in results if r["status"] == "created")
                existed = sum(1 for r in results if r["status"] == "exists")
                total_created += created
                total_existed += existed
                print(f"  {created} created, {existed} existed")
            except Exception as e:
                print(f"  Error: {e}")

        print(f"\n=== Total: {total_created} created, {total_existed} existed across {len(repos)} repos ===")

    else:
        print(f"Unknown command: {command} {subcommand}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
