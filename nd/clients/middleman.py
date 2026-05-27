"""Middleman API client for fetching MR comments."""

from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass
class MRComment:
    """A comment on a merge request from middleman."""

    id: str
    body: str
    author: str
    created_at: datetime
    dedupe_key: str
    mr_number: int
    mr_title: str
    mr_url: str
    head_branch: str
    base_branch: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str

    @classmethod
    def from_dict(cls, data: dict) -> "MRComment":
        """Create from API response dict."""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return cls(
            id=str(data["id"]),
            body=data["body"],
            author=data["author"],
            created_at=created_at,
            dedupe_key=data["dedupe_key"],
            mr_number=int(data["mr_number"]),
            mr_title=data["mr_title"],
            mr_url=data["mr_url"],
            head_branch=data["head_branch"],
            base_branch=data["base_branch"],
            platform=data["platform"],
            platform_host=data["platform_host"],
            repo_owner=data["repo_owner"],
            repo_name=data["repo_name"],
        )


@dataclass
class Issue:
    """An issue from middleman."""

    id: str
    number: int
    title: str
    body: str
    state: str
    author: str
    assignees: list[str]
    url: str
    created_at: datetime
    updated_at: datetime
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str

    @classmethod
    def from_dict(cls, data: dict) -> "Issue":
        """Create from API response dict."""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = data["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return cls(
            id=str(data["id"]),
            number=int(data["number"]),
            title=data["title"],
            body=data.get("body", ""),
            state=data["state"],
            author=data["author"],
            assignees=data.get("assignees", []),
            url=data["url"],
            created_at=created_at,
            updated_at=updated_at,
            platform=data["platform"],
            platform_host=data["platform_host"],
            repo_owner=data["repo_owner"],
            repo_name=data["repo_name"],
        )


class MiddlemanClient:
    """Client for middleman REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_comments_since(
        self,
        since: datetime,
        current_user: str,
    ) -> list[MRComment]:
        """Fetch comments on user's MRs since the given timestamp."""
        client = await self._get_client()
        params = {
            "types": "issue_comment",
            "since": since.isoformat(),
        }
        response = await client.get("/api/v1/activity", params=params)
        response.raise_for_status()

        comments = []
        for item in response.json().get("items", []):
            # Filter to comments on MRs where current_user is author
            if item.get("mr_author") == current_user:
                comments.append(MRComment.from_dict(item))
        return comments

    async def get_comment_by_dedupe_key(self, dedupe_key: str) -> MRComment | None:
        """Fetch a specific comment by its dedupe key."""
        client = await self._get_client()
        params = {"dedupe_key": dedupe_key}
        response = await client.get("/api/v1/activity", params=params)
        response.raise_for_status()

        items = response.json().get("items", [])
        if items:
            return MRComment.from_dict(items[0])
        return None

    async def get_issues_assigned_to(self, username: str) -> list[Issue]:
        """Fetch open issues assigned to the given username."""
        client = await self._get_client()
        params = {
            "state": "open",
            "assignee": username,
        }
        response = await client.get("/api/v1/issues", params=params)
        response.raise_for_status()

        return [Issue.from_dict(item) for item in response.json().get("items", [])]
