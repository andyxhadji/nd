"""Kata CLI wrapper for task management."""

import asyncio
import json
import shlex
from dataclasses import dataclass


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
        """Create from kata JSON output."""
        return cls(
            id=data["id"],
            project=data["project"],
            title=data["title"],
            body=data.get("body", ""),
            labels=data.get("labels", []),
            owner=data.get("owner"),
        )


class KataClient:
    """Client for kata CLI operations."""

    def __init__(self, kata_server: str = ""):
        self.kata_server = kata_server

    def _base_cmd(self) -> list[str]:
        """Build base kata command with server flag if set."""
        cmd = ["kata"]
        if self.kata_server:
            cmd.extend(["--server", self.kata_server])
        return cmd

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        """Run kata command and return (returncode, stdout, stderr)."""
        cmd = self._base_cmd() + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def search(self, project: str, query: str) -> list[KataTask]:
        """Search for tasks matching a query."""
        returncode, stdout, stderr = await self._run(
            ["search", "--project", project, "--json", query]
        )
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
            return [KataTask.from_dict(t) for t in data.get("tasks", [])]
        except json.JSONDecodeError:
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
            "--body", body,
            "--project", project,
            "--idempotency-key", idempotency_key,
            "--json",
        ]
        for label in labels:
            args.extend(["--label", label])

        returncode, stdout, stderr = await self._run(args)
        if returncode != 0:
            return None
        try:
            data = json.loads(stdout)
            return data.get("id")
        except json.JSONDecodeError:
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
