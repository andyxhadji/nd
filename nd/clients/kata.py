"""Kata CLI wrapper for task management."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KataTask:
    """A task from kata."""

    id: str
    project: str
    title: str
    body: str
    labels: list[str]
    owner: str | None

    @classmethod
    def from_dict(cls, data: dict, project: str | None = None) -> "KataTask":
        """Create from a kata issue JSON object.

        kata returns issues as ``{"id": int, "project_id": int, "title": ...,
        "body": ..., ...}`` with no top-level "project" name or "labels"
        list. The ``id`` field on this dataclass stores a kata-resolvable
        qualified ref of the form ``<project_name>#<short_id>`` whenever
        possible — required because subsequent kata commands (assign, label,
        comment, close) need a project-qualified ref when the workspace has
        no .kata.toml/git ancestor (e.g. inside our docker container, cwd
        ``/app``). We fall back to uid/short_id/id-as-str only when project
        and short_id are not both present.

        ``project`` (optional) overrides the project name embedded in the
        result — useful when a list endpoint returns issues from a known
        project but doesn't repeat the name on each row.
        """
        project_name = project or data.get("project_name") or str(data.get("project_id") or "")
        short_id = data.get("short_id")
        if project_name and short_id:
            ref = f"{project_name}#{short_id}"
        else:
            issue_id = data.get("uid") or short_id or data.get("id")
            ref = str(issue_id) if issue_id is not None else ""
        return cls(
            id=ref,
            project=str(project_name),
            title=data.get("title", ""),
            body=data.get("body", ""),
            labels=data.get("labels", []),
            owner=data.get("owner"),
        )


class KataClient:
    """Client for kata CLI operations."""

    def __init__(self, kata_server: str = ""):
        self.kata_server = kata_server

    def _base_cmd(self) -> list[str]:
        """Build base kata command. Server selection is via the KATA_SERVER
        env var (the kata CLI has no --server flag); see _run for env wiring."""
        return ["kata"]

    def _env(self) -> dict[str, str]:
        """Build environment for subprocess. Sets KATA_SERVER when configured;
        otherwise inherits the parent env unchanged."""
        env = os.environ.copy()
        if self.kata_server:
            env["KATA_SERVER"] = self.kata_server
        return env

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        """Run kata command and return (returncode, stdout, stderr)."""
        cmd = self._base_cmd() + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def search(self, project: str, query: str) -> list[KataTask]:
        """Search for tasks matching a query.

        kata's search response shape:
        ``{"results": [{"issue": {...}, "score": ..., "matched_in": [...]}]}``.
        We unwrap the nested issue object before constructing KataTask.
        """
        returncode, stdout, stderr = await self._run(
            ["search", "--project", project, "--json", query]
        )
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
            results = data.get("results", [])
            return [KataTask.from_dict(r["issue"]) for r in results if r.get("issue")]
        except json.JSONDecodeError:
            logger.warning("kata search returned non-JSON stdout: %r", stdout)
            return []

    async def create(
        self,
        title: str,
        body: str,
        project: str,
        labels: list[str],
        idempotency_key: str,
    ) -> str | None:
        """Create a new task. Returns task ID or None on failure."""
        args = [
            "create",
            title,
            "--body",
            body,
            "--project",
            project,
            "--idempotency-key",
            idempotency_key,
            "--json",
        ]
        for label in labels:
            args.extend(["--label", label])

        returncode, stdout, stderr = await self._run(args)
        if returncode != 0:
            return None
        try:
            data = json.loads(stdout)
            # kata's create response shape: {"kata_api_version": 1, "issue": {...}, ...}
            issue = data.get("issue") or {}
            short_id = issue.get("short_id")
            project_name = issue.get("project_name") or project
            if project_name and short_id:
                return f"{project_name}#{short_id}"
            return issue.get("uid") or short_id
        except json.JSONDecodeError:
            logger.warning("kata create returned non-JSON stdout: %r", stdout)
            return None

    async def list_projects(self) -> list[str]:
        """List project names known to the daemon.

        ``kata projects list --json`` returns
        ``{"kata_api_version": 1, "projects": [{"name": ..., ...}, ...]}``.
        Returns an empty list on any failure.
        """
        returncode, stdout, _ = await self._run(["projects", "list", "--json"])
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("kata projects list returned non-JSON stdout: %r", stdout)
            return []
        return [p["name"] for p in data.get("projects", []) if p.get("name")]

    async def ready(self, label: str, unowned: bool = True) -> list[KataTask]:
        """Get tasks ready for work across all projects.

        ``kata ready`` is a project-scoped command and refuses to run with
        ``project_not_initialized`` when invoked from a workspace lacking a
        ``.kata.toml`` / git ancestor (the case for our docker containers,
        cwd ``/app``). To work around this we enumerate projects via the
        daemon and call ``kata ready --project <name>`` once per project.

        kata's ready response shape: ``{"kata_api_version": 1, "issues":
        [{"short_id": ..., "title": ..., ...}, ...]}`` — the per-issue rows
        do not embed a project name, so we attach it from the iteration
        context when constructing each KataTask.
        """
        projects = await self.list_projects()
        tasks: list[KataTask] = []
        for project in projects:
            args = ["ready", "--project", project, "--label", label, "--json"]
            if unowned:
                args.append("--unowned")
            returncode, stdout, _ = await self._run(args)
            if returncode != 0:
                continue
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                logger.warning(
                    "kata ready --project %s returned non-JSON stdout: %r",
                    project,
                    stdout,
                )
                continue
            for issue in data.get("issues", []):
                tasks.append(KataTask.from_dict(issue, project=project))
        return tasks

    async def assign(self, task_id: str, owner: str) -> bool:
        """Assign a task to an owner."""
        returncode, _, _ = await self._run(["assign", task_id, owner])
        return returncode == 0

    async def label(self, task_id: str, label: str) -> bool:
        """Add a label to a task."""
        returncode, _, _ = await self._run(["label", task_id, label])
        return returncode == 0

    async def comment(self, task_id: str, message: str) -> bool:
        """Add a comment to a task."""
        returncode, _, _ = await self._run(["comment", task_id, message])
        return returncode == 0

    async def close(self, task_id: str, reason: str, comment: str) -> bool:
        """Close a task."""
        returncode, _, _ = await self._run(
            ["close", task_id, "--reason", reason, "--comment", comment]
        )
        return returncode == 0

    @staticmethod
    def build_task_body(
        mr_url: str,
        mr_title: str,
        head_branch: str,
        base_branch: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        mr_number: int,
        comment_author: str,
        comment_body: str,
        dedupe_key: str,
        category: str,
    ) -> str:
        """Build structured task body markdown."""
        return f"""## MR Context
- **MR:** [{repo_owner}/{repo_name}!{mr_number}]({mr_url})
- **Title:** {mr_title}
- **Branch:** {head_branch} -> {base_branch}
- **Platform:** {platform} ({platform_host})

## Original Comment
**Author:** {comment_author}

{comment_body}

## Metadata
- **Dedupe Key:** `{dedupe_key}`
- **Category:** {category}
"""

    @staticmethod
    def build_issue_task_body(
        issue_url: str,
        issue_title: str,
        issue_number: int,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        issue_author: str,
        issue_body: str,
        assignees: list[str],
    ) -> str:
        """Build structured task body markdown for an issue."""
        assignees_str = ", ".join(assignees) if assignees else "None"
        return f"""## Issue Context
- **Issue:** [{repo_owner}/{repo_name}#{issue_number}]({issue_url})
- **Title:** {issue_title}
- **Platform:** {platform} ({platform_host})
- **Assignees:** {assignees_str}

## Issue Description
**Author:** {issue_author}

{issue_body}
"""
