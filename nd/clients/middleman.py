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
        """Create from API response dict.

        Handles both activity endpoint format (item_number/item_title/item_url)
        and direct comment format (mr_number/mr_title/mr_url).
        """
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Activity endpoint uses item_* fields, direct comment uses mr_* fields
        mr_number = data.get("mr_number") or data.get("item_number")
        mr_title = data.get("mr_title") or data.get("item_title")
        mr_url = data.get("mr_url") or data.get("item_url")

        # Extract platform info from nested repo object if present
        repo = data.get("repo", {})
        platform = data.get("platform") or repo.get("provider")
        platform_host = data.get("platform_host") or repo.get("platform_host")
        repo_owner = data.get("repo_owner") or repo.get("owner")
        repo_name = data.get("repo_name") or repo.get("name")

        return cls(
            id=str(data["id"]),
            body=data["body"],
            author=data["author"],
            created_at=created_at,
            dedupe_key=data["dedupe_key"],
            mr_number=int(mr_number),
            mr_title=mr_title,
            mr_url=mr_url,
            head_branch=data.get("head_branch", ""),
            base_branch=data.get("base_branch", ""),
            platform=platform,
            platform_host=platform_host,
            repo_owner=repo_owner,
            repo_name=repo_name,
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
        """Create from API response dict.

        Middleman's /api/v1/issues returns PascalCase top-level keys (ID, Number,
        CreatedAt, ...) with platform info nested under "repo". Older/test fixtures
        use snake_case. Accept both.
        """

        def pick(*keys, default=None):
            for k in keys:
                if k in data:
                    return data[k]
            return default

        repo = data.get("repo") or {}

        def parse_dt(value):
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value

        return cls(
            id=str(pick("id", "ID")),
            number=int(pick("number", "Number")),
            title=pick("title", "Title"),
            body=pick("body", "Body", default="") or "",
            state=pick("state", "State"),
            author=pick("author", "Author"),
            assignees=data.get("assignees", []),
            url=pick("url", "URL"),
            created_at=parse_dt(pick("created_at", "CreatedAt")),
            updated_at=parse_dt(pick("updated_at", "UpdatedAt")),
            platform=pick("platform", default=repo.get("provider")),
            platform_host=pick("platform_host", default=repo.get("platform_host")),
            repo_owner=pick("repo_owner", default=repo.get("owner")),
            repo_name=pick("repo_name", default=repo.get("name")),
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
        current_users: list[str] | None = None,
    ) -> list[MRComment]:
        """Fetch comments on MRs authored by any of the current_users since the given timestamp.

        Args:
            since: Fetch comments created after this timestamp
            current_users: List of usernames to filter MRs by author. If None or empty, no filtering.

        Returns:
            List of MRComment objects for comments on MRs where the author is in current_users
        """
        client = await self._get_client()
        params = {
            "types": "comment",
            "since": since.isoformat(),
        }
        response = await client.get("/api/v1/activity", params=params)
        response.raise_for_status()

        comments = []
        for item in response.json().get("items", []):
            # Filter to comments on MRs where author is in current_users
            # If current_users is None or empty, include all comments
            mr_author = item.get("mr_author")
            if not current_users or (mr_author and mr_author in current_users):
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

        # /api/v1/issues returns a bare JSON array; tolerate {"items": [...]} too.
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [Issue.from_dict(item) for item in items]
