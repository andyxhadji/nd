# Worker Workspace Preparation

## Summary

Add a workspace-preparation step to the nd-worker agent so that, after
claiming a kata task, it clones the target repository (or fetches into a
cached bare clone) and creates an isolated git worktree at the relevant
ref before invoking the harness. Today the worker references a hardcoded
`/tmp/{project}` path that is never created; the harness, the
deterministic analyzer, and `roborev refine` therefore have no real
checkout to operate on.

## Motivation

The worker's `process_task` reasoner threads `repo_path = f"/tmp/{project}"`
into `analyze_task`, `plan_changes`, `execute_changes`, and `run_roborev`,
but no step in the worker actually creates that directory or clones the
repo into it. Concretely:

- `execute_changes` calls `app.harness(...)` without a working-directory
  argument; whatever edits Claude Code makes land in the agent
  container's cwd (`/app`), not in a checkout of the target repo.
- `run_roborev` runs `roborev refine` with `cwd=repo_path`. Because that
  directory does not exist, the subprocess fails before roborev can
  inspect anything.
- For MR-tagged tasks, the worker should be operating on the MR's
  `head_branch`. There is no checkout step that puts that branch on
  disk.
- For issue-tagged tasks, the kata body produced by
  `KataClient.build_issue_task_body` does not include any branch
  information, so `_parse_task_body` cannot recover one even if it
  tried. Issue tasks need a fresh branch off the repo's default
  branch.

Because two workers can claim independent tasks against the same
project, a shared `/tmp/{project}` directory would race even if it
existed. The right primitive is a per-task git worktree backed by a
shared bare cache.

## Design

### Layout on disk

Inside each agent container:

```
/var/nd/
├── repos/                       # bare cache (one per repo)
│   ├── github.com/
│   │   └── andyxhadji/
│   │       └── langextract-bedrock.git/
│   └── gitlab.com/
│       └── org/
│           └── repo.git/
└── work/                        # per-task worktrees
    ├── langextract-bedrock-7by6/
    └── sweets-r1t6/
```

- `repos/<host>/<owner>/<repo>.git` is a bare clone, fetched once and
  refreshed before each task. Sharing this cache across tasks avoids
  re-downloading the full history every time.
- `work/<task-slug>/` is a worktree linked to the bare cache. The slug
  is the kata short_id qualifier (`<project>-<short_id>` — slashes in
  project names are replaced with `-`) so two workers cannot collide.

`/var/nd` is owned by the worker user inside the container and is
**not** mounted as a docker volume by default. Worktrees and the bare
cache are ephemeral; if the container restarts mid-task, the affected
task is re-claimable after its kata `in-progress` label is cleared by
human intervention. We do not attempt resume-after-restart in v1.

### New module: `nd/clients/workspace.py`

Introduce a `WorkspaceClient` that owns all git interactions. Keeping
this out of `nd/worker/agent.py` matches the rest of the codebase
(`clients/middleman.py`, `clients/kata.py`, `clients/platform.py`).

```python
@dataclass(frozen=True)
class Workspace:
    repo_path: str       # absolute path to the worktree
    branch: str          # the checked-out branch
    base_branch: str     # the branch we forked from (issues) or the MR target
    bare_path: str       # absolute path to the bare cache (for cleanup)


class WorkspaceClient:
    def __init__(
        self,
        root: str = "/var/nd",
        github_token: str = "",
        gitlab_token: str = "",
    ): ...

    async def prepare(
        self,
        platform: str,         # "github" | "gitlab"
        platform_host: str,    # e.g. "github.com"
        repo_owner: str,
        repo_name: str,
        head_branch: str | None,  # MRs only; issues pass None
        base_branch: str | None,  # MRs supply this; issues default to repo HEAD
        task_slug: str,        # used for the worktree directory name
    ) -> Workspace | None: ...

    async def cleanup(self, workspace: Workspace) -> None: ...
```

`prepare()` is responsible for:

1. Compute the bare cache path and the worktree path.
2. If the bare cache does not exist, run
   `git clone --bare <auth_url> <bare_path>`.
3. Otherwise run `git -C <bare_path> fetch --prune origin`.
4. Determine the working branch:
   - For MR tasks: check out the MR's `head_branch`. If the branch is
     already a worktree, fail fast (the task is already in flight on
     this worker).
   - For issue tasks: create a fresh branch
     `nd/issue-<short_id>` off `base_branch` (defaulting to the repo's
     default branch as resolved by `git symbolic-ref refs/remotes/origin/HEAD`).
5. Run `git -C <bare_path> worktree add <worktree_path> <branch>` (or
   `git worktree add -b <new_branch> <worktree_path> <base>` for issue
   tasks).
6. Return a `Workspace`. On any subprocess failure, log stderr and
   return `None`.

`cleanup()` runs `git -C <bare_path> worktree remove --force <worktree_path>`
and best-effort deletes the directory if the kata wrap-up succeeded.
For failed/paused tasks we leave the worktree in place so a human can
inspect.

#### Auth URL construction

```
github  -> https://x-access-token:<GITHUB_TOKEN>@<host>/<owner>/<repo>.git
gitlab  -> https://oauth2:<GITLAB_TOKEN>@<host>/<owner>/<repo>.git
```

When the corresponding token is empty, fall back to plain
`https://<host>/<owner>/<repo>.git` and let git fail loudly on private
repos. The auth URL is **only** passed to the bare clone/fetch and is
never persisted in the worktree's remote config; we use
`git -c credential.helper=` and the URL form above to avoid writing
secrets into `.git/config`.

### Schema additions in `nd/schemas.py`

Following the project rule "all schemas live in `nd/schemas.py`" we add:

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


class WorkspaceResult(BaseModel):
    prepared: bool
    repo_path: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    error: str | None = None
```

`AnalysisInput`, `ExecutionInput`, and `RoborevInput` already have
`repo_path: str` so no schema changes are needed there. The values
they receive will be the real worktree path returned by the new
reasoner.

### New reasoners on the worker

Add to `nd/worker/agent.py`:

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
) -> dict: ...


@app.reasoner()
async def cleanup_workspace(
    repo_path: str,
    bare_path: str,
) -> dict: ...
```

`prepare_workspace` delegates to `WorkspaceClient.prepare(...)` and
returns a `WorkspaceResult.model_dump()`.

`cleanup_workspace` delegates to `WorkspaceClient.cleanup(...)`. It is
called from `finalize_task` only when `status == "completed"`. For
`failed` / `needs-human` / `paused_for_*` outcomes the worktree is
deliberately preserved.

### `process_task` flow changes

The orchestration in `process_task` becomes:

```python
context = _parse_task_body(body)
if not context:
    return ProcessResult(status="failed", error="Could not parse task body").model_dump()

ws_result = await app.call(
    f"{app.node_id}.prepare_workspace",
    task_id=task_id,
    project=project,
    platform=context["platform"],
    platform_host=context["platform_host"],
    repo_owner=context["repo_owner"],
    repo_name=project,                       # by current convention
    head_branch=context.get("head_branch"),
    base_branch=context.get("base_branch"),
    is_issue=context.get("category") == "issue",
)
ws = WorkspaceResult(**ws_result)
if not ws.prepared:
    await kata.label(task_id, "needs-human")
    return ProcessResult(
        status="failed",
        error=f"workspace prep failed: {ws.error}",
    ).model_dump()

repo_path = ws.repo_path  # used everywhere `f"/tmp/{project}"` appears today
```

The four downstream `app.call` sites that currently pass
`repo_path=f"/tmp/{project}"` are updated to pass `repo_path=ws.repo_path`.

### `execute_changes` must thread the path into the harness

Today `execute_changes` accepts `repo_path` but does not pass it to
`app.harness`. The harness needs a working directory so Claude Code's
edits land in the worktree. Per the agentfield SDK, this is the `cwd`
parameter on `app.harness`. Update the call:

```python
await app.harness(
    goal=goal,
    provider="claude-code",
    tools=["read", "write", "edit", "bash"],
    max_iterations=20,
    cwd=repo_path,                # <-- new
)
```

After the harness returns, run `git -C repo_path rev-parse HEAD` (via
asyncio subprocess) to capture the actual `commit_sha` and
`git -C repo_path diff --name-only HEAD~1..HEAD` to populate
`files_changed`. These two fields are currently hard-coded to
`[]` / `None` in `ExecutionResult`, which is also a v1 gap; this spec
fixes it because `run_roborev` and `draft_response` both depend on a
real `commit_sha`.

### `_parse_task_body` updates

Two changes:

1. **Detect issue tasks.** Issue bodies start with `## Issue Context`
   rather than `## MR Context`. When that header is present, set
   `context["category"] = "issue"` and parse:
   - `**Issue:** [owner/repo#N](url)` -> `repo_owner`, `repo_name`,
     `mr_number` (we keep the field name for symmetry but it is the
     issue number), `mr_url`.
   - `**Title:**`, `**Platform:** ...`, `**Author:**`, body text.
   - `head_branch` / `base_branch` remain unset; `prepare_workspace`
     will create the branch.
2. **Set `comment_body`** from the issue's description (the text
   between `## Issue Description` and end of body) when parsing an
   issue task.

The existing MR parsing remains unchanged.

### Configuration additions in `nd/config.py`

```python
workspace_root: str = "/var/nd"          # WORKSPACE_ROOT
workspace_keep_on_failure: bool = True   # WORKSPACE_KEEP_ON_FAILURE
```

`GITHUB_TOKEN` / `GITLAB_TOKEN` are already in `Config`; the workspace
client reads them from the same struct.

### Dockerfile / compose

`git` is already installed in the runtime image (Dockerfile line 16),
so no image changes are required for v1. We do **not** mount
`/var/nd` as a volume; bare caches and worktrees are ephemeral within
a container's lifetime. Operators who want persistent caches can mount
`/var/nd` themselves.

### Cleanup semantics

| `process_task` outcome      | Worktree           | Bare cache     |
|-----------------------------|--------------------|----------------|
| `completed`                 | removed            | kept           |
| `failed`                    | kept               | kept           |
| `paused_for_spec`           | kept               | kept           |
| `paused_for_review`         | kept               | kept           |
| `addressed` (no post)       | kept               | kept           |

The bare cache is never removed by the worker; operators who want to
reclaim disk run `rm -rf /var/nd/repos/<host>/<owner>/<repo>.git`.

### Failure modes

- **Repo does not exist / 404 on clone**: `prepare()` returns `None`,
  the worker labels the task `needs-human` with an error string.
- **`head_branch` does not exist on origin**: same as above. We do not
  fall back to `base_branch` because that would silently produce a
  task on the wrong commit.
- **Worktree path already exists**: `git worktree add` errors. We
  treat this as a fatal prep failure rather than racing — the
  expectation is that two workers never claim the same kata task.
- **Disk pressure**: out of scope for v1. We rely on operators to
  size container disks and run periodic `git worktree prune`.

## Out of scope

- Resume-after-restart for in-flight tasks.
- Pushing the worker's commit back up to a forked branch / opening
  a PR. The worker only commits locally; posting a comment with the
  commit SHA is the v1 hand-off contract. Adding a `git push` step is
  a follow-up because it requires deciding which remote/branch to
  push to (especially for issue tasks).
- Cross-task caching of dependency installs (npm, pip, go mod). Each
  worktree gets a fresh install at harness time.
- Kata projects that are not 1:1 with a single git repo.

## Migration / rollout

This is additive. Existing kata tasks that were queued before this
change continue to parse via the unchanged MR branch of
`_parse_task_body`, and `prepare_workspace` is invoked from
`process_task` regardless. There is no backward-compatibility shim
needed because `process_task` was previously running against a
non-existent path; any caller that depended on the old path was
already broken.

## Testing

Unit tests (`tests/unit/test_workspace.py`):

- `WorkspaceClient.prepare` issues the expected git commands when the
  bare cache is absent (`clone --bare` then `worktree add`).
- `WorkspaceClient.prepare` issues `fetch --prune` when the bare
  cache exists.
- Issue tasks create a `nd/issue-<short_id>` branch off the resolved
  default branch.
- Auth URL is constructed correctly for github/gitlab and falls back
  to anonymous when the token is empty.
- `cleanup` runs `worktree remove --force`.
- All git invocations are exercised via a `_FakeProc` patch on
  `asyncio.create_subprocess_exec`, mirroring the existing
  `KataClient` test pattern.

Worker reasoner wiring tests (`tests/unit/test_worker_workspace.py`):

- `prepare_workspace` returns `prepared=False` with a populated
  `error` when the underlying client fails.
- `process_task` aborts to `needs-human` when prep fails (no
  `analyze_task` call is made).
- `cleanup_workspace` is invoked on `completed` and skipped on
  `failed` / `paused_*`.

Functional tests (`tests/functional/test_workspace_e2e.py`, gated on
`GITHUB_TOKEN` and a public read-only fixture repo): clone, worktree
add, `git rev-parse HEAD`, then cleanup, asserting the directories
appear and disappear.

## Open questions

1. Should the bare cache live inside `/var/nd` (per-container,
   ephemeral) or be mountable by default? v1 picks ephemeral; document
   the mount option in the README so operators can opt in.
2. Does `app.harness` accept `cwd` directly, or do we need to wrap it
   so claude-code's tool invocations chdir into the worktree?
   Implementation phase will confirm against the agentfield SDK; if
   `cwd` is not supported we will need a thin wrapper that
   `os.chdir`s before/after calling `app.harness`.
3. For issue tasks the worker creates `nd/issue-<short_id>` locally
   but never pushes. When we later add the push step, do we push to
   `origin` (requires write scope on the token) or to a fork? This
   is captured under "Out of scope" but flagged here so the spec
   reviewer can weigh in early.
