"""Workspace preparation: bare git cache + per-task worktrees."""

import asyncio
import logging
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Workspace:
    """A prepared, on-disk workspace for a single task."""

    repo_path: str  # absolute path to the worktree
    branch: str  # the checked-out branch
    base_branch: str  # what we forked from / the MR target
    bare_path: str  # absolute path to the shared bare cache


# Validation pattern for path components used to build the bare cache path.
# Allows letters, digits, dot, dash, underscore. Hosts may also contain ":"
# (for ``host:port``). We explicitly reject "/", "\", and any ".." segment.
_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-]+$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def _check_safe_component(value: str, *, allow_colon: bool, label: str) -> None:
    """Reject path-traversal-y values before they hit os.path.join.

    We don't want a malicious or buggy upstream caller to be able to escape
    ``WORKSPACE_ROOT/repos/`` via "..", absolute paths, or embedded slashes.
    """
    if not value:
        raise ValueError(f"{label} must be non-empty")
    if value in (".", ".."):
        raise ValueError(f"{label} must not be '.' or '..'")
    pattern = _SAFE_HOST_RE if allow_colon else _SAFE_NAME_RE
    if not pattern.fullmatch(value):
        raise ValueError(f"{label} contains unsafe characters: {value!r}")


def _anon_clone_url(platform_host: str, repo_owner: str, repo_name: str) -> str:
    """Build an anonymous HTTPS clone URL.

    Tokens are *not* embedded in the URL — they are supplied at runtime via
    a per-call ``GIT_ASKPASS`` helper so they don't appear in ``ps``/argv.
    """
    return f"https://{platform_host}/{repo_owner}/{repo_name}.git"


def _askpass_env(
    platform: str,
    github_token: str,
    gitlab_token: str,
) -> tuple[dict[str, str], str | None]:
    """Build a ``GIT_ASKPASS`` script + env dict for the given platform.

    Returns ``(env_overrides, tempdir_to_cleanup)``. ``tempdir_to_cleanup``
    is ``None`` when no token is configured (anonymous clone path).

    The askpass helper script lives in a 0700 tempdir, is itself 0700, and
    reads the token from ``GIT_ASKPASS_TOKEN`` and the username from
    ``GIT_ASKPASS_USERNAME``. The script and dir are removed after the git
    invocation completes (successfully or not).
    """
    if platform == "github" and github_token:
        username = "x-access-token"
        token = github_token
    elif platform == "gitlab" and gitlab_token:
        username = "oauth2"
        token = gitlab_token
    else:
        return {}, None

    tmpdir = tempfile.mkdtemp(prefix="nd-askpass-")
    os.chmod(tmpdir, 0o700)
    helper_path = os.path.join(tmpdir, "askpass.sh")
    # The helper distinguishes "Username for ..." vs "Password for ..." by
    # the prompt git passes as $1. Match both explicitly and refuse any
    # other prompt rather than silently leaking the token.
    script = (
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  Username*) printf "%s" "$GIT_ASKPASS_USERNAME" ;;\n'
        '  Password*) printf "%s" "$GIT_ASKPASS_TOKEN" ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    with open(helper_path, "w") as f:
        f.write(script)
    os.chmod(helper_path, stat.S_IRWXU)  # 0700

    env = {
        "GIT_ASKPASS": helper_path,
        "GIT_ASKPASS_USERNAME": username,
        "GIT_ASKPASS_TOKEN": token,
        # Disable interactive terminal prompts as a belt-and-suspenders.
        "GIT_TERMINAL_PROMPT": "0",
    }
    return env, tmpdir


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
        # Reject path-traversal payloads before constructing the path. This
        # is defense in depth: callers should already pass clean values.
        _check_safe_component(platform_host, allow_colon=True, label="platform_host")
        _check_safe_component(owner, allow_colon=False, label="owner")
        _check_safe_component(repo, allow_colon=False, label="repo")
        return os.path.join(self.root, "repos", platform_host, owner, f"{repo}.git")

    def _worktree_path(self, task_slug: str) -> str:
        # Replace slashes / unsafe chars so kata project names with "/" or "#" are safe.
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", task_slug).strip("-")
        return os.path.join(self.root, "work", safe)

    async def _run(
        self,
        args: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Run a subprocess and return (returncode, stdout, stderr).

        When ``env`` is provided, it is merged on top of the current
        process environment so the child inherits PATH etc.
        """
        full_env: dict[str, str] | None
        if env:
            full_env = dict(os.environ)
            full_env.update(env)
        else:
            full_env = None
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=full_env,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

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
        out directly. For issue tasks pass ``issue_short_id``; we create
        ``nd/issue-<short_id>`` off ``base_branch`` (or origin/HEAD if
        ``base_branch`` is None).
        """
        bare_path = self._bare_path(platform_host, repo_owner, repo_name)
        worktree_path = self._worktree_path(task_slug)

        # Atomically claim the worktree directory: ``os.makedirs`` with
        # ``exist_ok=False`` raises ``FileExistsError`` if another caller
        # already claimed this slug, avoiding the previous TOCTOU window.
        # ``git worktree add`` requires the target NOT to exist, so we
        # create the parent only and remove our placeholder before the
        # ``worktree add`` call.
        os.makedirs(os.path.dirname(worktree_path), exist_ok=True)
        try:
            os.mkdir(worktree_path)
        except FileExistsError:
            # ``FileExistsError`` is the canonical (Py3) exception for
            # ``mkdir`` on an existing path and is itself an ``OSError``
            # subclass with ``errno == EEXIST``, so we don't need a
            # separate ``OSError``/``errno`` branch here.
            logger.warning("worktree path %s already exists; failing prep", worktree_path)
            return None
        # ``git worktree add`` refuses to create into an existing directory,
        # so remove our placeholder now that we've reserved the slot.
        os.rmdir(worktree_path)

        anon_url = _anon_clone_url(platform_host, repo_owner, repo_name)
        env_overrides, askpass_tmpdir = _askpass_env(platform, self.github_token, self.gitlab_token)
        os.makedirs(os.path.dirname(bare_path), exist_ok=True)

        try:
            if not os.path.exists(bare_path):
                rc, _, err = await self._run(
                    ["git", "clone", "--bare", anon_url, bare_path],
                    env=env_overrides,
                )
                if rc != 0:
                    logger.warning("git clone --bare failed: %s", err.strip())
                    return None
            else:
                rc, _, err = await self._run(
                    [
                        "git",
                        "-C",
                        bare_path,
                        "fetch",
                        "--prune",
                        anon_url,
                        "+refs/heads/*:refs/heads/*",
                    ],
                    env=env_overrides,
                )
                if rc != 0:
                    logger.warning("git fetch failed: %s", err.strip())
                    return None
        finally:
            # Always wipe the askpass helper, even on failure paths.
            if askpass_tmpdir is not None:
                shutil.rmtree(askpass_tmpdir, ignore_errors=True)

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
                    "git",
                    "-C",
                    bare_path,
                    "worktree",
                    "add",
                    "-b",
                    new_branch,
                    worktree_path,
                    base_branch,
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

    async def cleanup(self, workspace: Workspace) -> None:
        """Remove the worktree. Best-effort; never raises."""
        rc, _, err = await self._run(
            [
                "git",
                "-C",
                workspace.bare_path,
                "worktree",
                "remove",
                "--force",
                workspace.repo_path,
            ],
        )
        if rc != 0:
            logger.warning(
                "git worktree remove failed: %s; falling back to rm -rf",
                err.strip(),
            )
            shutil.rmtree(workspace.repo_path, ignore_errors=True)
