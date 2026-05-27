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
    def from_dict(cls, data: dict) -> "KataTask":
        """Create from a kata issue JSON object.

        kata returns issues as ``{"id": int, "project_id": int, "title": ...,
        "body": ..., ...}`` with no top-level "project" name or "labels"
        list. We coerce id to str and fall back gracefully when the optional
        fields are absent so this works for both the search-results path
        (which omits labels) and any future shape that includes them.
        """
        issue_id = data.get("uid") or data.get("short_id") or data.get("id")
        return cls(
            id=str(issue_id) if issue_id is not None else "",
            project=str(data.get("project_name") or data.get("project_id") or ""),
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
            return issue.get("uid") or issue.get("short_id")
        except json.JSONDecodeError:
            logger.warning("kata create returned non-JSON stdout: %r", stdout)
            return None

    async def ready(self, label: str, unowned: bool = True) -> list[KataTask]:
        """Get tasks ready for work."""
        args = ["ready", "--label", label, "--json"]
        if unowned:
            args.append("--unowned")

        returncode, stdout, stderr = await self._run(args)
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
            return [KataTask.from_dict(t) for t in data.get("tasks", [])]
        except json.JSONDecodeError:
            logger.warning("kata ready returned non-JSON stdout: %r", stdout)
            return []

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
