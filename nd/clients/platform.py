"""Platform API client for posting responses to GitHub/GitLab."""

import httpx
from urllib.parse import quote


class PlatformClient:
    """Client for posting responses to GitHub and GitLab."""

    def __init__(
        self,
        github_token: str,
        gitlab_token: str,
        timeout: float = 30.0,
    ):
        self.github_token = github_token
        self.gitlab_token = gitlab_token
        self.timeout = timeout
        self._github_client: httpx.AsyncClient | None = None
        self._gitlab_client: httpx.AsyncClient | None = None

    async def _get_github_client(self) -> httpx.AsyncClient:
        if self._github_client is None:
            self._github_client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self.timeout,
            )
        return self._github_client

    async def _get_gitlab_client(self, host: str) -> httpx.AsyncClient:
        if self._gitlab_client is None:
            base_url = f"https://{host}"
            self._gitlab_client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "PRIVATE-TOKEN": self.gitlab_token,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._gitlab_client

    async def close(self) -> None:
        if self._github_client is not None:
            await self._github_client.aclose()
            self._github_client = None
        if self._gitlab_client is not None:
            await self._gitlab_client.aclose()
            self._gitlab_client = None

    def _gitlab_comment_url(
        self,
        host: str,
        owner: str,
        repo: str,
        mr_number: int,
        discussion_id: str,
    ) -> str:
        """Build GitLab discussion note URL."""
        project_path = quote(f"{owner}/{repo}", safe="")
        return (
            f"https://{host}/api/v4/projects/{project_path}"
            f"/merge_requests/{mr_number}/discussions/{discussion_id}/notes"
        )

    def _github_comment_url(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
    ) -> str:
        """Build GitHub comment reply URL."""
        owner_escaped = quote(owner, safe="")
        repo_escaped = quote(repo, safe="")
        return (
            f"https://api.github.com/repos/{owner_escaped}/{repo_escaped}"
            f"/pulls/{pr_number}/comments/{comment_id}/replies"
        )

    async def post_gitlab_reply(
        self,
        host: str,
        owner: str,
        repo: str,
        mr_number: int,
        discussion_id: str,
        body: str,
    ) -> bool:
        """Post a reply to a GitLab discussion."""
        client = await self._get_gitlab_client(host)
        url = self._gitlab_comment_url(host, owner, repo, mr_number, discussion_id)
        # Use relative URL since base_url is set
        path = url.replace(f"https://{host}", "")
        response = await client.post(path, json={"body": body})
        return response.status_code in (200, 201)

    async def post_github_reply(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> bool:
        """Post a reply to a GitHub PR comment."""
        client = await self._get_github_client()
        owner_escaped = quote(owner, safe="")
        repo_escaped = quote(repo, safe="")
        path = f"/repos/{owner_escaped}/{repo_escaped}/pulls/{pr_number}/comments/{comment_id}/replies"
        response = await client.post(path, json={"body": body})
        return response.status_code in (200, 201)

    async def post_response(
        self,
        platform: str,
        platform_host: str,
        owner: str,
        repo: str,
        mr_number: int,
        thread_id: str,
        body: str,
    ) -> bool:
        """Post a response to the appropriate platform."""
        if platform == "gitlab":
            return await self.post_gitlab_reply(
                host=platform_host,
                owner=owner,
                repo=repo,
                mr_number=mr_number,
                discussion_id=thread_id,
                body=body,
            )
        elif platform == "github":
            try:
                comment_id = int(thread_id)
            except ValueError:
                raise ValueError(f"Invalid GitHub thread_id (must be numeric): {thread_id}")
            return await self.post_github_reply(
                owner=owner,
                repo=repo,
                pr_number=mr_number,
                comment_id=comment_id,
                body=body,
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
