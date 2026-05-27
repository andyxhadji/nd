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

    repo_path: str  # absolute path to the worktree
    branch: str  # the checked-out branch
    base_branch: str  # what we forked from / the MR target
    bare_path: str  # absolute path to the shared bare cache


def _auth_clone_url(
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    github_token: str,
    gitlab_token: str,
) -> str:
    """Build an authenticated HTTPS clone URL.

    Tokens are only ever passed to ``git clone --bare`` / ``git fetch``;
    they must never be persisted in the worktree's ``.git/config``.
    """
    base = f"{platform_host}/{repo_owner}/{repo_name}.git"
    if platform == "github" and github_token:
        return f"https://x-access-token:{github_token}@{base}"
    if platform == "gitlab" and gitlab_token:
        return f"https://oauth2:{gitlab_token}@{base}"
    return f"https://{base}"


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
        # Replace slashes / unsafe chars so kata project names with "/" or "#" are safe.
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", task_slug).strip("-")
        return os.path.join(self.root, "work", safe)

    async def _run(
        self,
        args: list[str],
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        """Run a subprocess and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
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

        if os.path.exists(worktree_path):
            logger.warning("worktree path %s already exists; failing prep", worktree_path)
            return None

        auth_url = _auth_clone_url(
            platform,
            platform_host,
            repo_owner,
            repo_name,
            self.github_token,
            self.gitlab_token,
        )
        os.makedirs(os.path.dirname(bare_path), exist_ok=True)

        if not os.path.exists(bare_path):
            rc, _, err = await self._run(["git", "clone", "--bare", auth_url, bare_path])
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
                    auth_url,
                    "+refs/heads/*:refs/heads/*",
                ],
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
