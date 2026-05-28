# Worker Workspace Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workspace-preparation step to nd-worker so each claimed
kata task runs against a freshly prepared git worktree backed by a
shared bare cache, instead of the current hardcoded `/tmp/{project}`
that is never created.

**Architecture:** New `nd/clients/workspace.py` (`WorkspaceClient` +
`Workspace` dataclass), two new schemas (`WorkspaceInput`,
`WorkspaceResult`), two new reasoners on the worker
(`prepare_workspace`, `cleanup_workspace`), and edits to
`process_task`, `execute_changes`, and `_parse_task_body` to thread
the real worktree path through the pipeline and capture real
`commit_sha` / `files_changed` after the harness run.

**Tech Stack:** Python 3.11+, asyncio subprocess, Pydantic, AgentField

**Working Directory:** `/Users/andy/.superset/worktrees/99cc5a38-5fb1-4d5b-9c3f-f5182514d4bb/chipped-geranium`

**Spec:** `docs/superpowers/specs/2026-05-27-worker-workspace-prep.md`

---

### Task 1: Add workspace settings to Config

**Files:**
- Modify: `nd/config.py`

- [ ] **Step 1: Add `workspace_root` and `workspace_keep_on_failure` to `Config`**

In `nd/config.py`, add the two fields and read them from env:

```python
@dataclass(frozen=True)
class Config:
    """Application configuration from environment."""

    # ... existing fields ...
    agent_port: int
    workspace_root: str                     # NEW
    workspace_keep_on_failure: bool         # NEW

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            # ... existing kwargs ...
            agent_port=int(os.getenv("AGENT_PORT", "0")),
            workspace_root=os.getenv("WORKSPACE_ROOT", "/var/nd"),
            workspace_keep_on_failure=os.getenv(
                "WORKSPACE_KEEP_ON_FAILURE", "1"
            ) not in ("0", "false", "False", ""),
        )
```

- [ ] **Step 2: Document new env vars in README**

Add `WORKSPACE_ROOT` (default `/var/nd`) and
`WORKSPACE_KEEP_ON_FAILURE` (default `true`) to the env table in
`README.md`. Note that `/var/nd` is ephemeral by default and document
how to mount it as a docker volume for persistent caches.

- [ ] **Step 3: Commit**

```bash
git add nd/config.py README.md
git commit -m "feat(config): add workspace_root and workspace_keep_on_failure"
```

---

### Task 2: Add `WorkspaceClient` and `Workspace` to clients

**Files:**
- Create: `nd/clients/workspace.py`

- [ ] **Step 1: Module skeleton**

Create `nd/clients/workspace.py` with the imports, the `Workspace`
frozen dataclass, and a logger. Match the style of
`nd/clients/kata.py`:

```python
"""Workspace preparation: bare git cache + per-task worktrees."""

import asyncio
import logging
import os
import re
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Workspace:
    """A prepared, on-disk workspace for a single task."""

    repo_path: str       # absolute path to the worktree
    branch: str          # the checked-out branch
    base_branch: str     # what we forked from / the MR target
    bare_path: str       # absolute path to the shared bare cache
```

- [ ] **Step 2: Auth URL builder**

Add a helper that constructs the authenticated clone URL. Tokens are
only ever passed to `git clone --bare` / `git fetch`; never persisted
in the worktree's `.git/config`.

```python
def _auth_clone_url(
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    github_token: str,
    gitlab_token: str,
) -> str:
    base = f"{platform_host}/{repo_owner}/{repo_name}.git"
    if platform == "github" and github_token:
        return f"https://x-access-token:{github_token}@{base}"
    if platform == "gitlab" and gitlab_token:
        return f"https://oauth2:{gitlab_token}@{base}"
    return f"https://{base}"
```

- [ ] **Step 3: `WorkspaceClient` skeleton + `_run` helper**

```python
class WorkspaceClient:
    """Manages bare repo caches and per-task git worktrees."""

    def __init__(
        self,
        root: str = "/var/nd",
        github_token: str = "",
        gitlab_token: str = "",
    ):
        self.root = root
        self.github_token = github_token
        self.gitlab_token = gitlab_token

    def _bare_path(self, platform_host: str, owner: str, repo: str) -> str:
        return os.path.join(self.root, "repos", platform_host, owner, f"{repo}.git")

    def _worktree_path(self, task_slug: str) -> str:
        # Replace slashes so kata project names that contain "/" are safe.
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", task_slug).strip("-")
        return os.path.join(self.root, "work", safe)

    async def _run(
        self,
        args: list[str],
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()
```

- [ ] **Step 4: `prepare()`**

Implement clone-or-fetch + `worktree add`:

```python
async def prepare(
    self,
    *,
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    head_branch: str | None,
    base_branch: str | None,
    task_slug: str,
    issue_short_id: str | None = None,
) -> Workspace | None:
    """Clone-or-fetch the bare cache and add a fresh worktree.

    For MR tasks, ``head_branch`` must be set; we check that branch
    out directly. For issue tasks, pass ``issue_short_id``; we create
    ``nd/issue-<short_id>`` off ``base_branch`` (or origin/HEAD if
    base_branch is None).
    """
    bare_path = self._bare_path(platform_host, repo_owner, repo_name)
    worktree_path = self._worktree_path(task_slug)

    if os.path.exists(worktree_path):
        logger.warning("worktree path %s already exists; failing prep", worktree_path)
        return None

    auth_url = _auth_clone_url(
        platform, platform_host, repo_owner, repo_name,
        self.github_token, self.gitlab_token,
    )
    os.makedirs(os.path.dirname(bare_path), exist_ok=True)

    if not os.path.exists(bare_path):
        rc, _, err = await self._run(["git", "clone", "--bare", auth_url, bare_path])
        if rc != 0:
            logger.warning("git clone --bare failed: %s", err.strip())
            return None
    else:
        rc, _, err = await self._run(
            ["git", "-C", bare_path, "fetch", "--prune", auth_url, "+refs/heads/*:refs/heads/*"],
        )
        if rc != 0:
            logger.warning("git fetch failed: %s", err.strip())
            return None

    # Resolve effective base_branch from origin/HEAD if needed.
    if base_branch is None:
        rc, out, _ = await self._run(
            ["git", "-C", bare_path, "symbolic-ref", "--short", "HEAD"],
        )
        base_branch = out.strip() if rc == 0 and out.strip() else "main"

    if head_branch:
        rc, _, err = await self._run(
            ["git", "-C", bare_path, "worktree", "add", worktree_path, head_branch],
        )
        branch = head_branch
    else:
        new_branch = f"nd/issue-{issue_short_id}" if issue_short_id else f"nd/task-{task_slug}"
        rc, _, err = await self._run(
            [
                "git", "-C", bare_path, "worktree", "add",
                "-b", new_branch, worktree_path, base_branch,
            ],
        )
        branch = new_branch

    if rc != 0:
        logger.warning("git worktree add failed: %s", err.strip())
        return None

    return Workspace(
        repo_path=worktree_path,
        branch=branch,
        base_branch=base_branch,
        bare_path=bare_path,
    )
```

- [ ] **Step 5: `cleanup()`**

```python
async def cleanup(self, workspace: Workspace) -> None:
    """Remove the worktree. Best-effort; never raises."""
    rc, _, err = await self._run(
        [
            "git", "-C", workspace.bare_path, "worktree", "remove",
            "--force", workspace.repo_path,
        ],
    )
    if rc != 0:
        logger.warning("git worktree remove failed: %s; falling back to rm -rf", err.strip())
        shutil.rmtree(workspace.repo_path, ignore_errors=True)
```

- [ ] **Step 6: Commit**

```bash
git add nd/clients/workspace.py
git commit -m "feat(clients): add WorkspaceClient for bare cache + per-task worktrees"
```

---

### Task 3: Add workspace schemas

**Files:**
- Modify: `nd/schemas.py`

- [ ] **Step 1: Add WorkspaceInput and WorkspaceResult**

In `nd/schemas.py`, add (alongside the other input/result pairs):

```python
class WorkspaceInput(BaseModel):
    task_id: str
    project: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    head_branch: str | None = None
    base_branch: str | None = None
    is_issue: bool = False
    issue_short_id: str | None = None


class WorkspaceResult(BaseModel):
    prepared: bool
    repo_path: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    bare_path: str | None = None
    error: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add nd/schemas.py
git commit -m "feat(schemas): add WorkspaceInput and WorkspaceResult"
```

---

### Task 4: Teach `_parse_task_body` to handle issue bodies

**Files:**
- Modify: `nd/worker/agent.py`

- [ ] **Step 1: Add an issue-context branch to `_parse_task_body`**

Issue bodies (built by `KataClient.build_issue_task_body`) start with
`## Issue Context` and have:

```
- **Issue:** [owner/repo#N](url)
- **Title:** ...
- **Platform:** github (github.com)
- **Assignees:** ...

## Issue Description
**Author:** ...

<body>
```

Update `_parse_task_body` so that when `## Issue Context` is the
first section it sets `context["category"] = "issue"`, parses
`repo_owner`, `repo_name`, `mr_number` (the issue number),
`mr_url`, `mr_title` (the issue title), `platform`,
`platform_host`, and the `comment_body` from the `## Issue
Description` block. `head_branch` / `base_branch` remain unset for
issue tasks; the new `prepare_workspace` reasoner will pick a base
from origin/HEAD.

```python
issue_match = re.search(
    r"## Issue Context\s*\n.*?\*\*Issue:\*\* \[([^/]+)/([^#]+)#(\d+)\]\((https?://[^)]+)\)",
    body,
    re.DOTALL,
)
if issue_match:
    context["category"] = "issue"
    context["repo_owner"] = issue_match.group(1)
    context["repo_name"] = issue_match.group(2)
    context["mr_number"] = int(issue_match.group(3))
    context["mr_url"] = issue_match.group(4)
    # ... extract title, platform, platform_host, body ...
```

Keep the existing MR branch unchanged; the issue branch only fires
when `## Issue Context` is the first heading.

- [ ] **Step 2: Commit**

```bash
git add nd/worker/agent.py
git commit -m "feat(worker): parse issue task bodies in _parse_task_body"
```

---

### Task 5: Add `prepare_workspace` and `cleanup_workspace` reasoners

**Files:**
- Modify: `nd/worker/agent.py`

- [ ] **Step 1: Construct a `WorkspaceClient` next to other clients**

In `create_worker_agent`, after the existing client construction:

```python
from nd.clients.workspace import WorkspaceClient

workspace = WorkspaceClient(
    root=config.workspace_root,
    github_token=config.github_token,
    gitlab_token=config.gitlab_token,
)
```

- [ ] **Step 2: Add `prepare_workspace` reasoner**

```python
@app.reasoner()
async def prepare_workspace(
    task_id: str,
    project: str,
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    head_branch: str | None = None,
    base_branch: str | None = None,
    is_issue: bool = False,
    issue_short_id: str | None = None,
) -> dict:
    """Clone-or-fetch + worktree add for the claimed task."""
    task_slug = f"{project}-{issue_short_id or task_id}".replace("#", "-")
    ws = await workspace.prepare(
        platform=platform,
        platform_host=platform_host,
        repo_owner=repo_owner,
        repo_name=repo_name,
        head_branch=None if is_issue else head_branch,
        base_branch=base_branch,
        task_slug=task_slug,
        issue_short_id=issue_short_id if is_issue else None,
    )
    if ws is None:
        return WorkspaceResult(prepared=False, error="workspace prep failed").model_dump()
    return WorkspaceResult(
        prepared=True,
        repo_path=ws.repo_path,
        branch=ws.branch,
        base_branch=ws.base_branch,
        bare_path=ws.bare_path,
    ).model_dump()
```

- [ ] **Step 3: Add `cleanup_workspace` reasoner**

```python
@app.reasoner()
async def cleanup_workspace(repo_path: str, bare_path: str) -> dict:
    """Best-effort worktree teardown after task completion."""
    await workspace.cleanup(
        Workspace(repo_path=repo_path, branch="", base_branch="", bare_path=bare_path),
    )
    return {"cleaned": True}
```

- [ ] **Step 4: Commit**

```bash
git add nd/worker/agent.py
git commit -m "feat(worker): add prepare_workspace and cleanup_workspace reasoners"
```

---

### Task 6: Wire `prepare_workspace` into `process_task`

**Files:**
- Modify: `nd/worker/agent.py`

- [ ] **Step 1: Call `prepare_workspace` immediately after parse**

In `process_task`, after `context = _parse_task_body(body)` and the
parse-failure early-return, add:

```python
ws_result = await app.call(
    f"{app.node_id}.prepare_workspace",
    task_id=task_id,
    project=project,
    platform=context.get("platform", ""),
    platform_host=context.get("platform_host", ""),
    repo_owner=context.get("repo_owner", ""),
    repo_name=context.get("repo_name", project),
    head_branch=context.get("head_branch"),
    base_branch=context.get("base_branch"),
    is_issue=context.get("category") == "issue",
    issue_short_id=task_id.split("#")[-1] if "#" in task_id else None,
)
ws = WorkspaceResult(**ws_result)
if not ws.prepared:
    await kata.label(task_id, "needs-human")
    return ProcessResult(
        status="failed",
        error=f"workspace prep failed: {ws.error}",
    ).model_dump()
repo_path = ws.repo_path
```

- [ ] **Step 2: Replace `f"/tmp/{project}"` with `repo_path`**

There are exactly four `repo_path=f"/tmp/{project}"` call sites in
`process_task` (analyze_task, plan_changes, execute_changes,
run_roborev). Replace each with `repo_path=repo_path`.

- [ ] **Step 3: Call `cleanup_workspace` only on success**

At the end of `process_task` (after `finalize_task` returns and we
build the `completed` `ProcessResult`), call:

```python
if config.workspace_keep_on_failure is False or status_is_completed:
    await app.call(
        f"{app.node_id}.cleanup_workspace",
        repo_path=ws.repo_path,
        bare_path=ws.bare_path,
    )
```

For v1, only call cleanup on the `completed` path. The
`paused_for_*` and `failed` returns leave the worktree on disk for
human inspection.

- [ ] **Step 4: Commit**

```bash
git add nd/worker/agent.py
git commit -m "feat(worker): thread prepared workspace through process_task"
```

---

### Task 7: Fix `execute_changes` to use the harness correctly

**Files:**
- Modify: `nd/worker/agent.py`

- [ ] **Step 1: Use the real `app.harness` parameter names**

The current call uses `goal=` and `max_iterations=`, but
`agentfield.Agent.harness` actually takes `prompt=` and `max_turns=`.
Update the call and add `cwd=repo_path` so Claude Code edits land
inside the worktree:

```python
await app.harness(
    prompt=goal,
    provider="claude-code",
    tools=["read", "write", "edit", "bash"],
    max_turns=20,
    cwd=repo_path,
)
```

- [ ] **Step 2: Capture real `commit_sha` and `files_changed`**

After the harness returns, use `git -C repo_path` to populate the two
fields that are currently hardcoded to `None` / `[]`:

```python
async def _git(args: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", repo_path, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode().strip()

rc_sha, sha = await _git(["rev-parse", "HEAD"])
commit_sha = sha if rc_sha == 0 else None

rc_files, files_text = await _git(["diff", "--name-only", "HEAD~1..HEAD"])
files_changed = [f for f in files_text.splitlines() if f] if rc_files == 0 else []
```

If the harness made no commit (e.g. it only ran a build or printed a
diff), `HEAD~1..HEAD` may still resolve to the pre-existing commit
range; treat that as `files_changed=[]` and let downstream draft text
note "no changes committed".

- [ ] **Step 3: Commit**

```bash
git add nd/worker/agent.py
git commit -m "fix(worker): pass cwd to harness and capture real commit sha"
```

---

### Task 8: Unit tests for `WorkspaceClient`

**Files:**
- Create: `tests/unit/test_workspace.py`

- [ ] **Step 1: Patch helper that captures git invocations**

Mirror the `_FakeProc` / `_patch_kata_subprocess_sequence` pattern
from `tests/unit/test_clients.py`. Each test queues a list of
`(returncode, stdout)` tuples; the patched
`asyncio.create_subprocess_exec` pops one per call.

- [ ] **Step 2: Test `prepare()` with no existing bare cache**

Patch `os.path.exists` to return `False` for both the bare and
worktree paths. Queue successful responses for `git clone --bare`
and `git worktree add`. Assert:

- The first subprocess call is `git clone --bare <auth_url> <bare_path>`.
- The second is `git -C <bare_path> worktree add <worktree_path> <head_branch>`.
- The returned `Workspace.repo_path` matches the worktree path.

- [ ] **Step 3: Test `prepare()` with existing bare cache**

Patch `os.path.exists` so the bare exists but the worktree does not.
Assert the first call is `git -C <bare_path> fetch --prune ...` and
no `git clone --bare` is issued.

- [ ] **Step 4: Test issue-task branch creation**

Call `prepare(head_branch=None, issue_short_id="7by6")` with
`base_branch=None`. Queue a successful `symbolic-ref` returning
`main`, then a successful `worktree add -b nd/issue-7by6 ... main`.
Assert the captured commands include `-b nd/issue-7by6` and the
returned `Workspace.branch == "nd/issue-7by6"`.

- [ ] **Step 5: Test auth URL construction**

Three sub-tests: github with token, gitlab with token, github with
empty token. Assert the auth URL passed to `git clone --bare` matches
each of the three forms in the spec.

- [ ] **Step 6: Test `prepare()` returns None when worktree path exists**

Patch `os.path.exists(worktree_path) -> True`. Assert no subprocess
calls are made and `prepare()` returns `None`.

- [ ] **Step 7: Test `cleanup()`**

Queue a successful `git worktree remove --force` response. Assert the
captured command matches and that no exception is raised.

- [ ] **Step 8: Commit**

```bash
git add tests/unit/test_workspace.py
git commit -m "test(unit): WorkspaceClient prepare/cleanup paths"
```

---

### Task 9: Unit tests for issue-body parsing

**Files:**
- Modify: `tests/unit/test_worker.py` (or create if absent)

- [ ] **Step 1: Test `_parse_task_body` on an issue body**

Build a body via `KataClient.build_issue_task_body(...)` and feed it
to `_parse_task_body`. Assert:

- `context["category"] == "issue"`
- `context["repo_owner"]`, `context["repo_name"]`, `context["mr_number"]`,
  `context["mr_url"]`, `context["platform"]`, `context["platform_host"]`
  are extracted correctly
- `context["comment_body"]` contains the issue description (not the
  full markdown)
- `context.get("head_branch")` is `None`

- [ ] **Step 2: Test that MR-body parsing is unchanged**

Add (or keep) a test that builds an MR body via
`KataClient.build_task_body` and parses it; assert the MR-shaped
keys (`head_branch`, `base_branch`, `dedupe_key`) come through.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_worker.py
git commit -m "test(unit): _parse_task_body handles issue bodies"
```

---

### Task 10: Reasoner-level unit tests

**Files:**
- Modify: `tests/unit/test_worker.py`

- [ ] **Step 1: Test `prepare_workspace` returns failure when client returns None**

Patch `WorkspaceClient.prepare` to return `None`; assert the reasoner
returns `WorkspaceResult(prepared=False, ...)`.

- [ ] **Step 2: Test `process_task` aborts to needs-human on prep failure**

Patch `prepare_workspace` (via `app.call` indirection — see existing
worker tests for the pattern) to return
`WorkspaceResult(prepared=False).model_dump()`; assert the function
returns `ProcessResult(status="failed", ...)`, no `analyze_task`
call is made, and `kata.label(task_id, "needs-human")` is invoked.

- [ ] **Step 3: Test `cleanup_workspace` is called only on completed**

Run a happy-path `process_task` with all downstream reasoners
returning success; assert `cleanup_workspace` was called once. Run a
`paused_for_review` path; assert `cleanup_workspace` was NOT called.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_worker.py
git commit -m "test(unit): workspace prep wiring in process_task"
```

---

### Task 11: Functional smoke test (gated)

**Files:**
- Create: `tests/functional/test_workspace_e2e.py`

- [ ] **Step 1: Skip-unless-token gate**

```python
@pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"),
    reason="needs GITHUB_TOKEN for clone",
)
```

- [ ] **Step 2: Clone -> worktree add -> rev-parse -> cleanup**

Use a small public repo (e.g. `octocat/Hello-World`) under a tmp
`workspace_root`. Assert the worktree directory appears, contains a
`.git` file (worktree marker), `git rev-parse HEAD` resolves, and
that `cleanup()` removes the directory.

- [ ] **Step 3: Commit**

```bash
git add tests/functional/test_workspace_e2e.py
git commit -m "test(functional): WorkspaceClient end-to-end against public repo"
```

---

### Task 12: Update CLAUDE.md and README

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Add `nd/clients/workspace.py` to the project layout listing in CLAUDE.md**

In the layout block, add the workspace client alongside the others:

```
clients/
├── middleman.py
├── kata.py
├── platform.py
└── workspace.py     # NEW: bare cache + per-task worktrees
```

- [ ] **Step 2: Add `prepare_workspace` / `cleanup_workspace` to the worker reasoner list**

Update the worker line:

```
worker/agent.py      # Reasoners: claim_task, process_task, prepare_workspace,
                     #            analyze_task, plan_changes, execute_changes,
                     #            run_roborev, draft_response, post_response,
                     #            finalize_task, cleanup_workspace
```

- [ ] **Step 3: Document `WORKSPACE_ROOT` / `WORKSPACE_KEEP_ON_FAILURE` in README**

Add the two env vars to the env table in `README.md` and add a short
"Worker workspaces" subsection under "Configuration" that explains
the `/var/nd/repos` and `/var/nd/work` layout and how to opt into a
persistent cache via a docker volume.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: document worker workspace prep step"
```

---

### Task 13: Verify, push, and review

- [ ] **Step 1: Run the full check locally**

```bash
ruff check . && ruff format --check . && pytest tests/unit -v
```

Coverage should remain ≥50%. If it dips, add tests for whichever
branch is uncovered.

- [ ] **Step 2: Sanity-check inside the worker container**

```bash
docker compose build worker-1
docker compose up -d --force-recreate worker-1
docker compose exec worker-1 python3 -c '
import asyncio
from nd.clients.workspace import WorkspaceClient
async def main():
    c = WorkspaceClient(root="/tmp/nd-smoke", github_token="")
    ws = await c.prepare(
        platform="github", platform_host="github.com",
        repo_owner="octocat", repo_name="Hello-World",
        head_branch="master", base_branch=None,
        task_slug="smoke",
    )
    print(ws)
    await c.cleanup(ws)
asyncio.run(main())
'
```

Expect a `Workspace(...)` print and an `ls /tmp/nd-smoke/work` showing
the directory before cleanup and gone after.

- [ ] **Step 3: Push and request review**

```bash
git push
roborev review --branch --wait
```

Address any High/Medium findings via `/roborev-refine`.

---

## Out of scope (matches spec)

- Resume-after-restart for in-flight tasks.
- `git push` of the worker's commit / opening a PR.
- Cross-task dependency caching (npm/pip/go-mod).
- Kata projects that span multiple git repos.
